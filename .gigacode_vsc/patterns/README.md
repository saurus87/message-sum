# Паттерны кода

Здесь лежат полные блоки кода для ключевых паттернов проекта.

## Файлы

| Файл | Описание |
|------|----------|
| `telethon.md` | Обработка сообщений, фоновые задачи, диалоги, даты, авторизация |
| `scheduler.md` | Mutex, run_summarize, run_scheduled, _fetch_from_telegram, парсер LLM |
| `collector.md` | collect, дедупликация, сохранение сообщений |
| `database.md` | get_processed_messages, update_message_summary |
| `llm_client.md` | OAuth, API вызов, токены, форматы, промпты |
| `formatter.md` | Группировка по каналам, telegram_id типы |

## Использование

В GIGACODE.md ссылки на паттерны выглядят так:
```
### Название паттерна
Смотри: `.gigacode_vsc/patterns/filename.md#section-name`
- Краткое описание
```

AI автоматически читает эти файлы при необходимости полного кода.
