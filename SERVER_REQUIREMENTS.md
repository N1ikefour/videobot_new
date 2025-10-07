# 🖥️ Требования к серверу для 200 пользователей (50-100 одновременно)

**Дата:** 2025-10-07  
**Конфигурация:** 20 одновременных обработок видео

---

## 📊 Анализ нагрузки

### Параметры проекта:

- **Общее количество пользователей:** 200 человек
- **Пиковая нагрузка:** 50-100 одновременных пользователей
- **Семафор бота:** 20 одновременных обработок (установлено в `bot.py`)
- **Время обработки:** 2-3 минуты на видео (с параллельной обработкой копий)

### Расчет ресурсов:

**На одну обработку видео:**

- CPU: ~2 ядра (кодирование видео)
- RAM: ~1 ГБ
- Disk I/O: активное чтение/запись

**Для 20 одновременных обработок:**

- CPU: 20 × 2 = **40 vCPU**
- RAM: 20 × 1 ГБ = **20 ГБ** + 8 ГБ для системы = **28-32 ГБ**
- SSD: **200-300 ГБ** (временные файлы, кеш)

---

## 🎯 Рекомендуемые конфигурации сервера

### ⭐ Вариант 1: Оптимальный (Рекомендуется)

**Характеристики:**

```
CPU: 32 vCPU (AMD EPYC или Intel Xeon)
RAM: 64 ГБ
SSD: 500 ГБ NVMe
Сеть: 1 Гбит/с
ОС: Ubuntu 22.04 LTS
```

**Почему эта конфигурация:**

- 32 vCPU позволят обрабатывать 15-20 видео одновременно комфортно
- 64 ГБ RAM дает запас на пики нагрузки
- 500 ГБ SSD хватит для временных файлов множества пользователей

**Провайдеры и цены:**

#### Hetzner (Германия) - Выгоднее всего

```
Dedicated Server AX102
- AMD Ryzen 9 7950X (16 cores / 32 threads)
- 128 GB DDR5 RAM
- 2× 1.92 TB NVMe SSD
- 1 Гбит/с
Цена: €119/мес (~₽13,000/мес)
```

#### Selectel (Россия)

```
Выделенный сервер
- 32 vCPU
- 64 GB RAM
- 500 GB SSD
Цена: ~₽18,000-22,000/мес
```

#### Hetzner Cloud (если не нужен dedicated)

```
CCX53
- 32 vCPU
- 64 GB RAM
- 360 GB NVMe
Цена: €169/мес (~₽19,000/мес)
```

---

### 💎 Вариант 2: Премиум (Максимальная производительность)

**Характеристики:**

```
CPU: 48-64 vCPU
RAM: 128 ГБ
SSD: 1 ТБ NVMe
Сеть: 1-10 Гбит/с
```

**Когда использовать:**

- Планируете рост до 500+ пользователей
- Нужна максимальная скорость обработки
- Хотите запас для апгрейдов

**Провайдеры:**

#### Hetzner Dedicated

```
AX162-R
- AMD Ryzen 9 7950X3D (16 cores / 32 threads)
- 128 GB DDR5 RAM
- 2× 3.84 TB NVMe SSD
Цена: €149/мес (~₽16,500/мес)
```

#### AWS EC2 (Гибкий, но дороже)

```
c6i.8xlarge
- 32 vCPU
- 64 GB RAM
- До 10 Гбит/с
Цена: ~$1,200/мес (~₽110,000/мес)
```

---

### 💰 Вариант 3: Бюджетный (Минимальная конфигурация)

**Характеристики:**

```
CPU: 16 vCPU
RAM: 32 ГБ
SSD: 200 ГБ
```

**Ограничения:**

- Семафор нужно уменьшить до 10 (`asyncio.Semaphore(10)`)
- Обрабатывает до 10 видео одновременно
- Может быть очередь при пиках нагрузки

**Провайдеры:**

#### Hetzner Cloud

```
CCX33
- 16 vCPU
- 32 GB RAM
- 240 GB NVMe
Цена: €91/мес (~₽10,000/мес)
```

#### Selectel

```
Облачный сервер
- 16 vCPU
- 32 GB RAM
- 200 GB SSD
Цена: ~₽9,000-12,000/мес
```

---

## 📈 Сравнение вариантов

