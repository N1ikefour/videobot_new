#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для просмотра данных в базе PostgreSQL
"""

import psycopg2
from config import DATABASE_CONFIG
from datetime import datetime

def view_database():
    """Показывает содержимое всех таблиц"""
    
    try:
        # Подключаемся к базе данных
        conn = psycopg2.connect(
            host=DATABASE_CONFIG['host'],
            port=DATABASE_CONFIG['port'],
            database=DATABASE_CONFIG['database'],
            user=DATABASE_CONFIG['user'],
            password=DATABASE_CONFIG['password']
        )
        
        cursor = conn.cursor()
        
        print("🗄️ СОДЕРЖИМОЕ БАЗЫ ДАННЫХ VIDEOBOT")
        print("=" * 60)
        
        # 1. Таблица users
        print("\n👥 ПОЛЬЗОВАТЕЛИ:")
        print("-" * 40)
        cursor.execute("""
            SELECT user_id, username, first_name, is_banned, 
                   created_at, last_activity, total_videos_processed,
                   subscription_type, subscription_expires_at
            FROM users 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        
        users = cursor.fetchall()
        if users:
            print(f"{'ID':<12} {'Username':<15} {'Имя':<15} {'Бан':<5} {'Создан':<12} {'Видео':<6} {'Подписка':<10}")
            print("-" * 80)
            for user in users:
                user_id, username, first_name, is_banned, created_at, last_activity, videos, sub_type, sub_exp = user
                ban_status = "ДА" if is_banned else "НЕТ"
                sub_info = f"{sub_type}" if sub_exp and sub_exp > datetime.now() else "истекла"
                created_str = created_at.strftime("%d.%m %H:%M") if created_at else "неизвестно"
                
                print(f"{user_id:<12} {username or 'нет':<15} {first_name or 'нет':<15} {ban_status:<5} {created_str:<12} {videos or 0:<6} {sub_info:<10}")
        else:
            print("Пользователей пока нет")
        
        # 2. Таблица admins
        print("\n👑 АДМИНИСТРАТОРЫ:")
        print("-" * 40)
        cursor.execute("SELECT user_id, permissions, created_at FROM admins")
        admins = cursor.fetchall()
        
        if admins:
            print(f"{'ID':<12} {'Права':<15} {'Создан':<20}")
            print("-" * 50)
            for admin in admins:
                user_id, permissions, created_at = admin
                created_str = created_at.strftime("%d.%m.%Y %H:%M") if created_at else "неизвестно"
                print(f"{user_id:<12} {permissions:<15} {created_str:<20}")
        else:
            print("Администраторов пока нет")
        
        # 3. Последняя активность
        print("\n📊 ПОСЛЕДНЯЯ АКТИВНОСТЬ:")
        print("-" * 40)
        cursor.execute("""
            SELECT u.username, u.first_name, ua.activity_type, ua.created_at
            FROM user_activity ua
            JOIN users u ON ua.user_id = u.user_id
            ORDER BY ua.created_at DESC
            LIMIT 15
        """)
        
        activities = cursor.fetchall()
        if activities:
            print(f"{'Пользователь':<20} {'Действие':<20} {'Время':<20}")
            print("-" * 60)
            for activity in activities:
                username, first_name, activity_type, created_at = activity
                user_display = f"{first_name or username or 'неизвестно'}"
                time_str = created_at.strftime("%d.%m %H:%M:%S") if created_at else "неизвестно"
                print(f"{user_display:<20} {activity_type:<20} {time_str:<20}")
        else:
            print("Активности пока нет")
        
        # 4. Статистика
        print("\n📈 ОБЩАЯ СТАТИСТИКА:")
        print("-" * 40)
        
        # Всего пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Активных пользователей (за последние 7 дней)
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) FROM user_activity 
            WHERE created_at >= NOW() - INTERVAL '7 days'
        """)
        active_users = cursor.fetchone()[0]
        
        # Забаненных пользователей
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_banned = true")
        banned_users = cursor.fetchone()[0]
        
        # Всего обработано видео
        cursor.execute("SELECT SUM(total_videos_processed) FROM users")
        total_videos = cursor.fetchone()[0] or 0
        
        # Админов
        cursor.execute("SELECT COUNT(*) FROM admins")
        total_admins = cursor.fetchone()[0]
        
        print(f"👥 Всего пользователей: {total_users}")
        print(f"🟢 Активных (7 дней): {active_users}")
        print(f"🔴 Забаненных: {banned_users}")
        print(f"🎬 Всего видео обработано: {total_videos}")
        print(f"👑 Администраторов: {total_admins}")
        
        # 5. Размер таблиц
        print("\n💾 РАЗМЕР ТАБЛИЦ:")
        print("-" * 40)
        tables = ['users', 'user_activity', 'admins', 'admin_actions', 'daily_stats']
        for table in tables:
            cursor.execute(f"""
                SELECT pg_size_pretty(pg_total_relation_size('{table}'))
            """)
            size = cursor.fetchone()[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"{table:<15} {count:>8} записей, размер: {size}")
        
        conn.close()
        
        print("\n" + "=" * 60)
        print("✅ Данные успешно загружены!")
        
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        print("\n💡 Проверьте:")
        print("1. Запущен ли PostgreSQL")
        print("2. Правильные ли настройки в .env")
        print("3. Создана ли база данных (запустите setup_postgres.py)")

if __name__ == "__main__":
    view_database()
