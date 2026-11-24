# Database-паттерны

## Повторная суммаризация (get_processed_messages)
```python
# Получаем обработанные сообщения из БД (с готовыми суммари)
messages = self.db.get_processed_messages(chat_ids)
# summary уже включено в результат (SELECT *)
```

## Обновление суммари сообщения в БД
```python
# После LLM сохраняем суммари для каждого нового сообщения
self.db.update_message_summary(telegram_id, summary_text)
# Устанавливает summary + processed=1
```
