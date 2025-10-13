# 🎮 Управление ботом на Timeweb - Полная шпаргалка

## 🔐 Подключение к серверу

### Вариант 1: По IP (быстрее)

```bash
ssh root@109.196.98.222
```

### Вариант 3: Зайти под пользователем videobot

```bash
# Сначала зайдите под root, затем:
su - videobot
```

---

## 📂 Директория бота

```bash
cd /home/videobot/videobot_new
```

---

## 🚀 Управление ботом через PM2

### Основные команды

```bash
# Посмотреть статус бота
pm2 list

# Посмотреть логи (в реальном времени)
pm2 logs videobot

# Посмотреть последние 50 строк логов
pm2 logs videobot --lines 50

# Остановить логи (Ctrl+C)

# Перезапустить бота
pm2 restart videobot

# Остановить бота
pm2 stop videobot

# Запустить бота (если остановлен)
pm2 start videobot

# Удалить бота из PM2
pm2 delete videobot

# Мониторинг ресурсов (CPU, память)
pm2 monit
```

---

## ⚙️ Запуск бота (если удалили из PM2)

```bash
# Перейдите в директорию
cd /home/videobot/videobot_new

# Запустите через PM2
pm2 start bot.py --name videobot --interpreter /home/videobot/videobot_new/venv/bin/python

# Сохраните конфигурацию
pm2 save
```

---

## 🔄 Автозапуск при перезагрузке сервера

```bash
# Настроить автозапуск
pm2 startup

# Скопируйте и выполните команду которую выдаст PM2
# Например: sudo env PATH=$PATH:/usr/bin pm2 startup systemd -u videobot --hp /home/videobot

# Сохраните список процессов
pm2 save
```

---

## 📝 Просмотр логов

```bash
# Логи PM2 (в реальном времени)
pm2 logs videobot

# Последние 100 строк
pm2 logs videobot --lines 100 --nostream

# Только ошибки
pm2 logs videobot --err

# Очистить логи
pm2 flush videobot
```

---

## 🔧 Обновление кода бота

### Вариант 1: Через git (если код в репозитории)

```bash
# Перейдите в директорию
cd /home/videobot/videobot_new

# Получите изменения
git pull

# Перезапустите бота
pm2 restart videobot

# Проверьте логи
pm2 logs videobot --lines 20
```

### Вариант 2: Загрузить файл вручную

```bash
# На своём компьютере (PowerShell):
scp bot.py root@109.196.98.222:/home/videobot/videobot_new/

# На сервере:
pm2 restart videobot
```

---

## 🛠️ Редактирование файлов на сервере

```bash
# Редактировать bot.py
nano /home/videobot/videobot_new/bot.py
# Ctrl+X для выхода, Y для сохранения, Enter

# Редактировать .env (токен и настройки)
nano /home/videobot/videobot_new/.env

# Редактировать config.py
nano /home/videobot/videobot_new/config.py

# После редактирования ОБЯЗАТЕЛЬНО перезапустите:
pm2 restart videobot
```

---

## 🧹 Очистка временных файлов

```bash
# Перейдите в директорию
cd /home/videobot/videobot_new

# Очистите временные видео
rm -rf temp/*
rm -rf output/*

# Проверьте размер
du -sh temp/ output/

# Очистка логов PM2
pm2 flush videobot
```

---

## 📊 Мониторинг сервера

```bash
# Использование памяти
free -h

# Использование диска
df -h

# Нагрузка CPU и процессы (нажмите q для выхода)
htop

# Только процессы бота
ps aux | grep bot.py

# Информация о системе
uname -a

# Uptime сервера
uptime
```

---

## 🆘 Экстренные команды

### Бот завис и не отвечает

```bash
# Жесткая остановка
pm2 delete videobot
pkill -9 -f bot.py

# Очистка
cd /home/videobot/videobot_new
rm -rf temp/* output/*

# Перезапуск
pm2 start bot.py --name videobot --interpreter /home/videobot/videobot_new/venv/bin/python
pm2 save
```

### Закончилась память

