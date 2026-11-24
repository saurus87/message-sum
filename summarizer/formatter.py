"""Форматирование результатов суммаризации."""

from datetime import datetime
from typing import Optional


def _format_message_link(chat_id, telegram_id,
                           chat_title: str = "") -> str:
    """
    Сформировать ссылку на сообщение в Telegram.

    Telegram MTProto не поддерживает кастомный текст для ссылок
    (MessageEntityTextUrl конвертируется в MessageEntityUrl).
    Поэтому возвращаем plain URL — Telegram сам сделает его кликабельным.

    Args:
        chat_id: ID чата (например, -1001234567890) — может быть str или int
        telegram_id: ID сообщения
        chat_title: название чата (для логирования)

    Returns:
        Plain URL или fallback
    """
    # Привести к int — из БД может прийти строка
    try:
        chat_id = int(chat_id) if chat_id else 0
    except (ValueError, TypeError):
        chat_id = 0

    try:
        telegram_id = int(telegram_id) if telegram_id else 0
    except (ValueError, TypeError):
        telegram_id = 0

    if not chat_id or not telegram_id:
        return str(telegram_id)

    # Каналы и супергруппы (ID < -10^10, т.е. -100...):
    # chat_id из БД в формате -100XXXXXXXXXX → URL требует XXXXXXXXXXXX
    # Обратная формула нормализации: original = -10^12 - normalized
    if chat_id < -10000000000:
        original_id = -1000000000000 - chat_id
        return f"https://t.me/c/{original_id}/{telegram_id}"

    return str(telegram_id)


def format_summary(
    summary_text: str,
    chat_titles: list[str],
    period_start: datetime,
    period_end: datetime,
    message_count: int,
    messages: Optional[list[dict]] = None,
    llm_summaries: Optional[dict] = None,
) -> str:
    """
    Отформатировать результат суммаризации для отправки.
    
    Args:
        summary_text: сырой ответ от LLM
        chat_titles: названия чатов
        period_start/period_end: период суммаризации
        message_count: количество сообщений
        messages: список сообщений (с полями telegram_id, summary, content, timestamp, chat_title, chat_id)
        llm_summaries: словарь {telegram_id: summary_text} для новых сообщений
    """
    header = (
        f"📊 Суммаризация\n"
        f"📅 Период: {period_start.strftime('%d.%m')} — {period_end.strftime('%d.%m.%Y %H:%M')}\n"
        f"💬 Чатов: {len(chat_titles)}\n"
        f"📨 Сообщений: {message_count}\n"
        f"{'─' * 30}\n"
    )

    if chat_titles:
        header += f"📌 Чаты: {', '.join(chat_titles[:5])}"
        if len(chat_titles) > 5:
            header += f" (+{len(chat_titles) - 5} ещё)"
        header += "\n"

    if not messages:
        # Fallback: если нет сообщений, показываем сырой summary
        if summary_text:
            return header + summary_text
        return header

    # Группировка сообщений по каналам (сохраняем порядок первого появления)
    grouped: dict[str, list[dict]] = {}
    for msg in messages:
        chat_title = msg.get("chat_title", "Unknown")
        if chat_title not in grouped:
            grouped[chat_title] = []
        grouped[chat_title].append(msg)

    # Собираем результат
    result = header

    for chat_title, chat_msgs in grouped.items():
        result += f"\n📌 {chat_title} | {len(chat_msgs)} сообщений\n"

        for i, msg in enumerate(chat_msgs, 1):
            telegram_id = msg.get("telegram_id")  # int
            timestamp = msg.get("timestamp", "")
            content = msg.get("content", "")
            stored_summary = msg.get("summary", "")
            chat_id = msg.get("chat_id", "")

            # Приоритет: stored summary (из БД) → LLM summary → текст сообщения
            if stored_summary:
                summary_part = stored_summary
            elif llm_summaries and telegram_id in llm_summaries:
                summary_part = llm_summaries[telegram_id]
            else:
                # Нет суммари — показываем текст сообщения
                summary_part = content[:300] if content else "(пустое сообщение)"
                if len(content) > 300:
                    summary_part += "..."

            # Форматируем время
            try:
                dt = datetime.fromisoformat(timestamp)
                time_str = dt.strftime("%d.%m %H:%M")
            except:
                time_str = timestamp[:16] if timestamp else "?"

            # Ссылка на оригинал (прямой URL для кликабельности)
            if chat_id:
                link = _format_message_link(chat_id, telegram_id, chat_title)
                link_display = f"🔗 {link}"
            else:
                link_display = f"{telegram_id}"

            # Формируем блок суммари
            result += f"\n{i}. {time_str} — {summary_part}\n"
            result += f"   {link_display}\n"

    return result
