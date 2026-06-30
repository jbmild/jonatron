from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from auth import is_authorized_user, reply_unauthorized_conversation
from deluge import (
    MAGNET_PREFIX,
    FileType,
    add_magnet_to_deluge,
    download_path_for,
    sanitize_name,
)
from strategies.base import BotStrategy

logger = logging.getLogger(__name__)

MAGNET, NAME, TYPE = 10, 11, 12


class AddTorrentStrategy(BotStrategy):
    callback_data = "strategy:add_torrent"
    button_label = "Add torrent"

    async def begin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.edit_message_text("Send the torrent magnet link to begin.")
        return MAGNET

    def conversation_states(self) -> dict[int, list]:
        return {
            MAGNET: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_magnet)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_name)],
            TYPE: [CallbackQueryHandler(self.receive_type)],
        }

    async def receive_magnet(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not is_authorized_user(update):
            return await reply_unauthorized_conversation(update)

        magnet = (update.message.text or "").strip()
        if not MAGNET_PREFIX.match(magnet):
            await update.message.reply_text(
                "That does not look like a magnet link. Send a link starting with magnet:?."
            )
            return MAGNET

        context.user_data["magnet"] = magnet
        await update.message.reply_text("What name should this download use?")
        return NAME

    async def receive_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not is_authorized_user(update):
            return await reply_unauthorized_conversation(update)

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

    async def receive_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()

        if not is_authorized_user(update):
            return await reply_unauthorized_conversation(update)

        magnet = context.user_data.get("magnet")
        name = context.user_data.get("name")
        if not magnet or not name:
            await query.edit_message_text(
                "This session expired. Send /start to open the menu again."
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
            "Send /start to open the menu again."
        )
        context.user_data.clear()
        return ConversationHandler.END
