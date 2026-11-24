# Scheduler-паттерны

## Mutex для суммаризации
```python
# asyncio.Lock — блокирует параллельные вызовы
class Scheduler:
    def __init__(self, client, db):
        self._summarize_lock = asyncio.Lock()

    async def run_summarize(self, fmt, msg_count=None, only_unread=False):
        if self._summarize_lock.locked():
            await client.send_message(owner_id, "⏳ Суммаризация уже выполняется")
            return False
        async with self._summarize_lock:
            return await self._run_summarize_internal(fmt, msg_count)
```

## Сбор N сообщений для /sum (Scheduler._fetch_from_telegram)
```python
# Берёт N сообщений из КАЖДОГО чата с пагинацией
# НЕ использует collector — делает напрямую
# ВАЖНО: использует iter_messages() с offset_id (НЕ get_messages с offset!)
# TelethonClient.get_messages() — обёртка над iter_messages()
# msg_count — это лимит на ОДИН чат, не общий
async def _fetch_from_telegram(self, chat_ids, msg_count):
    target = msg_count or 999999  # лимит на один чат

    all_messages = []
    for chat_id in chat_ids:
        chat_messages = []

        offset_id = 0
        while len(chat_messages) < target:
            remaining = target - len(chat_messages)
            limit = min(100, remaining)

            messages = await self.client.get_messages(
                chat_id, limit=limit, offset_id=offset_id
            )
            if not messages:
                break

            for msg in messages:
                if len(chat_messages) >= target:
                    break

                chat_messages.append(msg)

            offset_id = messages[-1].id
            if len(messages) < limit:
                break

        logger.info("Чат %d: получено %d сообщений", chat_id, len(chat_messages))
        all_messages.extend(chat_messages)

    return all_messages
```

## Расписание (Scheduler.run_scheduled) — cooldown 1 час
```python
async def run_scheduled(self):
    """Запустить суммаризацию по расписанию (если текущее время == schedule_time)."""
    schedule_time = self.db.get_setting("schedule_time")
    if not schedule_time:
        return

    # Проверка: текущее время по МСК должно совпадать с schedule_time (HH:MM)
    current_time = datetime.now(MSK).strftime("%H:%M")
    if current_time != schedule_time:
        return

    # Checkpoint: cooldown — не запускать чаще раза в час
    last = self.db.get_setting("last_schedule_run")
    if last:
        try:
            last_run = datetime.fromisoformat(last)
            if datetime.now(MSK) - last_run < timedelta(hours=1):
                return  # cooldown активен
        except Exception:
            pass

    # Запуск суммаризации
    await self.run_summarize(fmt="short")
    self.db.set_setting("last_schedule_run", datetime.now(MSK).isoformat())
```

## Нормализация chat_id (abs)
```python
# Telegram возвращает chat_id как -100..., а active_chats может содержать 100...
# Нормализация через abs() — выравнивает ID
raw_chat_id = msg.chat_id  # например -1001234567890
chat_id = raw_chat_id
for active_id in active_chat_ids:
    if abs(raw_chat_id) == abs(active_id):
        chat_id = active_id
        break
# Результат: chat_id всегда из active_chat_ids (сохраняет формат пользователя)
```

## Суммаризация (run_summarize) — с защитой и LLM только для новых
```python
# 1. Проверить mutex (asyncio.Lock) — блокировать параллельные вызовы
async with self._summarize_lock:
    # 2. Взять N сообщений из Telegram (с пагинацией)
    telegram_msgs = await self._fetch_from_telegram(chat_ids, msg_count)

    # 3. Сохранить в БД (deduplication через UNIQUE)
    for msg in telegram_msgs:
        self.db.save_message(telegram_id=msg.id, ...)

    # 4. Получить НОВЫЕ (processed=0) сообщения из БД
    new_messages = self.db.get_unprocessed_messages(chat_ids)

    # 5. Получить ОБРАБОТАННЫЕ (processed=1) сообщения из БД (с готовыми суммари)
    processed_msgs = self.db.get_processed_messages(chat_ids)

    # 6. Разделить на new + old, отфильтровать old по msg_count из каждого чата
    new_msgs = [m for m in new_messages if m["telegram_id"] in telegram_ids]
    old_msgs = [m for m in processed_msgs if m["telegram_id"] in telegram_ids]
    
    if msg_count:
        from collections import Counter
        chat_counts = Counter()
        filtered_old = []
        for m in old_msgs:
            chat_title = m.get("chat_title", "")
            if chat_counts[chat_title] < msg_count:
                filtered_old.append(m)
                chat_counts[chat_title] += 1
        old_msgs = filtered_old

    # 7. new + processed = N сообщений из КАЖДОГО чата, сортировка от старых к новым
    all_available = new_msgs + old_msgs
    all_available.sort(key=lambda m: m.get("timestamp", ""))
    messages = all_available

    # 8. На LLM отправить ТОЛЬКО новые сообщения (processed=0)
    messages_text = format_for_llm(new_msgs)
    summary = await self.llm_client.summarize(messages_text)

    # 9. Распарсить per-message summaries
    llm_summaries = self._parse_llm_summaries(summary, new_msgs)

    # 10. Сохранить суммари в БД и пометить как processed
    for msg in new_msgs:
        tid = msg["telegram_id"]
        if tid in llm_summaries:
            self.db.update_message_summary(tid, llm_summaries[tid])

    # 11. Отформатировать с stored summaries (formatter возьмёт summary из БД)
    formatted = format_summary(
        summary_text=summary if summary else "",
        chat_titles=chat_titles,
        period_start=period_start,
        period_end=period_end,
        message_count=len(messages),
        messages=messages,
        llm_summaries=llm_summaries,  # {telegram_id: summary_text}
    )
```

## Валидация telegram_id в парсере LLM
```python
# telegram_id должен быть числом — LLM может вернуть мусор
try:
    tid_int = int(telegram_id)
    result[tid_int] = summary_text
except ValueError:
    logger.warning("Пропущен невалидный telegram_id от LLM: '%s'", telegram_id)
```
