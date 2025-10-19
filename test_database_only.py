#!/usr/bin/env python3
"""
Скрипт для проверки подключения к PostgreSQL базе данных
"""

import os
import psycopg2
from dotenv import load_dotenv

def test_database_connection():
    """Проверяет подключение к PostgreSQL"""
    print("🗄️ ТЕСТИРОВАНИЕ ПОДКЛЮЧЕНИЯ К POSTGRESQL")
    print("=" * 60)
    
    # Загружаем .env файл
    load_dotenv()
    
    # Получаем параметры подключения
    db_config = {
        'host': os.environ.get('DB_HOST'),
        'port': os.environ.get('DB_PORT'),
        'database': os.environ.get('DB_NAME'),
        'user': os.environ.get('DB_USER'),
        'password': os.environ.get('DB_PASSWORD')
    }
    
    print("📋 Параметры подключения:")
    for key, value in db_config.items():
        if key == 'password':
            display_value = '*' * len(value) if value else 'НЕ ЗАДАН'
        else:
            display_value = value or 'НЕ ЗАДАН'
        print(f"   {key}: {display_value}")
    
    # Проверяем наличие всех параметров
    missing_params = [key for key, value in db_config.items() if not value]
    if missing_params:
        print(f"\n❌ Отсутствуют параметры: {', '.join(missing_params)}")
        return False
    
    print(f"\n🔗 Попытка подключения к {db_config['host']}:{db_config['port']}...")
    
    try:
        # Пытаемся подключиться
        conn = psycopg2.connect(**db_config)
        
        print("✅ Подключение успешно!")
        
        # Проверяем версию PostgreSQL
        with conn.cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            print(f"📊 Версия PostgreSQL: {version.split(',')[0]}")
            
            # Проверяем существование базы данных
            cursor.execute("SELECT current_database();")
            current_db = cursor.fetchone()[0]
            print(f"🗄️ Текущая база данных: {current_db}")
            
            # Проверяем права пользователя
            cursor.execute("SELECT current_user;")
            current_user = cursor.fetchone()[0]
            print(f"👤 Текущий пользователь: {current_user}")
            
            # Проверяем существующие таблицы
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            tables = cursor.fetchall()
            
            if tables:
                print(f"\n📋 Найдено таблиц: {len(tables)}")
                for table in tables:
                    print(f"   - {table[0]}")
            else:
                print("\n📋 Таблицы не найдены (база данных пустая)")
        
        conn.close()
        return True
        
    except psycopg2.OperationalError as e:
        print(f"❌ Ошибка подключения: {e}")
        print("\n🔧 Возможные причины:")
        print("   1. PostgreSQL не запущен")
        print("   2. Неверные параметры подключения")
        print("   3. База данных не существует")
        print("   4. Пользователь не имеет прав доступа")
        return False
        
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

def check_postgresql_service():
    """Проверяет статус службы PostgreSQL"""
    print("\n🔍 Проверка службы PostgreSQL...")
    print("=" * 40)
    
    try:
        # Для Windows
        import subprocess
        result = subprocess.run(
            ['sc', 'query', 'postgresql-x64-14'], 
            capture_output=True, 
            text=True
        )
        
        if 'RUNNING' in result.stdout:
            print("✅ Служба PostgreSQL запущена")
            return True
        elif 'STOPPED' in result.stdout:
            print("❌ Служба PostgreSQL остановлена")
            print("💡 Запустите: sc start postgresql-x64-14")
            return False
        else:
            print("❓ Статус службы неизвестен")
            return False
            
    except Exception as e:
        print(f"❌ Не удалось проверить службу: {e}")
        print("💡 Проверьте вручную через Диспетчер задач или services.msc")
        return False

if __name__ == "__main__":
    service_ok = check_postgresql_service()
    db_ok = test_database_connection()
    
    print("\n" + "=" * 60)
    print("📊 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
    
    if db_ok:
        print("✅ ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ РАБОТАЕТ!")
        print("🚀 Можно запускать приложения!")
    else:
        print("❌ ПРОБЛЕМЫ С ПОДКЛЮЧЕНИЕМ К БАЗЕ ДАННЫХ!")
        if not service_ok:
            print("🔧 Сначала запустите службу PostgreSQL!")
        else:
            print("🔧 Проверьте параметры подключения в .env файле!")