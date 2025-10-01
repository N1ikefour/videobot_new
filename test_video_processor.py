#!/usr/bin/env python3
"""
Тестовый скрипт для проверки основных функций VideoProcessor
"""

import os
import sys
import asyncio
import logging
from video_processor import VideoProcessor

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def test_video_processor():
    """Тестирует основные функции VideoProcessor"""
    
    logger.info("🧪 Начинаю тестирование VideoProcessor...")
    
    # Создаем экземпляр VideoProcessor
    try:
        processor = VideoProcessor()
        logger.info("✅ VideoProcessor успешно создан")
    except Exception as e:
        logger.error(f"❌ Ошибка при создании VideoProcessor: {e}")
        return False
    
    # Проверяем создание директорий
    try:
        from config import OUTPUT_DIR, TEMP_DIR
        logger.info(f"📁 OUTPUT_DIR: {OUTPUT_DIR}")
        logger.info(f"📁 TEMP_DIR: {TEMP_DIR}")
        
        if os.path.exists(OUTPUT_DIR):
            logger.info("✅ OUTPUT_DIR существует")
        else:
            logger.warning("⚠️ OUTPUT_DIR не существует")
            
        if os.path.exists(TEMP_DIR):
            logger.info("✅ TEMP_DIR существует")
        else:
            logger.warning("⚠️ TEMP_DIR не существует")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке директорий: {e}")
        return False
    
    # Проверяем импорты
    try:
        from moviepy.editor import VideoFileClip
        logger.info("✅ MoviePy импортирован успешно")
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта MoviePy: {e}")
        return False
    
    try:
        from PIL import Image
        logger.info("✅ PIL импортирован успешно")
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта PIL: {e}")
        return False
    
    try:
        import numpy as np
        logger.info("✅ NumPy импортирован успешно")
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта NumPy: {e}")
        return False
    
    # Проверяем опциональный OpenCV
    try:
        import cv2
        logger.info("✅ OpenCV доступен")
    except ImportError:
        logger.info("ℹ️ OpenCV недоступен (это нормально)")
    
    logger.info("🎉 Все основные тесты пройдены успешно!")
    return True

def main():
    """Главная функция"""
    logger.info("🚀 Запуск тестирования...")
    
    try:
        result = asyncio.run(test_video_processor())
        if result:
            logger.info("✅ Тестирование завершено успешно!")
            sys.exit(0)
        else:
            logger.error("❌ Тестирование завершилось с ошибками!")
            sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при тестировании: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()