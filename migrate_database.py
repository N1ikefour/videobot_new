#!/usr/bin/env python3
"""
Скрипт для миграции базы данных - добавление поддержки изображений
"""

import sqlite3
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def migrate_database(db_file="user_stats.db"):
    """Выполняет миграцию базы данных для добавления поддержки изображений"""
    try:
        logger.info(f"Начинаем миграцию базы данных: {db_file}")
        
        with sqlite3.connect(db_file) as conn:
            cursor = conn.cursor()
            
            # Проверяем, существует ли таблица users
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if cursor.fetchone():
                logger.info("Таблица users найдена")
                
                # Проверяем существующие колонки
                cursor.execute("PRAGMA table_info(users)")
                columns = [column[1] for column in cursor.fetchall()]
                logger.info(f"Существующие колонки: {columns}")
                
                # Добавляем недостающие колонки для изображений
                if 'total_images_processed' not in columns:
                    cursor.execute('ALTER TABLE users ADD COLUMN total_images_processed INTEGER DEFAULT 0')
                    logger.info("✅ Добавлена колонка total_images_processed")
                else:
                    logger.info("ℹ️ Колонка total_images_processed уже существует")
                
                if 'total_output_images' not in columns:
                    cursor.execute('ALTER TABLE users ADD COLUMN total_output_images INTEGER DEFAULT 0')
                    logger.info("✅ Добавлена колонка total_output_images")
                else:
                    logger.info("ℹ️ Колонка total_output_images уже существует")
            else:
                logger.error("❌ Таблица users не найдена!")
                return False
            
            # Проверяем, существует ли таблица image_processing_history
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='image_processing_history'")
            if not cursor.fetchone():
                # Создаем таблицу истории обработки изображений
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS image_processing_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        timestamp TEXT NOT NULL,
                        input_file_id TEXT,
                        input_file_size INTEGER,
                        output_count INTEGER NOT NULL,
                        processing_params TEXT,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                ''')
                logger.info("✅ Создана таблица image_processing_history")
            else:
                logger.info("ℹ️ Таблица image_processing_history уже существует")
            
            # Проверяем результат
            cursor.execute("PRAGMA table_info(users)")
            columns_after = [column[1] for column in cursor.fetchall()]
            logger.info(f"Колонки после миграции: {columns_after}")
            
            conn.commit()
            logger.info("✅ Миграция базы данных завершена успешно!")
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка при миграции базы данных: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Запуск миграции базы данных...")
    success = migrate_database()
    
    if success:
        print("✅ Миграция выполнена успешно!")
        print("Теперь можно запускать бота.")
    else:
        print("❌ Миграция не удалась!")
        print("Проверьте логи выше для получения подробной информации.")
