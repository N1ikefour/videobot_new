import os
import random
import asyncio
import logging
import time
import concurrent.futures
from multiprocessing import Process, Queue, Manager
from moviepy.editor import VideoFileClip, CompositeVideoClip
from PIL import Image, ImageDraw
import numpy as np
from config import OUTPUT_DIR, TEMP_DIR

# Настройка логирования
logger = logging.getLogger(__name__)

# Импортируем cv2 только если он нужен, иначе используем альтернативы
try:
    import cv2
    CV2_AVAILABLE = True
    logger.info("OpenCV успешно загружен")
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV недоступен, используем альтернативные методы обработки")

class VideoProcessor:
    def __init__(self):
        self.frame_colors = [
            (255, 0, 0),    # Красный
            (0, 255, 0),    # Зеленый
            (0, 0, 255),    # Синий
            (255, 255, 0),  # Желтый
            (255, 0, 255),  # Пурпурный
            (0, 255, 255),  # Голубой
        ]
        # Убираем ProcessPoolExecutor чтобы избежать проблем с pickle

    async def process_video(self, input_path: str, user_id: int, copies: int, add_frames: bool, compress: bool):
        """Основная функция обработки видео"""
        logger.info(f"=== НАЧАЛО ОБРАБОТКИ ВИДЕО ===")
        logger.info(f"Пользователь: {user_id}")
        logger.info(f"Входной файл: {input_path}")
        logger.info(f"Количество копий: {copies}")
        logger.info(f"Добавить рамки: {add_frames}")
        logger.info(f"Сжатие: {compress}")
        
        processed_videos = []
        
        try:
            # Проверяем существование входного файла
            if not os.path.exists(input_path):
                logger.error(f"Входной файл не найден: {input_path}")
                raise FileNotFoundError(f"Файл {input_path} не найден")
            
            logger.info(f"Входной файл найден: {input_path}")
            file_size = os.path.getsize(input_path) / (1024 * 1024)  # MB
            logger.info(f"Размер файла: {file_size:.2f} MB")
            
            for i in range(copies):
                logger.info(f"--- Обработка копии {i+1}/{copies} ---")
                output_path = f"{OUTPUT_DIR}/processed_{user_id}_{i+1}.mp4"
                
                # Увеличиваем таймаут для больших файлов
                timeout_seconds = max(300, int(file_size * 30))  # Минимум 5 минут, +30 сек на MB
                logger.info(f"Установлен таймаут: {timeout_seconds} секунд")
                
                try:
                    # Проверяем что входной файл существует перед передачей в процесс
                    if not os.path.exists(input_path):
                        raise FileNotFoundError(f"Файл {input_path} не найден")
                    
                    # Получаем абсолютные пути для передачи в процесс
                    abs_input_path = os.path.abspath(input_path)
                    abs_output_path = os.path.abspath(output_path)
                    
                    # Создаем директорию для выходного файла если не существует
                    os.makedirs(os.path.dirname(abs_output_path), exist_ok=True)
                    
                    # Используем ThreadPoolExecutor для избежания проблем с pickle
                    loop = asyncio.get_event_loop()
                    await asyncio.wait_for(
                        loop.run_in_executor(
                            None,  # Используем стандартный ThreadPoolExecutor
                            process_video_copy,
                            abs_input_path, abs_output_path, i, add_frames, compress
                        ),
                        timeout=timeout_seconds
                    )
                    
                    if os.path.exists(output_path):
                        output_size = os.path.getsize(output_path) / (1024 * 1024)
                        logger.info(f"Копия {i+1} создана успешно. Размер: {output_size:.2f} MB")
                        processed_videos.append(output_path)
                    else:
                        logger.error(f"Файл копии {i+1} не был создан")
                        
                except asyncio.TimeoutError:
                    logger.error(f"Таймаут при создании копии {i+1} (превышено {timeout_seconds} секунд)")
                    raise Exception(f"Превышено время ожидания при обработке копии {i+1}")
                except Exception as e:
                    logger.error(f"Ошибка при создании копии {i+1}: {str(e)}")
                    raise
            
            logger.info(f"=== ОБРАБОТКА ЗАВЕРШЕНА ===")
            logger.info(f"Создано копий: {len(processed_videos)}")
            return processed_videos
            
        except Exception as e:
            logger.error(f"Критическая ошибка при обработке видео: {str(e)}")
            # Очищаем созданные файлы при ошибке
            for file_path in processed_videos:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        logger.info(f"Удален временный файл: {file_path}")
                    except:
                        pass
            raise

    def __del__(self):
        """Деструктор класса"""
        pass  # Больше нет process_executor для закрытия


