# Telethon-паттерны

## Обработка сообщений
```python
import telethon.events
# Регистрация — НЕ @on_message
client.add_event_handler(
    process_message,
    telethon.events.NewMessage(chats=[owner_id]),
)
# Обработчик получает NewMessageEvent, не Message
async def process_message(self, event):
    sender_id = event.chat_id  # ← ID отправителя
    text = event.text or ''    # ← текст команды
    # event.chat_id — ID чата, event.text — текст сообщения
```

## Фоновая задача
```python
# Создай task — НЕ забывай сохранить ссылку!
task = asyncio.create_task(background_work())
# При остановке
task.cancel()
await task
```

## Ожидание остановки
```python
stop = asyncio.Event()
# ... add_signal_handler ...
await stop.wait()  # ← метод, не атрибут
```

## Сравнение ID
```python
# owner_chat_id берётся из БД (устанавливается при первом запуске)
# или из settings.owner_chat_id как fallback
owner_id = int(self.db.get_setting("owner_chat_id") or settings.owner_chat_id)
if sender_id != owner_id:
    return
```

## Авторизация (первый запуск)
```python
# Запуск: python3 code.py
# Вводит номер → код приходит в Telegram → вводишь код в терминал
# Скрипт: code.py
```

## Диалоги (Telethon 1.45+)
```python
# Dialog не имеет .peer — entity на Dialog
dialogs = await client.get_dialogs()
for dialog in dialogs:
    entity = dialog.entity  # ← entity на Dialog, не на peer
    if isinstance(entity, (Channel, Chat)):
        chat_id = entity.id  # ← id на entity
        title = entity.title
```

## Даты (timezone-aware)
```python
from datetime import datetime, timezone, timedelta
# МСК (UTC+3)
MSK = timezone(timedelta(hours=3))
# Все временные метки хранятся в МСК
since = datetime.now(MSK) - timedelta(hours=24)
# Telegram возвращает даты с timezone (UTC) — при сохранении конвертируются в МСК
if msg.date < since:
    continue
```
