from __future__ import annotations

from abc import ABC, abstractmethod

from telegram import Update
from telegram.ext import ContextTypes


class BotStrategy(ABC):
    """One main-menu action with its own conversation flow."""

    @property
    @abstractmethod
    def callback_data(self) -> str:
        """Callback data used on the main menu button."""

    @property
    @abstractmethod
    def button_label(self) -> str:
        """Label shown on the main menu button."""

    @abstractmethod
    async def begin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start this strategy after the user picks it from the main menu."""

    @abstractmethod
    def conversation_states(self) -> dict[int, list]:
        """ConversationHandler states owned by this strategy."""
