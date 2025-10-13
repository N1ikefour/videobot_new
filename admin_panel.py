from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, make_response
from functools import wraps
import asyncio
import json
from datetime import datetime, timedelta
import hashlib
import os
import sqlite3
from database import db_manager

app = Flask(__name__)
app.secret_key = os.environ.get('ADMIN_SECRET_KEY', 'your-secret-key-change-this')

# Конфигурация админ-панели
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')  # Измените в продакшене!

def login_required(f):
    """Декоратор для проверки авторизации"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def hash_password(password):
    """Хеширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == ADMIN_USERNAME and hash_password(password) == hash_password(ADMIN_PASSWORD):
            session['logged_in'] = True
            session['username'] = username
            flash('Успешный вход в систему', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Неверные учетные данные', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Выход из системы"""
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    """Главная панель администратора"""
    return render_template('dashboard.html')

@app.route('/api/stats')
@login_required
def api_stats():
    """API для получения статистики"""
    try:
        stats = db_manager.get_general_stats()
        
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/users')
@login_required
def api_users():
    """API для получения списка пользователей"""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        offset = (page - 1) * limit
        
        users = db_manager.get_all_users(limit, offset)
        
        # Get total count for pagination
        with sqlite3.connect(db_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]
        
        total_pages = (total_users + limit - 1) // limit
        
        return jsonify({
            'success': True,
            'data': {
                'users': users,
                'pagination': {
                    'current_page': page,
                    'total_pages': total_pages,
                    'total': total_users,
                    'per_page': limit
                }
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/active_users')
@login_required
def api_active_users():
    """API для получения активных пользователей"""
    try:
        hours = int(request.args.get('hours', 24))
        
        users = db_manager.get_active_users(hours)
        
        return jsonify({
            'success': True,
            'data': users,
            'hours': hours
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/ban_user', methods=['POST'])
@login_required
def api_ban_user():
    """API для блокировки пользователя"""
    try:
        data = request.get_json()
        user_id = int(data['user_id'])
        reason = data.get('reason', 'Нарушение правил')
        admin_id = 0  # ID админа из веб-панели
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(db_manager.ban_user(user_id, admin_id, reason))
        
        if success:
            # Логируем действие
            loop.run_until_complete(db_manager.log_admin_action(admin_id, 'ban_user', {
                'target_user_id': user_id,
                'reason': reason,
                'source': 'web_panel'
            }))
        
        loop.close()
        
        return jsonify({
            'success': success,
            'message': 'Пользователь заблокирован' if success else 'Ошибка при блокировке'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/unban_user', methods=['POST'])
@login_required
def api_unban_user():
    """API для разблокировки пользователя"""
    try:
        data = request.get_json()
        user_id = int(data['user_id'])
        admin_id = 0  # ID админа из веб-панели
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(db_manager.unban_user(user_id))
        
        if success:
            # Логируем действие
            loop.run_until_complete(db_manager.log_admin_action(admin_id, 'unban_user', {
                'target_user_id': user_id,
                'source': 'web_panel'
            }))
        
        loop.close()
        
        return jsonify({
            'success': success,
            'message': 'Пользователь разблокирован' if success else 'Ошибка при разблокировке'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/make_admin', methods=['POST'])
@login_required
def api_make_admin():
    try:
        user_id = request.json.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'User ID is required'})
        
        db_manager.set_admin_status(user_id, True)
        return jsonify({'success': True, 'message': 'User promoted to admin successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/user/<int:user_id>')
@login_required
def api_get_user(user_id):
    try:
        user = db_manager.get_user_details(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        return jsonify({'success': True, 'data': user})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/bulk_ban', methods=['POST'])
@login_required
def api_bulk_ban():
    try:
        user_ids = request.json.get('user_ids', [])
        if not user_ids:
            return jsonify({'success': False, 'message': 'User IDs are required'})
        
        affected = 0
        for user_id in user_ids:
            try:
                db_manager.ban_user(user_id, "Bulk ban by admin")
                affected += 1
            except:
                continue
        
        return jsonify({'success': True, 'data': {'affected': affected}})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/bulk_unban', methods=['POST'])
@login_required
def api_bulk_unban():
    try:
        user_ids = request.json.get('user_ids', [])
        if not user_ids:
            return jsonify({'success': False, 'message': 'User IDs are required'})
        
        affected = 0
        for user_id in user_ids:
            try:
                db_manager.unban_user(user_id)
                affected += 1
            except:
                continue
        
        return jsonify({'success': True, 'data': {'affected': affected}})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/bulk_make_admin', methods=['POST'])
@login_required
def api_bulk_make_admin():
    try:
        user_ids = request.json.get('user_ids', [])
        if not user_ids:
            return jsonify({'success': False, 'message': 'User IDs are required'})
        
        affected = 0
        for user_id in user_ids:
            try:
                db_manager.set_admin_status(user_id, True)
                affected += 1
            except:
                continue
        
        return jsonify({'success': True, 'data': {'affected': affected}})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/export_users')
@login_required
def api_export_users():
    try:
        import csv
        from io import StringIO
        
        # Get filters
        search = request.args.get('search', '')
        status = request.args.get('status', '')
        activity = request.args.get('activity', '')
        
        # Get all users with filters
        users = db_manager.get_users_filtered(search, status, activity, page=1, per_page=10000)
        
        # Create CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['User ID', 'First Name', 'Last Name', 'Username', 'Created At', 'Last Activity', 'Video Count', 'Is Banned', 'Is Admin'])
        
        # Write data
        for user in users['users']:
            writer.writerow([
                user['user_id'],
                user.get('first_name', ''),
                user.get('last_name', ''),
                user.get('username', ''),
                user.get('created_at', ''),
                user.get('last_activity', ''),
                user.get('video_count', 0),
                user.get('is_banned', False),
                user.get('is_admin', False)
            ])
        
        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=users_export.csv'
        
        return response
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/users')
@login_required
def users():
    """Страница управления пользователями"""
    return render_template('users.html')

@app.route('/analytics')
@login_required
def analytics():
    """Страница аналитики"""
    return render_template('analytics.html')

@app.route('/settings')
@login_required
def settings():
    """Страница настроек"""
    return render_template('settings.html')

if __name__ == '__main__':
    # Создаем необходимые директории
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    # Для продакшена на сервере используйте:
    # app.run(debug=False, host='0.0.0.0', port=5000)
    app.run(debug=True, host='0.0.0.0', port=5000)