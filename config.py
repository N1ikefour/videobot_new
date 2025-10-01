import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')

# Настройки для обработки видео
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB
SUPPORTED_FORMATS = ['.mp4', '.avi', '.mov', '.mkv']
OUTPUT_DIR = 'processed_videos'
TEMP_DIR = 'temp'

# Создаем необходимые директории
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)