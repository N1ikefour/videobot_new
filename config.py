import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')

# ID администраторов (через запятую в .env файле)
ADMIN_IDS_STR = os.getenv('ADMIN_IDS', '')
ADMIN_IDS = set()
if ADMIN_IDS_STR:
    try:
        # Парсим ID из строки, разделенной запятыми
        admin_ids_list = [int(id_str.strip()) for id_str in ADMIN_IDS_STR.split(',') if id_str.strip()]
        ADMIN_IDS = set(admin_ids_list)
    except ValueError:
        print("Ошибка: Неверный формат ADMIN_IDS в .env файле. Используйте числа через запятую.")
        ADMIN_IDS = set()

# Настройки для обработки видео
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB
SUPPORTED_VIDEO_FORMATS = ['.mp4', '.avi', '.mov', '.mkv']

# Настройки для обработки изображений
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB
SUPPORTED_IMAGE_FORMATS = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
OUTPUT_DIR = 'processed_videos'
OUTPUT_IMAGES_DIR = 'processed_images'
TEMP_DIR = 'temp'

# Создаем необходимые директории
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_IMAGES_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)