| Параметр                | Бюджетный      | Оптимальный ⭐  | Премиум       |
| ----------------------- | -------------- | --------------- | ------------- |
| vCPU                    | 16             | 32              | 48-64         |
| RAM                     | 32 ГБ          | 64 ГБ           | 128 ГБ        |
| SSD                     | 200 ГБ         | 500 ГБ          | 1 ТБ          |
| Одновременных обработок | 10             | 20              | 30+           |
| Цена/мес (Hetzner)      | €91 (~₽10k)    | €119 (~₽13k)    | €149 (~₽16k)  |
| Подходит для            | До 30 активных | 50-100 активных | 100+ активных |

---

## 🎯 Итоговая рекомендация

### Для ваших требований (200 пользователей, 50-100 активных):

**🏆 Рекомендуем: Hetzner AX102**

```
Сервер: Hetzner Dedicated AX102
CPU: AMD Ryzen 9 7950X (16 cores / 32 threads = 32 vCPU)
RAM: 128 GB DDR5
SSD: 2× 1.92 TB NVMe
Цена: €119/мес (~₽13,000/мес)
```

**Преимущества:**

- ✅ Отличная цена/производительность
- ✅ Мощный процессор для кодирования видео
- ✅ Огромный запас RAM (128 ГБ вместо 64 ГБ)
- ✅ Много места для временных файлов
- ✅ Dedicated сервер = стабильная производительность
- ✅ Быстрое NVMe хранилище

**Альтернатива (если нужна гибкость):**

- Hetzner CCX53 (облако) - €169/мес
- Можно масштабировать вверх/вниз при необходимости

---

## 🔧 Настройка под вашу нагрузку

### 1. В bot.py уже установлено

```python
# bot.py, строка 31
self.processing_semaphore = asyncio.Semaphore(20)
```

✅ Это позволит обрабатывать 20 видео одновременно

### 2. Мониторинг нагрузки

После запуска следите за метриками:

```bash
# Проверка нагрузки CPU
htop

# Использование RAM
free -h

# Активные Python процессы
ps aux | grep python | wc -l

# Должно быть примерно: базовый процесс + (количество активных обработок × 1-2)
```

### 3. Регулировка семафора по результатам

**Если сервер справляется и CPU < 70%:**

```python
self.processing_semaphore = asyncio.Semaphore(25)  # Увеличиваем
```

**Если сервер перегружен (CPU > 90%):**

```python
self.processing_semaphore = asyncio.Semaphore(15)  # Уменьшаем
```

---

## 📊 Пропускная способность

### С конфигурацией 20 одновременных обработок:

**Обработка видео:**

- 1 видео: 2-3 минуты
- 20 видео параллельно: 2-3 минуты
- За час: **20 × 20 = 400-600 видео**

**Пользователи:**

- За день (12 активных часов): **4,800-7,200 видео**
- При 3 видео на пользователя: **1,600-2,400 пользователей/день**

✅ **Вывод:** Конфигурация с запасом покрывает ваши 200 пользователей

---

## ⚡ Дополнительные оптимизации

### 1. Использование SSD кеша

```bash
# Монтируем tmpfs для временных файлов (использует RAM)
sudo mkdir /mnt/ramdisk
sudo mount -t tmpfs -o size=20G tmpfs /mnt/ramdisk

# В config.py изменить:
TEMP_DIR = '/mnt/ramdisk/temp'
```

**Эффект:** Ускорение работы с временными файлами в 10-50 раз

### 2. Настройка ffmpeg для многопоточности

В `video_processor.py` можно добавить:

```python
# При вызове write_videofile добавить:
threads=4  # Количество потоков для ffmpeg
```

### 3. Мониторинг в реальном времени

Установите Grafana + Prometheus для визуализации метрик:

- CPU/RAM usage
- Количество активных обработок
- Время обработки видео
- Длина очереди

---

## 🚀 Пошаговый план развертывания

### 1. Аренда сервера

- [ ] Зарегистрироваться на Hetzner.com
- [ ] Заказать Dedicated Server AX102
- [ ] Дождаться активации (1-24 часа)

### 2. Первоначальная настройка

```bash
# Подключаемся
ssh root@YOUR_SERVER_IP

# Обновляем систему
apt update && apt upgrade -y

# Устанавливаем базовые пакеты
apt install -y htop vim git curl wget
```

### 3. Установка зависимостей

```bash
# Python 3.11
add-apt-repository -y ppa:deadsnakes/ppa
apt update
apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# FFmpeg (критично!)
apt install -y ffmpeg

# Системные библиотеки
apt install -y libsm6 libxext6 libxrender-dev libgomp1 libglib2.0-0 libgl1-mesa-glx
```

