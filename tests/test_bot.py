from aiogram import Dispatcher

from bot.main import create_dispatcher


def test_bot_registers_start_and_help_without_network():
    dispatcher = create_dispatcher("https://taskflow.example/")

    assert isinstance(dispatcher, Dispatcher)
    assert len(dispatcher.message.handlers) == 2
