# GIGACODE.md — message-sum

## Правила работы (ОБЯЗАТЕЛЬНО К СЛЕДОВАНИЮ)
- **Тщательный анализ:** перед любыми изменениями — внимательно изучать проект, понимать как работает текущая логика
- **Оценка рисков:** если видны потенциальные проблемы в архитектуре — предлагать изменения, но обязательно оценивать, не сломают ли они существующий функционал
- **Подготовка к тестированию:** после изменений убедиться что всё готово к тестированию — очистить старые данные, если они мешают, проверить совместимость
- **Тестирование:** всегда проверять изменения — запускать тесты, проверять импорт модулей
- **Запуск после изменений:** после любых изменений кода — ОБЯЗАТЕЛЬНО перезапускать проект, останавливая перед этим его старую версию, и проверять что новая версия стартует без ошибок. Это критично для любых изменений.
- **Актуальная документация:** при каждом изменении логики или кода — обновлять документацию в GIGACODE.md и в других файлах документации
- **Не ломать рабочее:** при исправлении багов не ломать то что уже работает. Качественно проверять изменения, запускать тесты, проверять импорт модулей, перезапускать проект.

## Правило документации
⚠️ **При каждом изменении логики или кода — обновляй документацию в GIGACODE.md и в других файлах документации.**
Это критично для сохранения контекста проекта и корректной работы AI-ассистента в будущих сессиях.

## Проект
Суммаризатор сообщений Telegram: Telethon-клиент (личный аккаунт) читает чаты/каналы → GigaChat API суммаризует → результат отправляется в ЛС пользователя.

## Архитектура
```
Telethon Client → Summarizer (scheduler) → SQLite → GigaChat API → отправка в ЛС
```
- Один клиент — Telethon (авторизация по телефону, сессия в `.session`)
- Нет бота — команды обрабатываются через Telethon-клиент
- Summarizer — единственная точка вызова суммаризации (по команде из чата)
- Облачная LLM — GigaChat (OAuth токен, httpx)
- SQLite — лёгкое хранилище без доп. сервисов
- **Нет фонового планировщика** — суммаризация только по команде `/sum`
- **Нет фонового сбора** — сообщения собираются только при суммаризации

## .env
```env
TELETHON_PHONE=+7...
TELETHON_API_ID=...
TELETHON_API_HASH=...
GIGACHAT_KEY=...          # Base64 ключ из developers.sber.ru
RQUID=...                 # ID аккаунта (постоянный)
OWNER_CHAT_ID=-100...     # ID куда отправлять результат
GIGACHAT_MODEL=GigaChat-2 # опционально, по умолчанию GigaChat-2
DAILY_TOKEN_LIMIT=50000   # лимит токенов GigaChat в день
COLLECTOR_PER_CHAT_LIMIT=100 # сообщений на чат при сборе
CLEANUP_DAYS=30           # дней хранения сообщений
```

## GigaChat API
- OAuth: `POST https://ngw.devices.sberbank.ru:9443/api/v2/oauth`
  - `Authorization: Basic <ключ>` (не Bearer!)
  - `RqUID` в headers
  - `scope=GIGACHAT_API_PERS`
- Токен 30 мин → обновлять каждые 25 мин
- Chat completions: `POST https://api.giga.chat/v1/chat/completions`
  - `Authorization: Bearer <token>`
- SSL-верификация включена (использует системные CA)
- Доступные модели:
  - `GigaChat-2` — основная модель (по умолчанию)
  - `GigaChat-2-pro` — улучшенная версия для сложных задач
  - `GigaChat-2-lite` — быстрая и дешёвая модель
- Лимит токенов: 50000 в день (настраивается в DAILY_TOKEN_LIMIT)
- При достижении лимита — отправка уведомления пользователю
- `record_tokens_used` НАКАПЛИВАЕТ токены (не перезаписывает)

## Структура проекта
```
config/       settings.py, prompts.py
client/       telethon_client.py, filters.py
summarizer/   llm_client.py, formatter.py
storage/      database.py
scheduler/    runner.py (Summarizer — только run_summarize)
tests/        test_summarizer.py, test_filters.py,
               test_llm_client.py, test_scheduler.py,
               test_ssl_verify.py, test_formatter.py, test_database.py,
               test_prompts.py, test_main.py
main.py       точка входа
code.py       авторизация (первый запуск)
Dockerfile
docker-compose.yml
```
- **aggregator/collector.py удалён** — фоновый сбор больше не нужен

