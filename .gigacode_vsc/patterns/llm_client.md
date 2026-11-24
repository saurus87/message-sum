# LLM Client-паттерны

## GigaChat OAuth токен
```python
import httpx
# Получение токена
with httpx.Client() as http:
    response = http.post(
        "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        data={"scope": "GIGACHAT_API_PERS"},
        headers={
            "Authorization": f"Basic {settings.gigachat_key}",  # ← Basic, не Bearer!
            "RqUID": settings.rquid,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=30,
    )
    token = response.json().get("access_token")
```

## Вызов GigaChat API
```python
# Новый паттерн: использовать http_client() контекстный менеджер
with llm_client.http_client() as http:
    response = http.post(
        "https://api.giga.chat/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "model": settings.gigachat_model,
            "messages": [...],
            "temperature": 0.3,
            "max_tokens": 4096,
        },
        timeout=120,
    )
    summary = response.json()["choices"][0]["message"]["content"]
```

## Проверка лимита токенов
```python
# Проверка перед вызовом LLM
allowed, used = llm_client.check_token_limit()
if not allowed:
    await client.send_message(owner_id, "⚠️ Достигнут лимит токенов...")
    return False

# Запись использованных токенов
llm_client.record_tokens_used(total_tokens)
# Хранится в settings: tokens_used:YYYY-MM-DD
```

## Маппинг форматов и detail параметр
```python
# Формат читается из БД (пользовательские настройки)
fmt = db.get_setting("format") or "medium"

# Маппинг русских форматов → detail для LLM
detail_map = {
    "краткое": "short",
    "подробное": "detailed",
    "тезисы": "detailed",
}
detail = detail_map.get(fmt, "medium")

# GigaChatClient.summarize(messages_text, detail=detail)
# detail: "short" → 1 предложение на сообщение
# detail: "medium" → 2-3 предложения (по умолчанию)
# detail: "detailed" → 4-5 предложений с деталями
```

## Промпты (config/prompts.py)
```python
# 6 промптов в PROMPTS:
# Общие (для общей суммаризации):
#   "краткое"     — 1-2 абзаца, важные темы
#   "подробное"    — подробный конспект по темам
#   "тезисы"       — маркированный список, 1-2 предложения на тезис
# Per-message (для суммаризации каждого сообщения):
#   "per_message_short"  — 1 предложение, SUMMARY: [текст] | ID: [id] | CHAT: [чат]
#   "per_message"         — 2-3 предложения, тот же формат
#   "per_message_detailed" — 4-5 предложений с деталями, тот же формат

# Вызов:
from config.prompts import get_prompt
prompt = get_prompt("per_message_short")  # ← вернуть шаблон
```
