from __future__ import annotations

# Бот-смешарик — личный бот эмоциональной поддержки через юмор.
# Логика простая: получил свободный текст → отправил в LLM с характером
# смешарика (system_prompt.md) → вернул тёплый и смешной ответ.
# Никаких FSM, меню и базы — весь «характер» живёт в системном промпте.

import asyncio
import datetime
import logging
import os
import sys
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from llm import LLMError, LLMRateLimitError, ask_openrouter, load_system_prompt


_MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}
_WEEKDAYS_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]


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


async def send_morning_greeting(bot: Bot, admin_id: int, system_prompt: str) -> None:
    today = datetime.date.today()
    day = _WEEKDAYS_RU[today.weekday()]
    date_str = f"{today.day} {_MONTHS_RU[today.month]} {today.year}"
    prompt = (
        f"Сегодня {day}, {date_str}. Пришли мне тёплое утреннее приветствие с шуткой. "
        "Если на эту дату приходится известный праздник, историческая годовщина или "
        "интересное событие — упомяни его к месту."
    )
    try:
        text = await ask_openrouter(prompt, system_prompt)
        await bot.send_message(admin_id, text, parse_mode="HTML")
    except Exception:
        logging.exception("Ошибка отправки утреннего приветствия")


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

    tz = ZoneInfo(os.getenv("TIMEZONE", "Europe/Moscow"))
    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(
        send_morning_greeting,
        "cron",
        hour=9,
        minute=0,
        args=[bot, admin_id, system_prompt],
    )
    scheduler.start()
    logging.info("Планировщик запущен (утреннее приветствие в 09:00 %s).", tz)

    logging.info("Смешарик запущен. Жду сообщений…")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
