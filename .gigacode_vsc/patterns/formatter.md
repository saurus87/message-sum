# Formatter-паттерны

## Суммаризация с отдельными блоками
```python
# Промпт для LLM: SUMMARY: [текст] | ID: [id сообщения] | CHAT: [чат]
# Formatter группирует сообщения по каналам и форматирует:
# 📌 Название чата | N сообщений
#   1. 29.10 14:30 — суммари...
#      📎 <a href="https://t.me/c/...">12345</a>
#   2. 29.10 12:15 — суммари...
#      📎 <a href="https://t.me/c/...">12345</a>
```

## Форматирование с сообщениями (группировка по каналам)
```python
formatted = format_summary(
    summary_text=summary,
    chat_titles=chat_titles,
    period_start=since,
    period_end=datetime.now(MSK),
    message_count=len(messages),
    messages=messages,  # ← для группировки по каналам
    llm_summaries=llm_summaries,  # ← {telegram_id: summary_text}
)
# Formatter группирует messages по chat_title
# Внутри каждой группы — нумерация с 1, сортировка от старых к новым
```

## Типы telegram_id (int, НЕ str)
```python
# telegram_id из БД — int, ключи в llm_summaries — int
# НЕ приводить к str() при сравнении!
# "123" in {123: "text"} → False
for msg in messages:
    telegram_id = msg.get("telegram_id")  # ← int, НЕ str()
    stored_summary = msg.get("summary", "")

    # Приоритет: stored summary (из БД) → LLM summary → текст сообщения
    if stored_summary:
        summary_part = stored_summary
    elif llm_summaries and telegram_id in llm_summaries:
        summary_part = llm_summaries[telegram_id]  # ← int ключ
    else:
        summary_part = msg.get("content", "")[:300]
```
