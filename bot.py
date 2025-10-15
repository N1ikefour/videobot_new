import logging
import os
import asyncio
import time
import gc
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from config import BOT_TOKEN
from video_processor import VideoProcessor, process_video_copy_new
from database_postgres import DatabaseManager

# Создаем экземпляр менеджера БД
db_manager = DatabaseManager()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
MAIN_MENU, WAITING_FOR_VIDEO, PARAMETERS_MENU, CHOOSING_COPIES, CHOOSING_FRAMES, CHOOSING_RESOLUTION, CHOOSING_COMPRESSION = range(7)

class VideoBot:
    def __init__(self):
        self.video_processor = VideoProcessor()
        self.user_data = {}
        # Добавляем словарь для отслеживания активных задач обработки
        self.active_processing_tasks = {}
        # Семафор для ограничения количества одновременных обработок видео
        # Для конфигурации: 16 vCPU, 32 GB RAM
        # Оптимальное значение: 8 одновременных обработок
        self.processing_semaphore = asyncio.Semaphore(10)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user_name = update.effective_user.first_name
        user_id = update.effective_user.id
        username = update.effective_user.username
        last_name = update.effective_user.last_name
        
        # Добавляем или обновляем пользователя в базе данных
        db_manager.add_or_update_user(
            user_id=user_id,
            username=username,
            first_name=user_name,
            last_name=last_name
        )
        
        # Логируем активность пользователя
        db_manager.log_user_activity(user_id, 'start_command')
        
        # Проверяем, не забанен ли пользователь
        if db_manager.is_user_banned(user_id):
            await update.message.reply_text(
                "❌ Ваш аккаунт заблокирован.\n"
                "Обратитесь к администратору для разблокировки."
            )
            return ConversationHandler.END
        
        # Очищаем данные пользователя при старте
        if user_id in self.user_data:
            del self.user_data[user_id]
        
        welcome_text = (
            f"👋 **Привет, {user_name}!**\n\n"
            "**Бот для уникализации видео** 🚀\n\n"
            "📋 **Инструкция:**\n"
            "1️⃣ Нажмите кнопку 'Уникализировать видео'\n"
            "2️⃣ Отправьте видеофайл (до 50 МБ)\n"
            "3️⃣ Выберите параметры обработки\n"
            "4️⃣ Получите уникальные копии!\n\n"
            "Готовы начать? 👇"
        )
        
        # Создаем главное меню с одной кнопкой внизу экрана
        keyboard = [[KeyboardButton("🎬 Уникализировать видео")]]
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
            
            "📋 **Требования к видео:**\n"
            "• Размер: до 50 МБ\n"
            "• Формат: MP4, AVI, MOV, MKV\n"
            "• Длительность: до 10 минут\n\n"
            
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

    async def main_menu_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик главного меню"""
        text = update.message.text
        
        if text == "🎬 Уникализировать видео":
            await update.message.reply_text(
                "📹 **Отправьте видеофайл для обработки**\n\n"
                "📋 **Требования:**\n"
                "• Размер файла: до 50 МБ\n"
                "• Формат: MP4, AVI, MOV, MKV\n"
                "• Длительность: до 10 минут\n\n"
                "Просто прикрепите видео к сообщению 👇",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardRemove()
            )
            return WAITING_FOR_VIDEO

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
        
        # Проверяем, не забанен ли пользователь
        if db_manager.is_user_banned(user_id):
            await update.message.reply_text(
                "❌ Ваш аккаунт заблокирован.\n"
                "Обратитесь к администратору для разблокировки."
            )
            return ConversationHandler.END
        
        if update.message.video:
            video = update.message.video
            
            # Логируем загрузку видео
            db_manager.log_user_activity(
                user_id, 
                'video_upload', 
                {
                    'file_size': video.file_size,
                    'duration': video.duration,
                    'file_id': video.file_id
                }
            )
            
            # Сохраняем информацию о видео
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
                "Поддерживаемые форматы: MP4, AVI, MOV, MKV"
            )
            return WAITING_FOR_VIDEO

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
        start_time = time.time()  # Засекаем время начала обработки
        
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
                await processing_message.edit_text(
                    f"🔄 Обработка видео...\n"
                    f"📊 Параметры: {copies} копий\n\n"
                    f"📥 Скачиваю видео..."
                )
                
                video_file = await context.bot.get_file(video_file_id)
                input_path = f"temp/input_{user_id}.mp4"
                
                # Создаем директорию temp если не существует
                os.makedirs("temp", exist_ok=True)
                
                await video_file.download_to_drive(input_path)
                
                # Проверяем что файл был скачан
                if not os.path.exists(input_path):
                    logger.error(f"Файл {input_path} не был создан после скачивания")
                    await processing_message.edit_text("❌ Ошибка при скачивании видео. Попробуйте еще раз.")
                    return
                
                file_size = os.path.getsize(input_path)
                logger.info(f"Файл {input_path} успешно скачан, размер: {file_size} байт")
                
                # Обновляем статус
                await processing_message.edit_text(
                    f"🔄 Обработка видео...\n"
                    f"📊 Параметры: {copies} копий\n\n"
                    f"🎬 Создаю уникальные копии..."
                )
                
                # Создаем задачу обработки с callback для обновления прогресса
                processed_videos = await self._process_with_progress_updates(
                    input_path, user_id, copies, add_frames, compress, change_resolution,
                    processing_message
                )
                
                # Обновляем сообщение
                await processing_message.edit_text(
                    f"📤 Отправляю обработанные видео...\n"
                    f"✅ Создано {len(processed_videos)} уникальных копий"
                )
                
                # Отправляем обработанные видео
                for i, video_path in enumerate(processed_videos, 1):
                    # Обновляем прогресс отправки
                    await processing_message.edit_text(
                        f"📤 Отправляю видео {i}/{len(processed_videos)}...\n"
                        f"✅ Создано {len(processed_videos)} уникальных копий"
                    )
                    
                    # Используем asyncio.to_thread для неблокирующего чтения файла
                    video_data = await asyncio.to_thread(self._read_video_file, video_path)
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=video_data,
                        caption=f"🎬 Уникальная копия #{i}/{copies}"
                    )
                    # Удаляем временный файл
                    os.remove(video_path)
                
                # Удаляем входной файл
                if input_path and os.path.exists(input_path):
                    os.remove(input_path)
                
                # Логируем успешную обработку видео
                db_manager.log_user_activity(
                    user_id, 
                    'video_processed', 
                    {
                        'copies_created': len(processed_videos),
                        'processing_time': time.time() - start_time,
                        'settings': user_settings
                    }
                )
                
                # Финальное сообщение о завершении
                await processing_message.edit_text(
                    f"✅ Обработка завершена!\n"
                    f"📹 Отправлено {len(processed_videos)} уникальных копий",
                    parse_mode='Markdown'
                )
                
                # Отправляем отдельное сообщение с предложением прикрепить следующее видео
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="📹 **Прикрепите следующее видео**\n\n"
                         "📋 **Требования:**\n"
                         "• Размер файла: до 50 МБ\n"
                         "• Формат: MP4, AVI, MOV, MKV\n"
                         "• Длительность: до 10 минут\n\n"
                         "Просто прикрепите видео к сообщению 👇",
                    parse_mode='Markdown'
                )
                
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
                    await processing_message.edit_text(
                        f"❌ Произошла ошибка при обработке видео: {str(e)}\n\n"
                        "📹 **Прикрепите следующее видео**\n\n"
                        "📋 **Требования:**\n"
                        "• Размер файла: до 50 МБ\n"
                        "• Формат: MP4, AVI, MOV, MKV\n"
                        "• Длительность: до 10 минут\n\n"
                        "Просто прикрепите видео к сообщению 👇",
                        parse_mode='Markdown'
                    )
                except:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ Произошла ошибка при обработке видео: {str(e)}\n\n"
                             "📹 **Прикрепите следующее видео**\n\n"
                             "📋 **Требования:**\n"
                             "• Размер файла: до 50 МБ\n"
                             "• Формат: MP4, AVI, MOV, MKV\n"
                             "• Длительность: до 10 минут\n\n"
                             "Просто прикрепите видео к сообщению 👇",
                        parse_mode='Markdown'
                    )
                
                # Устанавливаем состояние ожидания видео через context
                context.user_data['conversation_state'] = WAITING_FOR_VIDEO
            finally:
                # Очищаем временные файлы при отмене
                if input_path and os.path.exists(input_path):
                    try:
                        os.remove(input_path)
                        logger.info(f"Удален входной файл: {input_path}")
                    except Exception as e:
                        logger.error(f"Ошибка при удалении входного файла {input_path}: {e}")
                
                # Очищаем обработанные файлы при отмене
                for video_path in processed_videos:
                    if os.path.exists(video_path):
                        try:
                            os.remove(video_path)
                            logger.info(f"Удален обработанный файл: {video_path}")
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
        await processing_message.edit_text(
            f"🔄 Обработка видео...\n"
            f"📊 Создаю {copies} копий параллельно\n\n"
            f"🚀 Запускаю обработку всех копий одновременно..."
        )
        
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
                        await processing_message.edit_text(new_text)
                        last_text = new_text
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
            timeout_seconds = max(300, int(file_size * 30))  # Минимум 5 минут
            
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
            logger.error(f"Таймаут при создании копии {copy_index+1}")
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
            "• Формат: MP4, AVI, MOV, MKV\n"
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
            "• Формат: MP4, AVI, MOV, MKV\n"
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

    # Админские команды
    async def admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать статистику пользователей (только для админов)"""
        user_id = update.effective_user.id
        
        # Проверяем, является ли пользователь админом
        if not db_manager.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав администратора")
            return
        
        try:
            stats = db_manager.get_general_stats()
            
            stats_text = f"""📊 **Статистика бота**

👥 **Пользователи:**
• Всего: {stats['total_users']}
• Активных за 24ч: {stats['active_24h']}
• Активных за 7 дней: {stats['active_7d']}
• Активных за 30 дней: {stats['active_30d']}

🎬 **Видео:**
• Всего обработано: {stats['total_videos']}
• За сегодня: {stats['videos_today']}
• За неделю: {stats['videos_week']}

🚫 **Заблокированные:** {stats['banned_users']}
"""
            
            await update.message.reply_text(stats_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            await update.message.reply_text("❌ Ошибка при получении статистики")

    async def admin_ban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Заблокировать пользователя (только для админов)"""
        user_id = update.effective_user.id
        
        # Проверяем, является ли пользователь админом
        if not db_manager.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав администратора")
            return
        
        # Проверяем аргументы команды
        if not context.args:
            await update.message.reply_text(
                "❌ Укажите ID пользователя для блокировки\n"
                "Пример: `/admin_ban 123456789`",
                parse_mode='Markdown'
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Нарушение правил"
            
            # Проверяем, не пытается ли админ заблокировать себя
            if target_user_id == user_id:
                await update.message.reply_text("❌ Вы не можете заблокировать себя")
                return
            
            # Проверяем, не является ли цель тоже админом
            if db_manager.is_admin(target_user_id):
                await update.message.reply_text("❌ Нельзя заблокировать другого администратора")
                return
            
            # Блокируем пользователя
            success = db_manager.ban_user(target_user_id, user_id, reason)
            
            if success:
                await update.message.reply_text(
                    f"✅ Пользователь {target_user_id} заблокирован\n"
                    f"📝 Причина: {reason}"
                )
                
                # Логируем действие админа
                db_manager.log_admin_action(user_id, 'ban_user', {
                    'target_user_id': target_user_id,
                    'reason': reason
                })
            else:
                await update.message.reply_text("❌ Ошибка при блокировке пользователя")
                
        except ValueError:
            await update.message.reply_text("❌ Неверный ID пользователя")
        except Exception as e:
            logger.error(f"Ошибка при блокировке пользователя: {e}")
            await update.message.reply_text("❌ Ошибка при блокировке пользователя")

    async def admin_unban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Разблокировать пользователя (только для админов)"""
        user_id = update.effective_user.id
        
        # Проверяем, является ли пользователь админом
        if not db_manager.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав администратора")
            return
        
        # Проверяем аргументы команды
        if not context.args:
            await update.message.reply_text(
                "❌ Укажите ID пользователя для разблокировки\n"
                "Пример: `/admin_unban 123456789`",
                parse_mode='Markdown'
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            
            # Разблокируем пользователя
            success = db_manager.unban_user(target_user_id, user_id)
            
            if success:
                await update.message.reply_text(f"✅ Пользователь {target_user_id} разблокирован")
                
                # Логируем действие админа
                db_manager.log_admin_action(user_id, 'unban_user', {
                    'target_user_id': target_user_id
                })
            else:
                await update.message.reply_text("❌ Ошибка при разблокировке пользователя")
                
        except ValueError:
            await update.message.reply_text("❌ Неверный ID пользователя")
        except Exception as e:
            logger.error(f"Ошибка при разблокировке пользователя: {e}")
            await update.message.reply_text("❌ Ошибка при разблокировке пользователя")

    async def admin_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список всех пользователей (только для админов)"""
        user_id = update.effective_user.id
        
        # Проверяем, является ли пользователь админом
        if not db_manager.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав администратора")
            return
        
        try:
            # Получаем параметры пагинации
            page = 1
            if context.args and context.args[0].isdigit():
                page = int(context.args[0])
            
            limit = 10
            offset = (page - 1) * limit
            
            users = db_manager.get_all_users(limit, offset)
            
            if not users:
                await update.message.reply_text("👥 Пользователи не найдены")
                return
            
            users_text = f"👥 **Пользователи (страница {page}):**\n\n"
            
            for user in users:
                status = "🚫 Заблокирован" if user['is_banned'] else "✅ Активен"
                users_text += f"**ID:** `{user['user_id']}`\n"
                users_text += f"**Имя:** {user['first_name'] or 'Не указано'}\n"
                users_text += f"**Username:** @{user['username'] or 'Не указан'}\n"
                users_text += f"**Статус:** {status}\n"
                users_text += f"**Видео:** {user['videos_processed']}\n"
                users_text += f"**Регистрация:** {user['created_at'][:10]}\n"
                users_text += "─────────────\n"
            
            users_text += f"\n📄 Страница {page} | Используйте `/admin_users {page + 1}` для следующей страницы"
            
            await update.message.reply_text(users_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка пользователей: {e}")
            await update.message.reply_text("❌ Ошибка при получении списка пользователей")

    async def admin_active_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать активных пользователей (только для админов)"""
        user_id = update.effective_user.id
        
        # Проверяем, является ли пользователь админом
        if not db_manager.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав администратора")
            return
        
        try:
            # Получаем период (по умолчанию 24 часа)
            hours = 24
            if context.args and context.args[0].isdigit():
                hours = int(context.args[0])
                if hours > 720:  # Максимум 30 дней
                    hours = 720
            
            active_users = db_manager.get_active_users(hours)
            
            if not active_users:
                await update.message.reply_text(f"👥 Активных пользователей за последние {hours} часов не найдено")
                return
            
            users_text = f"👥 **Активные пользователи за {hours}ч:**\n\n"
            
            for user in active_users[:20]:  # Показываем только первые 20
                users_text += f"**ID:** `{user['user_id']}`\n"
                users_text += f"**Имя:** {user['first_name'] or 'Не указано'}\n"
                users_text += f"**Последняя активность:** {user['last_activity'][:16]}\n"
                users_text += f"**Действий:** {user['activity_count']}\n"
                users_text += "─────────────\n"
            
            if len(active_users) > 20:
                users_text += f"\n... и еще {len(active_users) - 20} пользователей"
            
            users_text += f"\n📊 Всего активных: {len(active_users)}"
            
            await update.message.reply_text(users_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Ошибка при получении активных пользователей: {e}")
            await update.message.reply_text("❌ Ошибка при получении активных пользователей")

    async def admin_add_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Назначить пользователя администратором (только для супер-админов)"""
        user_id = update.effective_user.id
        
        # Проверяем, является ли пользователь супер-админом (первый админ в системе)
        # Для простоты, можно захардкодить ID создателя бота
        SUPER_ADMIN_ID = 454002721  # Замените на ваш Telegram ID
        
        if user_id != SUPER_ADMIN_ID:
            await update.message.reply_text("❌ Только супер-администратор может назначать админов")
            return
        
        # Проверяем аргументы команды
        if not context.args:
            await update.message.reply_text(
                "❌ Укажите ID пользователя для назначения админом\n"
                "Пример: `/admin_add_admin 123456789`",
                parse_mode='Markdown'
            )
            return
        
        try:
            target_user_id = int(context.args[0])
            
            # Назначаем админа
            success = db_manager.add_admin(target_user_id, user_id)
            
            if success:
                await update.message.reply_text(f"✅ Пользователь {target_user_id} назначен администратором")
                
                # Логируем действие
                db_manager.log_admin_action(user_id, 'make_admin', {
                    'target_user_id': target_user_id
                })
            else:
                await update.message.reply_text("❌ Ошибка при назначении администратора")
                
        except ValueError:
            await update.message.reply_text("❌ Неверный ID пользователя")
        except Exception as e:
            logger.error(f"Ошибка при назначении админа: {e}")
            await update.message.reply_text("❌ Ошибка при назначении администратора")

    async def admin_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список админских команд"""
        user_id = update.effective_user.id
        
        # Проверяем, является ли пользователь админом
        if not db_manager.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав администратора")
            return
        
        help_text = """🔧 **Команды администратора:**

📊 `/admin_stats` - Общая статистика бота
👥 `/admin_users [страница]` - Список всех пользователей
🟢 `/admin_active_users [часы]` - Активные пользователи
🚫 `/admin_ban <ID> [причина]` - Заблокировать пользователя
✅ `/admin_unban <ID>` - Разблокировать пользователя
❓ `/admin_help` - Эта справка

**Примеры:**
• `/admin_users 2` - 2-я страница пользователей
• `/admin_active_users 48` - активные за 48 часов
• `/admin_ban 123456789 спам` - заблокировать за спам
"""
        
        await update.message.reply_text(help_text, parse_mode='Markdown')

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
    
    # Админские команды
    application.add_handler(CommandHandler("admin_stats", video_bot.admin_stats))
    application.add_handler(CommandHandler("admin_ban", video_bot.admin_ban))
    application.add_handler(CommandHandler("admin_unban", video_bot.admin_unban))
    application.add_handler(CommandHandler("admin_users", video_bot.admin_users))
    application.add_handler(CommandHandler("admin_active_users", video_bot.admin_active_users))
    application.add_handler(CommandHandler("admin_add_admin", video_bot.admin_add_admin))
    application.add_handler(CommandHandler("admin_help", video_bot.admin_help))
    
    # Запускаем бота
    logger.info("Бот запущен")
    application.run_polling()

if __name__ == '__main__':
    main()