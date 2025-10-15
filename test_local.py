#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Простой тест для демонстрации работы с PostgreSQL
"""

import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

def test_environment():
    """Тестируем переменные окружения"""
    print("=== ТЕСТ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ===")
    
    # Проверяем основные переменные
    bot_token = os.getenv('BOT_TOKEN')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'videobot_db')
    db_user = os.getenv('DB_USER', 'videobot_user')
    db_password = os.getenv('DB_PASSWORD')
    
    print(f"BOT_TOKEN: {'✅ Установлен' if bot_token else '❌ Не найден'}")
    print(f"DB_HOST: {db_host}")
    print(f"DB_PORT: {db_port}")
    print(f"DB_NAME: {db_name}")
    print(f"DB_USER: {db_user}")
    print(f"DB_PASSWORD: {'✅ Установлен' if db_password else '❌ Не найден'}")
    
    return bool(bot_token and db_password)

def test_postgres_connection():
    """Тестируем подключение к PostgreSQL"""
    print("\n=== ТЕСТ ПОДКЛЮЧЕНИЯ К POSTGRESQL ===")
    
    try:
        import psycopg2
        print("✅ psycopg2 установлен")
        
        # Пытаемся подключиться
        from config import DATABASE_CONFIG
        
        conn = psycopg2.connect(
            host=DATABASE_CONFIG['host'],
            port=DATABASE_CONFIG['port'],
            database='postgres',  # Подключаемся к системной БД
            user=DATABASE_CONFIG['user'],
            password=DATABASE_CONFIG['password']
        )
        
        print("✅ Подключение к PostgreSQL успешно!")
        conn.close()
        return True
        
    except ImportError:
        print("❌ psycopg2 не установлен. Запустите: pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        print("\n💡 РЕШЕНИЕ:")
        print("1. Установите PostgreSQL")
        print("2. Запустите сервис PostgreSQL")
        print("3. Проверьте настройки в .env файле")
        return False

def test_database_manager():
    """Тестируем DatabaseManager"""
    print("\n=== ТЕСТ DATABASE MANAGER ===")
    
    try:
        from database_postgres import DatabaseManager
        
        # Создаем экземпляр
        db_manager = DatabaseManager()
        print("✅ DatabaseManager создан")
        
        # Пытаемся инициализировать БД
        db_manager.init_database()
        print("✅ База данных инициализирована")
        
        # Тестируем добавление пользователя
        test_user_id = 12345
        db_manager.add_or_update_user(
            user_id=test_user_id,
            username="test_user",
            first_name="Test",
            last_name="User"
        )
        print("✅ Пользователь добавлен")
        
        # Проверяем пользователя
        user = db_manager.get_user(test_user_id)
        if user:
            print(f"✅ Пользователь найден: {user['first_name']}")
        else:
            print("❌ Пользователь не найден")
        
        # Удаляем тестового пользователя
        db_manager.conn.execute("DELETE FROM users WHERE user_id = %s", (test_user_id,))
        db_manager.conn.commit()
        print("✅ Тестовый пользователь удален")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка DatabaseManager: {e}")
        return False

def main():
    """Главная функция тестирования"""
    print("🧪 ТЕСТИРОВАНИЕ ЛОКАЛЬНОЙ НАСТРОЙКИ")
    print("=" * 50)
    
    # Тест 1: Переменные окружения
    env_ok = test_environment()
    
    # Тест 2: Подключение к PostgreSQL
    postgres_ok = test_postgres_connection()
    
    # Тест 3: DatabaseManager (только если PostgreSQL работает)
    db_ok = False
    if postgres_ok:
        db_ok = test_database_manager()
    
    # Итоги
    print("\n" + "=" * 50)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print(f"Переменные окружения: {'✅' if env_ok else '❌'}")
    print(f"PostgreSQL: {'✅' if postgres_ok else '❌'}")
    print(f"DatabaseManager: {'✅' if db_ok else '❌'}")
    
    if env_ok and postgres_ok and db_ok:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ! Можно запускать бота.")
        print("\nСледующие шаги:")
        print("1. python bot.py - запуск бота")
        print("2. python admin_panel.py - запуск админ-панели")
    else:
        print("\n⚠️ Есть проблемы. Исправьте их перед запуском бота.")
        
        if not env_ok:
            print("\n🔧 Исправьте .env файл")
        if not postgres_ok:
            print("\n🔧 Установите и настройте PostgreSQL")

if __name__ == "__main__":
    main()
