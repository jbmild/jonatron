from __future__ import annotations

import logging
import os
import subprocess

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler

from auth import is_authorized_user, reply_unauthorized_conversation
from strategies.base import BotStrategy

logger = logging.getLogger(__name__)

CONFIRM = 20
CONFIRM_YES = "restart:yes"
CONFIRM_CANCEL = "restart:cancel"


def restart_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Yes, restart", callback_data=CONFIRM_YES),
                InlineKeyboardButton("Cancel", callback_data=CONFIRM_CANCEL),
            ]
        ]
    )


def restart_server() -> None:
    command = os.environ.get("RESTART_COMMAND", "sudo /sbin/reboot")
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise RuntimeError(detail)


class RestartServerStrategy(BotStrategy):
    callback_data = "strategy:restart_server"
    button_label = "Restart server"

    async def begin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.edit_message_text(
            "Restart the server now?",
            reply_markup=restart_confirm_keyboard(),
        )
        return CONFIRM

    def conversation_states(self) -> dict[int, list]:
        return {
            CONFIRM: [CallbackQueryHandler(self.handle_confirm)],
        }

    async def handle_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()

        if not is_authorized_user(update):
            return await reply_unauthorized_conversation(update)

        if query.data == CONFIRM_CANCEL:
            await query.edit_message_text(
                "Restart cancelled. Send /start to open the menu again."
            )
            return ConversationHandler.END

        if query.data != CONFIRM_YES:
            await query.edit_message_text(
                "Invalid selection. Send /start to open the menu again."
            )
            return ConversationHandler.END

        await query.edit_message_text("Restarting the server...")
        try:
            restart_server()
        except Exception as exc:
            logger.exception("Failed to restart server")
            await query.edit_message_text(
                f"Could not restart the server: {exc}\n\nSend /start to open the menu again."
            )
            return ConversationHandler.END

        return ConversationHandler.END
