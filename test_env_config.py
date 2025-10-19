#!/usr/bin/env python3
"""
Скрипт для проверки конфигурации .env файла
"""

import os
from dotenv import load_dotenv

def test_env_configuration():
    """Проверяет все необходимые переменные окружения"""
    print("🔍 Проверка конфигурации .env файла...")
    print("=" * 50)
    
    # Загружаем .env файл
    load_dotenv()
    
    # Список обязательных переменных
    required_vars = {
        'BOT_TOKEN': 'Токен Telegram бота',
        'DB_HOST': 'Хост PostgreSQL',
        'DB_PORT': 'Порт PostgreSQL',
        'DB_NAME': 'Имя базы данных',
        'DB_USER': 'Пользователь БД',
        'DB_PASSWORD': 'Пароль БД',
        'ADMIN_SECRET_KEY': 'Секретный ключ админ-панели',
        'ADMIN_USERNAME': 'Логин админа',
        'ADMIN_PASSWORD': 'Пароль админа'
    }
    
    missing_vars = []
    found_vars = []
    
    for var_name, description in required_vars.items():
        value = os.environ.get(var_name)
        if value:
            # Скрываем чувствительные данные
            if any(sensitive in var_name.lower() for sensitive in ['password', 'token', 'key']):
                display_value = f"{'*' * (len(value) - 4)}{value[-4:]}" if len(value) > 4 else "****"
            else:
                display_value = value
            
            print(f"✅ {var_name}: {display_value}")
            found_vars.append(var_name)
        else:
            print(f"❌ {var_name}: НЕ НАЙДЕНА ({description})")
            missing_vars.append(var_name)
    
    print("\n" + "=" * 50)
    
    if missing_vars:
        print(f"❌ Найдено {len(missing_vars)} отсутствующих переменных:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n📝 Добавьте их в .env файл!")
        return False
    else:
        print(f"✅ Все {len(found_vars)} переменных найдены!")
        return True

def test_database_config():
    """Проверяет конфигурацию базы данных"""
    print("\n🗄️ Проверка конфигурации базы данных...")
    print("=" * 50)
    
    db_host = os.environ.get('DB_HOST')
    db_port = os.environ.get('DB_PORT')
    db_name = os.environ.get('DB_NAME')
    db_user = os.environ.get('DB_USER')
    
    if all([db_host, db_port, db_name, db_user]):
        connection_string = f"postgresql://{db_user}:****@{db_host}:{db_port}/{db_name}"
        print(f"📡 Строка подключения: {connection_string}")
        return True
    else:
        print("❌ Неполная конфигурация базы данных!")
        return False

def test_admin_config():
    """Проверяет конфигурацию админ-панели"""
    print("\n👤 Проверка конфигурации админ-панели...")
    print("=" * 50)
    
    admin_username = os.environ.get('ADMIN_USERNAME')
    admin_password = os.environ.get('ADMIN_PASSWORD')
    admin_secret = os.environ.get('ADMIN_SECRET_KEY')
    
    if admin_username and admin_password and admin_secret:
        print(f"👤 Логин админа: {admin_username}")
        print(f"🔐 Пароль: {'*' * len(admin_password)}")
        print(f"🔑 Секретный ключ: {'*' * (len(admin_secret) - 4)}{admin_secret[-4:]}")
        return True
    else:
        print("❌ Неполная конфигурация админ-панели!")
        return False

if __name__ == "__main__":
    print("🚀 ТЕСТИРОВАНИЕ КОНФИГУРАЦИИ СИСТЕМЫ")
    print("=" * 60)
    
    env_ok = test_env_configuration()
    db_ok = test_database_config()
    admin_ok = test_admin_config()
    
    print("\n" + "=" * 60)
    print("📊 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
    
    if env_ok and db_ok and admin_ok:
        print("✅ ВСЕ КОНФИГУРАЦИИ КОРРЕКТНЫ!")
        print("🚀 Можно запускать систему!")
    else:
        print("❌ НАЙДЕНЫ ПРОБЛЕМЫ В КОНФИГУРАЦИИ!")
        print("🔧 Исправьте ошибки перед запуском!")