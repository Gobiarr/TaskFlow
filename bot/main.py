import asyncio
import logging
import os
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from backend.app.config import load_environment

load_environment()


def create_dispatcher(webapp_url: str | None) -> Dispatcher:
    dispatcher = Dispatcher()

    @dispatcher.message(CommandStart())
    async def start(message: Message) -> None:
        if not webapp_url:
            await message.answer(
                "TaskFlow Mini App пока не настроен. "
                "Добавьте TELEGRAM_WEBAPP_URL в .env."
            )
            return

        keyboard = ReplyKeyboardMarkup(
            keyboard=[[
                KeyboardButton(
                    text="Открыть TaskFlow",
                    web_app=WebAppInfo(url=webapp_url),
                )
            ]],
            resize_keyboard=True,
        )
        await message.answer(
            "Планируй задачи, развивай привычки и следи за прогрессом.",
            reply_markup=keyboard,
        )

    @dispatcher.message(Command("help"))
    async def help_command(message: Message) -> None:
        await message.answer(
            "Используйте /start, чтобы открыть TaskFlow Mini App."
        )

    return dispatcher


async def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Укажите TELEGRAM_BOT_TOKEN в .env")

    webapp_url = os.environ.get("TELEGRAM_WEBAPP_URL", "").strip()
    if webapp_url:
        parsed_url = urlparse(webapp_url)
        if parsed_url.scheme != "https" or not parsed_url.netloc:
            raise RuntimeError(
                "TELEGRAM_WEBAPP_URL должен быть полным HTTPS URL"
            )

    bot = Bot(token)
    try:
        await create_dispatcher(webapp_url or None).start_polling(
            bot,
            allowed_updates=["message"],
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
