# 🧪 ЛОКАЛЬНОЕ ТЕСТИРОВАНИЕ

## 📋 Пошаговая инструкция для фронтенд разработчика

### **Шаг 1: Установите PostgreSQL**

#### Windows:

1. Скачайте с https://www.postgresql.org/download/windows/
2. Установите с настройками по умолчанию
3. **ВАЖНО:** Запомните пароль для пользователя `postgres`
4. После установки PostgreSQL должен запуститься автоматически

#### macOS:

```bash
# Через Homebrew
brew install postgresql
brew services start postgresql
```

#### Linux (Ubuntu/Debian):

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### **Шаг 2: Создайте файл .env**

Создайте файл `.env` в корне проекта:

```env
# Telegram Bot Token (получите у @BotFather)
BOT_TOKEN=your_bot_token_here

# PostgreSQL Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=videobot_db
DB_USER=videobot_user
DB_PASSWORD=videobot123
DB_ADMIN_USER=postgres
DB_ADMIN_PASSWORD=your_postgres_password_here

# Admin Panel Configuration
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
ADMIN_SECRET_KEY=your-super-secret-key-here
```

**⚠️ ВАЖНО:** Замените `your_postgres_password_here` на пароль, который вы указали при установке PostgreSQL!

### **Шаг 3: Установите зависимости**

```bash
pip install -r requirements.txt
```

### **Шаг 4: Настройте базу данных**

```bash
python setup_postgres.py
```

Если всё прошло успешно, вы увидите:

```
Настройка PostgreSQL завершена успешно!
Информация для подключения:
   Host: localhost
   Port: 5432
   Database: videobot_db
   User: videobot_user
```

### **Шаг 5: Протестируйте настройку**

```bash
python test_local.py
```

Этот скрипт проверит:

- ✅ Переменные окружения
- ✅ Подключение к PostgreSQL
- ✅ Работу DatabaseManager

### **Шаг 6: Запустите бота**

```bash
python bot.py
```

Вы должны увидеть:

```
INFO - PostgreSQL база данных успешно инициализирована
INFO - Бот запущен
```

### **Шаг 7: Протестируйте бота**

1. Найдите вашего бота в Telegram
2. Отправьте команду `/start`
3. Попробуйте отправить видео

### **Шаг 8: Запустите админ-панель**

В новом терминале:

```bash
python admin_panel.py
```

Откройте в браузере: `http://localhost:5000`

Логин: `admin`
Пароль: `admin123`

---

## 🚨 УСТРАНЕНИЕ ПРОБЛЕМ

### **Ошибка: "connection refused"**

```
psycopg2.OperationalError: connection to server at "localhost" (::1), port 5432 failed: Connection refused
```

**Решение:**

1. Убедитесь что PostgreSQL установлен
2. Запустите PostgreSQL сервис:
   - Windows: через Services или pgAdmin
   - macOS: `brew services start postgresql`
   - Linux: `sudo systemctl start postgresql`

### **Ошибка: "password authentication failed"**

```
psycopg2.OperationalError: FATAL: password authentication failed
```

**Решение:**

1. Проверьте пароль в `.env` файле
2. Убедитесь что пароль правильный (тот что указали при установке PostgreSQL)

### **Ошибка: "database does not exist"**

```
psycopg2.OperationalError: FATAL: database "videobot_db" does not exist
```

**Решение:**

1. Запустите `python setup_postgres.py` еще раз
2. Убедитесь что скрипт выполнился без ошибок

### **Ошибка: "module not found"**

```
ModuleNotFoundError: No module named 'psycopg2'
```

**Решение:**

```bash
pip install psycopg2-binary
```

---

## 🎯 ЧТО ТЕСТИРОВАТЬ

### **1. Основной функционал бота:**

- ✅ Команда `/start`
- ✅ Отправка видео
- ✅ Выбор количества копий (1, 3, 6)
- ✅ Обработка видео
- ✅ Получение результата

### **2. База данных:**

- ✅ Регистрация пользователей
- ✅ Логирование активности
- ✅ Статистика

### **3. Админ-панель:**

- ✅ Вход в админку
- ✅ Просмотр пользователей
- ✅ Статистика
- ✅ Бан/разбан пользователей

### **4. Админ-команды в Telegram:**

- ✅ `/admin_stats` - статистика
- ✅ `/admin_users` - список пользователей
- ✅ `/admin_ban @username` - бан пользователя
- ✅ `/admin_unban @username` - разбан пользователя

---

## 📊 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ

### **При успешном тестировании:**

1. **Бот отвечает на команды**
2. **Видео обрабатывается корректно**
3. **Пользователи сохраняются в БД**
4. **Админ-панель открывается**
5. **Статистика отображается**

### **В базе данных создаются таблицы:**

- `users` - пользователи
- `user_activity` - активность
- `admin_actions` - действия админов
- `daily_stats` - статистика

---

## 🚀 ГОТОВО К ПРОДАКШЕНУ!

После успешного локального тестирования вы можете:

1. **Загрузить код на сервер TimeWeb**
2. **Установить PostgreSQL на сервере**
3. **Настроить переменные окружения**
4. **Запустить бота**

**Удачного тестирования!** 🎉
