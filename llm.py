from __future__ import annotations

# Слой работы с OpenRouter — внешний LLM-провайдер.
# Тут только сетевой вызов и парсинг ответа. Никакой логики бота, никаких
# обработчиков aiogram — это позволяет менять модель/провайдера, не трогая bot.py.

import logging
import os
from pathlib import Path

import httpx


# URL чат-комплишена OpenRouter (формат совместим с OpenAI API).
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Модель Claude через OpenRouter. OpenRouter маршрутизирует запрос к Anthropic.
# Sonnet 4.6 — сильная в живом творческом тексте на русском, тёплый слог,
# дешевле топовой Opus. Для смешарика (юмор + поддержка) — отличный баланс.
# ВАЖНО: точный «слаг» модели сверь на openrouter.ai/models — имена там вида
# anthropic/claude-... и иногда меняются. Если запрос вернёт 404
# «No endpoints found» — открой каталог и поправь строку MODEL ниже.
MODEL = "anthropic/claude-sonnet-4.5"

# Таймаут запроса. 60 секунд — компромисс между UX и тем, что юзер не уйдёт.
TIMEOUT_SECONDS = 60


class LLMRateLimitError(Exception):
    # OpenRouter вернул 429 — превышен лимит запросов. Бот покажет
    # юзеру отдельное сообщение «попробуй через минуту».
    pass


class LLMError(Exception):
    # Любая другая ошибка LLM-слоя: сеть, 5xx, кривой JSON, отсутствие ключа.
    # bot.py отлавливает её и показывает универсальную заглушку.
    pass


def load_system_prompt() -> str:
    # читаем system_prompt.md из корня проекта (рядом с bot.py и llm.py).
    # Делается один раз при старте — содержимое не меняется в рантайме.
    prompt_path = Path(__file__).parent / "system_prompt.md"
    return prompt_path.read_text(encoding="utf-8")


async def ask_openrouter(user_text: str, system_prompt: str) -> str:
    # один запрос к OpenRouter: системный промпт + текст юзера → ответ модели.
    # без истории диалога — это сознательное решение для v1: экономит токены
    # и держит каждый ответ независимым. Память диалога — задел на будущее.

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise LLMError("OPENROUTER_API_KEY не найден в .env")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # необязательные заголовки для рейтинга OpenRouter
        "HTTP-Referer": "https://github.com/AllaStancheva",
        "X-Title": "smesharik",
    }

    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(OPENROUTER_URL, headers=headers, json=body)

        if response.status_code == 429:
            raise LLMRateLimitError("OpenRouter rate limit (HTTP 429)")

        if response.status_code != 200:
            logging.error(
                "OpenRouter HTTP %s, тело ответа: %s",
                response.status_code,
                response.text,
            )
            raise LLMError(f"OpenRouter HTTP {response.status_code}")

        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    except LLMRateLimitError:
        # пробрасываем дальше — bot.py обрабатывает её отдельно
        raise
    except httpx.HTTPError as e:
        logging.exception("сетевая ошибка при запросе к OpenRouter")
        raise LLMError(f"Сетевая ошибка: {e}") from e
    except (KeyError, ValueError) as e:
        logging.exception("не удалось распарсить ответ OpenRouter")
        raise LLMError(f"Ошибка парсинга ответа: {e}") from e
