"""Точка входа в приложение."""

import asyncio
import logging
import signal

import telethon.events

from config.settings import settings
from client.telethon_client import TelethonClient
from storage.database import Database, normalize_channel_id
from scheduler.runner import Summarizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class MessageSumApp:
    """Основное приложение."""

    def __init__(self):
        self.db = Database(settings.db_path)
        self.client = TelethonClient()
        self.summarizer = Summarizer(self.client, self.db)
        self._running = False

    async def process_message(self, event):
        """Обработать входящее сообщение."""
        sender_id = event.chat_id
        if sender_id is None:
            logger.warning("Не удалось определить chat_id")
            return
        
        logger.info("Получено сообщение от chat_id=%s", sender_id)
        
        owner_id = int(self.db.get_setting("owner_chat_id") or settings.owner_chat_id)
        if sender_id != owner_id:
            logger.info("Сообщение не от владельца (chat_id=%s, owner_id=%s)", sender_id, owner_id)
            return

        text = event.text or ''
        logger.info("Команда: %s", text)
        if text.startswith('/'):
            await self.handle_command_text(text)

    async def handle_command_text(self, text: str):
        """Обработать команду из текста сообщения."""
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ''

        if cmd == '/start' or cmd == '/s':
            await self._cmd_start()
        elif cmd == '/my_id' or cmd == '/id':
            await self._cmd_my_id()
        elif cmd == '/chats' or cmd == '/c':
            await self._cmd_chats()
        elif cmd == '/active' or cmd == '/a':
            await self._cmd_active()
        elif cmd == '/summarize' or cmd == '/sum' or cmd == '/ж':
            await self._cmd_summarize(args)
        elif cmd == '/status' or cmd == '/st':
            await self._cmd_status()
        elif cmd == '/settings' or cmd == '/set':
            await self._cmd_settings(args)
        elif cmd == '/add_chat' or cmd == '/ac':
            await self._cmd_add_chat(args)
        elif cmd == '/rm_chat' or cmd == '/rc':
            await self._cmd_rm_chat(args)
        elif cmd == '/add_all' or cmd == '/aa':
            await self._cmd_add_all()

    async def _cmd_start(self):
        welcome = (
            "👋 Привет! Я — суммаризатор Telegram.\n\n"
            "Я читаю сообщения из выбранных чатов и каналов\n"
            "и отправляю краткие резюме вам в личку.\n\n"
            "Доступные команды:\n"
            "  /chats (/c) — список всех чатов\n"
            "  /active (/a) — список активных чатов\n"
            "  /add_chat (/ac) <ID> — добавить чат в активные\n"
            "  /rm_chat (/rc) <ID> — убрать чат из активных\n"
            "  /rm_chat (/rc) all — убрать все чаты\n"
            "  /add_all (/aa) — активировать все чаты\n"
            "  /summarize (/sum) (/ж) [N] — суммаризация (N=число сообщений)\n"
            "  /status (/st) — статус последнего запуска\n"
            "  /settings (/set) format:<краткое|подробное|тезисы>\n"
        )
        await self.client.send_message(settings.owner_chat_id, welcome)

    async def _cmd_my_id(self):
        me = await self.client.get_me()
        info = f"🔑 Ваш ID: {me.id}\n\nИспользуйте его в OWNER_CHAT_ID для .env"
        await self.client.send_message(settings.owner_chat_id, info)

    async def _cmd_chats(self):
        """Команда /chats — список чатов и управление."""
        dialogs = await self.client.get_dialogs()
        active_ids = self.db.get_setting("active_chats")
        active_set = set(map(int, active_ids.split(","))) if active_ids else set()

        # Собрать все чаты/каналы
        from telethon.tl.types import Channel, Chat

        telegram_chats = []
        for dialog in dialogs:
            if not dialog.entity:
                continue
            entity = dialog.entity
            if isinstance(entity, (Channel, Chat)):
                chat_id = normalize_channel_id(getattr(entity, 'id', None) or 0)
                title = getattr(entity, 'title', dialog.name or 'Unknown')
                if chat_id:
                    telegram_chats.append({
                        "id": chat_id,
                        "title": title,
                        "active": chat_id in active_set,
                    })

        if not telegram_chats:
            await self.client.send_message(settings.owner_chat_id, "❌ Нет доступных чатов/каналов.")
            return

        # Показать список
        lines = ["📋 Доступные чаты/каналы:\n"]
        for i, chat in enumerate(telegram_chats, 1):
            mark = "✅" if chat["active"] else "⬜"
            lines.append(f"  {i}. {mark} {chat['title']} (ID: {chat['id']})")

        lines.append("\n📌 Активные:")
        active_chats = [c for c in telegram_chats if c["active"]]
        if active_chats:
            for c in active_chats:
                lines.append(f"  ✅ {c['title']} (ID: {c['id']})")
        else:
            lines.append("  (нет)")

        lines.append("\n💡 Для активации:")
        lines.append("  /add_chat <ID> — добавить в активные")
        lines.append("  /rm_chat <ID> — убрать из активных")
        lines.append("  /rm_chat all — убрать все чаты")
        lines.append("  /add_all — активировать все")

        text = "\n".join(lines)
        await self.client.send_message(settings.owner_chat_id, text)

    async def _cmd_active(self):
        """Команда /active — список активных чатов."""
        active_ids_str = self.db.get_setting("active_chats")
        if not active_ids_str:
            await self.client.send_message(
                settings.owner_chat_id,
                "⬜ Нет активных чатов. Используйте /add_chat <ID> для добавления."
            )
            return

        active_ids = [int(x.strip()) for x in active_ids_str.split(",") if x.strip()]
        dialogs = await self.client.get_dialogs()

        # Найти названия чатов по ID
        active_chats = []
        for dialog in dialogs:
            if not dialog.entity:
                continue
            from telethon.tl.types import Channel, Chat
            if isinstance(dialog.entity, (Channel, Chat)):
                chat_id = normalize_channel_id(getattr(dialog.entity, 'id', None) or 0)
                if chat_id and chat_id in active_ids:
                    title = getattr(dialog.entity, 'title', dialog.name or 'Unknown')
                    active_chats.append({"id": chat_id, "title": title})

        if not active_chats:
            await self.client.send_message(
                settings.owner_chat_id,
                "⬜ Нет активных чатов. Используйте /add_chat <ID> для добавления."
            )
            return

        lines = ["📌 Активные чаты:\n"]
        for i, chat in enumerate(active_chats, 1):
            lines.append(f"  {i}. ✅ {chat['title']} (ID: {chat['id']})")

        lines.append(f"\nВсего активных: {len(active_chats)}")
        lines.append("\n💡 Управление:")
        lines.append("  /rm_chat <ID> — убрать из активных")
        lines.append("  /rm_chat all — убрать все чаты")
        lines.append("  /add_chat <ID> — добавить в активные")

        text = "\n".join(lines)
        await self.client.send_message(settings.owner_chat_id, text)

    async def _cmd_summarize(self, args: str):
        """Команда /summarize — суммаризация с опциональным числом сообщений."""
        msg_count = None
        only_unread = False

        if args:
            try:
                msg_count = int(args.strip())
                if msg_count <= 0 or msg_count > 1000:
                    await self.client.send_message(
                        settings.owner_chat_id,
                        "❌ Укажите число от 1 до 1000: /summarize 50"
                    )
                    return
            except ValueError:
                await self.client.send_message(
                    settings.owner_chat_id,
                    "❌ Неверный формат. Пример: /summarize 50"
                )
                return
        else:
            # Без аргументов — только непрочитанные, max 20 из каждого чата
            msg_count = 20
            only_unread = True

        # Читаем формат из настроек пользователя
        fmt = self.db.get_setting("format") or "short"

        await self.client.send_message(settings.owner_chat_id, "⏳ Суммаризация...")
        success = await self.summarizer.run_summarize(
            fmt=fmt, msg_count=msg_count, only_unread=only_unread
        )
        if not success:
            await self.client.send_message(
                settings.owner_chat_id,
                "❌ Нет сообщений для суммаризации или ошибка."
            )

    async def _cmd_status(self):
        last = self.db.get_last_summary()
        if not last:
            await self.client.send_message(settings.owner_chat_id, "📭 Суммаризаций пока не было.")
            return
        status = (
            f"📊 Последняя суммаризация:\n"
            f"📅 {last['period_start'][:16] if last['period_start'] else 'N/A'}\n"
            f"📝 Статус: {last['status']}\n"
            f"📋 Формат: {last['format']}"
        )
        await self.client.send_message(settings.owner_chat_id, status)

    async def _cmd_settings(self, args: str):
        if args.startswith("format:"):
            fmt = args.split(":", 1)[1].strip()
            valid_formats = ["краткое", "подробное", "тезисы"]
            if fmt not in valid_formats:
                await self.client.send_message(settings.owner_chat_id, f"❌ Неверный формат. Доступно: {', '.join(valid_formats)}")
                return
            self.db.set_setting("format", fmt)
            await self.client.send_message(settings.owner_chat_id, f"✅ Формат установлен: {fmt}")
        else:
            await self.client.send_message(settings.owner_chat_id, "🔧 /settings format:<краткое|подробное|тезисы>")

    async def _cmd_add_chat(self, args: str):
        if not args:
            await self.client.send_message(settings.owner_chat_id, "❌ Укажите ID чата: /add_chat <ID>\nПример: /add_chat -1001234567890")
            return
        try:
            raw_chat_id = int(args.strip())
        except ValueError:
            await self.client.send_message(settings.owner_chat_id, "❌ Неверный ID. Используйте числовое значение.")
            return
        chat_id = normalize_channel_id(raw_chat_id)
        active_ids = self.db.get_setting("active_chats")
        active_set = set(map(int, active_ids.split(","))) if active_ids else set()
        active_set.add(chat_id)
        self.db.set_setting("active_chats", ",".join(map(str, active_set)))
        await self.client.send_message(settings.owner_chat_id, f"✅ Чат {chat_id} добавлен в активные")

    async def _cmd_rm_chat(self, args: str):
        if not args:
            await self.client.send_message(
                settings.owner_chat_id,
                "❌ Укажите ID чата или 'all': /rm_chat <ID>\nПример: /rm_chat all"
            )
            return
        arg = args.strip().lower()
        if arg == "all":
            active_ids_str = self.db.get_setting("active_chats")
            if active_ids_str:
                count = len([x.strip() for x in active_ids_str.split(",") if x.strip()])
            else:
                count = 0
            self.db.set_setting("active_chats", "")
            await self.client.send_message(
                settings.owner_chat_id,
                f"✅ Все чаты ({count}) удалены из активных"
            )
            return
        try:
            raw_chat_id = int(arg)
        except ValueError:
            await self.client.send_message(settings.owner_chat_id, "❌ Неверный ID.")
            return
        chat_id = normalize_channel_id(raw_chat_id)
        active_ids = self.db.get_setting("active_chats")
        active_set = set(map(int, active_ids.split(","))) if active_ids else set()
        active_set.discard(chat_id)
        self.db.set_setting("active_chats", ",".join(map(str, active_set)))
        await self.client.send_message(settings.owner_chat_id, f"✅ Чат {chat_id} удалён из активных")

    async def _cmd_add_all(self):
        dialogs = await self.client.get_dialogs()
        from telethon.tl.types import Channel, Chat

        all_ids = set()
        for dialog in dialogs:
            if not dialog.entity:
                continue
            entity = dialog.entity
            if isinstance(entity, (Channel, Chat)):
                chat_id = getattr(entity, 'id', None)
                if chat_id:
                    all_ids.add(normalize_channel_id(chat_id))

        if not all_ids:
            await self.client.send_message(settings.owner_chat_id, "❌ Нет доступных чатов/каналов.")
            return

        self.db.set_setting("active_chats", ",".join(map(str, all_ids)))
        await self.client.send_message(settings.owner_chat_id, f"✅ Активировано {len(all_ids)} чатов/каналов")

    async def run(self):
        """Запустить приложение."""
        logger.info("Запуск message-sum...")

        async with self.client:
            me = await self.client.get_me()
            logger.info("Авторизован как: %s (@%s)", me.first_name, me.username or 'N/A')

            # Сохранить OWNER_CHAT_ID если не установлен
            if not self.db.get_setting("owner_chat_id"):
                self.db.set_setting("owner_chat_id", str(me.id))

            # Обработка сообщений — правильный паттерн Telethon
            owner_id = int(self.db.get_setting("owner_chat_id") or settings.owner_chat_id)
            self.client.client.add_event_handler(
                self.process_message,
                telethon.events.NewMessage(chats=[owner_id]),
            )
            logger.info("Обработчик зарегистрирован для ID: %d", owner_id)

            self._running = True
            logger.info("Приложение запущено. Ожидание сообщений...")

            # Ожидание сигналов завершения
            stop = asyncio.Event()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop = asyncio.get_running_loop()
                loop.add_signal_handler(sig, stop.set)
            await stop.wait()

            self._running = False

        logger.info("Приложение остановлено.")


def main():
    app = MessageSumApp()
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("Завершено по Ctrl+C")


if __name__ == "__main__":
    main()