## Зависимости
- `telethon>=1.45.0` — Telegram MTProto
- `openai>=1.10.0,<3.0.0` — GigaChat API (совместим с OpenAI SDK)
- `python-dotenv>=1.2.4` — `.env`
- `pydantic>=2.0` — валидация конфига
- `pydantic-settings>=2.0` — BaseSettings для pydantic v2
- `httpx>=0.27.0` — OAuth тоhttp://t.me/c/1001466120158/4840кен и HTTP-запросы к GigaChat

## SQLite схема
- `messages`: id (PRIMARY KEY AUTOINCREMENT), telegram_id (INTEGER UNIQUE), chat_id (NOT NULL), chat_title, content, timestamp (DATETIME), processed (BOOLEAN DEFAULT 0), summary (TEXT), chat_type (TEXT)
- `summaries`: id (PRIMARY KEY AUTOINCREMENT), chat_ids (TEXT JSON), period_start (DATETIME), period_end (DATETIME), summary_text (TEXT), format (TEXT), status (TEXT DEFAULT 'pending')
- `settings`: key (TEXT PRIMARY KEY), value (TEXT)
- Индексы: `idx_messages_chat(chat_id)`, `idx_messages_processed(processed)`, `idx_messages_timestamp(timestamp)`, `idx_messages_telegram(telegram_id)`, `idx_messages_optimized(chat_id, processed, timestamp)`

### Ключевые методы БД
- `get_unprocessed_messages(chat_ids, since)` — необработанные сообщения (фильтр: только каналы, chat_type='channel'), ORDER BY timestamp DESC
- `get_processed_messages(chat_ids, limit)` — обработанные сообщения (фильтр: только каналы, chat_type='channel'), ORDER BY timestamp DESC
- `get_all_messages(chat_ids)` — все сообщения без фильтра processed (фильтр: только каналы, chat_type='channel'), ORDER BY timestamp DESC ⚠️ не используется в основном потоке
- `mark_processed(message_ids)` — пометить как обработанные
- `save_message(telegram_id, chat_id, content, timestamp, summary="")` — сохранить новое сообщение (telegram_id UNIQUE)
- `update_message_summary(telegram_id, summary)` — обновить суммари + установить processed=1
- `save_summary(...)` — сохранить результат суммаризации
- `cleanup_old_messages(days)` — удалить старые сообщения
- `get_setting(key)` — получить настройку
- `set_setting(key, value)` — установить настройку

## Команды Telegram
| Команда | Короткая | Описание |
|---------|----------|----------|
| `/start` | `/s` | Приветствие, список команд |
| `/my_id` | `/id` | Показать ID пользователя |
| `/chats` | `/c` | Список всех чатов/каналов |
| `/active` | `/a` | Список активных чатов |
| `/add_chat` | `/ac` | Добавить чат в активные: `/ac <ID>` |
| `/rm_chat` | `/rc` | Убрать чат из активных: `/rc <ID>` или `/rc all` |
| `/add_all` | `/aa` | Активировать все чаты |
| `/summarize` | `/sum` / `/ж` | Суммаризация: `/sum` или `/ж` (непрочитанные, max 20/чат) или `/sum 50` (50 из каждого чата) |
| `/status` | `/st` | Статус последнего запуска |
| `/settings` | `/set` | Настройки: `/set format:краткое` |

## Запуск
```bash
# Первый запуск — авторизация
python3 code.py
# Введите номер → код придёт в Telegram → введите код в терминал

# Запуск приложения
python3 main.py

# Docker
docker-compose up -d
```

## Безопасность зависимостей
- Только официально поддерживаемые библиотеки и фреймворки
- Никаких сторонних/неофициальных обёрток — критично для безопасности
- Telethon, OpenAI SDK, Pydantic, python-dotenv, httpx, SQLite — всё из официальных репозиториев

## Особенности
- Нет бота — клиент работает как личный аккаунт
- Сессия в `.session` файле
- Автоочистка сообщений старше 30 дней (настраивается в CLEANUP_DAYS)
- Rate limits Telegram: встроенные паузы Telethon
- `.gitignore` уже исключает `.env`, `*.session`, `*.db`, `logs/`
- Все временные метки хранятся в UTC (Telegram возвращает timezone-aware даты)
- Суммаризация защищена mutex — параллельные вызовы блокируются
- `/sum N` берёт N сообщений из Telegram с пагинацией (limit=100, offset++)
- Collector использует telegram_id для дедупликации (UNIQUE constraint)
- При `/sum N`: новые сообщения (processed=0) отправляются на LLM, остальные N берутся из БД с готовыми суммари
- Summary для processed-сообщений берётся из БД (поле `summary`), не отправляется на LLM повторно
- LLM получает ТОЛЬКО новые сообщения (processed=0), summary для processed берётся из БД
- Лимит токенов GigaChat: 50000 в день (настраивается в DAILY_TOKEN_LIMIT), при достижении — уведомление пользователю

