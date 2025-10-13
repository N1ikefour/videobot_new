# 🌐 Установка админ-панели на сервер Timeweb - Полная инструкция

## 📋 Обзор системы

**Что это:** Веб-админ панель для управления Telegram ботом  
**Технологии:** Flask + SQLite + Bootstrap + Chart.js  
**Сервер:** 109.196.98.222 (тот же где бот)  
**Порт:** 5000 (или любой другой)

---

## 🎯 Что умеет админ-панель

✅ Статистика в реальном времени  
✅ Список всех пользователей с пагинацией  
✅ Бан/разбан пользователей  
✅ Назначение админов  
✅ Фильтрация и поиск  
✅ Экспорт в CSV  
✅ Графики и аналитика  
✅ История действий

---

## 🔐 Подключение к серверу

```bash
ssh root@109.196.98.222
```

---

## 📂 Структура файлов на сервере

```
/home/videobot/videobot_new/
├── bot.py                 # Telegram бот
├── admin_panel.py         # Веб админ-панель ← НОВОЕ
├── database.py            # Менеджер БД ← ОБНОВЛЕНО
├── config.py
├── .env                   # Переменные окружения ← ДОБАВИМ НАСТРОЙКИ
├── bot_database.db        # SQLite база ← СОЗДАСТСЯ АВТОМАТИЧЕСКИ
├── templates/             # HTML шаблоны ← НОВОЕ
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   └── users.html
└── static/                # CSS/JS файлы ← НОВОЕ
    ├── css/
    │   └── admin.css
    └── js/
```

---

## 📤 Шаг 1: Загрузка файлов на сервер

### Вариант 1: Через SCP (с вашего компьютера)

Откройте **PowerShell на вашем компьютере** и выполните:

```powershell
# Перейдите в папку проекта
cd D:\Проекты\finally_videobot\finnaly_videoBot

# Загрузите админ-панель
scp admin_panel.py root@109.196.98.222:/home/videobot/videobot_new/

# Загрузите обновленный database.py
scp database.py root@109.196.98.222:/home/videobot/videobot_new/

# Загрузите templates
scp -r templates root@109.196.98.222:/home/videobot/videobot_new/

# Загрузите static
scp -r static root@109.196.98.222:/home/videobot/videobot_new/
```

### Вариант 2: Через Git (если код в репозитории)

```bash
# На сервере
cd /home/videobot/videobot_new
git pull
```

---

## 🔧 Шаг 2: Установка зависимостей

```bash
# Переходим в директорию бота
cd /home/videobot/videobot_new

# Активируем виртуальное окружение
source venv/bin/activate

# Устанавливаем Flask и другие зависимости для админ-панели
pip install flask
pip install chart.js  # Для графиков (опционально)

# Проверяем что установлено
pip list | grep -i flask

# Должно показать: Flask 3.x.x
```

---

## ⚙️ Шаг 3: Настройка переменных окружения

```bash
# Редактируем .env файл
nano /home/videobot/videobot_new/.env
```

**Добавьте в конец файла:**

```bash
# === НАСТРОЙКИ АДМИН-ПАНЕЛИ ===

# Секретный ключ для сессий (ОБЯЗАТЕЛЬНО СМЕНИТЕ!)
ADMIN_SECRET_KEY=izmenyat_etot_klyuch_na_unikalniy_123456789

# Логин администратора
ADMIN_USERNAME=admin

# Пароль администратора (ОБЯЗАТЕЛЬНО СМЕНИТЕ!)
ADMIN_PASSWORD=secure_password_2025
```

**Сохраните:** `Ctrl+X` → `Y` → `Enter`

---

## 🚀 Шаг 4: Первый запуск (тестирование)

```bash
# Переходим в директорию
cd /home/videobot/videobot_new

# Активируем venv если не активировали
source venv/bin/activate

# Запускаем админ-панель для теста
python3 admin_panel.py
```

**Должно показать:**

```
* Running on http://0.0.0.0:5000
* Debug mode: on
```

Если работает - **отлично!** Нажмите `Ctrl+C` для остановки.

---

## 🔄 Шаг 5: Запуск через PM2 (постоянная работа)

