#!/usr/bin/env python3
"""Telegram bot with a main menu that routes to action strategies."""

from __future__ import annotations

import inspect
import logging
import os
import sys

from deluge_client import DelugeRPCClient
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from auth import is_authorized_user, reply_unauthorized, reply_unauthorized_conversation
from deluge import validate_deluge_config
from menu import menu_handlers, start
from strategies import collect_conversation_states

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_authorized_user(update):
        return await reply_unauthorized_conversation(update)

    context.user_data.clear()
    await update.message.reply_text(
        "Cancelled. Send /start when you want to open the menu."
    )
    return ConversationHandler.END


async def handle_unauthorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_authorized_user(update):
        return
    await reply_unauthorized(update)


def build_conversation_handler() -> ConversationHandler:
    states = menu_handlers()
    states.update(collect_conversation_states())
    return ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states=states,
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN is required.", file=sys.stderr)
        sys.exit(1)

    logger.info(
        "Starting jonatron bot (DelugeRPCClient signature: %s)",
        inspect.signature(DelugeRPCClient.__init__),
    )
    deluge_host = os.environ.get("DELUGE_HOST", "127.0.0.1")
    deluge_port = os.environ.get("DELUGE_PORT", "58846")
    logger.info("Deluge config from environment: host=%s port=%s", deluge_host, deluge_port)

    try:
        client = validate_deluge_config()
        logger.info(
            "Deluge client ready: host=%s port=%s user=%s",
            client.host,
            client.port,
            client.username,
        )
    except Exception as exc:
        logger.error("Deluge client configuration error: %s", exc)
        sys.exit(1)

    application = Application.builder().token(token).build()
    application.add_handler(build_conversation_handler(), group=0)
    application.add_handler(CallbackQueryHandler(handle_unauthorized), group=1)
    application.add_handler(MessageHandler(filters.ALL, handle_unauthorized), group=1)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
