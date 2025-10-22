import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)

def get_utc_now() -> str:
    """Получает текущее время в UTC"""
    return datetime.utcnow().isoformat()

def utc_to_msk(utc_datetime_str: str) -> str:
    """Конвертирует UTC время в московское время (UTC+3)"""
    try:
        if not utc_datetime_str or utc_datetime_str == 'N/A':
            return 'N/A'
        
        # Парсим UTC время
        utc_dt = datetime.fromisoformat(utc_datetime_str.replace('Z', ''))
        
        # Добавляем 3 часа для московского времени
        msk_dt = utc_dt + timedelta(hours=3)
        
        # Форматируем для отображения
        return msk_dt.strftime('%d.%m.%Y %H:%M МСК')
    except Exception as e:
        logger.error(f"Ошибка при конвертации времени {utc_datetime_str}: {e}")
        return utc_datetime_str

class DatabaseManager:
    """Менеджер базы данных SQLite для статистики пользователей"""
    
    def __init__(self, db_file: str = "user_stats.db"):
        self.db_file = db_file
        self.init_database()
    
    def init_database(self):
        """Инициализирует базу данных и создает таблицы"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Создаем таблицу пользователей
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        first_seen TEXT NOT NULL,
                        last_seen TEXT NOT NULL,
                        total_videos_processed INTEGER DEFAULT 0,
                        total_output_videos INTEGER DEFAULT 0,
                        processing_sessions INTEGER DEFAULT 0,
                        unique_days_active INTEGER DEFAULT 0
                    )
                ''')
                
                # Создаем таблицу дней активности
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_activity_days (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        activity_date TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users (user_id),
                        UNIQUE(user_id, activity_date)
                    )
                ''')
                
                # Создаем таблицу истории обработки видео
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS video_processing_history (
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
                
                # Создаем индексы для быстрого поиска
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_users_last_seen 
                    ON users (last_seen)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_activity_date 
                    ON user_activity_days (activity_date)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_processing_timestamp 
                    ON video_processing_history (timestamp)
                ''')
                
                conn.commit()
                logger.info("База данных инициализирована успешно")
                
        except Exception as e:
            logger.error(f"Ошибка при инициализации базы данных: {e}")
            raise
    
    def register_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """Регистрирует нового пользователя или обновляет существующего"""
        try:
            current_time = get_utc_now()
            today = datetime.now().date().isoformat()
            
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Проверяем, существует ли пользователь
                cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
                existing_user = cursor.fetchone()
                
                if existing_user:
                    # Обновляем существующего пользователя
                    cursor.execute('''
                        UPDATE users 
                        SET username = COALESCE(?, username),
                            first_name = COALESCE(?, first_name),
                            last_name = COALESCE(?, last_name),
                            last_seen = ?
                        WHERE user_id = ?
                    ''', (username, first_name, last_name, current_time, user_id))
                else:
                    # Создаем нового пользователя
                    cursor.execute('''
                        INSERT INTO users (user_id, username, first_name, last_name, first_seen, last_seen)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (user_id, username, first_name, last_name, current_time, current_time))
                
                # Добавляем текущий день в активные дни
                cursor.execute('''
                    INSERT OR IGNORE INTO user_activity_days (user_id, activity_date)
                    VALUES (?, ?)
                ''', (user_id, today))
                
                # Обновляем количество уникальных дней активности
                cursor.execute('''
                    UPDATE users 
                    SET unique_days_active = (
                        SELECT COUNT(DISTINCT activity_date) 
                        FROM user_activity_days 
                        WHERE user_id = ?
                    )
                    WHERE user_id = ?
                ''', (user_id, user_id))
                
                conn.commit()
                logger.info(f"Пользователь {user_id} зарегистрирован/обновлен")
                
        except Exception as e:
            logger.error(f"Ошибка при регистрации пользователя {user_id}: {e}")
            raise
    
    def record_video_processing(self, user_id: int, input_video_info: Dict, output_count: int, processing_params: Dict):
        """Записывает информацию об обработке видео"""
        try:
            current_time = get_utc_now()
            today = datetime.now().date().isoformat()
            
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Обновляем статистику пользователя
                cursor.execute('''
                    UPDATE users 
                    SET total_videos_processed = total_videos_processed + 1,
                        total_output_videos = total_output_videos + ?,
                        processing_sessions = processing_sessions + 1,
                        last_seen = ?
                    WHERE user_id = ?
                ''', (output_count, current_time, user_id))
                
                # Добавляем текущий день в активные дни
                cursor.execute('''
                    INSERT OR IGNORE INTO user_activity_days (user_id, activity_date)
                    VALUES (?, ?)
                ''', (user_id, today))
                
                # Обновляем количество уникальных дней активности
                cursor.execute('''
                    UPDATE users 
                    SET unique_days_active = (
                        SELECT COUNT(DISTINCT activity_date) 
                        FROM user_activity_days 
                        WHERE user_id = ?
                    )
                    WHERE user_id = ?
                ''', (user_id, user_id))
                
                # Записываем в историю обработки
                cursor.execute('''
                    INSERT INTO video_processing_history 
                    (user_id, timestamp, input_file_id, input_file_size, output_count, processing_params)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    user_id, 
                    current_time, 
                    input_video_info.get('file_id'),
                    input_video_info.get('file_size'),
                    output_count,
                    json.dumps(processing_params)
                ))
                
                conn.commit()
                logger.info(f"Статистика обработки записана для пользователя {user_id}")
                
        except Exception as e:
            logger.error(f"Ошибка при записи статистики обработки: {e}")
            raise
    
    def get_user_stats(self, user_id: int) -> Optional[Dict]:
        """Получает статистику конкретного пользователя"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT user_id, username, first_name, last_name, first_seen, last_seen,
                           total_videos_processed, total_output_videos, processing_sessions, unique_days_active
                    FROM users 
                    WHERE user_id = ?
                ''', (user_id,))
                
                user_data = cursor.fetchone()
                if not user_data:
                    return None
                
                # Получаем последние 5 записей обработки
                cursor.execute('''
                    SELECT timestamp, output_count, processing_params
                    FROM video_processing_history 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT 5
                ''', (user_id,))
                
                processing_history = []
                for record in cursor.fetchall():
                    processing_history.append({
                        'timestamp': record[0],
                        'output_count': record[1],
                        'processing_params': json.loads(record[2]) if record[2] else {}
                    })
                
                # Вычисляем среднее количество выходных видео за сессию
                avg_output = 0
                if user_data[8] > 0:  # processing_sessions > 0
                    avg_output = round(user_data[7] / user_data[8], 2)  # total_output_videos / processing_sessions
                
                return {
                    'user_id': user_data[0],
                    'username': user_data[1] or 'N/A',
                    'first_name': user_data[2] or 'N/A',
                    'last_name': user_data[3] or 'N/A',
                    'first_seen': user_data[4],
                    'last_seen': user_data[5],
                    'first_seen_msk': utc_to_msk(user_data[4]),
                    'last_seen_msk': utc_to_msk(user_data[5]),
                    'total_videos_processed': user_data[6],
                    'total_output_videos': user_data[7],
                    'processing_sessions': user_data[8],
                    'unique_days_active': user_data[9],
                    'avg_output_per_session': avg_output,
                    'video_history': processing_history
                }
                
        except Exception as e:
            logger.error(f"Ошибка при получении статистики пользователя {user_id}: {e}")
            return None
    
    def get_all_users_stats(self) -> Dict:
        """Получает общую статистику всех пользователей"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Общая статистика
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_users,
                        SUM(total_videos_processed) as total_videos_processed,
                        SUM(total_output_videos) as total_output_videos,
                        SUM(processing_sessions) as total_processing_sessions
                    FROM users
                ''')
                
                totals = cursor.fetchone()
                
                # Топ пользователей по количеству обработанных видео
                cursor.execute('''
                    SELECT user_id, username, first_name, last_name, last_seen,
                           total_videos_processed, total_output_videos, unique_days_active,
                           CASE 
                               WHEN processing_sessions > 0 
                               THEN ROUND(CAST(total_output_videos AS REAL) / processing_sessions, 2)
                               ELSE 0 
                           END as avg_output_per_session
                    FROM users 
                    ORDER BY total_videos_processed DESC 
                    LIMIT 10
                ''')
                
                top_users = []
                for row in cursor.fetchall():
                    top_users.append({
                        'user_id': row[0],
                        'username': row[1] or 'N/A',
                        'first_name': row[2] or 'N/A',
                        'last_name': row[3] or 'N/A',
                        'last_seen': row[4],
                        'last_seen_msk': utc_to_msk(row[4]),
                        'total_videos_processed': row[5],
                        'total_output_videos': row[6],
                        'unique_days_active': row[7],
                        'avg_output_per_session': row[8]
                    })
                
                return {
                    'total_users': totals[0] or 0,
                    'total_videos_processed': totals[1] or 0,
                    'total_output_videos': totals[2] or 0,
                    'total_processing_sessions': totals[3] or 0,
                    'users': top_users
                }
                
        except Exception as e:
            logger.error(f"Ошибка при получении общей статистики: {e}")
            return {
                'total_users': 0,
                'total_videos_processed': 0,
                'total_output_videos': 0,
                'total_processing_sessions': 0,
                'users': []
            }
    
    def get_recent_activity(self, days: int = 7) -> Dict:
        """Получает активность за последние N дней"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).date().isoformat()
            
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Пользователи, активные за последние N дней
                cursor.execute('''
                    SELECT COUNT(DISTINCT u.user_id) as active_users,
                           SUM(u.total_videos_processed) as videos_processed,
                           SUM(u.total_output_videos) as output_videos
                    FROM users u
                    WHERE u.last_seen >= ?
                ''', (cutoff_date,))
                
                recent_stats = cursor.fetchone()
                
                return {
                    'days': days,
                    'active_users': recent_stats[0] or 0,
                    'videos_processed': recent_stats[1] or 0,
                    'output_videos': recent_stats[2] or 0
                }
                
        except Exception as e:
            logger.error(f"Ошибка при получении статистики активности: {e}")
            return {
                'days': days,
                'active_users': 0,
                'videos_processed': 0,
                'output_videos': 0
            }
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Очищает старые данные (оставляет только последние N дней)"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).date().isoformat()
            cutoff_timestamp = (datetime.now() - timedelta(days=days_to_keep)).isoformat()
            
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Удаляем старые дни активности
                cursor.execute('''
                    DELETE FROM user_activity_days 
                    WHERE activity_date < ?
                ''', (cutoff_date,))
                
                # Удаляем старую историю обработки
                cursor.execute('''
                    DELETE FROM video_processing_history 
                    WHERE timestamp < ?
                ''', (cutoff_timestamp,))
                
                # Обновляем количество уникальных дней активности
                cursor.execute('''
                    UPDATE users 
                    SET unique_days_active = (
                        SELECT COUNT(DISTINCT activity_date) 
                        FROM user_activity_days 
                        WHERE user_activity_days.user_id = users.user_id
                    )
                ''')
                
                conn.commit()
                logger.info(f"Очищены данные старше {days_to_keep} дней")
                
        except Exception as e:
            logger.error(f"Ошибка при очистке старых данных: {e}")
    
    def get_database_stats(self) -> Dict:
        """Получает статистику самой базы данных"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Размер базы данных
                cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                db_size = cursor.fetchone()[0]
                
                # Количество записей в каждой таблице
                cursor.execute("SELECT COUNT(*) FROM users")
                users_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM user_activity_days")
                activity_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM video_processing_history")
                history_count = cursor.fetchone()[0]
                
                return {
                    'database_size_bytes': db_size,
                    'database_size_mb': round(db_size / (1024 * 1024), 2),
                    'users_count': users_count,
                    'activity_records': activity_count,
                    'history_records': history_count
                }
                
        except Exception as e:
            logger.error(f"Ошибка при получении статистики базы данных: {e}")
            return {}
