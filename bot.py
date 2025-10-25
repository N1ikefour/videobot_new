import logging
import os
import asyncio
import time
import gc
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from config import BOT_TOKEN, ADMIN_IDS, SUPPORTED_IMAGE_FORMATS, MAX_IMAGE_SIZE
from video_processor import VideoProcessor, process_video_copy_new
from image_processor import ImageProcessor
from database import DatabaseManager

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
MAIN_MENU, WAITING_FOR_VIDEO, WAITING_FOR_IMAGE, PARAMETERS_MENU, IMAGE_PARAMETERS_MENU, CHOOSING_COPIES, CHOOSING_FRAMES, CHOOSING_RESOLUTION, CHOOSING_COMPRESSION, CHOOSING_IMAGE_COPIES, CHOOSING_IMAGE_SIZE = range(11)

class VideoBot:
    def __init__(self):
        self.video_processor = VideoProcessor()
        self.image_processor = ImageProcessor()
        self.user_data = {}
        # Добавляем словарь для отслеживания активных задач обработки
        self.active_processing_tasks = {}
        # Семафор для ограничения количества одновременных обработок видео
        # Для конфигурации: 16 vCPU, 32 GB RAM
        # Оптимальное значение: 8 одновременных обработок
        self.processing_semaphore = asyncio.Semaphore(10)
        # Менеджер базы данных для статистики пользователей
        self.db_manager = DatabaseManager()
        # ID администраторов загружаются из .env файла
        self.admin_ids = ADMIN_IDS

    def is_admin(self, user_id: int) -> bool:
        """Проверяет, является ли пользователь администратором"""
        return user_id in self.admin_ids

    async def _delayed_file_cleanup(self, file_path: str, max_attempts: int = 5):
        """Отложенное удаление файла с повторными попытками"""
        for attempt in range(max_attempts):
            try:
                await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Файл {file_path} удален с попытки {attempt + 1}")
                    return
            except PermissionError:
                logger.warning(f"Попытка {attempt + 1}: файл {file_path} все еще заблокирован")
            except Exception as e:
                logger.error(f"Ошибка при удалении файла {file_path} (попытка {attempt + 1}): {e}")
        
        logger.error(f"Не удалось удалить файл {file_path} после {max_attempts} попыток")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user_name = update.effective_user.first_name
        user_id = update.effective_user.id
        username = update.effective_user.username
        last_name = update.effective_user.last_name
        
        # Регистрируем пользователя в базе данных
        self.db_manager.register_user(
            user_id=user_id,
            username=username,
            first_name=user_name,
            last_name=last_name
        )
        
        # Очищаем данные пользователя при старте
        if user_id in self.user_data:
            del self.user_data[user_id]
        
        welcome_text = (
            f"👋 **Привет, {user_name}!**\n\n"
            "**Бот для уникализации видео и изображений** 🚀\n\n"
            "📋 **Инструкция:**\n"
            "1️⃣ Выберите тип контента (видео или изображение)\n"
            "2️⃣ Отправьте файл (видео до 50 МБ, изображение до 20 МБ)\n"
            "3️⃣ Выберите параметры обработки\n"
            "4️⃣ Получите уникальные копии!\n\n"
            "Готовы начать? 👇"
        )
        
        # Создаем главное меню с кнопками для видео и изображений
        keyboard = [
            [KeyboardButton("🎬 Уникализировать видео")],
            [KeyboardButton("🖼️ Уникализировать изображение")]
        ]
        reply_markup = ReplyKeyboardMarkup(
            keyboard, 
            resize_keyboard=True, 
            one_time_keyboard=False
        )
        
        # Проверяем, есть ли уже активный разговор
        if context.user_data.get('conversation_state'):
            # Если есть активный разговор, сбрасываем его
            context.user_data.clear()
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return MAIN_MENU

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = (
            "🆘 **Помощь по использованию бота**\n\n"
            
            "📋 **Основные команды:**\n"
            "• `/start` - Начать работу с ботом\n"
            "• `/help` - Показать эту справку\n\n"
            
            "🎬 **Как уникализировать видео:**\n"
            "1️⃣ Нажмите кнопку '🎬 Уникализировать видео'\n"
            "2️⃣ Отправьте видеофайл (до 50 МБ)\n"
            "3️⃣ Выберите параметры:\n"
            "   • Количество копий (1-3-6)\n"
            "   • Добавить цветные рамки\n"
            "   • Изменить разрешение\n"
            "   • Сжать видео\n"
            "4️⃣ Получите уникальные копии!\n\n"
            
            "🖼️ **Как уникализировать изображения:**\n"
            "1️⃣ Нажмите кнопку '🖼️ Уникализировать изображение'\n"
            "2️⃣ Отправьте изображение (до 20 МБ)\n"
            "3️⃣ Выберите параметры:\n"
            "   • Количество копий (1-6)\n"
            "   • Добавить цветной фон\n"
            "   • Применить фильтры\n"
            "   • Добавить повороты\n"
            "   • Изменить размер\n"
            "4️⃣ Получите уникальные копии!\n\n"
            
            "📋 **Требования к файлам:**\n"
            "• Видео: до 50 МБ, MP4/AVI/MKV\n"
            "• Изображения: до 20 МБ, JPG/PNG/BMP/TIFF/WEBP\n"
            "• Длительность видео: до 10 минут\n\n"
            
            "⚡ **Особенности:**\n"
            "• Параллельная обработка (быстро!)\n"
            "• Автоматическая очистка файлов\n"
            "• Поддержка множества пользователей\n\n"
            
            "❓ **Проблемы?**\n"
            "Напишите `/start` для перезапуска бота"
        )
        
        await update.message.reply_text(
            help_text,
            parse_mode='Markdown'
        )

    async def admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для получения общей статистики пользователей (только для админов)"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
            return
        
        try:
            stats = self.db_manager.get_all_users_stats()
            recent_stats = self.db_manager.get_recent_activity(7)
            
            # Формируем сообщение со статистикой
            message = (
                "📊 **ОБЩАЯ СТАТИСТИКА БОТА**\n\n"
                f"👥 **Пользователи:** {stats['total_users']}\n"
                f"📹 **Видео обработано:** {stats['total_videos_processed']}\n"
                f"🎬 **Выходных видео:** {stats['total_output_videos']}\n"
                f"🖼️ **Изображений обработано:** {stats['total_images_processed']}\n"
                f"🎨 **Выходных изображений:** {stats['total_output_images']}\n"
                f"⚙️ **Сессий обработки:** {stats['total_processing_sessions']}\n\n"
                f"📈 **За последние 7 дней:**\n"
                f"• Активных пользователей: {recent_stats['active_users']}\n"
                f"• Обработано видео: {recent_stats['videos_processed']}\n"
                f"• Создано выходных видео: {recent_stats['output_videos']}\n"
                f"• Обработано изображений: {recent_stats['images_processed']}\n"
                f"• Создано выходных изображений: {recent_stats['output_images']}\n\n"
                "🔝 **ТОП-10 ПОЛЬЗОВАТЕЛЕЙ:**\n"
            )
            
            # Добавляем топ пользователей
            for i, user in enumerate(stats['users'][:10], 1):
                username = user['username'] if user['username'] != 'N/A' else 'Без username'
                first_name = user['first_name'] if user['first_name'] != 'N/A' else 'Без имени'
                last_seen_msk = user.get('last_seen_msk', 'N/A')
                
                # Экранируем специальные символы Markdown
                def escape_markdown(text):
                    if text == 'N/A' or text is None:
                        return text
                    # Экранируем символы, которые могут нарушить Markdown
                    escape_chars = ['*', '_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
                    for char in escape_chars:
                        text = str(text).replace(char, f'\\{char}')
                    return text
                
                safe_username = escape_markdown(username)
                safe_first_name = escape_markdown(first_name)
                safe_last_seen = escape_markdown(last_seen_msk)
                
                message += (
                    f"{i}\\. {safe_first_name} \\(@{safe_username}\\)\n"
                    f"   ID: {user['user_id']}\n"
                    f"   📹 Видео: {user['total_videos_processed']} \\| "
                    f"🎬 Выходных: {user['total_output_videos']} \\| "
                    f"🖼️ Изображений: {user['total_images_processed']} \\| "
                    f"🎨 Выходных: {user['total_output_images']} \\| "
                    f"📅 Дней активен: {user['unique_days_active']}\n"
                    f"   🕐 Последнее использование: {safe_last_seen}\n\n"
                )
            
            # Разбиваем сообщение на части если оно слишком длинное
            if len(message) > 4000:
                # Отправляем основную статистику
                main_stats = (
                    "📊 **ОБЩАЯ СТАТИСТИКА БОТА**\n\n"
                    f"👥 **Пользователи:** {stats['total_users']}\n"
                    f"📹 **Видео обработано:** {stats['total_videos_processed']}\n"
                    f"🎬 **Выходных видео:** {stats['total_output_videos']}\n"
                    f"🖼️ **Изображений обработано:** {stats['total_images_processed']}\n"
                    f"🎨 **Выходных изображений:** {stats['total_output_images']}\n"
                    f"⚙️ **Сессий обработки:** {stats['total_processing_sessions']}\n\n"
                    f"📈 **За последние 7 дней:**\n"
                    f"• Активных пользователей: {recent_stats['active_users']}\n"
                    f"• Обработано видео: {recent_stats['videos_processed']}\n"
                    f"• Создано выходных видео: {recent_stats['output_videos']}\n"
                    f"• Обработано изображений: {recent_stats['images_processed']}\n"
                    f"• Создано выходных изображений: {recent_stats['output_images']}"
                )
                await update.message.reply_text(main_stats, parse_mode='Markdown')
                
                # Отправляем топ пользователей отдельным сообщением
                top_users = "🔝 **ТОП-10 ПОЛЬЗОВАТЕЛЕЙ:**\n"
                for i, user in enumerate(stats['users'][:10], 1):
                    username = user['username'] if user['username'] != 'N/A' else 'Без username'
                    first_name = user['first_name'] if user['first_name'] != 'N/A' else 'Без имени'
                    last_seen_msk = user.get('last_seen_msk', 'N/A')
                    
                    # Экранируем специальные символы Markdown
                    def escape_markdown(text):
                        if text == 'N/A' or text is None:
                            return text
                        # Экранируем символы, которые могут нарушить Markdown
                        escape_chars = ['*', '_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
                        for char in escape_chars:
                            text = str(text).replace(char, f'\\{char}')
                        return text
                    
                    safe_username = escape_markdown(username)
                    safe_first_name = escape_markdown(first_name)
                    safe_last_seen = escape_markdown(last_seen_msk)
                    
                    top_users += (
                        f"{i}\\. {safe_first_name} \\(@{safe_username}\\)\n"
                        f"   ID: {user['user_id']}\n"
                        f"   📹 Видео: {user['total_videos_processed']} \\| "
                        f"🎬 Выходных: {user['total_output_videos']} \\| "
                        f"🖼️ Изображений: {user['total_images_processed']} \\| "
                        f"🎨 Выходных: {user['total_output_images']} \\| "
                        f"📅 Дней активен: {user['unique_days_active']}\n"
                        f"   🕐 Последнее использование: {safe_last_seen}\n\n"
                    )
                await update.message.reply_text(top_users)
            else:
                await update.message.reply_text(message, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            await update.message.reply_text(f"❌ Ошибка при получении статистики: {str(e)}")

    async def user_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для получения статистики конкретного пользователя (только для админов)"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
            return
        
        # Получаем ID пользователя из аргументов команды
        if not context.args:
            await update.message.reply_text(
                "❌ Укажите ID пользователя.\n"
                "Пример: `/userstats 123456789`"
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            user_stats = self.db_manager.get_user_stats(target_user_id)
            
            if not user_stats:
                await update.message.reply_text(f"❌ Пользователь с ID {target_user_id} не найден.")
                return
            
            # Формируем сообщение со статистикой пользователя
            username = user_stats.get('username', 'N/A')
            first_name = user_stats.get('first_name', 'N/A')
            last_name = user_stats.get('last_name', 'N/A')
            
            # Используем московское время
            first_seen = user_stats.get('first_seen_msk', 'N/A')
            last_seen = user_stats.get('last_seen_msk', 'N/A')
            
            message = (
                f"👤 **СТАТИСТИКА ПОЛЬЗОВАТЕЛЯ**\n\n"
                f"🆔 **ID:** {target_user_id}\n"
                f"👤 **Имя:** {first_name} {last_name}\n"
                f"📱 **Username:** @{username}\n\n"
                f"📅 **Активность:**\n"
                f"• Первый визит: {first_seen}\n"
                f"• Последний визит: {last_seen}\n"
                f"• Дней активен: {user_stats.get('unique_days_active', 0)}\n\n"
                f"📹 **Обработка видео:**\n"
                f"• Видео загружено: {user_stats.get('total_videos_processed', 0)}\n"
                f"• Выходных видео: {user_stats.get('total_output_videos', 0)}\n\n"
                f"🖼️ **Обработка изображений:**\n"
                f"• Изображений загружено: {user_stats.get('total_images_processed', 0)}\n"
                f"• Выходных изображений: {user_stats.get('total_output_images', 0)}\n\n"
                f"⚙️ **Общая статистика:**\n"
                f"• Сессий обработки: {user_stats.get('processing_sessions', 0)}\n"
                f"• Среднее на сессию: {user_stats.get('avg_output_per_session', 0)}\n\n"
            )
            
            # Добавляем последние 5 обработок видео
            video_history = user_stats.get('video_history', [])
            if video_history:
                message += "📋 **Последние обработки:**\n"
                for i, record in enumerate(video_history[-5:], 1):
                    timestamp = datetime.fromisoformat(record.get('timestamp', '1970-01-01')).strftime('%d.%m %H:%M')
                    output_count = record.get('output_count', 0)
                    message += f"{i}. {timestamp} - {output_count} копий\n"
            else:
                message += "📋 **История обработки:** Нет записей\n"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except ValueError:
            await update.message.reply_text("❌ Неверный формат ID пользователя. Используйте только цифры.")
        except Exception as e:
            logger.error(f"Ошибка при получении статистики пользователя: {e}")
            await update.message.reply_text(f"❌ Ошибка при получении статистики: {str(e)}")

    async def admin_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда помощи для администраторов"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
            return
        
        help_text = (
            "🛠️ **КОМАНДЫ ДЛЯ АДМИНИСТРАТОРОВ**\n\n"
            "📊 **Статистика:**\n"
            "• `/adminstats` - Общая статистика бота\n"
            "• `/userstats <ID>` - Статистика конкретного пользователя\n\n"
            "📋 **Примеры:**\n"
            "• `/userstats 123456789` - Статистика пользователя с ID 123456789\n\n"
            "ℹ️ **Примечание:**\n"
            "Все команды доступны только администраторам."
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def main_menu_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик главного меню"""
        text = update.message.text
        
        if text == "🎬 Уникализировать видео":
            await update.message.reply_text(
                "📹 **Отправьте видеофайл для обработки**\n\n"
                "📋 **Требования:**\n"
                "• Размер файла: до 50 МБ\n"
                "• Формат: MP4, AVI, MKV\n"
                "• Длительность: до 10 минут\n\n"
                "Просто прикрепите видео к сообщению 👇",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardRemove()
            )
            return WAITING_FOR_VIDEO
        elif text == "🖼️ Уникализировать изображение":
            await update.message.reply_text(
                "🖼️ **Отправьте изображение для обработки**\n\n"
                "📋 **Требования:**\n"
                "• Размер файла: до 20 МБ\n"
                "• Формат: JPG, PNG, BMP, TIFF, WEBP\n"
                "• Разрешение: любое\n\n"
                "Просто прикрепите изображение к сообщению 👇",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardRemove()
            )
            return WAITING_FOR_IMAGE

    def _all_parameters_selected(self, user_settings: dict) -> bool:
        """Проверяет, выбраны ли все необходимые параметры"""
        return (
            user_settings.get('copies', 0) > 0 and
            'add_frames' in user_settings and
            'change_resolution' in user_settings and
            'compress' in user_settings
        )

    async def show_parameters_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню со всеми параметрами обработки с inline кнопками"""
        user_id = update.effective_user.id
        user_settings = self.user_data.get(user_id, {})
        
        # Формируем текст с отметками для выбранных параметров
        copies = user_settings.get('copies', 1)
        frames_status = "✅" if user_settings.get('add_frames', False) else "❌"
        resolution_status = "✅" if user_settings.get('change_resolution', False) else "❌"
        compression_status = "✅" if user_settings.get('compress', False) else "❌"
        
        # Проверяем, выбраны ли все параметры
        all_selected = self._all_parameters_selected(user_settings)
        
        # Создаем inline клавиатуру с параметрами
        keyboard = [
            [InlineKeyboardButton(f"Количество копий: {copies}", callback_data="choose_copies")],
            [InlineKeyboardButton(f"Рамки {frames_status}", callback_data="toggle_frames")],
            [InlineKeyboardButton(f"Разрешение {resolution_status}", callback_data="toggle_resolution")],
            [InlineKeyboardButton(f"Сжатие {compression_status}", callback_data="toggle_compression")]
        ]
        
        # Добавляем кнопку запуска только если все параметры выбраны
        if all_selected:
            keyboard.append([InlineKeyboardButton("🚀 Запустить уникализацию", callback_data="start_processing")])
        
        keyboard.append([InlineKeyboardButton("🔄 Начать заново", callback_data="restart_process")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем или редактируем сообщение
        status_text = "✅ Все параметры выбраны!" if all_selected else "⚠️ Выберите все параметры для продолжения"
        
        message_text = (
            "⚙️ **Параметры обработки видео**\n\n"
            f"{status_text}\n\n"
            "Нажимайте на кнопки ниже для изменения параметров.\n"
            "✅ - параметр включен, ❌ - параметр выключен\n\n"
        )
        
        if all_selected:
            message_text += "Когда все готово, нажмите '🚀 Запустить уникализацию'"
        else:
            message_text += "Необходимо выбрать все параметры перед запуском обработки."
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        return PARAMETERS_MENU

    async def parameters_menu_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик меню параметров"""
        user_id = update.effective_user.id
        text = update.message.text
        
        if "Количество копий" in text:
            return await self.choose_copies_menu(update, context)
        elif "Рамки" in text:
            return await self.toggle_frames(update, context)
        elif "Разрешение" in text:
            return await self.toggle_resolution(update, context)
        elif "Сжатие" in text:
            return await self.toggle_compression(update, context)
        elif text == "🚀 Запустить уникализацию":
            # Проверяем, что все параметры выбраны перед запуском
            user_settings = self.user_data.get(user_id, {})
            if self._all_parameters_selected(user_settings):
                return await self.start_final_processing(update, context)
            else:
                await update.message.reply_text(
                    "⚠️ **Не все параметры выбраны!**\n\n"
                    "Пожалуйста, выберите все необходимые параметры перед запуском обработки.",
                    parse_mode='Markdown'
                )
                return await self.show_parameters_menu(update, context)
        elif text == "⚠️ Выберите все параметры":
            await update.message.reply_text(
                "⚠️ **Необходимо выбрать все параметры**\n\n"
                "Для запуска обработки видео необходимо:\n"
                "• Выбрать количество копий\n"
                "• Включить или выключить рамки\n"
                "• Включить или выключить изменение разрешения\n"
                "• Включить или выключить сжатие\n\n"
                "После выбора всех параметров кнопка запуска станет активной.",
                parse_mode='Markdown'
            )
            return PARAMETERS_MENU
        elif text == "🔄 Начать заново":
            return await self.restart_process(update, context)
        
        return PARAMETERS_MENU

    async def choose_copies_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню выбора количества копий"""
        query = update.callback_query
        await query.answer()  # Убираем индикатор загрузки
        
        # Создаем inline кнопки для выбора количества копий
        keyboard = [
            [InlineKeyboardButton("1 копия", callback_data="copies_1")],
            [InlineKeyboardButton("3 копии", callback_data="copies_3")],
            [InlineKeyboardButton("6 копий", callback_data="copies_6")],
            [InlineKeyboardButton("🔙 Назад к параметрам", callback_data="back_to_parameters")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📊 **Выберите количество копий:**\n\n"
            "Чем больше копий, тем больше уникальных вариантов видео вы получите.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return CHOOSING_COPIES

    async def toggle_frames(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переключает параметр добавления рамок"""
        query = update.callback_query
        await query.answer()  # Убираем индикатор загрузки
        
        user_id = update.effective_user.id
        if user_id in self.user_data:
            current_value = self.user_data[user_id].get('add_frames', False)
            self.user_data[user_id]['add_frames'] = not current_value
        
        return await self.show_parameters_menu(update, context)

    async def toggle_resolution(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переключает параметр изменения разрешения"""
        query = update.callback_query
        await query.answer()  # Убираем индикатор загрузки
        
        user_id = update.effective_user.id
        if user_id in self.user_data:
            current_value = self.user_data[user_id].get('change_resolution', False)
            self.user_data[user_id]['change_resolution'] = not current_value
        
        return await self.show_parameters_menu(update, context)

    async def toggle_compression(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переключает параметр сжатия"""
        query = update.callback_query
        await query.answer()  # Убираем индикатор загрузки
        
        user_id = update.effective_user.id
        if user_id in self.user_data:
            current_value = self.user_data[user_id].get('compress', False)
            self.user_data[user_id]['compress'] = not current_value
        
        return await self.show_parameters_menu(update, context)

    async def _update_parameters_keyboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Беззвучно обновляет клавиатуру с параметрами"""
        user_id = update.effective_user.id
        user_settings = self.user_data.get(user_id, {})
        
        # Формируем текст с отметками для выбранных параметров
        copies_text = f"Количество копий: {user_settings.get('copies', 1)}"
        frames_text = f"Рамки {'✅' if user_settings.get('add_frames', False) else ''}"
        resolution_text = f"Разрешение {'✅' if user_settings.get('change_resolution', False) else ''}"
        compression_text = f"Сжатие {'✅' if user_settings.get('compress', False) else ''}"
        
        # Проверяем, выбраны ли все параметры
        all_selected = self._all_parameters_selected(user_settings)
        
        # Создаем клавиатуру с параметрами
        keyboard = [
            [KeyboardButton(copies_text)],
            [KeyboardButton(frames_text)],
            [KeyboardButton(resolution_text)],
            [KeyboardButton(compression_text)]
        ]
        
        # Добавляем кнопку запуска только если все параметры выбраны
        if all_selected:
            keyboard.append([KeyboardButton("🚀 Запустить уникализацию")])
        else:
            keyboard.append([KeyboardButton("⚠️ Выберите все параметры")])
        
        keyboard.append([KeyboardButton("🔄 Начать заново")])
        
        reply_markup = ReplyKeyboardMarkup(
            keyboard, 
            resize_keyboard=True, 
            one_time_keyboard=False
        )
        
        # Беззвучно обновляем клавиатуру через context
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=".",  # Минимальный текст
                reply_markup=reply_markup
            )
            # Сразу удаляем это сообщение
            await context.bot.delete_message(
                chat_id=user_id,
                message_id=update.message.message_id + 1
            )
        except:
            # Если что-то пошло не так, ничего не делаем
            pass
        
        return PARAMETERS_MENU

    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик получения видео от пользователя"""
        user_id = update.effective_user.id
        
        if update.message.video:
            # Сохраняем информацию о видео
            video = update.message.video
            self.user_data[user_id] = {
                'video_file_id': video.file_id,
                'video_file_name': f"video_{user_id}_{video.file_unique_id}.mp4",
                # Инициализируем параметры по умолчанию
                'copies': 1,
                'add_frames': False,
                'change_resolution': False,
                'compress': False
            }
            
            await update.message.reply_text(
                "✅ **Видео получено!**\n\n"
                "📊 Теперь выберите параметры обработки из меню ниже:",
                parse_mode='Markdown'
            )
            
            return await self.show_parameters_menu(update, context)
        else:
            await update.message.reply_text(
                "❌ Пожалуйста, отправьте видеофайл.\n\n"
                "Поддерживаемые форматы: MP4, AVI, MKV"
            )
            return WAITING_FOR_VIDEO

    async def handle_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик получения изображения от пользователя"""
        user_id = update.effective_user.id
        
        if update.message.photo:
            # Получаем изображение с максимальным качеством
            photo = update.message.photo[-1]  # Берем самое большое изображение
            
            # Проверяем размер файла
            if photo.file_size and photo.file_size > MAX_IMAGE_SIZE:
                await update.message.reply_text(
                    f"❌ **Файл слишком большой!**\n\n"
                    f"Максимальный размер: {MAX_IMAGE_SIZE // (1024 * 1024)} МБ\n"
                    f"Размер вашего файла: {photo.file_size // (1024 * 1024)} МБ\n\n"
                    "Пожалуйста, сожмите изображение и попробуйте снова.",
                    parse_mode='Markdown'
                )
                return WAITING_FOR_IMAGE
            
            # Сохраняем информацию об изображении
            self.user_data[user_id] = {
                'image_file_id': photo.file_id,
                'image_file_name': f"image_{user_id}_{photo.file_unique_id}.jpg",
                'file_type': 'image',
                # Инициализируем параметры по умолчанию
                'copies': 1,
                'add_frames': False,
                'add_filters': False,
                'add_rotation': False,
                'change_size': False
            }
            
            await update.message.reply_text(
                "✅ **Изображение получено!**\n\n"
                "📊 Теперь выберите параметры обработки из меню ниже:",
                parse_mode='Markdown'
            )
            
            return await self.show_image_parameters_menu(update, context)
        else:
            await update.message.reply_text(
                "❌ Пожалуйста, отправьте изображение.\n\n"
                f"Поддерживаемые форматы: {', '.join(SUPPORTED_IMAGE_FORMATS).upper()}"
            )
            return WAITING_FOR_IMAGE

    def _all_image_parameters_selected(self, user_settings: dict) -> bool:
        """Проверяет, выбраны ли все необходимые параметры для изображений"""
        return (
            user_settings.get('copies', 0) > 0 and
            'add_frames' in user_settings and
            'add_filters' in user_settings and
            'add_rotation' in user_settings and
            ('change_size' in user_settings or 'target_size' in user_settings)
        )

    async def show_image_parameters_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню параметров обработки изображений с inline кнопками"""
        user_id = update.effective_user.id
        user_settings = self.user_data.get(user_id, {})
        
        # Формируем текст с отметками для выбранных параметров
        copies = user_settings.get('copies', 1)
        frames_status = "✅" if user_settings.get('add_frames', False) else "❌"
        filters_status = "✅" if user_settings.get('add_filters', False) else "❌"
        rotation_status = "✅" if user_settings.get('add_rotation', False) else "❌"
        size_status = "✅" if user_settings.get('change_size', False) else "❌"
        
        # Проверяем, выбраны ли все параметры
        all_selected = self._all_image_parameters_selected(user_settings)
        
        # Получаем выбранный размер для отображения
        target_size = user_settings.get('target_size', None)
        if target_size:
            size_display = f"Размер: {target_size} ✅"
        else:
            size_display = f"Размер {size_status}"
        
        # Создаем inline клавиатуру с параметрами
        keyboard = [
            [InlineKeyboardButton(f"Количество копий: {copies}", callback_data="choose_image_copies")],
            [InlineKeyboardButton(f"Фон {frames_status}", callback_data="toggle_image_frames")],
            [InlineKeyboardButton(f"Фильтры {filters_status}", callback_data="toggle_image_filters")],
            [InlineKeyboardButton(f"Повороты {rotation_status}", callback_data="toggle_image_rotation")],
            [InlineKeyboardButton(size_display, callback_data="choose_image_size")]
        ]
        
        # Добавляем кнопку запуска только если все параметры выбраны
        if all_selected:
            keyboard.append([InlineKeyboardButton("🚀 Запустить уникализацию", callback_data="start_image_processing")])
        
        keyboard.append([InlineKeyboardButton("🔄 Начать заново", callback_data="restart_process")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем или редактируем сообщение
        status_text = "✅ Все параметры выбраны!" if all_selected else "⚠️ Выберите все параметры для продолжения"
        
        message_text = (
            "⚙️ **Параметры обработки изображения**\n\n"
            f"{status_text}\n\n"
            "Нажимайте на кнопки ниже для изменения параметров.\n"
            "✅ - параметр включен, ❌ - параметр выключен\n\n"
        )
        
        if all_selected:
            message_text += "Когда все готово, нажмите '🚀 Запустить уникализацию'"
        else:
            message_text += "Необходимо выбрать все параметры перед запуском обработки."
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        return IMAGE_PARAMETERS_MENU

    async def start_processing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса обработки видео"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if user_id not in self.user_data:
            await query.edit_message_text("Сначала отправьте видео!")
            return ConversationHandler.END
        
        # Сразу переходим к выбору количества копий, так как видео уже получено
        keyboard = [
            [InlineKeyboardButton("1 копия", callback_data="copies_1")],
            [InlineKeyboardButton("3 копии", callback_data="copies_3")],
            [InlineKeyboardButton("6 копий", callback_data="copies_6")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Выберите количество копий видео:",
            reply_markup=reply_markup
        )
        return CHOOSING_COPIES

    async def process_video_for_uniqualization(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка видео для уникализации - выбор количества копий"""
        user_id = update.effective_user.id
        
        if update.message.video:
            # Обновляем данные о видео для обработки
            video = update.message.video
            self.user_data[user_id]['processing_video_id'] = video.file_id
            
            # Создаем кнопки для выбора количества копий
            keyboard = [
                [InlineKeyboardButton("1 копия", callback_data="copies_1")],
                [InlineKeyboardButton("3 копии", callback_data="copies_3")],
                [InlineKeyboardButton("6 копий", callback_data="copies_6")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Выберите количество копий видео:",
                reply_markup=reply_markup
            )
            return CHOOSING_COPIES
        else:
            await update.message.reply_text("Пожалуйста, отправьте видеофайл для обработки.")
            return WAITING_FOR_VIDEO

    async def choose_copies(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора количества копий"""
        query = update.callback_query
        await query.answer()  # Убираем индикатор загрузки
        
        user_id = update.effective_user.id
        callback_data = query.data
        
        if callback_data.startswith("copies_"):
            # Извлекаем число из callback_data
            copies = int(callback_data.split("_")[1])
            
            # Сохраняем выбор
            if user_id in self.user_data:
                self.user_data[user_id]['copies'] = copies
            
            # Возвращаемся к меню параметров без дополнительного сообщения
            return await self.show_parameters_menu(update, context)
        
        elif callback_data == "back_to_parameters":
            return await self.show_parameters_menu(update, context)
        
        return CHOOSING_COPIES

    async def choose_frames(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор добавления рамок"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        add_frames = query.data.split('_')[1] == 'yes'
        self.user_data[user_id]['add_frames'] = add_frames
        
        # Создаем кнопки для выбора разрешения с навигацией
        keyboard = [
            [InlineKeyboardButton("📐 Изменить разрешение", callback_data="resolution_yes")],
            [InlineKeyboardButton("🎯 Оставить оригинальное", callback_data="resolution_no")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_copies")],
            [InlineKeyboardButton("🔄 Начать заново", callback_data="restart_process")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        frames_text = "с цветными рамками" if add_frames else "без рамок"
        await query.edit_message_text(
            f"🎨 **Выбрано:** {frames_text}\n\n"
            "📐 **Изменить разрешение видео?**\n"
            "Изменение разрешения добавляет уникальности",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return CHOOSING_RESOLUTION

    async def choose_resolution(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор изменения разрешения"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        change_resolution = query.data.split('_')[1] == 'yes'
        self.user_data[user_id]['change_resolution'] = change_resolution
        
        # Создаем кнопки для выбора сжатия с навигацией
        keyboard = [
            [InlineKeyboardButton("🗜️ Сжать видео", callback_data="compress_yes")],
            [InlineKeyboardButton("📹 Не сжимать", callback_data="compress_no")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_frames")],
            [InlineKeyboardButton("🔄 Начать заново", callback_data="restart_process")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        resolution_text = "изменить разрешение" if change_resolution else "оригинальное разрешение"
        await query.edit_message_text(
            f"📐 **Выбрано:** {resolution_text}\n\n"
            "🗜️ **Сжать видео для уменьшения размера?**\n"
            "Сжатие ускорит загрузку и отправку",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return CHOOSING_COMPRESSION

    async def choose_compression(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор сжатия и показ финального подтверждения"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        compress = query.data.split('_')[1] == 'yes'
        self.user_data[user_id]['compress'] = compress
        
        # Получаем все параметры
        user_settings = self.user_data[user_id]
        copies = user_settings['copies']
        add_frames = user_settings['add_frames']
        change_resolution = user_settings['change_resolution']
        
        compress_text = "со сжатием" if compress else "без сжатия"
        frames_text = "с рамками" if add_frames else "без рамок"
        resolution_text = "изменить разрешение" if change_resolution else "оригинальное разрешение"
        
        # Создаем кнопки для финального подтверждения
        keyboard = [
            [InlineKeyboardButton("✅ Начать обработку", callback_data="start_processing")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_resolution")],
            [InlineKeyboardButton("🔄 Начать заново", callback_data="restart_process")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Показываем финальное подтверждение с параметрами
        await query.edit_message_text(
            f"✅ **Все параметры выбраны!**\n\n"
            f"📊 **Итоговые параметры:**\n"
            f"• Копий: {copies}\n"
            f"• Рамки: {frames_text}\n"
            f"• Разрешение: {resolution_text}\n"
            f"• Сжатие: {compress_text}\n\n"
            f"🚀 Готов начать обработку видео?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return CHOOSING_COMPRESSION

    async def _process_video_async(self, user_id: int, user_settings: dict, 
                                 processing_message, context, chat_id: int):
        """Асинхронная обработка видео с промежуточными обновлениями"""
        input_path = None
        processed_videos = []
        
        # Используем семафор для ограничения количества одновременных обработок
        async with self.processing_semaphore:
            try:
                copies = user_settings['copies']
                add_frames = user_settings['add_frames']
                compress = user_settings['compress']
                change_resolution = user_settings['change_resolution']
                
                # Используем оригинальное видео
                video_file_id = user_settings.get('processing_video_id', user_settings['video_file_id'])
                
                # Скачиваем файл
                try:
                    await asyncio.wait_for(
                        processing_message.edit_text(
                            f"🔄 Обработка видео...\n"
                            f"📊 Параметры: {copies} копий\n\n"
                            f"📥 Скачиваю видео..."
                        ),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("Таймаут при обновлении сообщения о скачивании")
                except Exception as e:
                    logger.warning(f"Ошибка при обновлении сообщения: {e}")
                
                video_file = await context.bot.get_file(video_file_id)
                input_path = f"temp/input_{user_id}.mp4"
                
                # Создаем директорию temp если не существует
                os.makedirs("temp", exist_ok=True)
                
                await video_file.download_to_drive(input_path)
                
                # Проверяем что файл был скачан
                if not os.path.exists(input_path):
                    logger.error(f"Файл {input_path} не был создан после скачивания")
                    try:
                        await asyncio.wait_for(
                            processing_message.edit_text("❌ Ошибка при скачивании видео. Попробуйте еще раз."),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning("Таймаут при отправке сообщения об ошибке скачивания")
                    except Exception as e:
                        logger.warning(f"Ошибка при отправке сообщения об ошибке: {e}")
                    return
                
                file_size = os.path.getsize(input_path)
                logger.info(f"Файл {input_path} успешно скачан, размер: {file_size} байт")
                
                # Обновляем статус
                try:
                    await asyncio.wait_for(
                        processing_message.edit_text(
                            f"🔄 Обработка видео...\n"
                            f"📊 Параметры: {copies} копий\n\n"
                            f"🎬 Создаю уникальные копии..."
                        ),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("Таймаут при обновлении сообщения о создании копий")
                except Exception as e:
                    logger.warning(f"Ошибка при обновлении сообщения: {e}")
                
                # Создаем задачу обработки с callback для обновления прогресса
                processed_videos = await self._process_with_progress_updates(
                    input_path, user_id, copies, add_frames, compress, change_resolution,
                    processing_message
                )
                
                # Обновляем сообщение
                try:
                    await asyncio.wait_for(
                        processing_message.edit_text(
                            f"📤 Отправляю обработанные видео...\n"
                            f"✅ Создано {len(processed_videos)} уникальных копий"
                        ),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("Таймаут при обновлении сообщения о готовности к отправке")
                except Exception as e:
                    logger.warning(f"Ошибка при обновлении сообщения: {e}")
                
                # Отправляем обработанные видео
                for i, video_path in enumerate(processed_videos, 1):
                    # Обновляем прогресс отправки
                    try:
                        await asyncio.wait_for(
                            processing_message.edit_text(
                                f"📤 Отправляю видео {i}/{len(processed_videos)}...\n"
                                f"✅ Создано {len(processed_videos)} уникальных копий"
                            ),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning(f"Таймаут при обновлении прогресса отправки {i}/{len(processed_videos)}")
                    except Exception as e:
                        logger.warning(f"Ошибка при обновлении прогресса: {e}")
                    
                    # Используем asyncio.to_thread для неблокирующего чтения файла
                    video_data = await asyncio.to_thread(self._read_video_file, video_path)
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=video_data,
                        caption=f"🎬 Уникальная копия #{i}/{copies}"
                    )
                    # Удаляем временный файл
                    os.remove(video_path)
                
                # Удаляем входной файл с задержкой
                if input_path and os.path.exists(input_path):
                    try:
                        # Небольшая задержка для освобождения файла
                        await asyncio.sleep(1)
                        os.remove(input_path)
                        logger.info(f"Удален входной файл: {input_path}")
                    except PermissionError:
                        logger.warning(f"Не удалось удалить входной файл {input_path} - файл заблокирован")
                        # Планируем удаление позже
                        asyncio.create_task(self._delayed_file_cleanup(input_path))
                    except Exception as e:
                        logger.error(f"Ошибка при удалении входного файла {input_path}: {e}")
                
                # Финальное сообщение о завершении
                try:
                    await asyncio.wait_for(
                        processing_message.edit_text(
                            f"✅ Обработка завершена!\n"
                            f"📹 Отправлено {len(processed_videos)} уникальных копий"
                        ),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("Таймаут при отправке финального сообщения")
                    # Отправляем новое сообщение вместо редактирования
                    try:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"✅ Обработка завершена!\n"
                                 f"📹 Отправлено {len(processed_videos)} уникальных копий"
                        )
                    except Exception as send_error:
                        logger.error(f"Не удалось отправить финальное сообщение: {send_error}")
                except Exception as e:
                    logger.warning(f"Не удалось отредактировать сообщение: {e}")
                    # Отправляем новое сообщение вместо редактирования
                    try:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"✅ Обработка завершена!\n"
                                 f"📹 Отправлено {len(processed_videos)} уникальных копий"
                        )
                    except Exception as send_error:
                        logger.error(f"Не удалось отправить финальное сообщение: {send_error}")
                
                # Записываем статистику обработки
                try:
                    input_video_info = {
                        'file_id': video_file_id,
                        'file_size': file_size,
                        'duration': 'unknown'  # Можно добавить получение длительности
                    }
                    
                    processing_params = {
                        'copies': copies,
                        'add_frames': add_frames,
                        'compress': compress,
                        'change_resolution': change_resolution
                    }
                    
                    self.db_manager.record_video_processing(
                        user_id=user_id,
                        input_video_info=input_video_info,
                        output_count=len(processed_videos),
                        processing_params=processing_params
                    )
                    logger.info(f"Статистика записана для пользователя {user_id}")
                except Exception as e:
                    logger.error(f"Ошибка при записи статистики: {e}")
                
                # Отправляем отдельное сообщение с предложением прикрепить следующее видео
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="📹 Прикрепите следующее видео\n\n"
                             "📋 Требования:\n"
                             "• Размер файла: до 50 МБ\n"
                             "• Формат: MP4, AVI, MKV\n"
                             "• Длительность: до 10 минут\n\n"
                             "Просто прикрепите видео к сообщению 👇"
                    )
                except Exception as e:
                    logger.error(f"Ошибка при отправке сообщения: {e}")
                
                # Устанавливаем состояние ожидания видео через context
                context.user_data['conversation_state'] = WAITING_FOR_VIDEO
                
            except asyncio.CancelledError:
                logger.info(f"Обработка видео для пользователя {user_id} была отменена")
                # Не показываем сообщение об ошибке при отмене
                return
                
            except Exception as e:
                logger.error(f"Ошибка при обработке видео: {e}")
                
                # Переход к ожиданию следующего видео при ошибке
                try:
                    await asyncio.wait_for(
                        processing_message.edit_text(
                            f"❌ Произошла ошибка при обработке видео: {str(e)}\n\n"
                            "📹 Прикрепите следующее видео\n\n"
                            "📋 Требования:\n"
                            "• Размер файла: до 50 МБ\n"
                            "• Формат: MP4, AVI, MKV\n"
                            "• Длительность: до 10 минут\n\n"
                            "Просто прикрепите видео к сообщению 👇"
                        ),
                        timeout=5.0
                    )
                except Exception as edit_error:
                    logger.warning(f"Не удалось отредактировать сообщение об ошибке: {edit_error}")
                    try:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"❌ Произошла ошибка при обработке видео: {str(e)}\n\n"
                                 "📹 Прикрепите следующее видео\n\n"
                                 "📋 Требования:\n"
                                 "• Размер файла: до 50 МБ\n"
                                 "• Формат: MP4, AVI, MKV\n"
                                 "• Длительность: до 10 минут\n\n"
                                 "Просто прикрепите видео к сообщению 👇"
                        )
                    except Exception as send_error:
                        logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}")
                
                # Устанавливаем состояние ожидания видео через context
                context.user_data['conversation_state'] = WAITING_FOR_VIDEO
            finally:
                # Очищаем временные файлы при отмене с безопасным удалением
                if input_path and os.path.exists(input_path):
                    try:
                        await asyncio.sleep(0.5)  # Небольшая задержка
                        os.remove(input_path)
                        logger.info(f"Удален входной файл: {input_path}")
                    except PermissionError:
                        logger.warning(f"Входной файл {input_path} заблокирован, планируем отложенное удаление")
                        asyncio.create_task(self._delayed_file_cleanup(input_path))
                    except Exception as e:
                        logger.error(f"Ошибка при удалении входного файла {input_path}: {e}")
                
                # Очищаем обработанные файлы при отмене
                for video_path in processed_videos:
                    if os.path.exists(video_path):
                        try:
                            await asyncio.sleep(0.1)  # Небольшая задержка между удалениями
                            os.remove(video_path)
                            logger.info(f"Удален обработанный файл: {video_path}")
                        except PermissionError:
                            logger.warning(f"Обработанный файл {video_path} заблокирован, планируем отложенное удаление")
                            asyncio.create_task(self._delayed_file_cleanup(video_path))
                        except Exception as e:
                            logger.error(f"Ошибка при удалении обработанного файла {video_path}: {e}")
                
                # Очищаем данные пользователя и активную задачу
                if user_id in self.user_data:
                    del self.user_data[user_id]
                if user_id in self.active_processing_tasks:
                    del self.active_processing_tasks[user_id]

    async def _process_with_progress_updates(self, input_path: str, user_id: int, 
                                           copies: int, add_frames: bool, compress: bool, change_resolution: bool,
                                           processing_message):
        """Обработка видео с параллельной обработкой всех копий одновременно"""
        
        # Обновляем статус - начинаем параллельную обработку
        try:
            await asyncio.wait_for(
                processing_message.edit_text(
                    f"🔄 Обработка видео...\n"
                    f"📊 Создаю {copies} копий параллельно\n\n"
                    f"🚀 Запускаю обработку всех копий одновременно..."
                ),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            logger.warning("Таймаут при обновлении сообщения о начале параллельной обработки")
        except Exception as e:
            logger.warning(f"Ошибка при обновлении сообщения: {e}")
        
        # Создаем задачи для параллельной обработки всех копий
        tasks = []
        output_paths = []
        
        for i in range(copies):
            output_path = f"output/processed_{user_id}_{i+1}.mp4"
            output_paths.append(output_path)
            
            # Создаем задачу для каждой копии
            task = self._process_single_copy(
                input_path, output_path, i, add_frames, compress, change_resolution, user_id
            )
            tasks.append(task)
        
        # Создаем задачу для периодического обновления статуса
        completed_count = {'value': 0}
        status_update_task = asyncio.create_task(
            self._update_processing_status(processing_message, copies, completed_count)
        )
        
        # Запускаем все копии параллельно
        logger.info(f"🚀 Запускаю параллельную обработку {copies} копий")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Останавливаем обновление статуса
        status_update_task.cancel()
        try:
            await status_update_task
        except asyncio.CancelledError:
            pass
        
        # Собираем успешно обработанные видео
        processed_videos = []
        for i, (result, output_path) in enumerate(zip(results, output_paths)):
            if isinstance(result, Exception):
                logger.error(f"❌ Ошибка при создании копии {i+1}: {str(result)}")
            elif result and os.path.exists(output_path):
                processed_videos.append(output_path)
                logger.info(f"✅ Копия {i+1} создана успешно")
            else:
                logger.error(f"❌ Копия {i+1} не была создана")
        
        logger.info(f"✅ Параллельная обработка завершена. Успешно: {len(processed_videos)}/{copies}")
        return processed_videos
    
    async def _update_processing_status(self, processing_message, total_copies: int, completed_count: dict):
        """Периодически обновляет статус обработки"""
        dots = 0
        last_text = ""
        while True:
            try:
                await asyncio.sleep(3)  # Обновляем каждые 3 секунды
                dots = (dots + 1) % 4
                animation = "." * dots
                
                new_text = (
                    f"🔄 Обработка видео{animation}\n"
                    f"📊 Обрабатываю {total_copies} копий параллельно\n\n"
                    f"⚡ Это быстрее в {total_copies}x раз!\n"
                    f"⏳ Пожалуйста, подождите..."
                )
                
                # Редактируем только если текст изменился
                if new_text != last_text:
                    try:
                        # Добавляем таймаут для редактирования сообщения (5 секунд)
                        await asyncio.wait_for(
                            processing_message.edit_text(new_text),
                            timeout=5.0
                        )
                        last_text = new_text
                    except asyncio.TimeoutError:
                        logger.warning("Таймаут при редактировании сообщения, пропускаем обновление")
                    except Exception as edit_error:
                        # Если не удается отредактировать, пропускаем это обновление
                        logger.warning(f"Не удалось отредактировать сообщение: {edit_error}")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка при обновлении статуса: {e}")
                break

    async def _process_single_copy(self, input_path: str, output_path: str, 
                                 copy_index: int, add_frames: bool, compress: bool, change_resolution: bool, user_id: int = None):
        """Обработка одной копии видео"""
        try:
            # Используем ThreadPoolExecutor вместо ProcessPoolExecutor для избежания проблем с pickle
            loop = asyncio.get_event_loop()
            
            # Увеличиваем таймаут для больших файлов
            file_size = os.path.getsize(input_path) / (1024 * 1024)  # MB
            timeout_seconds = max(600, int(file_size * 60))  # Минимум 10 минут, +60 сек на MB
            logger.info(f"Установлен таймаут: {timeout_seconds} секунд для файла {file_size:.2f} MB")
            
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,  # Используем стандартный ThreadPoolExecutor
                    self._process_video_copy_wrapper,
                    input_path, output_path, copy_index, add_frames, compress, change_resolution, user_id
                ),
                timeout=timeout_seconds
            )
            
            return True
            
        except asyncio.TimeoutError:
            logger.error(f"Таймаут при создании копии {copy_index+1} (превышен лимит {timeout_seconds} секунд)")
            logger.error(f"Файл: {input_path}, размер: {file_size:.2f} MB")
            return False
        except Exception as e:
            logger.error(f"Ошибка при создании копии {copy_index+1}: {str(e)}")
            return False

    def _process_video_copy_wrapper(self, input_path: str, output_path: str, 
                                  copy_index: int, add_frames: bool, compress: bool, change_resolution: bool, user_id: int = None):
        """Обертка для функции обработки видео"""
        from video_processor import process_video_copy_new
        
        # Получаем абсолютные пути
        abs_input_path = os.path.abspath(input_path)
        abs_output_path = os.path.abspath(output_path)
        
        # Создаем директорию для выходного файла если не существует
        os.makedirs(os.path.dirname(abs_output_path), exist_ok=True)
        
        # Вызываем функцию обработки с user_id для поддержки отмены
        return process_video_copy_new(abs_input_path, abs_output_path, copy_index, add_frames, compress, change_resolution, user_id)

    def _read_video_file(self, video_path: str):
        """Синхронная функция для чтения видеофайла"""
        with open(video_path, 'rb') as video_file:
            return video_file.read()

    async def back_to_main(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Возврат в главное меню"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        if user_id in self.user_data:
            del self.user_data[user_id]
        
        welcome_text = (
            "🎬 **Главное меню**\n\n"
            "**Бот для уникализации видео** 🚀\n\n"
            "📋 **Инструкция:**\n"
            "1️⃣ Нажмите кнопку 'Уникализировать видео'\n"
            "2️⃣ Отправьте видеофайл (до 50 МБ)\n"
            "3️⃣ Выберите количество копий (1-3-6)\n"
            "4️⃣ Выберите параметры обработки\n"
            "5️⃣ Получите уникальные копии!\n\n"
            "Готовы начать? 👇"
        )
        
        keyboard = [[InlineKeyboardButton("🎬 Уникализировать видео", callback_data="main_menu_start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    async def back_to_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Возврат к загрузке видео"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "📤 **Отправьте видеофайл для обработки**\n\n"
            "📋 **Требования:**\n"
            "• Размер файла: до 50 МБ\n"
            "• Формат: MP4, AVI, MKV\n"
            "• Длительность: до 10 минут\n\n"
            "⬇️ Прикрепите видео к сообщению",
            parse_mode='Markdown'
        )
        return WAITING_FOR_VIDEO

    async def back_to_copies(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Возврат к выбору количества копий"""
        query = update.callback_query
        await query.answer()
        
        keyboard = [
            [InlineKeyboardButton("1 копия", callback_data="copies_1")],
            [InlineKeyboardButton("3 копии", callback_data="copies_3")], 
            [InlineKeyboardButton("6 копий", callback_data="copies_6")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")],
            [InlineKeyboardButton("🔄 Начать заново", callback_data="restart_process")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "✅ **Видео получено!**\n\n"
            "📊 Выберите количество копий для создания:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return CHOOSING_COPIES

    async def back_to_frames(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Возврат к выбору рамок"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        if user_id not in self.user_data:
            await query.edit_message_text("❌ Данные сессии утеряны. Начните заново с /start")
            return ConversationHandler.END
        
        # Создаем кнопки для выбора рамок с навигацией
        keyboard = [
            [InlineKeyboardButton("🖼️ Добавить рамки", callback_data="frames_yes")],
            [InlineKeyboardButton("📹 Без рамок", callback_data="frames_no")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_copies")],
            [InlineKeyboardButton("🔄 Начать заново", callback_data="restart_process")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        copies = self.user_data[user_id]['copies']
        await query.edit_message_text(
            f"📊 **Выбрано:** {copies} копий\n\n"
            "🖼️ **Добавить цветные рамки к видео?**\n"
            "Рамки помогают сделать каждую копию уникальной",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return CHOOSING_FRAMES

    async def back_to_resolution(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Возврат к выбору разрешения"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        if user_id not in self.user_data:
            await query.edit_message_text("❌ Данные сессии утеряны. Начните заново с /start")
            return ConversationHandler.END
        
        # Создаем кнопки для выбора разрешения с навигацией
        keyboard = [
            [InlineKeyboardButton("📐 Изменить разрешение", callback_data="resolution_yes")],
            [InlineKeyboardButton("📹 Оригинальное разрешение", callback_data="resolution_no")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_frames")],
            [InlineKeyboardButton("🔄 Начать заново", callback_data="restart_process")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        user_settings = self.user_data[user_id]
        copies = user_settings['copies']
        frames_text = "с рамками" if user_settings['add_frames'] else "без рамок"
        
        await query.edit_message_text(
            f"📊 **Выбрано:** {copies} копий {frames_text}\n\n"
            "📐 **Изменить разрешение видео?**\n"
            "Изменение разрешения поможет сделать копии более уникальными",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return CHOOSING_RESOLUTION

    async def restart_process(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Перезапуск процесса - возврат к главному меню"""
        user_id = update.effective_user.id
        
        # Останавливаем активную обработку если есть
        if user_id in self.active_processing_tasks:
            self.active_processing_tasks[user_id].cancel()
            del self.active_processing_tasks[user_id]
        
        # Очищаем данные пользователя
        if user_id in self.user_data:
            # Удаляем загруженное видео если есть
            if 'video_path' in self.user_data[user_id]:
                video_path = self.user_data[user_id]['video_path']
                if os.path.exists(video_path):
                    try:
                        os.remove(video_path)
                        logger.info(f"Удален файл: {video_path}")
                    except Exception as e:
                        logger.error(f"Ошибка при удалении файла {video_path}: {e}")
            
            del self.user_data[user_id]
        
        # Убираем клавиатуру и показываем сообщение о загрузке видео
        reply_markup = ReplyKeyboardRemove()
        
        message_text = (
            "📹 **Отправьте видеофайл для обработки**\n\n"
            "📋 **Требования:**\n"
            "• Размер файла: до 50 МБ\n"
            "• Формат: MP4, AVI, MKV\n"
            "• Длительность: до 10 минут\n\n"
            "Просто прикрепите видео к сообщению 👇"
        )
        
        # Проверяем, есть ли callback_query или обычное сообщение
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                message_text,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        return WAITING_FOR_VIDEO

    async def start_final_processing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запуск финальной обработки видео"""
        query = update.callback_query
        await query.answer()  # Убираем индикатор загрузки
        
        user_id = update.effective_user.id
        
        if user_id not in self.user_data:
            await query.edit_message_text("❌ Данные сессии утеряны. Начните заново с /start")
            return ConversationHandler.END
        
        # Получаем все параметры
        user_settings = self.user_data[user_id]
        copies = user_settings['copies']
        add_frames = user_settings['add_frames']
        change_resolution = user_settings['change_resolution']
        compress = user_settings['compress']
        
        compress_text = "со сжатием" if compress else "без сжатия"
        frames_text = "с рамками" if add_frames else "без рамок"
        resolution_text = "изменить разрешение" if change_resolution else "оригинальное разрешение"
        
        # Отправляем сообщение о начале обработки
        processing_message = await query.edit_message_text(
            f"🔄 Запускаю обработку видео...\n"
            f"📊 Параметры:\n"
            f"• Копий: {copies}\n"
            f"• Рамки: {frames_text}\n"
            f"• Разрешение: {resolution_text}\n"
            f"• Сжатие: {compress_text}\n\n"
            f"⏳ Подготавливаю к обработке..."
        )
        
        # Запускаем обработку в фоновом режиме
        task = asyncio.create_task(
            self._process_video_async(
                user_id, 
                user_settings, 
                processing_message, 
                context,
                update.effective_chat.id
            )
        )
        
        # Сохраняем задачу для возможной отмены
        self.active_processing_tasks[user_id] = task
        
        # Возвращаем состояние ожидания видео, чтобы бот мог принимать новые видео
        return WAITING_FOR_VIDEO

    # Методы для обработки изображений
    async def choose_image_copies_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню выбора количества копий для изображений"""
        query = update.callback_query
        await query.answer()
        
        # Создаем inline кнопки для выбора количества копий
        keyboard = [
            [InlineKeyboardButton("1 копия", callback_data="image_copies_1")],
            [InlineKeyboardButton("3 копии", callback_data="image_copies_3")],
            [InlineKeyboardButton("6 копий", callback_data="image_copies_6")],
            [InlineKeyboardButton("🔙 Назад к параметрам", callback_data="back_to_image_parameters")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📊 **Выберите количество копий изображения:**\n\n"
            "Чем больше копий, тем больше уникальных вариантов изображения вы получите.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return CHOOSING_IMAGE_COPIES

    async def toggle_image_frames(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переключает параметр добавления рамок для изображений"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        if user_id in self.user_data:
            current_value = self.user_data[user_id].get('add_frames', False)
            self.user_data[user_id]['add_frames'] = not current_value
        
        return await self.show_image_parameters_menu(update, context)

    async def toggle_image_filters(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переключает параметр добавления фильтров для изображений"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        if user_id in self.user_data:
            current_value = self.user_data[user_id].get('add_filters', False)
            self.user_data[user_id]['add_filters'] = not current_value
        
        return await self.show_image_parameters_menu(update, context)

    async def toggle_image_rotation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переключает параметр добавления поворотов для изображений"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        if user_id in self.user_data:
            current_value = self.user_data[user_id].get('add_rotation', False)
            self.user_data[user_id]['add_rotation'] = not current_value
        
        return await self.show_image_parameters_menu(update, context)

    async def toggle_image_size(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переключает параметр изменения размера для изображений"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        if user_id in self.user_data:
            current_value = self.user_data[user_id].get('change_size', False)
            self.user_data[user_id]['change_size'] = not current_value
        
        return await self.show_image_parameters_menu(update, context)

    async def choose_image_copies(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора количества копий для изображений"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        callback_data = query.data
        
        if callback_data.startswith("image_copies_"):
            # Извлекаем число из callback_data
            copies = int(callback_data.split("_")[2])
            
            # Сохраняем выбор
            if user_id in self.user_data:
                self.user_data[user_id]['copies'] = copies
            
            # Возвращаемся к меню параметров изображений
            return await self.show_image_parameters_menu(update, context)
        
        elif callback_data == "back_to_image_parameters":
            return await self.show_image_parameters_menu(update, context)
        
        return IMAGE_PARAMETERS_MENU

    async def choose_image_size_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню выбора размера изображения"""
        query = update.callback_query
        await query.answer()
        
        # Создаем inline кнопки для выбора размера
        keyboard = [
            [InlineKeyboardButton("📱 1080x1920 (Stories/Reels)", callback_data="image_size_1080x1920")],
            [InlineKeyboardButton("📺 1920x1080 (Горизонтальное)", callback_data="image_size_1920x1080")],
            [InlineKeyboardButton("⬜ 1080x1080 (Квадрат)", callback_data="image_size_1080x1080")],
            [InlineKeyboardButton("📸 1080x1350 (Instagram 4:5)", callback_data="image_size_1080x1350")],
            [InlineKeyboardButton("🖥️ 1920x1440 (16:12)", callback_data="image_size_1920x1440")],
            [InlineKeyboardButton("📐 1680x1050 (16:10)", callback_data="image_size_1680x1050")],
            [InlineKeyboardButton("💻 1600x900 (16:9)", callback_data="image_size_1600x900")],
            [InlineKeyboardButton("🖼️ 1440x1080 (4:3)", callback_data="image_size_1440x1080")],
            [InlineKeyboardButton("📱 1280x720 (HD)", callback_data="image_size_1280x720")],
            [InlineKeyboardButton("📺 1024x768 (4:3)", callback_data="image_size_1024x768")],
            [InlineKeyboardButton("📱 960x540 (16:9)", callback_data="image_size_960x540")],
            [InlineKeyboardButton("📱 800x600 (4:3)", callback_data="image_size_800x600")],
            [InlineKeyboardButton("📱 720x480 (3:2)", callback_data="image_size_720x480")],
            [InlineKeyboardButton("📱 640x480 (4:3)", callback_data="image_size_640x480")],
            [InlineKeyboardButton("📱 576x432 (4:3)", callback_data="image_size_576x432")],
            [InlineKeyboardButton("📱 480x360 (4:3)", callback_data="image_size_480x360")],
            [InlineKeyboardButton("📱 320x240 (4:3)", callback_data="image_size_320x240")],
            [InlineKeyboardButton("📱 240x180 (4:3)", callback_data="image_size_240x180")],
            [InlineKeyboardButton("📱 160x120 (4:3)", callback_data="image_size_160x120")],
            [InlineKeyboardButton("❌ Не изменять размер", callback_data="image_size_original")],
            [InlineKeyboardButton("🔙 Назад к параметрам", callback_data="back_to_image_parameters")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📐 **Выберите размер изображения:**\n\n"
            "Выберите желаемый размер для ваших изображений. "
            "Популярные размеры для социальных сетей выделены отдельно.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return CHOOSING_IMAGE_SIZE

    async def choose_image_size(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора размера изображения"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        callback_data = query.data
        
        if callback_data.startswith("image_size_"):
            # Извлекаем размер из callback_data
            size_str = callback_data.replace("image_size_", "")
            
            # Сохраняем выбор
            if user_id in self.user_data:
                if size_str == "original":
                    self.user_data[user_id]['change_size'] = False
                    self.user_data[user_id]['target_size'] = None
                else:
                    self.user_data[user_id]['change_size'] = True
                    self.user_data[user_id]['target_size'] = size_str
            
            # Возвращаемся к меню параметров изображений
            return await self.show_image_parameters_menu(update, context)
        
        elif callback_data == "back_to_image_parameters":
            return await self.show_image_parameters_menu(update, context)
        
        return CHOOSING_IMAGE_SIZE

    async def start_image_processing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запуск обработки изображения"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        if user_id not in self.user_data:
            await query.edit_message_text("❌ Данные сессии утеряны. Начните заново с /start")
            return ConversationHandler.END
        
        # Получаем все параметры
        user_settings = self.user_data[user_id]
        copies = user_settings['copies']
        add_frames = user_settings['add_frames']
        add_filters = user_settings['add_filters']
        add_rotation = user_settings['add_rotation']
        change_size = user_settings['change_size']
        
        frames_text = "с рамками" if add_frames else "без рамок"
        filters_text = "с фильтрами" if add_filters else "без фильтров"
        rotation_text = "с поворотами" if add_rotation else "без поворотов"
        size_text = "с изменением размера" if change_size else "оригинальный размер"
        
        # Отправляем сообщение о начале обработки
        processing_message = await query.edit_message_text(
            f"🔄 Запускаю обработку изображения...\n"
            f"📊 Параметры:\n"
            f"• Копий: {copies}\n"
            f"• Фон: {frames_text}\n"
            f"• Фильтры: {filters_text}\n"
            f"• Повороты: {rotation_text}\n"
            f"• Размер: {size_text}\n\n"
            f"⏳ Подготавливаю к обработке..."
        )
        
        # Запускаем обработку в фоновом режиме
        task = asyncio.create_task(
            self._process_image_async(
                user_id, 
                user_settings, 
                processing_message, 
                context,
                update.effective_chat.id
            )
        )
        
        # Сохраняем задачу для возможной отмены
        self.active_processing_tasks[user_id] = task
        
        # Возвращаем состояние ожидания изображения
        return WAITING_FOR_IMAGE

    async def _process_image_async(self, user_id: int, user_settings: dict, 
                                 processing_message, context, chat_id: int):
        """Асинхронная обработка изображения с промежуточными обновлениями"""
        input_path = None
        processed_images = []
        
        try:
            copies = user_settings['copies']
            add_frames = user_settings['add_frames']
            add_filters = user_settings['add_filters']
            add_rotation = user_settings['add_rotation']
            change_size = user_settings['change_size']
            
            # Используем оригинальное изображение
            image_file_id = user_settings.get('image_file_id')
            
            # Скачиваем файл
            try:
                await asyncio.wait_for(
                    processing_message.edit_text(
                        f"🔄 Обработка изображения...\n"
                        f"📊 Параметры: {copies} копий\n\n"
                        f"📥 Скачиваю изображение..."
                    ),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("Таймаут при обновлении сообщения о скачивании")
            except Exception as e:
                logger.warning(f"Ошибка при обновлении сообщения: {e}")
            
            image_file = await context.bot.get_file(image_file_id)
            input_path = f"temp/input_image_{user_id}.jpg"
            
            # Создаем директорию temp если не существует
            os.makedirs("temp", exist_ok=True)
            
            await image_file.download_to_drive(input_path)
            
            # Проверяем что файл был скачан
            if not os.path.exists(input_path):
                logger.error(f"Файл {input_path} не был создан после скачивания")
                try:
                    await asyncio.wait_for(
                        processing_message.edit_text("❌ Ошибка при скачивании изображения. Попробуйте еще раз."),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("Таймаут при отправке сообщения об ошибке скачивания")
                except Exception as e:
                    logger.warning(f"Ошибка при отправке сообщения об ошибке: {e}")
                return
            
            file_size = os.path.getsize(input_path)
            logger.info(f"Файл {input_path} успешно скачан, размер: {file_size} байт")
            
            # Обновляем статус
            try:
                await asyncio.wait_for(
                    processing_message.edit_text(
                        f"🔄 Обработка изображения...\n"
                        f"📊 Параметры: {copies} копий\n\n"
                        f"🎨 Создаю уникальные копии..."
                    ),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("Таймаут при обновлении сообщения о создании копий")
            except Exception as e:
                logger.warning(f"Ошибка при обновлении сообщения: {e}")
            
            # Получаем выбранный размер
            target_size = user_settings.get('target_size', None)
            if target_size:
                # Парсим размер из строки "1080x1920"
                try:
                    width, height = map(int, target_size.split('x'))
                    target_size_tuple = (width, height)
                except:
                    target_size_tuple = None
            else:
                target_size_tuple = None
            
            # Обрабатываем изображение
            processed_images = await self.image_processor.process_image(
                input_path, user_id, copies, add_frames, add_filters, add_rotation, change_size, target_size_tuple
            )
            
            # Обновляем сообщение
            try:
                await asyncio.wait_for(
                    processing_message.edit_text(
                        f"📤 Отправляю обработанные изображения...\n"
                        f"✅ Создано {len(processed_images)} уникальных копий"
                    ),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("Таймаут при обновлении сообщения о готовности к отправке")
            except Exception as e:
                logger.warning(f"Ошибка при обновлении сообщения: {e}")
            
            # Отправляем обработанные изображения
            for i, image_path in enumerate(processed_images, 1):
                # Обновляем прогресс отправки
                try:
                    await asyncio.wait_for(
                        processing_message.edit_text(
                            f"📤 Отправляю изображение {i}/{len(processed_images)}...\n"
                            f"✅ Создано {len(processed_images)} уникальных копий"
                        ),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Таймаут при обновлении прогресса отправки {i}/{len(processed_images)}")
                except Exception as e:
                    logger.warning(f"Ошибка при обновлении прогресса: {e}")
                
                # Используем asyncio.to_thread для неблокирующего чтения файла
                image_data = await asyncio.to_thread(self._read_image_file, image_path)
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=image_data,
                    caption=f"🖼️ Уникальная копия #{i}/{copies}"
                )
                # Удаляем временный файл
                os.remove(image_path)
            
            # Удаляем входной файл с задержкой
            if input_path and os.path.exists(input_path):
                try:
                    # Небольшая задержка для освобождения файла
                    await asyncio.sleep(1)
                    os.remove(input_path)
                    logger.info(f"Удален входной файл: {input_path}")
                except PermissionError:
                    logger.warning(f"Не удалось удалить входной файл {input_path} - файл заблокирован")
                except Exception as e:
                    logger.error(f"Ошибка при удалении входного файла {input_path}: {e}")
            
            # Финальное сообщение о завершении
            try:
                await asyncio.wait_for(
                    processing_message.edit_text(
                        f"✅ Обработка завершена!\n"
                        f"🖼️ Отправлено {len(processed_images)} уникальных копий"
                    ),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("Таймаут при отправке финального сообщения")
                # Отправляем новое сообщение вместо редактирования
                try:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"✅ Обработка завершена!\n"
                             f"🖼️ Отправлено {len(processed_images)} уникальных копий"
                    )
                except Exception as send_error:
                    logger.error(f"Не удалось отправить финальное сообщение: {send_error}")
            except Exception as e:
                logger.warning(f"Не удалось отредактировать сообщение: {e}")
                # Отправляем новое сообщение вместо редактирования
                try:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"✅ Обработка завершена!\n"
                             f"🖼️ Отправлено {len(processed_images)} уникальных копий"
                    )
                except Exception as send_error:
                    logger.error(f"Не удалось отправить финальное сообщение: {send_error}")
            
            # Записываем статистику обработки
            try:
                input_image_info = {
                    'file_id': image_file_id,
                    'file_size': file_size,
                }
                
                processing_params = {
                    'copies': copies,
                    'add_frames': add_frames,
                    'add_filters': add_filters,
                    'add_rotation': add_rotation,
                    'change_size': change_size
                }
                
                self.db_manager.record_image_processing(
                    user_id=user_id,
                    input_image_info=input_image_info,
                    output_count=len(processed_images),
                    processing_params=processing_params
                )
                logger.info(f"Статистика изображений записана для пользователя {user_id}")
            except Exception as e:
                logger.error(f"Ошибка при записи статистики изображений: {e}")
            
            # Отправляем отдельное сообщение с предложением прикрепить следующее изображение
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="🖼️ Прикрепите следующее изображение\n\n"
                         "📋 Требования:\n"
                         "• Размер файла: до 20 МБ\n"
                         "• Формат: JPG, PNG, BMP, TIFF, WEBP\n"
                         "• Разрешение: любое\n\n"
                         "Просто прикрепите изображение к сообщению 👇"
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения: {e}")
            
            # Устанавливаем состояние ожидания изображения через context
            context.user_data['conversation_state'] = WAITING_FOR_IMAGE
            
        except Exception as e:
            logger.error(f"Ошибка при обработке изображения: {e}")
            
            # Переход к ожиданию следующего изображения при ошибке
            try:
                await asyncio.wait_for(
                    processing_message.edit_text(
                        f"❌ Произошла ошибка при обработке изображения: {str(e)}\n\n"
                        "🖼️ Прикрепите следующее изображение\n\n"
                        "📋 Требования:\n"
                        "• Размер файла: до 20 МБ\n"
                        "• Формат: JPG, PNG, BMP, TIFF, WEBP\n"
                        "• Разрешение: любое\n\n"
                        "Просто прикрепите изображение к сообщению 👇"
                    ),
                    timeout=5.0
                )
            except Exception as edit_error:
                logger.warning(f"Не удалось отредактировать сообщение об ошибке: {edit_error}")
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ Произошла ошибка при обработке изображения: {str(e)}\n\n"
                             "🖼️ Прикрепите следующее изображение\n\n"
                             "📋 Требования:\n"
                             "• Размер файла: до 20 МБ\n"
                             "• Формат: JPG, PNG, BMP, TIFF, WEBP\n"
                             "• Разрешение: любое\n\n"
                             "Просто прикрепите изображение к сообщению 👇"
                    )
                except Exception as send_error:
                    logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}")
            
            # Устанавливаем состояние ожидания изображения через context
            context.user_data['conversation_state'] = WAITING_FOR_IMAGE
        finally:
            # Очищаем временные файлы при отмене с безопасным удалением
            if input_path and os.path.exists(input_path):
                try:
                    await asyncio.sleep(0.5)  # Небольшая задержка
                    os.remove(input_path)
                    logger.info(f"Удален входной файл: {input_path}")
                except PermissionError:
                    logger.warning(f"Входной файл {input_path} заблокирован, планируем отложенное удаление")
                except Exception as e:
                    logger.error(f"Ошибка при удалении входного файла {input_path}: {e}")
            
            # Очищаем обработанные файлы при отмене
            for image_path in processed_images:
                if os.path.exists(image_path):
                    try:
                        await asyncio.sleep(0.1)  # Небольшая задержка между удалениями
                        os.remove(image_path)
                        logger.info(f"Удален обработанный файл: {image_path}")
                    except PermissionError:
                        logger.warning(f"Обработанный файл {image_path} заблокирован, планируем отложенное удаление")
                    except Exception as e:
                        logger.error(f"Ошибка при удалении обработанного файла {image_path}: {e}")
            
            # Очищаем данные пользователя и активную задачу
            if user_id in self.user_data:
                del self.user_data[user_id]
            if user_id in self.active_processing_tasks:
                del self.active_processing_tasks[user_id]

    def _read_image_file(self, image_path: str):
        """Синхронная функция для чтения изображения"""
        with open(image_path, 'rb') as image_file:
            return image_file.read()

def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        print("Ошибка: BOT_TOKEN не найден в переменных окружения!")
        return
    
    # Очищаем старые временные файлы при запуске
    from video_processor import cleanup_old_temp_files
    from config import TEMP_DIR
    cleanup_old_temp_files(TEMP_DIR)
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Создаем экземпляр бота
    video_bot = VideoBot()
    
    # Настраиваем обработчик разговора
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', video_bot.start)
        ],
        states={
            MAIN_MENU: [
                MessageHandler(filters.TEXT & filters.Regex("^🎬 Уникализировать видео$"), video_bot.main_menu_handler),
                MessageHandler(filters.TEXT & filters.Regex("^🖼️ Уникализировать изображение$"), video_bot.main_menu_handler),
                CallbackQueryHandler(video_bot.show_parameters_menu, pattern="^start_processing$"),
                CommandHandler('start', video_bot.start),  # Добавляем /start в MAIN_MENU
                CommandHandler('help', video_bot.help_command)  # Добавляем /help в MAIN_MENU
            ],
            WAITING_FOR_VIDEO: [
                MessageHandler(filters.VIDEO, video_bot.handle_video),
                CallbackQueryHandler(video_bot.show_parameters_menu, pattern="^start_processing$"),
                CommandHandler('start', video_bot.start),  # Добавляем /start в WAITING_FOR_VIDEO
                CommandHandler('help', video_bot.help_command)  # Добавляем /help в WAITING_FOR_VIDEO
            ],
            WAITING_FOR_IMAGE: [
                MessageHandler(filters.PHOTO, video_bot.handle_image),
                CallbackQueryHandler(video_bot.show_image_parameters_menu, pattern="^start_image_processing$"),
                CommandHandler('start', video_bot.start),  # Добавляем /start в WAITING_FOR_IMAGE
                CommandHandler('help', video_bot.help_command)  # Добавляем /help в WAITING_FOR_IMAGE
            ],
            IMAGE_PARAMETERS_MENU: [
                CallbackQueryHandler(video_bot.choose_image_copies_menu, pattern="^choose_image_copies$"),
                CallbackQueryHandler(video_bot.toggle_image_frames, pattern="^toggle_image_frames$"),
                CallbackQueryHandler(video_bot.toggle_image_filters, pattern="^toggle_image_filters$"),
                CallbackQueryHandler(video_bot.toggle_image_rotation, pattern="^toggle_image_rotation$"),
                CallbackQueryHandler(video_bot.choose_image_size_menu, pattern="^choose_image_size$"),
                CallbackQueryHandler(video_bot.start_image_processing, pattern="^start_image_processing$"),
                CallbackQueryHandler(video_bot.restart_process, pattern="^restart_process$"),
                CommandHandler('start', video_bot.start),  # Добавляем /start в IMAGE_PARAMETERS_MENU
                CommandHandler('help', video_bot.help_command)  # Добавляем /help в IMAGE_PARAMETERS_MENU
            ],
            PARAMETERS_MENU: [
                CallbackQueryHandler(video_bot.choose_copies_menu, pattern="^choose_copies$"),
                CallbackQueryHandler(video_bot.toggle_frames, pattern="^toggle_frames$"),
                CallbackQueryHandler(video_bot.toggle_resolution, pattern="^toggle_resolution$"),
                CallbackQueryHandler(video_bot.toggle_compression, pattern="^toggle_compression$"),
                CallbackQueryHandler(video_bot.start_final_processing, pattern="^start_processing$"),
                CallbackQueryHandler(video_bot.restart_process, pattern="^restart_process$"),
                CommandHandler('start', video_bot.start),  # Добавляем /start в PARAMETERS_MENU
                CommandHandler('help', video_bot.help_command)  # Добавляем /help в PARAMETERS_MENU
            ],
            CHOOSING_COPIES: [
                CallbackQueryHandler(video_bot.choose_copies, pattern="^copies_[136]$"),
                CallbackQueryHandler(video_bot.show_parameters_menu, pattern="^back_to_parameters$"),
                CommandHandler('start', video_bot.start),  # Добавляем /start в CHOOSING_COPIES
                CommandHandler('help', video_bot.help_command)  # Добавляем /help в CHOOSING_COPIES
            ],
            CHOOSING_FRAMES: [
                CallbackQueryHandler(video_bot.choose_frames, pattern="^frames_(yes|no)$"),
                CallbackQueryHandler(video_bot.back_to_copies, pattern="^back_to_copies$"),
                CallbackQueryHandler(video_bot.restart_process, pattern="^restart_process$"),
                CommandHandler('start', video_bot.start),  # Добавляем /start в CHOOSING_FRAMES
                CommandHandler('help', video_bot.help_command)  # Добавляем /help в CHOOSING_FRAMES
            ],
            CHOOSING_RESOLUTION: [
                CallbackQueryHandler(video_bot.choose_resolution, pattern="^resolution_(yes|no)$"),
                CallbackQueryHandler(video_bot.back_to_frames, pattern="^back_to_frames$"),
                CallbackQueryHandler(video_bot.restart_process, pattern="^restart_process$"),
                CommandHandler('start', video_bot.start),  # Добавляем /start в CHOOSING_RESOLUTION
                CommandHandler('help', video_bot.help_command)  # Добавляем /help в CHOOSING_RESOLUTION
            ],
            CHOOSING_COMPRESSION: [
                CallbackQueryHandler(video_bot.choose_compression, pattern="^compress_(yes|no)$"),
                CallbackQueryHandler(video_bot.back_to_resolution, pattern="^back_to_resolution$"),
                CallbackQueryHandler(video_bot.restart_process, pattern="^restart_process$"),
                CommandHandler('start', video_bot.start),  # Добавляем /start в CHOOSING_COMPRESSION
                CommandHandler('help', video_bot.help_command)  # Добавляем /help в CHOOSING_COMPRESSION
            ],
            CHOOSING_IMAGE_COPIES: [
                CallbackQueryHandler(video_bot.choose_image_copies, pattern="^image_copies_[136]$"),
                CallbackQueryHandler(video_bot.show_image_parameters_menu, pattern="^back_to_image_parameters$"),
                CommandHandler('start', video_bot.start),  # Добавляем /start в CHOOSING_IMAGE_COPIES
                CommandHandler('help', video_bot.help_command)  # Добавляем /help в CHOOSING_IMAGE_COPIES
            ],
            CHOOSING_IMAGE_SIZE: [
                CallbackQueryHandler(video_bot.choose_image_size, pattern="^image_size_"),
                CallbackQueryHandler(video_bot.show_image_parameters_menu, pattern="^back_to_image_parameters$"),
                CommandHandler('start', video_bot.start),  # Добавляем /start в CHOOSING_IMAGE_SIZE
                CommandHandler('help', video_bot.help_command)  # Добавляем /help в CHOOSING_IMAGE_SIZE
            ]
        },
        fallbacks=[
            CommandHandler('start', video_bot.start),  # Добавляем /start в fallbacks для всех состояний
            CommandHandler('help', video_bot.help_command)  # Добавляем /help в fallbacks для всех состояний
        ]
    )
    
    # Добавляем обработчики
    application.add_handler(conv_handler)
    
    # Добавляем отдельный обработчик /start для случаев вне разговора
    application.add_handler(CommandHandler('start', video_bot.start))
    
    # Добавляем обработчик команды /help
    application.add_handler(CommandHandler('help', video_bot.help_command))
    
    # Добавляем админские команды
    application.add_handler(CommandHandler('adminstats', video_bot.admin_stats))
    application.add_handler(CommandHandler('userstats', video_bot.user_stats))
    application.add_handler(CommandHandler('adminhelp', video_bot.admin_help))
    
    # Запускаем бота
    logger.info("Бот запущен")
    application.run_polling()

if __name__ == '__main__':
    main()