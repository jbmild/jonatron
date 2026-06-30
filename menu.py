from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from strategies import STRATEGIES, STRATEGY_BY_CALLBACK

MENU = 100


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(strategy.button_label, callback_data=strategy.callback_data)]
            for strategy in STRATEGIES
        ]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "What would you like to do?",
        reply_markup=main_menu_keyboard(),
    )
    return MENU


async def menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    strategy = STRATEGY_BY_CALLBACK.get(query.data or "")
    if not strategy:
        await query.edit_message_text(
            "Invalid selection. Send /start to open the menu again."
        )
        return ConversationHandler.END

    context.user_data["active_strategy"] = strategy.callback_data
    return await strategy.begin(update, context)


async def menu_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Choose an option from the menu or send /start.",
        reply_markup=main_menu_keyboard(),
    )
    return MENU


def menu_handlers() -> dict[int, list]:
    return {
        MENU: [
            CallbackQueryHandler(menu_choice),
            MessageHandler(filters.TEXT & ~filters.COMMAND, menu_prompt),
        ],
    }
