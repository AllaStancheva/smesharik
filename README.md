# Смешарик 🙂

Личный Telegram-бот эмоциональной поддержки через юмор. Напиши ему своё
состояние — он ответит тепло и с улыбкой, чтобы переключить тебя на хорошую волну.

## Как устроено
- `bot.py` — Telegram-бот (aiogram 3.x, polling)
- `llm.py` — связка с OpenRouter (модель Claude)
- `system_prompt.md` — характер бота (тон, приёмы юмора, границы)

## Запуск локально

1. Создай виртуальное окружение и поставь зависимости:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
2. Скопируй `.env.example` в `.env` и впиши реальные значения:
   - `TELEGRAM_BOT_TOKEN` — токен от [@BotFather](https://t.me/BotFather)
   - `OPENROUTER_API_KEY` — ключ из [openrouter.ai/keys](https://openrouter.ai/keys)
3. Запусти:
   ```powershell
   python bot.py
   ```
4. Напиши боту в Telegram.

## Модель
Модель задаётся одной строкой `MODEL` в `llm.py`. Каталог моделей —
[openrouter.ai/models](https://openrouter.ai/models).

<!-- autodeploy test -->
