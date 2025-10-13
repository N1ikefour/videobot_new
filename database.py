#!/usr/bin/env python3
"""
Модуль для работы с базой данных пользователей и админ функций
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Менеджер базы данных для пользователей и админ функций"""
    
    def __init__(self, db_path: str = "bot_database.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных и создание таблиц"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Таблица пользователей
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        is_banned BOOLEAN DEFAULT FALSE,
                        ban_reason TEXT,
                        banned_at TIMESTAMP,
                        banned_by INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        total_videos_processed INTEGER DEFAULT 0,
                        subscription_type TEXT DEFAULT 'free',
                        subscription_expires_at TIMESTAMP,
                        subscription_created_at TIMESTAMP
                    )
                ''')
                
                # Таблица активности пользователей
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_activity (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        activity_type TEXT,
                        activity_data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                ''')
                
                # Таблица админских действий
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS admin_actions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        admin_id INTEGER,
                        action_type TEXT,
                        target_user_id INTEGER,
                        action_data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (admin_id) REFERENCES users (user_id),
                        FOREIGN KEY (target_user_id) REFERENCES users (user_id)
                    )
                ''')
                
                # Таблица админов
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS admins (
                        user_id INTEGER PRIMARY KEY,
                        permissions TEXT DEFAULT 'basic',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by INTEGER,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                ''')
                
                # Таблица статистики
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS daily_stats (
                        date TEXT PRIMARY KEY,
                        total_users INTEGER DEFAULT 0,
                        active_users INTEGER DEFAULT 0,
                        new_users INTEGER DEFAULT 0,
                        videos_processed INTEGER DEFAULT 0,
                        banned_users INTEGER DEFAULT 0
                    )
                ''')
                
                conn.commit()
                logger.info("База данных успешно инициализирована")
                
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise
    
    def add_or_update_user(self, user_id: int, username: str = None, 
                          first_name: str = None, last_name: str = None) -> bool:
        """Добавить или обновить пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Проверяем, существует ли пользователь
                cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
                exists = cursor.fetchone()
                
                if exists:
                    # Обновляем существующего пользователя
                    cursor.execute('''
                        UPDATE users 
                        SET username = ?, first_name = ?, last_name = ?, last_activity = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    ''', (username, first_name, last_name, user_id))
                else:
                    # Добавляем нового пользователя
                    cursor.execute('''
                        INSERT INTO users (user_id, username, first_name, last_name)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, username, first_name, last_name))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Ошибка добавления/обновления пользователя {user_id}: {e}")
            return False
    
    def log_user_activity(self, user_id: int, activity_type: str, activity_data: Dict = None):
        """Логирование активности пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Обновляем последнюю активность пользователя
                cursor.execute('''
                    UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?
                ''', (user_id,))
                
                # Добавляем запись об активности
                cursor.execute('''
                    INSERT INTO user_activity (user_id, activity_type, activity_data)
                    VALUES (?, ?, ?)
                ''', (user_id, activity_type, json.dumps(activity_data) if activity_data else None))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Ошибка логирования активности пользователя {user_id}: {e}")
    
    def increment_user_videos(self, user_id: int):
        """Увеличить счетчик обработанных видео пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users 
                    SET total_videos_processed = total_videos_processed + 1,
                        last_activity = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                ''', (user_id,))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Ошибка обновления счетчика видео для пользователя {user_id}: {e}")
    
    def ban_user(self, user_id: int, admin_id: int, reason: str = None) -> bool:
        """Забанить пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Баним пользователя
                cursor.execute('''
                    UPDATE users 
                    SET is_banned = TRUE, ban_reason = ?, banned_at = CURRENT_TIMESTAMP, banned_by = ?
                    WHERE user_id = ?
                ''', (reason, admin_id, user_id))
                
                # Логируем админское действие
                cursor.execute('''
                    INSERT INTO admin_actions (admin_id, action_type, target_user_id, action_data)
                    VALUES (?, 'ban', ?, ?)
                ''', (admin_id, user_id, json.dumps({'reason': reason})))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Ошибка бана пользователя {user_id}: {e}")
            return False
    
    def unban_user(self, user_id: int, admin_id: int) -> bool:
        """Разбанить пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Разбаниваем пользователя
                cursor.execute('''
                    UPDATE users 
                    SET is_banned = FALSE, ban_reason = NULL, banned_at = NULL, banned_by = NULL
                    WHERE user_id = ?
                ''', (user_id,))
                
                # Логируем админское действие
                cursor.execute('''
                    INSERT INTO admin_actions (admin_id, action_type, target_user_id, action_data)
                    VALUES (?, 'unban', ?, NULL)
                ''', (admin_id, user_id))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Ошибка разбана пользователя {user_id}: {e}")
            return False
    
    def is_user_banned(self, user_id: int) -> bool:
        """Проверить, забанен ли пользователь"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
                result = cursor.fetchone()
                return result[0] if result else False
                
        except Exception as e:
            logger.error(f"Ошибка проверки бана пользователя {user_id}: {e}")
            return False
    
    def add_admin(self, user_id: int, admin_id: int, permissions: str = 'basic') -> bool:
        """Добавить администратора"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO admins (user_id, permissions, created_by)
                    VALUES (?, ?, ?)
                ''', (user_id, permissions, admin_id))
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Ошибка добавления админа {user_id}: {e}")
            return False
    
    def is_admin(self, user_id: int) -> bool:
        """Проверить, является ли пользователь администратором"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
                return cursor.fetchone() is not None
                
        except Exception as e:
            logger.error(f"Ошибка проверки админских прав {user_id}: {e}")
            return False
    
    def get_user_stats(self, user_id: int) -> Optional[Dict]:
        """Получить статистику пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id, username, first_name, last_name, is_banned, ban_reason,
                           created_at, last_activity, total_videos_processed, subscription_type
                    FROM users WHERE user_id = ?
                ''', (user_id,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'user_id': result[0],
                        'username': result[1],
                        'first_name': result[2],
                        'last_name': result[3],
                        'is_banned': result[4],
                        'ban_reason': result[5],
                        'created_at': result[6],
                        'last_activity': result[7],
                        'total_videos_processed': result[8],
                        'subscription_type': result[9]
                    }
                return None
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики пользователя {user_id}: {e}")
            return None
    
    def get_active_users(self, hours: int = 24) -> List[Dict]:
        """Получить список активных пользователей за последние N часов"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Вычисляем время N часов назад
                time_threshold = datetime.now() - timedelta(hours=hours)
                
                cursor.execute('''
                    SELECT user_id, username, first_name, last_name, last_activity, 
                           total_videos_processed, is_banned, subscription_type
                    FROM users 
                    WHERE last_activity >= ?
                    ORDER BY last_activity DESC
                ''', (time_threshold.isoformat(),))
                
                results = cursor.fetchall()
                return [
                    {
                        'user_id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3],
                        'last_activity': row[4],
                        'total_videos_processed': row[5],
                        'is_banned': row[6],
                        'subscription_type': row[7]
                    }
                    for row in results
                ]
                
        except Exception as e:
            logger.error(f"Ошибка получения активных пользователей: {e}")
            return []
    
    def get_all_users(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Получить список всех пользователей с пагинацией"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id, username, first_name, last_name, created_at,
                           last_activity, total_videos_processed, is_banned, subscription_type
                    FROM users 
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                ''', (limit, offset))
                
                results = cursor.fetchall()
                return [
                    {
                        'user_id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3],
                        'created_at': row[4],
                        'last_activity': row[5],
                        'total_videos_processed': row[6],
                        'is_banned': row[7],
                        'subscription_type': row[8]
                    }
                    for row in results
                ]
                
        except Exception as e:
            logger.error(f"Ошибка получения списка пользователей: {e}")
            return []
    
    def get_user_details(self, user_id):
        """Get detailed user information"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT u.*, 
                           COUNT(ua.id) as activity_count,
                           a.user_id IS NOT NULL as is_admin
                    FROM users u
                    LEFT JOIN user_activity ua ON u.user_id = ua.user_id
                    LEFT JOIN admins a ON u.user_id = a.user_id
                    WHERE u.user_id = ?
                    GROUP BY u.user_id
                """, (user_id,))
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Error getting user details: {e}")
            return None

    def get_users_filtered(self, search='', status='', activity='', page=1, per_page=20):
        """Get filtered users with pagination"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Build WHERE clause
                where_conditions = []
                params = []
                
                if search:
                    where_conditions.append("(u.user_id LIKE ? OR u.first_name LIKE ? OR u.username LIKE ?)")
                    search_param = f"%{search}%"
                    params.extend([search_param, search_param, search_param])
                
                if status == 'active':
                    where_conditions.append("u.is_banned = 0")
                elif status == 'banned':
                    where_conditions.append("u.is_banned = 1")
                elif status == 'admin':
                    where_conditions.append("a.user_id IS NOT NULL")
                
                if activity:
                    if activity == '24h':
                        where_conditions.append("u.last_activity >= datetime('now', '-1 day')")
                    elif activity == '7d':
                        where_conditions.append("u.last_activity >= datetime('now', '-7 days')")
                    elif activity == '30d':
                        where_conditions.append("u.last_activity >= datetime('now', '-30 days')")
                
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
                total_users = cursor.fetchone()[0]
                
                # Get users with pagination
                offset = (page - 1) * per_page
                query = f"""
                    SELECT u.*, 
                           a.user_id IS NOT NULL as is_admin
                    FROM users u
                    LEFT JOIN admins a ON u.user_id = a.user_id
                    {where_clause}
                    ORDER BY u.last_activity DESC, u.created_at DESC
                    LIMIT ? OFFSET ?
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
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Общее количество пользователей
                cursor.execute('SELECT COUNT(*) FROM users')
                total_users = cursor.fetchone()[0]
                
                # Активные пользователи за разные периоды
                now = datetime.now()
                
                # За 24 часа
                time_24h = now - timedelta(hours=24)
                cursor.execute('SELECT COUNT(*) FROM users WHERE last_activity >= ?', (time_24h.isoformat(),))
                active_24h = cursor.fetchone()[0]
                
                # За 7 дней
                time_7d = now - timedelta(days=7)
                cursor.execute('SELECT COUNT(*) FROM users WHERE last_activity >= ?', (time_7d.isoformat(),))
                active_7d = cursor.fetchone()[0]
                
                # За 30 дней
                time_30d = now - timedelta(days=30)
                cursor.execute('SELECT COUNT(*) FROM users WHERE last_activity >= ?', (time_30d.isoformat(),))
                active_30d = cursor.fetchone()[0]
                
                # Общее количество обработанных видео
                cursor.execute('SELECT SUM(total_videos_processed) FROM users')
                result = cursor.fetchone()[0]
                total_videos = result if result else 0
                
                # Видео за сегодня
                today = now.replace(hour=0, minute=0, second=0, microsecond=0)
                cursor.execute('''
                    SELECT COUNT(*) FROM user_activity 
                    WHERE activity_type = 'video_upload' AND created_at >= ?
                ''', (today.isoformat(),))
                videos_today = cursor.fetchone()[0]
                
                # Видео за неделю
                week_ago = now - timedelta(days=7)
                cursor.execute('''
                    SELECT COUNT(*) FROM user_activity 
                    WHERE activity_type = 'video_upload' AND created_at >= ?
                ''', (week_ago.isoformat(),))
                videos_week = cursor.fetchone()[0]
                
                # Заблокированные пользователи
                cursor.execute('SELECT COUNT(*) FROM users WHERE is_banned = 1')
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