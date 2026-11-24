"""Скрипт авторизации в Telegram (MTProto).

Создаёт новую сессию и сохраняет её в message_sum.session.
Запуск: python3 code.py
"""

import asyncio
import sys
from pathlib import Path

from telethon import TelegramClient
from config.settings import settings


async def authorize():
    """Авторизация и создание новой сессии."""
    
    # Удалить старую повреждённую сессию
    session_path = Path(settings.session_file)
    if session_path.exists():
        print(f"🗑️  Удаление старой сессии: {session_path}")
        session_path.unlink()
    
    # Создаём клиент с сохранением в файл
    client = TelegramClient(
        settings.session_file,
        settings.telethon_api_id,
        settings.telethon_api_hash,
    )
    
    print(f"📱 Номер: {settings.telethon_phone}")
    print()
    
    try:
        # Подключаемся
        print("🔌 Подключение к Telegram...")
        await client.connect()
        print("✅ Подключено!")
        
        # Проверяем, авторизован ли уже
        me = await client.get_me()
        if me:
            print(f"✅ Уже авторизован: {me.first_name} (@{me.username})")
        else:
            raise Exception("Не авторизован")
        
    except Exception:
        # Нужно ввести код
        try:
            print("📤 Отправка кода...")
            await client.start(phone=settings.telethon_phone)
            
            me = await client.get_me()
            print(f"\n✅ Авторизован: {me.first_name} (@{me.username})")
            print(f"   ID: {me.id}")
            
        except TypeError:
            # Вводим код вручную
            code = input("\n🔑 Введите код из Telegram: ").strip()
            await client.start(phone=settings.telethon_phone, code=code)
            
            me = await client.get_me()
            print(f"\n✅ Авторизован: {me.first_name} (@{me.username})")
            print(f"   ID: {me.id}")
    
    # Проверяем файл сессии
    if session_path.exists():
        size = session_path.stat().st_size
        print(f"\n💾 Сессия сохранена в: {settings.session_file}")
        print(f"   Размер: {size} байт")
        print("✅ Готово!")
    else:
        print("\n❌ Файл сессии не создан!")
        sys.exit(1)
    
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(authorize())
