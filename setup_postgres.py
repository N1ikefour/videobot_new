#!/usr/bin/env python3
"""
Скрипт для настройки PostgreSQL базы данных для видеобота
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

load_dotenv()

def setup_database():
    """Настройка PostgreSQL базы данных"""
    
    # Параметры подключения к PostgreSQL
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_ADMIN_USER = os.getenv('DB_ADMIN_USER', 'postgres')
    DB_ADMIN_PASSWORD = os.getenv('DB_ADMIN_PASSWORD', 'postgres')
    
    # Параметры для базы данных бота
    DB_NAME = os.getenv('DB_NAME', 'videobot_db')
    DB_USER = os.getenv('DB_USER', 'videobot_user')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'videobot_password')
    
    try:
        # Подключаемся к PostgreSQL как администратор
        print(f"Подключение к PostgreSQL на {DB_HOST}:{DB_PORT}...")
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_ADMIN_USER,
            password=DB_ADMIN_PASSWORD
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Создаем базу данных если не существует
        print(f"Создание базы данных '{DB_NAME}'...")
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(f'CREATE DATABASE "{DB_NAME}"')
            print(f"✅ База данных '{DB_NAME}' создана")
        else:
            print(f"✅ База данных '{DB_NAME}' уже существует")
        
        # Создаем пользователя если не существует
        print(f"Создание пользователя '{DB_USER}'...")
        cursor.execute(f"SELECT 1 FROM pg_roles WHERE rolname='{DB_USER}'")
        user_exists = cursor.fetchone()
        
        if not user_exists:
            cursor.execute(f"CREATE USER \"{DB_USER}\" WITH PASSWORD '{DB_PASSWORD}'")
            print(f"✅ Пользователь '{DB_USER}' создан")
        else:
            print(f"✅ Пользователь '{DB_USER}' уже существует")
        
        # Предоставляем права на базу данных
        print(f"Предоставление прав пользователю '{DB_USER}' на базу '{DB_NAME}'...")
        cursor.execute(f'GRANT ALL PRIVILEGES ON DATABASE "{DB_NAME}" TO "{DB_USER}"')
        
        # Переключаемся на базу данных бота для предоставления прав на схемы
        conn.close()
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_ADMIN_USER,
            password=DB_ADMIN_PASSWORD
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Предоставляем права на схему public
        cursor.execute(f'GRANT ALL ON SCHEMA public TO "{DB_USER}"')
        cursor.execute(f'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "{DB_USER}"')
        cursor.execute(f'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "{DB_USER}"')
        cursor.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "{DB_USER}"')
        cursor.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO "{DB_USER}"')
        
        print(f"Права предоставлены пользователю '{DB_USER}'")
        
        conn.close()
        
        print("\nНастройка PostgreSQL завершена успешно!")
        print(f"\nИнформация для подключения:")
        print(f"   Host: {DB_HOST}")
        print(f"   Port: {DB_PORT}")
        print(f"   Database: {DB_NAME}")
        print(f"   User: {DB_USER}")
        print(f"   Password: {DB_PASSWORD}")
        
        print(f"\n🔧 Строка подключения:")
        print(f"   postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
        
        print(f"\n📝 Добавьте эти переменные в .env файл:")
        print(f"   DB_HOST={DB_HOST}")
        print(f"   DB_PORT={DB_PORT}")
        print(f"   DB_NAME={DB_NAME}")
        print(f"   DB_USER={DB_USER}")
        print(f"   DB_PASSWORD={DB_PASSWORD}")
        
    except Exception as e:
        print(f"❌ Ошибка настройки PostgreSQL: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Настройка PostgreSQL для видеобота")
    print("=" * 50)
    
    success = setup_database()
    
    if success:
        print("\n✅ Настройка завершена! Теперь можно запускать бота.")
    else:
        print("\n❌ Настройка не удалась. Проверьте параметры подключения.")
