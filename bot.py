from __future__ import annotations

# Бот-смешарик — личный бот эмоциональной поддержки через юмор.
# Логика простая: получил свободный текст → отправил в LLM с характером
# смешарика (system_prompt.md) → вернул тёплый и смешной ответ.
# Никаких FSM, меню и базы — весь «характер» живёт в системном промпте.

import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

from llm import LLMError, LLMRateLimitError, ask_openrouter, load_system_prompt


# Приветствие при /start — короткое и тёплое.
WELCOME = "Привет 🙂 Я твой бот-смешарик. Ты как?"


async def on_start(message: Message) -> None:
    await message.answer(WELCOME)


async def on_stranger(message: Message) -> None:
    # сюда попадают все, кто НЕ хозяин: личный бот вежливо отказывает.
    # Важно: тут НЕТ обращения к LLM — чужой человек не жжёт баланс OpenRouter.
    await message.answer("Это личный бот — он общается только со своим хозяином 🙂")


def make_free_text_handler(system_prompt: str):
    # фабрика обработчика: замыкаем системный промпт, чтобы не читать файл
    # на каждое сообщение (он загружается один раз при старте).
    async def on_free_text(message: Message) -> None:
        # плейсхолдер, пока модель думает — чтобы юзер видел реакцию сразу
        thinking = await message.answer("😊 секундочку…")
        try:
            answer = await ask_openrouter(message.text, system_prompt)
        except LLMRateLimitError:
            await thinking.edit_text(
                "Слишком много запросов прямо сейчас 🙈 Попробуй через минутку."
            )
            return
        except LLMError:
            logging.exception("LLM-ошибка при ответе юзеру")
            await thinking.edit_text(
                "Ой, у меня что-то заело с мыслями 🤖 Попробуй ещё раз чуть позже."
            )
            return

        # удаляем плейсхолдер и отправляем ответ. parse_mode="HTML" — модель
        # может вернуть простую разметку; при кривом HTML шлём как обычный текст.
        try:
            await thinking.delete()
            await message.answer(answer, parse_mode="HTML")
        except Exception:
            logging.exception("не удалось отправить ответ с HTML, шлю как текст")
            await message.answer(answer)

    return on_free_text


async def main() -> None:
    # фикс кириллицы в print/логах на Windows-консоли (cp1252 → UTF-8)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    logging.basicConfig(level=logging.INFO)
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "Не найден TELEGRAM_BOT_TOKEN в .env. "
            "Создай бота у @BotFather и впиши токен в файл .env."
        )

    # ADMIN_ID — Telegram-ID хозяина. Бот личный: отвечает только ему,
    # всех остальных перехватывает on_stranger (без обращения к LLM).
    admin_id_raw = os.getenv("ADMIN_ID")
    if not admin_id_raw:
        raise SystemExit(
            "Не найден ADMIN_ID в .env. "
            "Впиши свой Telegram-ID (число) в файл .env, чтобы бот отвечал только тебе."
        )
    admin_id = int(admin_id_raw)

    system_prompt = load_system_prompt()

    bot = Bot(token=token)
    dp = Dispatcher()

    # Сначала — обработчики хозяина (фильтр «только от admin_id»).
    dp.message.register(on_start, CommandStart(), F.from_user.id == admin_id)
    dp.message.register(
        make_free_text_handler(system_prompt), F.text, F.from_user.id == admin_id
    )
    # Последним — перехват всех чужих. Регистрируется в конце: aiogram берёт
    # первый подошедший обработчик, поэтому хозяин уходит выше, чужие — сюда.
    dp.message.register(on_stranger)

    logging.info("Смешарик запущен. Жду сообщений…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