```bash
# Останавливаем тестовый запуск (если не остановили)
# Ctrl+C

# Запускаем админ-панель через PM2
pm2 start admin_panel.py \
  --name admin-panel \
  --interpreter /home/videobot/videobot_new/venv/bin/python

# Сохраняем конфигурацию PM2
pm2 save

# Проверяем статус
pm2 list
```

**Должно показать:**

```
┌────┬───────────────┬─────────────┬─────────┬──────────┬────────┬──────┬───────────┬──────────┐
│ id │ name          │ namespace   │ version │ mode     │ pid    │ status│ cpu      │ mem      │
├────┼───────────────┼─────────────┼─────────┼──────────┼────────┼───────┼──────────┼──────────┤
│ 0  │ videobot      │ default     │ N/A     │ fork     │ 1745   │ online│ 0%       │ 50mb     │
│ 1  │ admin-panel   │ default     │ N/A     │ fork     │ 2156   │ online│ 0%       │ 35mb     │ ← НОВЫЙ!
└────┴───────────────┴─────────────┴─────────┴──────────┴────────┴───────┴──────────┴──────────┘
```

---

## 🌐 Шаг 6: Доступ к админ-панели

### Вариант 1: Прямой доступ по IP и порту

Админ-панель доступна по адресу:

```
http://109.196.98.222:5000
```

**Проверка:**

```bash
# На сервере проверяем что порт открыт
curl http://localhost:5000

# Должно вернуть HTML код страницы входа
```

### Вариант 2: Через Nginx (красивый URL)

Если хотите доступ через домен или без указания порта:

```bash
# Установите Nginx если нет
sudo apt update
sudo apt install nginx -y

# Создайте конфигурацию
sudo nano /etc/nginx/sites-available/admin-panel
```

**Содержимое файла:**

```nginx
server {
    listen 80;
    server_name 109.196.98.222;  # Или ваш домен

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Активируем:**

```bash
# Создаём символическую ссылку
sudo ln -s /etc/nginx/sites-available/admin-panel /etc/nginx/sites-enabled/

# Проверяем конфигурацию
sudo nginx -t

# Перезапускаем Nginx
sudo systemctl restart nginx

# Теперь админ-панель доступна на: http://109.196.98.222
```

---

## 🔒 Шаг 7: Открытие порта (если нужно)

Если админ-панель не открывается извне:

```bash
# Проверяем firewall
sudo ufw status

# Открываем порт 5000
sudo ufw allow 5000

# Или если используете Nginx
sudo ufw allow 80
sudo ufw allow 443  # Для HTTPS
```

---

## 🔑 Шаг 8: Первый вход

1. **Откройте браузер**
2. **Перейдите:** `http://109.196.98.222:5000` (или `http://109.196.98.222` если через Nginx)
3. **Введите данные:**
   - **Логин:** `admin` (или что указали в .env)
   - **Пароль:** `secure_password_2025` (или что указали в .env)
4. **Нажмите "Войти"**

**Должны попасть на дашборд со статистикой!** 🎉

---

## 📊 Возможности админ-панели

### 1. Главная панель (Dashboard)

- 📈 Статистика в реальном времени
- 👥 Общее количество пользователей
- ⚡ Активные за 24ч, 7д, 30д
- 🎬 Количество обработанных видео
- 🚫 Заблокированные пользователи
- 📉 Графики активности

### 2. Управление пользователями (/users)

- 🔍 Поиск по ID/имени/username
- 🎯 Фильтрация (активные/заблокированные/админы)
- 🚫 Бан пользователя с указанием причины
- ✅ Разбан пользователя
- 👑 Назначение админских прав
- 📥 Экспорт списка в CSV
- 📄 Пагинация

### 3. API эндпоинты

- `GET /api/stats` - общая статистика
- `GET /api/users` - список пользователей
- `GET /api/active_users?hours=24` - активные пользователи
- `POST /api/ban_user` - забанить
- `POST /api/unban_user` - разбанить
- `POST /api/make_admin` - сделать админом
- `GET /api/export_users` - экспорт в CSV

---

## 🎮 Управление админ-панелью через PM2

```bash
# Посмотреть статус
pm2 list

# Посмотреть логи админ-панели
pm2 logs admin-panel

# Посмотреть последние 50 строк
pm2 logs admin-panel --lines 50

# Перезапустить админ-панель
pm2 restart admin-panel

# Остановить админ-панель
pm2 stop admin-panel

# Запустить админ-панель
pm2 start admin-panel

# Удалить из PM2
pm2 delete admin-panel

# Мониторинг ресурсов
pm2 monit
```

