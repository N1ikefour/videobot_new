#!/usr/bin/env python3
"""
Модуль для работы с PostgreSQL базой данных пользователей и админ функций
"""

import psycopg2
import psycopg2.extras
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json
from config import DATABASE_CONFIG, DATABASE_URL

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Менеджер PostgreSQL базы данных для пользователей и админ функций"""
    
    def __init__(self):
        self.db_config = DATABASE_CONFIG
        self.connection_string = DATABASE_URL
        self.init_database()
    
    def get_connection(self):
        """Получить подключение к базе данных"""
        return psycopg2.connect(
            host=self.db_config['host'],
            port=self.db_config['port'],
            database=self.db_config['database'],
            user=self.db_config['user'],
            password=self.db_config['password']
        )
    
    def init_database(self):
        """Инициализация базы данных и создание таблиц"""
        try:
            with self.get_connection() as conn:
                conn.autocommit = True
                cursor = conn.cursor()
                
                # Таблица пользователей
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username VARCHAR(255),
                        first_name VARCHAR(255),
                        last_name VARCHAR(255),
                        is_banned BOOLEAN DEFAULT FALSE,
                        ban_reason TEXT,
                        banned_at TIMESTAMP,
                        banned_by BIGINT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        total_videos_processed INTEGER DEFAULT 0,
                        subscription_type VARCHAR(50) DEFAULT 'free',
                        subscription_expires_at TIMESTAMP,
                        subscription_created_at TIMESTAMP
                    )
                ''')
                
                # Таблица активности пользователей
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_activity (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        activity_type VARCHAR(100),
                        activity_data JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                ''')
                
                # Таблица админских действий
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS admin_actions (
                        id SERIAL PRIMARY KEY,
                        admin_id BIGINT,
                        action_type VARCHAR(100),
                        target_user_id BIGINT,
                        action_data JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (admin_id) REFERENCES users (user_id),
                        FOREIGN KEY (target_user_id) REFERENCES users (user_id)
                    )
                ''')
                
                # Таблица админов
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS admins (
                        user_id BIGINT PRIMARY KEY,
                        permissions VARCHAR(50) DEFAULT 'basic',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by BIGINT,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                ''')
                
                # Таблица статистики
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS daily_stats (
                        date DATE PRIMARY KEY,
                        total_users INTEGER DEFAULT 0,
                        active_users INTEGER DEFAULT 0,
                        new_users INTEGER DEFAULT 0,
                        videos_processed INTEGER DEFAULT 0,
                        banned_users INTEGER DEFAULT 0
                    )
                ''')
                
                # Создаем индексы для производительности
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_last_activity ON users(last_activity)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_is_banned ON users(is_banned)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_activity_created_at ON user_activity(created_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_activity_user_id ON user_activity(user_id)')
                
                # Создаем первого админа если его нет
                self.create_first_admin()
                
                logger.info("PostgreSQL база данных успешно инициализирована")
                
        except Exception as e:
            logger.error(f"Ошибка инициализации PostgreSQL базы данных: {e}")
            raise
    
    def create_first_admin(self):
        """Создает первого админа если его нет"""
        try:
            # ID первого админа (замените на ваш Telegram ID)
            FIRST_ADMIN_ID = 454002721  # Замените на ваш ID!
            
            with self.get_connection() as conn:
                conn.autocommit = True
                cursor = conn.cursor()
                
                # Проверяем, есть ли уже админы
                cursor.execute('SELECT COUNT(*) FROM admins')
                admin_count = cursor.fetchone()[0]
                
                if admin_count == 0:
                    # Создаем первого админа
                    cursor.execute('''
                        INSERT INTO admins (user_id, permissions, created_by)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id) DO NOTHING
                    ''', (FIRST_ADMIN_ID, 'super_admin', FIRST_ADMIN_ID))
                    
                    logger.info(f"Создан первый админ с ID: {FIRST_ADMIN_ID}")
                    
        except Exception as e:
            logger.error(f"Ошибка создания первого админа: {e}")
    
    def add_or_update_user(self, user_id: int, username: str = None, 
                          first_name: str = None, last_name: str = None) -> bool:
        """Добавить или обновить пользователя"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Используем UPSERT для PostgreSQL
                cursor.execute('''
                    INSERT INTO users (user_id, username, first_name, last_name, last_activity)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        last_activity = CURRENT_TIMESTAMP
                ''', (user_id, username, first_name, last_name))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Ошибка добавления/обновления пользователя {user_id}: {e}")
            return False
    
    def log_user_activity(self, user_id: int, activity_type: str, activity_data: Dict = None):
        """Логирование активности пользователя"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Обновляем последнюю активность пользователя
                cursor.execute('''
                    UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = %s
                ''', (user_id,))
                
                # Добавляем запись об активности
                cursor.execute('''
                    INSERT INTO user_activity (user_id, activity_type, activity_data)
                    VALUES (%s, %s, %s)
                ''', (user_id, activity_type, json.dumps(activity_data) if activity_data else None))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Ошибка логирования активности пользователя {user_id}: {e}")
    
    def increment_user_videos(self, user_id: int):
        """Увеличить счетчик обработанных видео пользователя"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users 
                    SET total_videos_processed = total_videos_processed + 1,
                        last_activity = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                ''', (user_id,))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Ошибка обновления счетчика видео для пользователя {user_id}: {e}")
    
    def ban_user(self, user_id: int, admin_id: int, reason: str = None) -> bool:
        """Забанить пользователя"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Баним пользователя
                cursor.execute('''
                    UPDATE users 
                    SET is_banned = TRUE, ban_reason = %s, banned_at = CURRENT_TIMESTAMP, banned_by = %s
                    WHERE user_id = %s
                ''', (reason, admin_id, user_id))
                
                # Логируем админское действие
                cursor.execute('''
                    INSERT INTO admin_actions (admin_id, action_type, target_user_id, action_data)
                    VALUES (%s, %s, %s, %s)
                ''', (admin_id, 'ban', user_id, json.dumps({'reason': reason})))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Ошибка бана пользователя {user_id}: {e}")
            return False
    
    def log_admin_action(self, admin_id: int, action_type: str, action_data: Dict = None) -> bool:
        """Логирование админских действий"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO admin_actions (admin_id, action_type, action_data)
                    VALUES (%s, %s, %s)
                ''', (admin_id, action_type, json.dumps(action_data) if action_data else None))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка логирования админского действия: {e}")
            return False

    def unban_user(self, user_id: int, admin_id: int) -> bool:
        """Разбанить пользователя"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Разбаниваем пользователя
                cursor.execute('''
                    UPDATE users 
                    SET is_banned = FALSE, ban_reason = NULL, banned_at = NULL, banned_by = NULL
                    WHERE user_id = %s
                ''', (user_id,))
                
                # Логируем админское действие
                cursor.execute('''
                    INSERT INTO admin_actions (admin_id, action_type, target_user_id, action_data)
                    VALUES (%s, %s, %s, NULL)
                ''', (admin_id, 'unban', user_id))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Ошибка разбана пользователя {user_id}: {e}")
            return False
    
    def is_user_banned(self, user_id: int) -> bool:
        """Проверить, забанен ли пользователь"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT is_banned FROM users WHERE user_id = %s', (user_id,))
                result = cursor.fetchone()
                return result[0] if result else False
                
        except Exception as e:
            logger.error(f"Ошибка проверки бана пользователя {user_id}: {e}")
            return False
    
    def add_admin(self, user_id: int, admin_id: int, permissions: str = 'basic') -> bool:
        """Добавить администратора"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO admins (user_id, permissions, created_by)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        permissions = EXCLUDED.permissions,
                        created_by = EXCLUDED.created_by
                ''', (user_id, permissions, admin_id))
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Ошибка добавления админа {user_id}: {e}")
            return False
    
    def is_admin(self, user_id: int) -> bool:
        """Проверить, является ли пользователь администратором"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT user_id FROM admins WHERE user_id = %s', (user_id,))
                return cursor.fetchone() is not None
                
        except Exception as e:
            logger.error(f"Ошибка проверки админских прав {user_id}: {e}")
            return False
    
    def get_user_stats(self, user_id: int) -> Optional[Dict]:
        """Получить статистику пользователя"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute('''
                    SELECT user_id, username, first_name, last_name, is_banned, ban_reason,
                           created_at, last_activity, total_videos_processed, subscription_type
                    FROM users WHERE user_id = %s
                ''', (user_id,))
                
                result = cursor.fetchone()
                return dict(result) if result else None
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики пользователя {user_id}: {e}")
            return None
    
    def get_active_users(self, hours: int = 24) -> List[Dict]:
        """Получить список активных пользователей за последние N часов"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                cursor.execute('''
                    SELECT user_id, username, first_name, last_name, last_activity, 
                           total_videos_processed, is_banned, subscription_type
                    FROM users 
                    WHERE last_activity >= NOW() - INTERVAL '%s hours'
                    ORDER BY last_activity DESC
                ''', (hours,))
                
                results = cursor.fetchall()
                return [dict(row) for row in results]
                
        except Exception as e:
            logger.error(f"Ошибка получения активных пользователей: {e}")
            return []
    
    def get_all_users(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Получить список всех пользователей с пагинацией"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute('''
                    SELECT user_id, username, first_name, last_name, created_at,
                           last_activity, total_videos_processed, is_banned, subscription_type
                    FROM users 
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                ''', (limit, offset))
                
                results = cursor.fetchall()
                return [dict(row) for row in results]
                
        except Exception as e:
            logger.error(f"Ошибка получения списка пользователей: {e}")
            return []
    
    def get_user_details(self, user_id):
        """Get detailed user information"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute("""
                    SELECT u.*, 
                           COUNT(ua.id) as activity_count,
                           a.user_id IS NOT NULL as is_admin
                    FROM users u
                    LEFT JOIN user_activity ua ON u.user_id = ua.user_id
                    LEFT JOIN admins a ON u.user_id = a.user_id
                    WHERE u.user_id = %s
                    GROUP BY u.user_id, a.user_id
                """, (user_id,))
                
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting user details: {e}")
            return None

    def get_users_filtered(self, search='', status='', activity='', page=1, per_page=20):
        """Get filtered users with pagination"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # Build WHERE clause
                where_conditions = []
                params = []
                
                if search:
                    where_conditions.append("(u.user_id::text LIKE %s OR u.first_name LIKE %s OR u.username LIKE %s)")
                    search_param = f"%{search}%"
                    params.extend([search_param, search_param, search_param])
                
                if status == 'active':
                    where_conditions.append("u.is_banned = FALSE")
                elif status == 'banned':
                    where_conditions.append("u.is_banned = TRUE")
                elif status == 'admin':
                    where_conditions.append("a.user_id IS NOT NULL")
                
                if activity:
                    if activity == '24h':
                        where_conditions.append("u.last_activity >= NOW() - INTERVAL '1 day'")
                    elif activity == '7d':
                        where_conditions.append("u.last_activity >= NOW() - INTERVAL '7 days'")
                    elif activity == '30d':
                        where_conditions.append("u.last_activity >= NOW() - INTERVAL '30 days'")
                
                where_clause = ""
                if where_conditions:
                    where_clause = "WHERE " + " AND ".join(where_conditions)
                
                # Count total users
                count_query = f"""
                    SELECT COUNT(DISTINCT u.user_id)
                    FROM users u
                    LEFT JOIN admins a ON u.user_id = a.user_id
                    {where_clause}
                """
                cursor.execute(count_query, params)
                total_users = cursor.fetchone()['count']
                
                # Get users with pagination
                offset = (page - 1) * per_page
                query = f"""
                    SELECT u.*, 
                           a.user_id IS NOT NULL as is_admin
                    FROM users u
                    LEFT JOIN admins a ON u.user_id = a.user_id
                    {where_clause}
                    ORDER BY u.last_activity DESC, u.created_at DESC
                    LIMIT %s OFFSET %s
                """
                params.extend([per_page, offset])
                cursor.execute(query, params)
                
                users = [dict(row) for row in cursor.fetchall()]
                
                return {
                    'users': users,
                    'pagination': {
                        'current_page': page,
                        'per_page': per_page,
                        'total': total_users,
                        'total_pages': (total_users + per_page - 1) // per_page
                    }
                }
        except Exception as e:
            logger.error(f"Error getting filtered users: {e}")
            return {'users': [], 'pagination': {'current_page': 1, 'per_page': per_page, 'total': 0, 'total_pages': 0}}

    def get_general_stats(self) -> Dict:
        """Получить общую статистику бота"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Общее количество пользователей
                cursor.execute('SELECT COUNT(*) FROM users')
                total_users = cursor.fetchone()[0]
                
                # Активные пользователи за разные периоды
                cursor.execute('SELECT COUNT(*) FROM users WHERE last_activity >= NOW() - INTERVAL \'24 hours\'')
                active_24h = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM users WHERE last_activity >= NOW() - INTERVAL \'7 days\'')
                active_7d = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM users WHERE last_activity >= NOW() - INTERVAL \'30 days\'')
                active_30d = cursor.fetchone()[0]
                
                # Общее количество обработанных видео
                cursor.execute('SELECT SUM(total_videos_processed) FROM users')
                result = cursor.fetchone()[0]
                total_videos = result if result else 0
                
                # Видео за сегодня
                cursor.execute('''
                    SELECT COUNT(*) FROM user_activity 
                    WHERE activity_type = 'video_upload' AND created_at >= CURRENT_DATE
                ''')
                videos_today = cursor.fetchone()[0]
                
                # Видео за неделю
                cursor.execute('''
                    SELECT COUNT(*) FROM user_activity 
                    WHERE activity_type = 'video_upload' AND created_at >= NOW() - INTERVAL '7 days'
                ''')
                videos_week = cursor.fetchone()[0]
                
                # Заблокированные пользователи
                cursor.execute('SELECT COUNT(*) FROM users WHERE is_banned = TRUE')
                banned_users = cursor.fetchone()[0]
                
                return {
                    'total_users': total_users,
                    'active_24h': active_24h,
                    'active_7d': active_7d,
                    'active_30d': active_30d,
                    'total_videos': total_videos,
                    'videos_today': videos_today,
                    'videos_week': videos_week,
                    'banned_users': banned_users
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения общей статистики: {e}")
            return {
                'total_users': 0,
                'active_24h': 0,
                'active_7d': 0,
                'active_30d': 0,
                'total_videos': 0,
                'videos_today': 0,
                'videos_week': 0,
                'banned_users': 0
            }

# Глобальный экземпляр менеджера базы данных
db_manager = DatabaseManager()