```bash
# Проверка
free -h

# Очистка
rm -rf /home/videobot/videobot_new/temp/*
rm -rf /home/videobot/videobot_new/output/*

# Уменьшите семафор в bot.py (строка 33)
nano /home/videobot/videobot_new/bot.py
# Найдите: self.processing_semaphore = asyncio.Semaphore(10)
# Измените на: self.processing_semaphore = asyncio.Semaphore(2)

pm2 restart videobot
```

### Закончилось место на диске

```bash
# Проверка места
df -h

# Очистка логов системы
journalctl --vacuum-time=3d

# Очистка временных файлов
rm -rf /tmp/*
rm -rf /home/videobot/videobot_new/temp/*
rm -rf /home/videobot/videobot_new/output/*

# Найти большие файлы
du -h /home/videobot/videobot_new | sort -rh | head -20
```

---

## 🔄 Перезагрузка сервера

```bash
# Мягкая перезагрузка
sudo reboot

# После перезагрузки PM2 автоматически запустит бота (если настроен startup)
# Проверьте через 1-2 минуты:
pm2 list
```

---

## 📦 Установка/переустановка зависимостей

```bash
# Перейдите в директорию
cd /home/videobot/videobot_new

# Активируйте виртуальное окружение
source venv/bin/activate

# Обновите pip
pip install --upgrade pip

# Установите зависимости
pip install -r requirements.txt

# Проверьте что установлено
pip list

# Деактивируйте venv
deactivate

# Перезапустите бота
pm2 restart videobot
```

---

## 🐛 Диагностика проблем

### Полная диагностика одной командой

```bash
echo "=== СТАТУС БОТА ===" && pm2 list && echo "" && echo "=== ПОСЛЕДНИЕ ЛОГИ ===" && pm2 logs videobot --lines 30 --nostream && echo "" && echo "=== РЕСУРСЫ ===" && free -h && df -h / && echo "" && echo "=== PYTHON ===" && python3 --version && echo "" && echo "=== FFMPEG ===" && ffmpeg -version 2>/dev/null | head -1
```

### Проверка конкретных проблем

```bash
# Проверка .env файла (есть ли токен)
cat /home/videobot/videobot_new/.env

# Проверка зависимостей Python
source /home/videobot/videobot_new/venv/bin/activate && pip list | grep -E "telegram|moviepy|opencv" && deactivate

# Проверка ffmpeg (критично для обработки видео!)
ffmpeg -version

# Проверка временных файлов
ls -lah /home/videobot/videobot_new/temp/
ls -lah /home/videobot/videobot_new/output/
```

---

## 📱 Проверка бота в Telegram

1. Откройте бота в Telegram
2. Отправьте `/start`
3. Должно появиться приветствие

Если не работает:

```bash
# Проверьте логи
pm2 logs videobot --lines 50

# Проверьте что бот online
pm2 list

# Перезапустите
pm2 restart videobot
```

---

## ⚡ Быстрые команды (шпаргалка)

| Действие               | Команда                            |
| ---------------------- | ---------------------------------- |
| Подключиться к серверу | `ssh root@109.196.98.222`          |
| Перейти в папку бота   | `cd /home/videobot/videobot_new`   |
| Статус бота            | `pm2 list`                         |
| Логи бота              | `pm2 logs videobot`                |
| Перезапуск             | `pm2 restart videobot`             |
| Остановить             | `pm2 stop videobot`                |
| Запустить              | `pm2 start videobot`               |
| Очистить temp          | `rm -rf temp/* output/*`           |
| Редактировать код      | `nano bot.py`                      |
| Проверить память       | `free -h`                          |
| Проверить диск         | `df -h`                            |
| Обновить из git        | `git pull && pm2 restart videobot` |

---

## 📞 Поддержка Timeweb

- **Сайт:** https://timeweb.cloud/
- **Email:** support@timeweb.ru
- **Телефон:** 8 800 201-49-23
- **Панель управления:** https://timeweb.cloud/my/servers

---

## ✅ Финальный чеклист

- [✅] Бот запущен через PM2
- [✅] PM2 сохранён: `pm2 save`
- [✅] Автозапуск настроен: `pm2 startup`
- [✅] Бот отвечает в Telegram
- [✅] Логи чистые, без ошибок: `pm2 logs videobot`

---

**🎉 БОТ РАБОТАЕТ!**

Сохраните этот файл - в нём ВСЁ что нужно для управления ботом! 📚