---

## 🔄 Обновление админ-панели

### Способ 1: Через SCP

```powershell
# На локальном компьютере (PowerShell)
cd D:\Проекты\finally_videobot\finnaly_videoBot

scp admin_panel.py root@109.196.98.222:/home/videobot/videobot_new/
scp database.py root@109.196.98.222:/home/videobot/videobot_new/
scp -r templates root@109.196.98.222:/home/videobot/videobot_new/
scp -r static root@109.196.98.222:/home/videobot/videobot_new/

# На сервере
pm2 restart admin-panel
pm2 logs admin-panel --lines 20
```

### Способ 2: Через Git

```bash
# На сервере
cd /home/videobot/videobot_new
git pull
pm2 restart admin-panel
pm2 logs admin-panel
```

---

## 🛠️ Редактирование на сервере

```bash
# Редактировать админ-панель
nano /home/videobot/videobot_new/admin_panel.py

# Редактировать базу данных
nano /home/videobot/videobot_new/database.py

# Редактировать .env (настройки)
nano /home/videobot/videobot_new/.env

# После редактирования ОБЯЗАТЕЛЬНО перезапустите
pm2 restart admin-panel
```

---

## 🐛 Диагностика проблем

### Проблема 1: Админ-панель не запускается

```bash
# Проверьте логи
pm2 logs admin-panel --lines 100

# Проверьте что Flask установлен
source /home/videobot/videobot_new/venv/bin/activate
pip list | grep Flask

# Если нет - установите
pip install flask
pm2 restart admin-panel
```

### Проблема 2: Не открывается в браузере

```bash
# Проверьте что процесс запущен
pm2 list

# Проверьте что порт слушается
sudo netstat -tlnp | grep :5000

# Проверьте локально
curl http://localhost:5000

# Проверьте firewall
sudo ufw status
sudo ufw allow 5000
```

### Проблема 3: Ошибка авторизации

```bash
# Проверьте .env файл
cat /home/videobot/videobot_new/.env | grep ADMIN

# Должно быть:
# ADMIN_SECRET_KEY=...
# ADMIN_USERNAME=...
# ADMIN_PASSWORD=...

# Если нет - добавьте и перезапустите
nano /home/videobot/videobot_new/.env
pm2 restart admin-panel
```

### Проблема 4: База данных не создаётся

```bash
# Проверьте файл базы
ls -la /home/videobot/videobot_new/bot_database.db

# Если нет - создайте вручную запустив Python
cd /home/videobot/videobot_new
source venv/bin/activate
python3 -c "from database import db_manager; print('DB initialized')"

# Проверьте права
chmod 664 /home/videobot/videobot_new/bot_database.db
```

### Проблема 5: "ModuleNotFoundError: No module named 'flask'"

```bash
# Активируйте venv и установите Flask
cd /home/videobot/videobot_new
source venv/bin/activate
pip install flask
deactivate

# Перезапустите с правильным интерпретатором
pm2 delete admin-panel
pm2 start admin_panel.py --name admin-panel --interpreter /home/videobot/videobot_new/venv/bin/python
pm2 save
```

---

## 🔍 Полная диагностика одной командой

```bash
echo "=== АДМИН-ПАНЕЛЬ ДИАГНОСТИКА ===" && \
pm2 list && \
echo "" && \
echo "=== ЛОГИ АДМИН-ПАНЕЛИ ===" && \
pm2 logs admin-panel --lines 20 --nostream && \
echo "" && \
echo "=== ПОРТЫ ===" && \
sudo netstat -tlnp | grep :5000 && \
echo "" && \
echo "=== БАЗА ДАННЫХ ===" && \
ls -lh /home/videobot/videobot_new/bot_database.db && \
echo "" && \
echo "=== FLASK ===" && \
source /home/videobot/videobot_new/venv/bin/activate && pip list | grep Flask && deactivate
```

---

## 🔐 Безопасность

### 1. Смените пароли!

