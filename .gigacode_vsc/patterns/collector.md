# Collector-паттерны

## Сбор сообщений (collector) — фоновый
```python
# Collector собирает N сообщений из КАЖДОГО чата для фоновой сборки
# Если hours=None — собирает с 2020-01-01 (все сообщения)
# per_chat_limit — максимальное количество сообщений на один чат
# ВАЖНО: использует iter_messages() с offset_id (НЕ get_messages с offset!)
# TelethonClient.get_messages() — обёртка над iter_messages()
async def collect(self, hours: Optional[int] = None, per_chat_limit: Optional[int] = None):
    if per_chat_limit is None:
        per_chat_limit = settings.collector_per_chat_limit

    if hours is not None:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
    else:
        since = datetime(2020, 1, 1, tzinfo=timezone.utc)

    # Последовательный сбор с пагинацией для каждого чата
    for chat_id in chat_ids:
        offset_id = 0  # ID самого старого полученного сообщения
        while saved < per_chat_limit:
            messages = await client.get_messages(chat_id, limit=100, offset_id=offset_id)
            if not messages:
                break
            for msg in messages:
                if msg.date < since:
                    break
                # ... сохранение ...
            # offset_id = ID самого старого сообщения в текущем батче
            offset_id = messages[-1].id if messages else 0
            if len(messages) < 100:
                break
```

## Проверка дедупликации
```python
# Collector проверяет ВСЕ сообщения в БД (и processed=0, и processed=1)
# Для этого используется прямой SQL-запрос, а не get_unprocessed_messages
with self.db._get_connection() as conn:
    existing_ids = {
        row["id"] for row in conn.execute(
            "SELECT id FROM messages WHERE chat_id = ? AND timestamp >= ?",
            (chat_id, since.isoformat())
        ).fetchall()
    }
```

## Сохранение с telegram_id
```python
# telegram_id UNIQUE — дедупликация на уровне БД
result = self.db.save_message(
    telegram_id=msg.id,  # ← уникальный ID из Telegram
    chat_id=chat_id,
    chat_title=chat_title,
    content=content,
    timestamp=msg.date,
)
if result > 0:
    saved += 1  # -1 если уже есть
```
