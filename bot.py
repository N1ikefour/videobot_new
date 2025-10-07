import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from config import BOT_TOKEN
from video_processor import VideoProcessor, process_video_copy_new

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
WAITING_FOR_VIDEO, CHOOSING_COPIES, CHOOSING_FRAMES, CHOOSING_RESOLUTION, CHOOSING_COMPRESSION = range(5)

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
        """Обработчик команды /start - приветствие пользователя"""
        user = update.effective_user
        welcome_text = (
            f"Привет, {user.first_name}! 👋\n\n"
            "🎬 **Бот для уникализации видео**\n\n"
            "📋 **Как пользоваться:**\n"
            "1️⃣ Отправьте мне видеофайл (до 50 МБ)\n"
            "2️⃣ Нажмите кнопку 'Уникализировать видео'\n"
            "3️⃣ Выберите количество копий (1-5)\n"
            "4️⃣ Выберите, добавлять ли цветные рамки\n"
            "5️⃣ Выберите уровень сжатия\n"
            "6️⃣ Дождитесь обработки и получите уникальные копии!\n\n"
            "⚡ **Что делает бот:**\n"
            "• Изменяет скорость воспроизведения\n"
            "• Добавляет цветные рамки (по желанию)\n"
            "• Корректирует яркость и контраст\n"
            "• Поворачивает видео на небольшой угол\n"
            "• Добавляет едва заметный шум\n\n"
            "⏱️ **Время обработки:** ~2-3 минуты на копию\n"
        )
        
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
        return ConversationHandler.END

    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик получения видео от пользователя"""
        user_id = update.effective_user.id
        
        if update.message.video:
            # Сохраняем информацию о видео
            video = update.message.video
            self.user_data[user_id] = {
                'video_file_id': video.file_id,
                'video_file_name': f"video_{user_id}_{video.file_unique_id}.mp4"
            }
            
            # Создаем кнопку для уникализации
            keyboard = [[InlineKeyboardButton("🎬 Уникализировать видео", callback_data="start_processing")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Видео получено! ✅\nНажмите кнопку ниже для начала обработки:",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("Пожалуйста, отправьте видеофайл.")

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
            [InlineKeyboardButton("2 копии", callback_data="copies_2")],
            [InlineKeyboardButton("3 копии", callback_data="copies_3")]
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
                [InlineKeyboardButton("2 копии", callback_data="copies_2")],
                [InlineKeyboardButton("3 копии", callback_data="copies_3")]
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
        """Выбор количества копий"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        copies = int(query.data.split('_')[1])
        self.user_data[user_id]['copies'] = copies
        
        # Создаем кнопки для выбора рамок
        keyboard = [
            [InlineKeyboardButton("✅ Добавить рамки", callback_data="frames_yes")],
            [InlineKeyboardButton("❌ Без рамок", callback_data="frames_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"Выбрано копий: {copies}\n\nВыберите опцию рамок:",
            reply_markup=reply_markup
        )
        return CHOOSING_FRAMES

    async def choose_frames(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор добавления рамок"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        add_frames = query.data.split('_')[1] == 'yes'
        self.user_data[user_id]['add_frames'] = add_frames
        
        # Создаем кнопки для выбора разрешения
        keyboard = [
            [InlineKeyboardButton("📐 Изменить разрешение", callback_data="resolution_yes")],
            [InlineKeyboardButton("🎯 Оставить оригинальное", callback_data="resolution_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        frames_text = "с рамками" if add_frames else "без рамок"
        await query.edit_message_text(
            f"Выбрано: {frames_text}\n\nИзменить разрешение видео?",
            reply_markup=reply_markup
        )
        return CHOOSING_RESOLUTION

    async def choose_resolution(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор изменения разрешения"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        change_resolution = query.data.split('_')[1] == 'yes'
        self.user_data[user_id]['change_resolution'] = change_resolution
        
        # Создаем кнопки для выбора сжатия
        keyboard = [
            [InlineKeyboardButton("🗜️ Сжать видео", callback_data="compress_yes")],
            [InlineKeyboardButton("📹 Не сжимать", callback_data="compress_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        resolution_text = "изменить разрешение" if change_resolution else "оригинальное разрешение"
        await query.edit_message_text(
            f"Выбрано: {resolution_text}\n\nВыберите опцию сжатия:",
            reply_markup=reply_markup
        )
        return CHOOSING_COMPRESSION

    async def choose_compression(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор сжатия и запуск неблокирующей обработки"""
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
                query.message.chat_id
            )
        )
        
        # Сохраняем задачу для возможной отмены
        self.active_processing_tasks[user_id] = task
        
        # Сразу возвращаем управление боту
        return ConversationHandler.END

    async def _process_video_async(self, user_id: int, user_settings: dict, 
                                 processing_message, context, chat_id: int):
        """Асинхронная обработка видео с промежуточными обновлениями"""
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
                os.remove(input_path)
                
                # Финальное сообщение
                await processing_message.edit_text(
                    f"✅ Обработка завершена!\n"
                    f"📹 Отправлено {len(processed_videos)} уникальных копий\n\n"
                    "Отправьте новое видео для обработки или используйте /start"
                )
                
            except Exception as e:
                logger.error(f"Ошибка при обработке видео: {e}")
                try:
                    await processing_message.edit_text(
                        f"❌ Произошла ошибка при обработке видео: {str(e)}\n\n"
                        "Попробуйте еще раз или отправьте другое видео."
                    )
                except:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ Произошла ошибка при обработке видео: {str(e)}\n\n"
                             "Попробуйте еще раз или отправьте другое видео."
                    )
            finally:
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
                input_path, output_path, i, add_frames, compress, change_resolution
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
        while True:
            try:
                await asyncio.sleep(3)  # Обновляем каждые 3 секунды
                dots = (dots + 1) % 4
                animation = "." * dots
                
                await processing_message.edit_text(
                    f"🔄 Обработка видео{animation}\n"
                    f"📊 Обрабатываю {total_copies} копий параллельно\n\n"
                    f"⚡ Это быстрее в {total_copies}x раз!\n"
                    f"⏳ Пожалуйста, подождите..."
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка при обновлении статуса: {e}")
                break

    async def _process_single_copy(self, input_path: str, output_path: str, 
                                 copy_index: int, add_frames: bool, compress: bool, change_resolution: bool):
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
                    input_path, output_path, copy_index, add_frames, compress, change_resolution
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
                                  copy_index: int, add_frames: bool, compress: bool, change_resolution: bool):
        """Обертка для функции обработки видео"""
        from video_processor import process_video_copy_new
        
        # Получаем абсолютные пути
        abs_input_path = os.path.abspath(input_path)
        abs_output_path = os.path.abspath(output_path)
        
        # Создаем директорию для выходного файла если не существует
        os.makedirs(os.path.dirname(abs_output_path), exist_ok=True)
        
        # Вызываем функцию обработки
        return process_video_copy_new(abs_input_path, abs_output_path, copy_index, add_frames, compress, change_resolution)

    def _read_video_file(self, video_path: str):
        """Синхронная функция для чтения видеофайла"""
        with open(video_path, 'rb') as video_file:
            return video_file.read()

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена операции"""
        user_id = update.effective_user.id
        if user_id in self.user_data:
            del self.user_data[user_id]
        
        await update.message.reply_text("Операция отменена.")
        return ConversationHandler.END

def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        print("Ошибка: BOT_TOKEN не найден в переменных окружения!")
        return
    
    # Создаем экземпляр бота
    bot = VideoBot()
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Создаем ConversationHandler для обработки видео
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(bot.start_processing, pattern="^start_processing$")],
        states={
            CHOOSING_COPIES: [CallbackQueryHandler(bot.choose_copies, pattern="^copies_")],
            CHOOSING_FRAMES: [CallbackQueryHandler(bot.choose_frames, pattern="^frames_")],
            CHOOSING_RESOLUTION: [CallbackQueryHandler(bot.choose_resolution, pattern="^resolution_")],
            CHOOSING_COMPRESSION: [CallbackQueryHandler(bot.choose_compression, pattern="^compress_")],
        },
        fallbacks=[CommandHandler("cancel", bot.cancel)],
        per_user=True,  # Важно для поддержки множественных пользователей
        per_message=False  # Отключаем отслеживание per_message для CallbackQueryHandler
    )
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(MessageHandler(filters.VIDEO, bot.handle_video))
    application.add_handler(conv_handler)
    
    # Запускаем бота
    print("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()