# Глобальная функция для обработки видео в отдельном процессе
def process_video_copy(input_path: str, output_path: str, copy_index: int, add_frames: bool, compress: bool):
    """Функция для обработки видео в отдельном процессе (обходит GIL)"""
    import os
    import logging
    import gc
    import time
    from moviepy.editor import VideoFileClip
    
    # Настраиваем логирование для процесса
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    video = None
    modified_video = None
    temp_audio_file = None
    
    try:
        logger.info(f"Процесс {os.getpid()}: Начинаю обработку {input_path}")
        
        # Проверяем что входной файл существует
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Входной файл {input_path} не найден в процессе")
        
        # Создаем директорию для выходного файла если не существует
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # Загружаем видео
        logger.info(f"Процесс {os.getpid()}: Загружаю видео")
        video = VideoFileClip(input_path)
        
        # Применяем уникальные модификации
        logger.info(f"Процесс {os.getpid()}: Применяю модификации")
        modified_video = apply_unique_modifications(video, copy_index, add_frames)
        
        # Настройки сжатия
        if compress:
            codec = 'libx264'
            bitrate = '500k'
            audio_codec = 'aac'
        else:
            codec = 'libx264'
            bitrate = None
            audio_codec = 'aac'
        
        # Создаем уникальное имя для временного аудио файла
        temp_audio_file = f"temp-audio-{copy_index}-{int(time.time())}-{os.getpid()}.m4a"
        
        logger.info(f"Процесс {os.getpid()}: Сохраняю видео в {output_path}")
        
        # Отключаем verbose вывод MoviePy
        import moviepy.config as config
        try:
            config.FFMPEG_BINARY = config.try_download_binaries()
        except:
            pass  # Игнорируем ошибки конфигурации
        
        modified_video.write_videofile(
            output_path,
            codec=codec,
            bitrate=bitrate,
            audio_codec=audio_codec,
            temp_audiofile=temp_audio_file,
            remove_temp=True,
            verbose=False,
            logger=None
        )
        
        logger.info(f"Процесс {os.getpid()}: Обработка завершена успешно")
                
    except Exception as e:
        logger.error(f"Процесс {os.getpid()}: Ошибка при обработке видео: {e}")
        raise
        
    finally:
        # Принудительно закрываем все видео объекты
        try:
            if modified_video is not None:
                modified_video.close()
                del modified_video
        except:
            pass
            
        try:
            if video is not None:
                video.close()
                del video
        except:
            pass
        
        # Удаляем временный аудио файл если он остался
        if temp_audio_file and os.path.exists(temp_audio_file):
            try:
                time.sleep(0.5)  # Небольшая задержка
                os.remove(temp_audio_file)
                logger.info(f"Процесс {os.getpid()}: Удален временный аудио файл: {temp_audio_file}")
            except Exception as e:
                logger.warning(f"Процесс {os.getpid()}: Не удалось удалить временный аудио файл {temp_audio_file}: {e}")
        
        # Принудительная очистка памяти
        gc.collect()


def apply_unique_modifications(video, copy_index: int, add_frames: bool):
    """Применяет уникальные модификации к видео"""
    # Расширенная палитра цветов для рамок
    frame_colors = [
        (255, 0, 0),      # Красный
        (0, 255, 0),      # Зеленый  
        (0, 0, 255),      # Синий
        (255, 255, 0),    # Желтый
        (255, 0, 255),    # Пурпурный
        (0, 255, 255),    # Голубой
        (255, 128, 0),    # Оранжевый
        (128, 0, 255),    # Фиолетовый
        (255, 192, 203),  # Розовый
        (0, 128, 0),      # Темно-зеленый
        (128, 128, 0),    # Оливковый
        (0, 128, 128),    # Темно-голубой
        (128, 0, 0),      # Темно-красный
        (0, 0, 128),      # Темно-синий
        (255, 165, 0),    # Оранжево-красный
        (75, 0, 130),     # Индиго
        (238, 130, 238),  # Фиолетово-розовый
        (255, 20, 147),   # Темно-розовый
        (0, 191, 255),    # Ярко-голубой
        (50, 205, 50),    # Лайм-зеленый
        (255, 69, 0),     # Красно-оранжевый
        (138, 43, 226),   # Сине-фиолетовый
        (255, 215, 0),    # Золотой
        (220, 20, 60),    # Малиновый
        (32, 178, 170),   # Светло-морской
        (255, 105, 180),  # Ярко-розовый
        (124, 252, 0),    # Лайм
        (255, 99, 71),    # Томатный
        (72, 61, 139),    # Темно-синий сланец
        (255, 140, 0)     # Темно-оранжевый
    ]
    
    if add_frames:
        # Генерируем случайные параметры для уникальности
        import time
        import hashlib
        
        # Создаем уникальный seed на основе времени и copy_index
        current_time = int(time.time() * 1000000)  # Микросекунды для большей уникальности
        seed_string = f"{current_time}_{copy_index}_{random.randint(1, 999999)}"
        seed_hash = int(hashlib.md5(seed_string.encode()).hexdigest()[:8], 16)
        
        # Используем seed для генерации случайных параметров
        random.seed(seed_hash)
        
        # Случайный выбор цвета из расширенной палитры
        color = random.choice(frame_colors)
        
        # Случайная толщина рамки от 3 до 15 пикселей
        frame_thickness = random.randint(3, 15)
        
        logger.info(f"Копия {copy_index + 1}: цвет рамки {color}, толщина {frame_thickness}px")
        
        # Создаем цветную рамку
        frame_clip = add_frame_to_video(video, color, frame_thickness)
        return frame_clip
    else:
        # Просто изменяем яркость или контрастность
        brightness_factor = 1.0 + (copy_index * 0.05)  # Небольшое изменение яркости
        modified_video = video.fx(lambda clip: clip.multiply_volume(brightness_factor))
        return modified_video


