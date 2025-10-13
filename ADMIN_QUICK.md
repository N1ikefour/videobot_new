# ⚡ Админ-панель - Быстрая шпаргалка

## 🚀 Установка (первый раз)

```bash
# 1. Подключитесь
ssh root@109.196.98.222

# 2. Перейдите в папку бота
cd /home/videobot/videobot_new

# 3. Загрузите файлы (с вашего компьютера через PowerShell):
scp admin_panel.py root@109.196.98.222:/home/videobot/videobot_new/
scp database.py root@109.196.98.222:/home/videobot/videobot_new/
scp -r templates root@109.196.98.222:/home/videobot/videobot_new/
scp -r static root@109.196.98.222:/home/videobot/videobot_new/

# 4. Установите Flask
source venv/bin/activate
pip install flask
deactivate

# 5. Настройте .env
nano .env
# Добавьте:
# ADMIN_SECRET_KEY=ваш_секретный_ключ
# ADMIN_USERNAME=admin
# ADMIN_PASSWORD=ваш_пароль

# 6. Запустите
pm2 start admin_panel.py --name admin-panel --interpreter /home/videobot/videobot_new/venv/bin/python
pm2 save

# 7. Откройте в браузере
# http://109.196.98.222:5000
```

---

## 📊 Основные команды

```bash
# Статус
pm2 list

# Логи
pm2 logs admin-panel

# Перезапуск
pm2 restart admin-panel

# Остановить
pm2 stop admin-panel

# Запустить
pm2 start admin-panel
```

---

## 🔄 Обновление

```bash
# Загрузите новые файлы (PowerShell)
scp admin_panel.py root@109.196.98.222:/home/videobot/videobot_new/

# На сервере перезапустите
pm2 restart admin-panel
```

---

## 🌐 Доступ

**URL:** http://109.196.98.222:5000  
**Логин:** admin (из .env)  
**Пароль:** (из .env)

---

## 🐛 Если не работает

```bash
# 1. Проверьте логи
pm2 logs admin-panel --lines 50

# 2. Проверьте Flask
source venv/bin/activate && pip list | grep Flask

# 3. Установите Flask если нет
pip install flask
pm2 restart admin-panel

# 4. Откройте порт
sudo ufw allow 5000

# 5. Проверьте .env
cat .env | grep ADMIN
```

---

**Подробнее:** см. ADMIN_PANEL_SETUP.md
