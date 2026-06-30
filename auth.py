from telegram import Update
from telegram.ext import ApplicationHandlerStop, ConversationHandler

AUTHORIZED_USERNAME = "joni_m91"
WELCOME_MESSAGE = "Welcome to jonatron"


def is_authorized_user(update: Update) -> bool:
    user = update.effective_user
    if not user or not user.username:
        return False
    return user.username.lower() == AUTHORIZED_USERNAME.lower()


async def reply_unauthorized(update: Update) -> None:
    query = update.callback_query
    if query:
        await query.answer()
        if query.message:
            try:
                await query.edit_message_text(WELCOME_MESSAGE)
                return
            except Exception:
                pass
        if query.message:
            await query.message.reply_text(WELCOME_MESSAGE)
        return

    message = update.effective_message
    if message:
        await message.reply_text(WELCOME_MESSAGE)


async def reply_unauthorized_conversation(update: Update) -> int:
    await reply_unauthorized(update)
    return ConversationHandler.END


async def gate_unauthorized(update: Update, context) -> None:
    """Block every update from non-authorized users before other handlers run."""
    if is_authorized_user(update):
        return
    await reply_unauthorized(update)
    raise ApplicationHandlerStop
