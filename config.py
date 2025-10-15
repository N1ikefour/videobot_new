import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')

# Настройки для обработки видео
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB
SUPPORTED_FORMATS = ['.mp4', '.avi', '.mov', '.mkv']
OUTPUT_DIR = 'processed_videos'
TEMP_DIR = 'temp'

# Настройки базы данных PostgreSQL
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'videobot_db'),
    'user': os.getenv('DB_USER', 'videobot_user'),
    'password': os.getenv('DB_PASSWORD', 'videobot_password')
}

# Формируем строку подключения
DATABASE_URL = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"

# Создаем необходимые директории
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)