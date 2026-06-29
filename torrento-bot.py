#!/usr/bin/env python3
"""Telegram bot that collects torrent details and adds them to Deluge."""

from __future__ import annotations

import inspect
import logging
import os
import re
import sys
from enum import Enum
from pathlib import Path

from deluge_client import DelugeRPCClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

MAGNET, NAME, TYPE = range(3)

BASE_OTHER = Path("/home/sharing")
BASE_MOVIES = Path("/home/sharing/media/movies")
BASE_SHOWS = Path("/home/sharing/media/shows")

MAGNET_PREFIX = re.compile(r"^magnet:\?", re.IGNORECASE)
INVALID_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

AUTHORIZED_USERNAME = "joni_m91"
WELCOME_MESSAGE = "Welcome to jonatron"


class FileType(str, Enum):
    MOVIE = "movie"
    TV_SHOW = "tv_show"
    OTHER = "other"


def get_deluge_client() -> DelugeRPCClient:
    host = os.environ.get("DELUGE_HOST", "127.0.0.1")
    port = int(os.environ.get("DELUGE_PORT", "58846"))
    username = os.environ.get("DELUGE_USERNAME", "localclient")
    password = os.environ.get("DELUGE_PASSWORD")
    if not password:
        raise RuntimeError("DELUGE_PASSWORD is not set in the environment.")

    init_params = inspect.signature(DelugeRPCClient.__init__).parameters
    if "username" in init_params:
        return DelugeRPCClient(host, port, username, password)
    return DelugeRPCClient(host, port, password)


def sanitize_name(name: str) -> str:
    cleaned = INVALID_NAME_CHARS.sub("_", name.strip())
    cleaned = cleaned.strip(". ")
    if not cleaned:
        raise ValueError("Download name cannot be empty.")
    return cleaned


def download_path_for(file_type: FileType, name: str) -> Path:
    safe_name = sanitize_name(name)
    if file_type is FileType.MOVIE:
        return BASE_MOVIES / safe_name
    if file_type is FileType.TV_SHOW:
        return BASE_SHOWS / safe_name
    return BASE_OTHER / safe_name


def add_magnet_to_deluge(magnet: str, download_path: Path) -> str:
    download_path.mkdir(parents=True, exist_ok=True)
    client = get_deluge_client()
    client.connect()
    try:
        torrent_id = client.call(
            "core.add_torrent_magnet",
            magnet.strip(),
            {"download_location": str(download_path), "add_paused": False},
        )
    finally:
        client.disconnect()

    if not torrent_id:
        raise RuntimeError("Deluge did not return a torrent id.")
    return torrent_id


def is_authorized_user(update: Update) -> bool:
    user = update.effective_user
    if not user or not user.username:
        return False
    return user.username.lower() == AUTHORIZED_USERNAME.lower()


async def reply_unauthorized(update: Update) -> int:
    message = update.effective_message
    if message:
        await message.reply_text(WELCOME_MESSAGE)
    return ConversationHandler.END


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_authorized_user(update):
        return await reply_unauthorized(update)

    context.user_data.clear()
    await update.message.reply_text(
        "Send the torrent magnet link to begin."
    )
    return MAGNET


async def receive_magnet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_authorized_user(update):
        return await reply_unauthorized(update)

    magnet = (update.message.text or "").strip()
    if not MAGNET_PREFIX.match(magnet):
        await update.message.reply_text(
            "That does not look like a magnet link. Send a link starting with magnet:?."
        )
        return MAGNET

    context.user_data["magnet"] = magnet
    await update.message.reply_text("What name should this download use?")
    return NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_authorized_user(update):
        return await reply_unauthorized(update)

    name = (update.message.text or "").strip()
    try:
        sanitize_name(name)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return NAME

    context.user_data["name"] = name
    keyboard = [
        [
            InlineKeyboardButton("Movie", callback_data=FileType.MOVIE.value),
            InlineKeyboardButton("TV show", callback_data=FileType.TV_SHOW.value),
        ],
        [InlineKeyboardButton("Other", callback_data=FileType.OTHER.value)],
    ]
    await update.message.reply_text(
        "What type of file is this?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return TYPE


async def receive_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not is_authorized_user(update):
        await query.edit_message_text(WELCOME_MESSAGE)
        return ConversationHandler.END

    magnet = context.user_data.get("magnet")
    name = context.user_data.get("name")
    if not magnet or not name:
        await query.edit_message_text(
            "This session expired. Send /start to begin again."
        )
        return ConversationHandler.END

    try:
        file_type = FileType(query.data)
    except ValueError:
        await query.edit_message_text("Invalid selection. Send /start to try again.")
        return ConversationHandler.END

    type_labels = {
        FileType.MOVIE: "movie",
        FileType.TV_SHOW: "TV show",
        FileType.OTHER: "other",
    }

    try:
        download_path = download_path_for(file_type, name)
        torrent_id = add_magnet_to_deluge(magnet, download_path)
    except Exception as exc:
        logger.exception("Failed to add torrent to Deluge")
        await query.edit_message_text(f"Could not add torrent to Deluge: {exc}")
        context.user_data.clear()
        return ConversationHandler.END

    await query.edit_message_text(
        "Torrent added to Deluge.\n"
        f"Type: {type_labels[file_type]}\n"
        f"Name: {name}\n"
        f"Path: {download_path}\n"
        f"Torrent id: {torrent_id}\n\n"
        "Send /start to add another download."
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_authorized_user(update):
        return await reply_unauthorized(update)

    context.user_data.clear()
    await update.message.reply_text("Cancelled. Send /start when you want to add a torrent.")
    return ConversationHandler.END


async def unauthorized_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_authorized_user(update):
        return
    await update.message.reply_text(WELCOME_MESSAGE)


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN is required.", file=sys.stderr)
        sys.exit(1)

    logger.info(
        "Starting jonatron bot (DelugeRPCClient signature: %s)",
        inspect.signature(DelugeRPCClient.__init__),
    )
    try:
        get_deluge_client()
    except Exception as exc:
        logger.error("Deluge client configuration error: %s", exc)
        sys.exit(1)

    application = Application.builder().token(token).build()

    conversation = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAGNET: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_magnet)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            TYPE: [CallbackQueryHandler(receive_type)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    application.add_handler(conversation)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, unauthorized_message),
        group=1,
    )
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