## Стратегия вызова LLM
⚠️ **Один запрос на чат, НЕ на все сообщения сразу.**

1. Новые сообщения группируются по чатам (`defaultdict(list)`)
2. Для каждого чата — отдельный вызов `llm_client.summarize()`
3. Ответы объединяются в `llm_summaries = {telegram_id: summary_text}`
4. Fallback: если парсер не нашёл суммари для сообщения — отдельный запрос с промптом "Суммаризируй это сообщение в 1-2 предложения"
5. Общая суммаризация по всем чатам — отдельный вызов

**Почему не один большой запрос:**
- LLM теряет формат при >15 сообщениях
- `max_tokens=4096` ограничивает длину ответа
- Парсер `_parse_llm_summaries` ищет `SUMMARY: ... | ID: ... | CHAT: ...` на каждой строке
- При смешивании чатов LLM путает контекст

**Парсер:** регистронезависимый поиск `ID` и `SUMMARY` через regex, гибкий к вариациям формата.

**Промпты:** содержат примеры формата и чёткие инструкции "НЕ добавляй вводный текст".

## Ссылки на сообщения (кликабельные ID)
- Formatter генерирует строку `ID: {telegram_id}|{chat_id}` для каждого сообщения (если chat_id != 0)
- Пример: `ID: 982|-1001234567890`
- `TelethonClient._parse_id_links()` парсит эту строку и создаёт `MessageEntityTextUrl`
- URL формируется как `https://t.me/c/{abs(chat_id)}/{telegram_id}`
- UTF-16 offsets конвертируются через `len(text[:py_offset].encode('utf-16-le')) // 2`
- `MessageEntityTextUrl` принимает только `(offset, length, url)` — **без аргумента `text`**

## Ключевые паттерны (следовать дословно)

Полные блоки кода вынесены в `.gigacode_vsc/patterns/`:

| Паттерн | Файл |
|---------|------|
| Обработка сообщений, фоновые задачи, диалоги, даты | `.gigacode_vsc/patterns/telethon.md` |
| Mutex, run_summarize, _fetch_from_telegram | `.gigacode_vsc/patterns/scheduler.md` |
| get_processed_messages, update_message_summary | `.gigacode_vsc/patterns/database.md` |
| OAuth, API, токены, форматы, промпты | `.gigacode_vsc/patterns/llm_client.md` |
| Группировка, telegram_id типы | `.gigacode_vsc/patterns/formatter.md` |

Смотри README: `.gigacode_vsc/patterns/README.md`

## Клиент отправки сообщений (TelethonClient)
- `send_message(chat_id, message)` — отправляет сообщение с formatting_entities
- `_parse_urls(text)` — находит plain URL (http(s)://) и создаёт `MessageEntityUrl`
- `_parse_id_links(text)` — парсит `ID: telegram_id|chat_id` и создаёт `MessageEntityTextUrl`
- `MessageEntityTextUrl` принимает только `(offset, length, url)` — **без аргумента `text`**
- UTF-16 offsets конвертируются через `len(text[:py_offset].encode('utf-16-le')) // 2`
- `_split_message(text, max_length=4000)` — разбивает длинные сообщения по лимиту Telegram

## Нормализация ID каналов
⚠️ **Telegram channels требуют ID в формате -100XXXXXXXXXX.**

- Функция `normalize_channel_id(chat_id)` в `storage/database.py` нормализует ID
- Positive ID `1352895466` → `-1001352895466`
- Negative ID уже нормализован → возвращается без изменений
- Используется во всех местах: collector, scheduler, main commands

## Текущее состояние
✅ Код написан и работает. MVP завершён.
🔄 Суммаризация только по команде `/sum`, без фонового планировщика.
🔄 Ссылки на оригинальные сообщения — прямые URL `https://t.me/c/{chat_id}/{telegram_id}`.
🔄 Строгая SSL-верификация с использованием системных CA.