### 4. Загрузка и настройка проекта

```bash
# Клонируем проект
cd /opt
git clone YOUR_REPOSITORY_URL videobot
cd videobot

# Создаем виртуальное окружение
python3.11 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
pip install --upgrade pip
pip install -r requirements.txt

# Создаем .env файл
nano .env
# Вставляем: BOT_TOKEN=your_token_here
```

### 5. Настройка systemd service

```bash
# Создаем service файл
nano /etc/systemd/system/videobot.service
```

Содержимое (адаптировано под мощный сервер):

```ini
[Unit]
Description=Telegram Video Bot (200 users, 50-100 concurrent)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/videobot
Environment="PATH=/opt/videobot/venv/bin"
ExecStart=/opt/videobot/venv/bin/python bot.py
Restart=always
RestartSec=10

# Логирование
StandardOutput=append:/opt/videobot/bot.log
StandardError=append:/opt/videobot/bot_error.log

# Ограничения ресурсов для 20 одновременных обработок
MemoryMax=56G
CPUQuota=3000%

[Install]
WantedBy=multi-user.target
```

```bash
# Активируем
systemctl daemon-reload
systemctl enable videobot
systemctl start videobot

# Проверяем
systemctl status videobot
```

### 6. Мониторинг

```bash
# Смотрим логи в реальном времени
tail -f /opt/videobot/bot.log

# Проверяем нагрузку
htop

# Статистика за последний час
journalctl -u videobot --since "1 hour ago"
```

---

## 🔒 Безопасность

### Настройка firewall

```bash
# Базовые правила
ufw allow OpenSSH
ufw enable

# Только если нужен веб-интерфейс мониторинга
ufw allow 3000  # Grafana
ufw allow 9090  # Prometheus
```

### Автоматические обновления безопасности

```bash
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

---

## 💾 Резервное копирование

### Ежедневный бэкап

```bash
# Создаем скрипт
nano /opt/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Бэкап только кода (без временных файлов)
tar -czf $BACKUP_DIR/videobot_$DATE.tar.gz \
    --exclude='temp/*' \
    --exclude='output/*' \
    --exclude='venv/*' \
    --exclude='__pycache__' \
    /opt/videobot

# Удаляем старые бэкапы (>14 дней)
find $BACKUP_DIR -type f -mtime +14 -delete

echo "Backup completed: videobot_$DATE.tar.gz"
```

```bash
# Делаем исполняемым
chmod +x /opt/backup.sh

# Добавляем в cron (каждый день в 4:00)
crontab -e
# Добавить: 0 4 * * * /opt/backup.sh
```

---

## 📞 Контакты и поддержка

### Hetzner Support

- Email: support@hetzner.com
- Telefon: +49 (0) 9831 505-0
- Docs: https://docs.hetzner.com/

### Мониторинг статуса

Создайте простой status endpoint:

```python
# В bot.py добавьте
import psutil

async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для проверки статуса сервера"""
    cpu_percent = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    status_msg = (
        f"📊 Статус сервера:\n\n"
        f"CPU: {cpu_percent}%\n"
        f"RAM: {ram.percent}% ({ram.used / 1024**3:.1f}/{ram.total / 1024**3:.1f} ГБ)\n"
        f"Disk: {disk.percent}% ({disk.used / 1024**3:.1f}/{disk.total / 1024**3:.1f} ГБ)\n"
        f"Активных обработок: {5 - self.processing_semaphore._value}/20"
    )

    await update.message.reply_text(status_msg)
```

---

## ✅ Финальный чек-лист

- [ ] Сервер арендован (Hetzner AX102 или аналог)
- [ ] Ubuntu 22.04 установлена
- [ ] Python 3.11 и FFmpeg установлены
- [ ] Проект загружен и настроен
- [ ] Семафор установлен на 20 (`bot.py` строка 31)
- [ ] Systemd service настроен и работает
- [ ] Логирование настроено
- [ ] Мониторинг настроен (htop, логи)
- [ ] Резервное копирование настроено
- [ ] Firewall настроен
- [ ] Тестовая обработка 5-10 видео одновременно прошла успешно
- [ ] Бот готов для 200 пользователей! 🚀

---

**Итоговая стоимость:** €119/мес (~₽13,000/мес)  
**Производительность:** До 600 видео в час  
**Готовность:** ✅ Готово к запуску в продакшн