def add_frame_to_video(video, color, thickness):
    """Добавляет цветную рамку к видео"""
    from moviepy.editor import ColorClip
    
    # Получаем размеры видео
    w, h = video.size
    
    # Создаем цветные полосы для рамки
    # Верхняя полоса
    top_frame = ColorClip(size=(w, thickness), color=color, duration=video.duration)
    # Нижняя полоса
    bottom_frame = ColorClip(size=(w, thickness), color=color, duration=video.duration)
    # Левая полоса
    left_frame = ColorClip(size=(thickness, h), color=color, duration=video.duration)
    # Правая полоса
    right_frame = ColorClip(size=(thickness, h), color=color, duration=video.duration)
    
    # Позиционируем рамки
    top_frame = top_frame.set_position(('center', 0))
    bottom_frame = bottom_frame.set_position(('center', h - thickness))
    left_frame = left_frame.set_position((0, 'center'))
    right_frame = right_frame.set_position((w - thickness, 'center'))
    
    # Создаем композитное видео с рамкой
    final_video = CompositeVideoClip([video, top_frame, bottom_frame, left_frame, right_frame])
    
    return final_video





    def cleanup_temp_files(self, user_id: int):
        """Очистка временных файлов пользователя"""
        try:
            # Удаляем временные файлы пользователя
            for filename in os.listdir(TEMP_DIR):
                if str(user_id) in filename:
                    file_path = os.path.join(TEMP_DIR, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
        except Exception as e:
            print(f"Ошибка при очистке временных файлов: {e}")

    def get_video_info(self, video_path: str):
        """Получение информации о видео"""
        try:
            clip = VideoFileClip(video_path)
            info = {
                'duration': clip.duration,
                'fps': clip.fps,
                'size': clip.size,
                'audio': clip.audio is not None
            }
            clip.close()
            return info
        except Exception as e:
            print(f"Ошибка при получении информации о видео: {e}")
            return None


def process_video_copy_new(input_path: str, output_path: str, copy_index: int, add_frames: bool, compress: bool, change_resolution: bool, user_id: int = None):
    """Обрабатывает одну копию видео - функция для использования в ProcessPoolExecutor"""
    video = None
    modified_video = None
    
    try:
        logger.info(f"Начинаю обработку копии {copy_index + 1}: {input_path} -> {output_path}")
        
        # Проверяем существование входного файла
        if not os.path.exists(input_path):
            logger.error(f"Входной файл не найден: {input_path}")
            return False
        
        # Создаем директорию для выходного файла
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Загружаем видео
        video = VideoFileClip(input_path)
        
        # Применяем уникальные модификации
        modified_video = apply_unique_modifications(video, copy_index, add_frames)
        
        # Изменяем разрешение если нужно
        if change_resolution:
            # Получаем текущие размеры
            original_width, original_height = modified_video.size
            
            # Всегда меняем на 1080x1920 (вертикальное видео для Stories/Reels)
            target_width, target_height = 1080, 1920
            
            # Проверяем, нужно ли изменение
            if original_width != target_width or original_height != target_height:
                modified_video = modified_video.resize((target_width, target_height))
                logger.info(f"Разрешение изменено с {original_width}x{original_height} на {target_width}x{target_height}")
            else:
                logger.info(f"Разрешение уже {target_width}x{target_height}, изменение не требуется")
        
        # Настройки сжатия
        if compress:
            codec_settings = {
                'codec': 'libx264',
                'bitrate': '1000k',
                'audio_codec': 'aac'
            }
        else:
            codec_settings = {
                'codec': 'libx264',
                'bitrate': '2000k',
                'audio_codec': 'aac'
            }
        
        # Создаем уникальное имя для временного аудиофайла
        temp_audio_name = f'temp-audio-{user_id}-{copy_index}.m4a' if user_id else f'temp-audio-{copy_index}.m4a'
        
        # Сохраняем видео
        modified_video.write_videofile(
            output_path,
            **codec_settings,
            temp_audiofile=temp_audio_name,
            remove_temp=True,
            verbose=False,
            logger=None
        )
        
        # Закрываем видео объекты
        video.close()
        modified_video.close()
        
        logger.info(f"Копия {copy_index + 1} успешно создана: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при создании копии {copy_index + 1}: {str(e)}")
        return False