```bash
nano /home/videobot/videobot_new/.env

# Измените:
ADMIN_SECRET_KEY=ваш_уникальный_секретный_ключ_минимум_32_символа
ADMIN_PASSWORD=очень_сложный_пароль_2025!@#

# Перезапустите
pm2 restart admin-panel
```

### 2. Настройте HTTPS (для продакшена)

```bash
# Установите Certbot
sudo apt install certbot python3-certbot-nginx

# Получите SSL сертификат (нужен домен!)
sudo certbot --nginx -d your-domain.com

# Certbot автоматически настроит Nginx для HTTPS
```

### 3. Ограничьте доступ по IP

```bash
# В конфигурации Nginx
sudo nano /etc/nginx/sites-available/admin-panel

# Добавьте:
location / {
    # Разрешить только ваш IP
    allow 123.45.67.89;  # Ваш IP
    deny all;

    proxy_pass http://127.0.0.1:5000;
    ...
}

sudo systemctl reload nginx
```

---

## 📱 Интеграция с Telegram ботом

Чтобы бот записывал данные в базу, нужно обновить `bot.py`:

### 1. Импортируйте database в bot.py

```bash
nano /home/videobot/videobot_new/bot.py
```

**Добавьте в начало файла:**

```python
from database import db_manager
```

### 2. Добавьте логирование пользователей

**В функции `start()` добавьте:**

```python
async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Добавляем/обновляем пользователя в БД
    db_manager.add_or_update_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    # Логируем активность
    db_manager.log_user_activity(user.id, 'start_command')

    # ... остальной код
```

### 3. Добавьте проверку бана

**Создайте middleware для проверки:**

```python
async def check_ban_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if db_manager.is_user_banned(user_id):
        await update.message.reply_text(
            "❌ Вы заблокированы и не можете использовать бота."
        )
        return False

    return True
```

### 4. Логируйте обработку видео

**В функции обработки видео добавьте:**

```python
# После успешной обработки
db_manager.increment_user_videos(user_id)
db_manager.log_user_activity(user_id, 'video_processed', {
    'copies': copies,
    'add_frames': add_frames
})
```

### 5. Перезапустите бота

```bash
pm2 restart videobot
pm2 logs videobot
```

---

## ⚡ Быстрые команды (шпаргалка)

| Действие                | Команда                               |
| ----------------------- | ------------------------------------- |
| Подключиться            | `ssh root@109.196.98.222`             |
| Перейти в папку         | `cd /home/videobot/videobot_new`      |
| Статус админ-панели     | `pm2 list`                            |
| Логи админ-панели       | `pm2 logs admin-panel`                |
| Перезапуск              | `pm2 restart admin-panel`             |
| Остановить              | `pm2 stop admin-panel`                |
| Запустить               | `pm2 start admin-panel`               |
| Редактировать настройки | `nano .env`                           |
| Проверить порт          | `sudo netstat -tlnp \| grep :5000`    |
| Открыть порт            | `sudo ufw allow 5000`                 |
| Проверить БД            | `ls -lh bot_database.db`              |
| Обновить из git         | `git pull && pm2 restart admin-panel` |

---

## 📞 Полезные ссылки

- **Админ-панель:** http://109.196.98.222:5000
- **API статистика:** http://109.196.98.222:5000/api/stats
- **API пользователи:** http://109.196.98.222:5000/api/users
- **Панель Timeweb:** https://timeweb.cloud/my/servers

---

## ✅ Финальный чеклист

- [ ] Файлы загружены на сервер
- [ ] Flask установлен: `pip list | grep Flask`
- [ ] .env настроен (SECRET_KEY, USERNAME, PASSWORD)
- [ ] Админ-панель запущена: `pm2 list`
- [ ] Порт 5000 открыт: `sudo ufw allow 5000`
- [ ] Админ-панель открывается в браузере
- [ ] Авторизация работает
- [ ] Статистика отображается
- [ ] Пользователи загружаются
- [ ] Бан/разбан работает
- [ ] PM2 сохранён: `pm2 save`
- [ ] Автозапуск настроен: `pm2 startup`

---

**🎉 АДМИН-ПАНЕЛЬ УСТАНОВЛЕНА И РАБОТАЕТ!**

Теперь у вас есть полноценная система управления ботом! 🚀

---

**Автор:** Nikita  
**Версия:** 1.0  
**Дата:** 2025-10-13
