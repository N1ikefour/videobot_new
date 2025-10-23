"""
Дополнительные обработчики для работы с изображениями
"""

import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from image_processor import ImageProcessor
from database import DatabaseManager

logger = logging.getLogger(__name__)

class ImageHandlers:
    def __init__(self, image_processor: ImageProcessor, db_manager: DatabaseManager):
        self.image_processor = image_processor
        self.db_manager = db_manager

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
        
        return "CHOOSING_IMAGE_COPIES"

    async def toggle_image_frames(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переключает параметр добавления рамок для изображений"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        if user_id in context.bot_data.get('user_data', {}):
            current_value = context.bot_data['user_data'][user_id].get('add_frames', False)
            context.bot_data['user_data'][user_id]['add_frames'] = not current_value
        
        # Возвращаемся к меню параметров изображений
        from bot import VideoBot
        bot_instance = VideoBot()
        return await bot_instance.show_image_parameters_menu(update, context)

    async def toggle_image_filters(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переключает параметр добавления фильтров для изображений"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        if user_id in context.bot_data.get('user_data', {}):
            current_value = context.bot_data['user_data'][user_id].get('add_filters', False)
            context.bot_data['user_data'][user_id]['add_filters'] = not current_value
        
        # Возвращаемся к меню параметров изображений
        from bot import VideoBot
        bot_instance = VideoBot()
        return await bot_instance.show_image_parameters_menu(update, context)

    async def toggle_image_rotation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переключает параметр добавления поворотов для изображений"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        if user_id in context.bot_data.get('user_data', {}):
            current_value = context.bot_data['user_data'][user_id].get('add_rotation', False)
            context.bot_data['user_data'][user_id]['add_rotation'] = not current_value
        
        # Возвращаемся к меню параметров изображений
        from bot import VideoBot
        bot_instance = VideoBot()
        return await bot_instance.show_image_parameters_menu(update, context)

    async def toggle_image_size(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переключает параметр изменения размера для изображений"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        if user_id in context.bot_data.get('user_data', {}):
            current_value = context.bot_data['user_data'][user_id].get('change_size', False)
            context.bot_data['user_data'][user_id]['change_size'] = not current_value
        
        # Возвращаемся к меню параметров изображений
        from bot import VideoBot
        bot_instance = VideoBot()
        return await bot_instance.show_image_parameters_menu(update, context)

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
            if user_id in context.bot_data.get('user_data', {}):
                context.bot_data['user_data'][user_id]['copies'] = copies
            
            # Возвращаемся к меню параметров изображений
            from bot import VideoBot
            bot_instance = VideoBot()
            return await bot_instance.show_image_parameters_menu(update, context)
        
        elif callback_data == "back_to_image_parameters":
            from bot import VideoBot
            bot_instance = VideoBot()
            return await bot_instance.show_image_parameters_menu(update, context)
        
        return "CHOOSING_IMAGE_COPIES"

    async def start_image_processing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запуск обработки изображения"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        if user_id not in context.bot_data.get('user_data', {}):
            await query.edit_message_text("❌ Данные сессии утеряны. Начните заново с /start")
            return "END"
        
        # Получаем все параметры
        user_settings = context.bot_data['user_data'][user_id]
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
            f"• Рамки: {frames_text}\n"
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
        if 'active_processing_tasks' not in context.bot_data:
            context.bot_data['active_processing_tasks'] = {}
        context.bot_data['active_processing_tasks'][user_id] = task
        
        # Возвращаем состояние ожидания изображения
        return "WAITING_FOR_IMAGE"

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
            
            # Обрабатываем изображение
            processed_images = await self.image_processor.process_image(
                input_path, user_id, copies, add_frames, add_filters, add_rotation, change_size
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
            context.user_data['conversation_state'] = "WAITING_FOR_IMAGE"
            
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
            context.user_data['conversation_state'] = "WAITING_FOR_IMAGE"
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
            if user_id in context.bot_data.get('user_data', {}):
                del context.bot_data['user_data'][user_id]
            if user_id in context.bot_data.get('active_processing_tasks', {}):
                del context.bot_data['active_processing_tasks'][user_id]

    def _read_image_file(self, image_path: str):
        """Синхронная функция для чтения изображения"""
        with open(image_path, 'rb') as image_file:
            return image_file.read()
