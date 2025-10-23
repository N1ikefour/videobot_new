import os
import random
import asyncio
import logging
import time
import hashlib
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import numpy as np
from config import OUTPUT_IMAGES_DIR, TEMP_DIR

# Настройка логирования
logger = logging.getLogger(__name__)

def cleanup_old_temp_images(temp_dir: str):
    """Очищает старые временные изображения старше 1 часа"""
    try:
        current_time = time.time()
        for filename in os.listdir(temp_dir):
            if filename.startswith('temp-image-') and (filename.endswith('.jpg') or filename.endswith('.png')):
                file_path = os.path.join(temp_dir, filename)
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > 3600:  # 1 час = 3600 секунд
                        os.remove(file_path)
                        logger.info(f"Удален старый временный файл изображения: {filename}")
    except Exception as e:
        logger.warning(f"Ошибка при очистке временных файлов изображений: {e}")

class ImageProcessor:
    def __init__(self):
        # Расширенная палитра цветов для рамок
        self.frame_colors = [
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

    async def process_image(self, input_path: str, user_id: int, copies: int, add_frames: bool, 
                          add_filters: bool, add_rotation: bool, change_size: bool, target_size: tuple = None):
        """Основная функция обработки изображения"""
        logger.info(f"=== НАЧАЛО ОБРАБОТКИ ИЗОБРАЖЕНИЯ ===")
        logger.info(f"Пользователь: {user_id}")
        logger.info(f"Входной файл: {input_path}")
        logger.info(f"Количество копий: {copies}")
        logger.info(f"Добавить рамки: {add_frames}")
        logger.info(f"Добавить фильтры: {add_filters}")
        logger.info(f"Добавить повороты: {add_rotation}")
        logger.info(f"Изменить размер: {change_size}")
        
        processed_images = []
        
        try:
            # Проверяем существование входного файла
            if not os.path.exists(input_path):
                logger.error(f"Входной файл не найден: {input_path}")
                raise FileNotFoundError(f"Файл {input_path} не найден")
            
            logger.info(f"Входной файл найден: {input_path}")
            file_size = os.path.getsize(input_path) / (1024 * 1024)  # MB
            logger.info(f"Размер файла: {file_size:.2f} MB")
            
            # Создаем задачи для параллельной обработки всех копий
            tasks = []
            output_paths = []
            
            for i in range(copies):
                output_path = f"{OUTPUT_IMAGES_DIR}/processed_{user_id}_{i+1}.jpg"
                output_paths.append(output_path)
                
                # Создаем задачу для каждой копии
                task = self._process_single_image_copy(
                    input_path, output_path, i, add_frames, add_filters, add_rotation, change_size, user_id, target_size
                )
                tasks.append(task)
            
            # Запускаем все копии параллельно
            logger.info(f"🚀 Запускаю параллельную обработку {copies} копий изображения")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Собираем успешно обработанные изображения
            for i, (result, output_path) in enumerate(zip(results, output_paths)):
                if isinstance(result, Exception):
                    logger.error(f"❌ Ошибка при создании копии {i+1}: {str(result)}")
                elif result and os.path.exists(output_path):
                    processed_images.append(output_path)
                    logger.info(f"✅ Копия {i+1} создана успешно")
                else:
                    logger.error(f"❌ Копия {i+1} не была создана")
            
            logger.info(f"✅ Параллельная обработка завершена. Успешно: {len(processed_images)}/{copies}")
            return processed_images
            
        except Exception as e:
            logger.error(f"Критическая ошибка при обработке изображения: {str(e)}")
            # Очищаем созданные файлы при ошибке
            for file_path in processed_images:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        logger.info(f"Удален временный файл: {file_path}")
                    except:
                        pass
            raise

    async def _process_single_image_copy(self, input_path: str, output_path: str, 
                                       copy_index: int, add_frames: bool, add_filters: bool, 
                                       add_rotation: bool, change_size: bool, user_id: int, target_size: tuple = None):
        """Обработка одной копии изображения"""
        try:
            # Используем ThreadPoolExecutor для обработки изображения
            loop = asyncio.get_event_loop()
            
            # Увеличиваем таймаут для больших файлов
            file_size = os.path.getsize(input_path) / (1024 * 1024)  # MB
            timeout_seconds = max(60, int(file_size * 10))  # Минимум 1 минута, +10 сек на MB
            logger.info(f"Установлен таймаут: {timeout_seconds} секунд для файла {file_size:.2f} MB")
            
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,  # Используем стандартный ThreadPoolExecutor
                    self._process_image_copy_wrapper,
                    input_path, output_path, copy_index, add_frames, add_filters, add_rotation, change_size, user_id, target_size
                ),
                timeout=timeout_seconds
            )
            
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"Таймаут при создании копии {copy_index+1} (превышен лимит {timeout_seconds} секунд)")
            return False
        except Exception as e:
            logger.error(f"Ошибка при создании копии {copy_index+1}: {str(e)}")
            return False

    def _process_image_copy_wrapper(self, input_path: str, output_path: str, 
                                  copy_index: int, add_frames: bool, add_filters: bool, 
                                  add_rotation: bool, change_size: bool, user_id: int, target_size: tuple = None):
        """Обертка для функции обработки изображения"""
        return process_image_copy_new(input_path, output_path, copy_index, add_frames, 
                                    add_filters, add_rotation, change_size, user_id, target_size)

def apply_unique_image_modifications(image: Image.Image, copy_index: int, add_frames: bool, 
                                   add_filters: bool, add_rotation: bool, change_size: bool, target_size: tuple = None):
    """Применяет уникальные модификации к изображению"""
    
    # Создаем уникальный seed на основе времени и copy_index
    current_time = int(time.time() * 1000000)  # Микросекунды для большей уникальности
    seed_string = f"{current_time}_{copy_index}_{random.randint(1, 999999)}"
    seed_hash = int(hashlib.md5(seed_string.encode()).hexdigest()[:8], 16)
    
    # Используем seed для генерации случайных параметров
    random.seed(seed_hash)
    
    modified_image = image.copy()
    
    # 1. Изменение размера (если включено)
    if change_size and target_size:
        # Используем переданный размер
        modified_image = modified_image.resize(target_size, Image.Resampling.LANCZOS)
        logger.info(f"Копия {copy_index + 1}: размер изменен на {target_size}")
    elif change_size and not target_size:
        # Случайные размеры для Stories/Reels/TikTok (fallback)
        target_sizes = [
            (1080, 1920),  # Вертикальное
            (1920, 1080),  # Горизонтальное
            (1080, 1080),  # Квадратное
            (1080, 1350),   # 4:5 (Instagram)
            (1080, 1080),   # 1:1
        ]
        random_size = random.choice(target_sizes)
        modified_image = modified_image.resize(random_size, Image.Resampling.LANCZOS)
        logger.info(f"Копия {copy_index + 1}: размер изменен на {random_size}")
    
    # 2. Поворот (если включен)
    if add_rotation:
        # Случайный поворот от -5 до +5 градусов
        rotation_angle = random.uniform(-2, 2)
        modified_image = modified_image.rotate(rotation_angle, expand=True, fillcolor=(255, 255, 255))
        logger.info(f"Копия {copy_index + 1}: поворот на {rotation_angle:.1f}°")
    
    # 3. Фильтры (если включены)
    if add_filters:
        # Выбираем случайное количество фильтров (1-3) для большей уникальности
        num_filters = random.randint(1, 3)
        available_filters = ['brightness', 'contrast', 'saturation', 'blur', 'sharpen', 'color_enhance', 'hue_shift', 'color_tint', 'curves_adjustment', 'color_channel_adjustment', 'levels_adjustment']
        selected_filters = random.sample(available_filters, min(num_filters, len(available_filters)))
        
        logger.info(f"Копия {copy_index + 1}: применяем фильтры: {selected_filters}")
        
        for filter_type in selected_filters:
            if filter_type == 'brightness':
                # Изменение яркости
                brightness_factor = random.uniform(0.8, 1.2)
                enhancer = ImageEnhance.Brightness(modified_image)
                modified_image = enhancer.enhance(brightness_factor)
                logger.info(f"  - яркость {brightness_factor:.2f}")
                
            elif filter_type == 'contrast':
                # Изменение контраста
                contrast_factor = random.uniform(0.8, 1.3)
                enhancer = ImageEnhance.Contrast(modified_image)
                modified_image = enhancer.enhance(contrast_factor)
                logger.info(f"  - контраст {contrast_factor:.2f}")
                
            elif filter_type == 'saturation':
                # Изменение насыщенности
                saturation_factor = random.uniform(0.7, 1.4)
                enhancer = ImageEnhance.Color(modified_image)
                modified_image = enhancer.enhance(saturation_factor)
                logger.info(f"  - насыщенность {saturation_factor:.2f}")
                
            elif filter_type == 'blur':
                # Легкое размытие
                blur_radius = random.uniform(0.5, 2.0)
                modified_image = modified_image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
                logger.info(f"  - размытие {blur_radius:.1f}px")
                
            elif filter_type == 'sharpen':
                # Увеличение резкости
                modified_image = modified_image.filter(ImageFilter.SHARPEN)
                logger.info(f"  - увеличение резкости")
                
            elif filter_type == 'color_enhance':
                # Улучшение цветов
                modified_image = modified_image.filter(ImageFilter.EDGE_ENHANCE)
                logger.info(f"  - улучшение цветов")
                
            elif filter_type == 'hue_shift':
                # Случайное изменение оттенка
                modified_image = apply_hue_shift(modified_image)
                logger.info(f"  - сдвиг оттенка")
                
            elif filter_type == 'color_tint':
                # Цветной оттенок с градиентом
                modified_image = apply_color_tint(modified_image)
                logger.info(f"  - цветной оттенок")
                
            elif filter_type == 'curves_adjustment':
                # Кривые для изменения тональности
                modified_image = apply_curves_adjustment(modified_image)
                logger.info(f"  - кривые тональности")
                
            elif filter_type == 'color_channel_adjustment':
                # Изменения отдельных цветовых каналов
                modified_image = apply_color_channel_adjustment(modified_image)
                logger.info(f"  - цветовые каналы")
                
            elif filter_type == 'levels_adjustment':
                # Изменения уровней
                modified_image = apply_levels_adjustment(modified_image)
                logger.info(f"  - уровни")
    
    # 4. Рамки (если включены)
    if add_frames:
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
        
        # Случайный выбор цвета рамки
        frame_color = random.choice(frame_colors)
        
        # Случайная толщина рамки от 5 до 50 пикселей
        frame_thickness = random.randint(5, 50)
        
        # Случайные пропорции для разных сторон рамки
        frame_style = random.choice(['uniform', 'top_bottom_thick', 'sides_thick'])
        
        modified_image = add_background_to_image(modified_image, frame_color, frame_thickness, frame_style)
        logger.info(f"Копия {copy_index + 1}: фон {frame_color}, толщина {frame_thickness}px, стиль {frame_style}")
    
    # 5. Небольшое изменение яркости для уникальности
    brightness_factor = 0.95 + (copy_index * 0.02)  # Очень небольшое изменение яркости
    enhancer = ImageEnhance.Brightness(modified_image)
    modified_image = enhancer.enhance(brightness_factor)
    logger.info(f"Копия {copy_index + 1}: финальная яркость {brightness_factor:.2f}")
    
    return modified_image

def add_background_to_image(image: Image.Image, color: tuple, thickness: int, frame_style: str = 'uniform'):
    """Добавляет цветной фон к изображению"""
    import numpy as np
    
    # Получаем размеры изображения
    width, height = image.size
    
    # Вычисляем толщину для разных сторон в зависимости от стиля
    if frame_style == 'top_bottom_thick':
        # Верх и низ толще боков
        top_bottom_thickness = thickness
        left_right_thickness = max(3, thickness // 3)
    elif frame_style == 'sides_thick':
        # Бока толще верха/низа
        left_right_thickness = thickness
        top_bottom_thickness = max(3, thickness // 3)
    else:  # uniform
        # Все стороны одинаковые
        top_bottom_thickness = thickness
        left_right_thickness = thickness
    
    # Создаем новое изображение с фоном
    new_width = width + (left_right_thickness * 2)
    new_height = height + (top_bottom_thickness * 2)
    
    # Создаем фон с градиентом или однотонным цветом
    background_style = random.choice(['solid', 'gradient_vertical', 'gradient_horizontal', 'gradient_diagonal'])
    
    if background_style == 'solid':
        # Однотонный фон
        background_image = Image.new('RGB', (new_width, new_height), color)
    else:
        # Градиентный фон
        background_image = create_gradient_background(new_width, new_height, color, background_style)
    
    # Вставляем оригинальное изображение в центр
    paste_x = left_right_thickness
    paste_y = top_bottom_thickness
    background_image.paste(image, (paste_x, paste_y))
    
    return background_image

def create_gradient_background(width: int, height: int, base_color: tuple, style: str):
    """Создает градиентный фон"""
    import numpy as np
    
    # Создаем базовый цвет
    r, g, b = base_color
    
    # Создаем вариации цвета для градиента
    if style == 'gradient_vertical':
        # Вертикальный градиент
        gradient = np.zeros((height, width, 3), dtype=np.uint8)
        for y in range(height):
            factor = y / height
            gradient[y, :] = [
                int(r * (0.7 + 0.3 * factor)),
                int(g * (0.7 + 0.3 * factor)),
                int(b * (0.7 + 0.3 * factor))
            ]
    elif style == 'gradient_horizontal':
        # Горизонтальный градиент
        gradient = np.zeros((height, width, 3), dtype=np.uint8)
        for x in range(width):
            factor = x / width
            gradient[:, x] = [
                int(r * (0.7 + 0.3 * factor)),
                int(g * (0.7 + 0.3 * factor)),
                int(b * (0.7 + 0.3 * factor))
            ]
    else:  # gradient_diagonal
        # Диагональный градиент
        gradient = np.zeros((height, width, 3), dtype=np.uint8)
        for y in range(height):
            for x in range(width):
                factor = (x + y) / (width + height)
                gradient[y, x] = [
                    int(r * (0.6 + 0.4 * factor)),
                    int(g * (0.6 + 0.4 * factor)),
                    int(b * (0.6 + 0.4 * factor))
                ]
    
    return Image.fromarray(gradient)

def apply_hue_shift(image: Image.Image):
    """Применяет эффект цветной пленки к изображению"""
    import numpy as np
    
    # Случайные цвета для пленки (более насыщенные и заметные)
    color_overlays = [
        (255, 80, 80, 0.4),      # Красная пленка
        (80, 255, 80, 0.4),      # Зеленая пленка
        (80, 80, 255, 0.4),      # Синяя пленка
        (255, 255, 80, 0.4),     # Желтая пленка
        (255, 80, 255, 0.4),     # Пурпурная пленка
        (80, 255, 255, 0.4),     # Голубая пленка
        (255, 120, 80, 0.4),     # Оранжевая пленка
        (120, 80, 255, 0.4),     # Фиолетовая пленка
        (80, 255, 120, 0.4),     # Лаймовая пленка
        (255, 180, 80, 0.4),     # Персиковая пленка
        (180, 80, 255, 0.4),     # Индиго пленка
        (255, 80, 180, 0.4),     # Розовая пленка
    ]
    
    # Выбираем случайный цвет пленки
    overlay_color = random.choice(color_overlays)
    r, g, b, alpha = overlay_color
    
    # Создаем цветную пленку
    overlay = Image.new('RGB', image.size, (r, g, b))
    
    # Применяем пленку с прозрачностью
    result = Image.blend(image, overlay, alpha)
    
    return result

def apply_color_tint(image: Image.Image):
    """Применяет цветной оттенок с градиентом к изображению"""
    import numpy as np
    
    # Случайные цвета для оттенка
    tint_colors = [
        (255, 150, 150),    # Теплый розовый
        (150, 255, 150),    # Теплый зеленый
        (150, 150, 255),    # Теплый синий
        (255, 255, 150),    # Теплый желтый
        (255, 150, 255),    # Теплый пурпурный
        (150, 255, 255),    # Теплый голубой
        (255, 200, 150),    # Теплый оранжевый
        (200, 150, 255),    # Теплый фиолетовый
        (150, 255, 200),    # Теплый лайм
        (255, 220, 150),    # Теплый персик
    ]
    
    # Выбираем случайный цвет
    tint_color = random.choice(tint_colors)
    
    # Создаем градиентную пленку
    width, height = image.size
    overlay = Image.new('RGB', (width, height))
    
    # Создаем градиент от прозрачного к цветному
    gradient_style = random.choice(['vertical', 'horizontal', 'diagonal', 'radial'])
    
    if gradient_style == 'vertical':
        # Вертикальный градиент
        for y in range(height):
            alpha = y / height * 0.4  # Максимум 40% прозрачности
            color = tuple(int(c * alpha + 255 * (1 - alpha)) for c in tint_color)
            for x in range(width):
                overlay.putpixel((x, y), color)
                
    elif gradient_style == 'horizontal':
        # Горизонтальный градиент
        for x in range(width):
            alpha = x / width * 0.4
            color = tuple(int(c * alpha + 255 * (1 - alpha)) for c in tint_color)
            for y in range(height):
                overlay.putpixel((x, y), color)
                
    elif gradient_style == 'diagonal':
        # Диагональный градиент
        for y in range(height):
            for x in range(width):
                alpha = ((x + y) / (width + height)) * 0.4
                color = tuple(int(c * alpha + 255 * (1 - alpha)) for c in tint_color)
                overlay.putpixel((x, y), color)
                
    else:  # radial
        # Радиальный градиент
        center_x, center_y = width // 2, height // 2
        max_distance = ((width ** 2 + height ** 2) ** 0.5) / 2
        for y in range(height):
            for x in range(width):
                distance = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
                alpha = (1 - distance / max_distance) * 0.4
                alpha = max(0, alpha)
                color = tuple(int(c * alpha + 255 * (1 - alpha)) for c in tint_color)
                overlay.putpixel((x, y), color)
    
    # Применяем пленку
    result = Image.blend(image, overlay, 0.3)
    
    return result

def apply_curves_adjustment(image: Image.Image):
    """Применяет случайные кривые для изменения тональности изображения"""
    import numpy as np
    
    # Конвертируем в массив для работы с кривыми
    img_array = np.array(image)
    
    # Создаем случайные кривые для каждого канала RGB
    for channel in range(3):  # R, G, B каналы
        # Создаем случайные точки для кривой
        curve_points = []
        
        # Добавляем начальную и конечную точки
        curve_points.append((0, random.randint(-20, 20)))
        curve_points.append((255, 255 + random.randint(-20, 20)))
        
        # Добавляем случайные промежуточные точки
        num_points = random.randint(1, 3)
        for _ in range(num_points):
            x = random.randint(50, 200)
            y = x + random.randint(-30, 30)
            y = max(0, min(255, y))  # Ограничиваем значения
            curve_points.append((x, y))
        
        # Сортируем точки по x
        curve_points.sort(key=lambda p: p[0])
        
        # Создаем кривую
        x_points = [p[0] for p in curve_points]
        y_points = [p[1] for p in curve_points]
        
        # Интерполируем кривую
        curve = np.interp(range(256), x_points, y_points)
        curve = np.clip(curve, 0, 255)
        
        # Применяем кривую к каналу
        img_array[:, :, channel] = curve[img_array[:, :, channel]]
    
    return Image.fromarray(img_array.astype(np.uint8))

def apply_color_channel_adjustment(image: Image.Image):
    """Применяет случайные изменения к отдельным цветовым каналам"""
    import numpy as np
    
    # Конвертируем в массив
    img_array = np.array(image)
    
    # Определяем цветовые диапазоны (как на картинке)
    color_ranges = {
        'red': (0, 30),
        'orange': (30, 60), 
        'yellow': (60, 90),
        'green': (90, 150),
        'blue': (150, 240),
        'purple': (240, 270),
        'pink': (270, 360)
    }
    
    # Выбираем случайные цветовые диапазоны для изменения
    num_adjustments = random.randint(2, 4)
    selected_ranges = random.sample(list(color_ranges.keys()), num_adjustments)
    
    # Конвертируем в HSV для работы с оттенками
    hsv_array = np.array(image.convert('HSV'))
    
    for color_range in selected_ranges:
        hue_min, hue_max = color_ranges[color_range]
        
        # Случайные изменения
        hue_shift = random.randint(-20, 20)
        saturation_factor = random.uniform(0.7, 1.4)
        brightness_factor = random.uniform(0.8, 1.2)
        
        # Создаем маску для выбранного цветового диапазона
        mask = (hsv_array[:, :, 0] >= hue_min) & (hsv_array[:, :, 0] <= hue_max)
        
        # Применяем изменения
        hsv_array[mask, 0] = (hsv_array[mask, 0] + hue_shift) % 360
        hsv_array[mask, 1] = np.clip(hsv_array[mask, 1] * saturation_factor, 0, 255)
        hsv_array[mask, 2] = np.clip(hsv_array[mask, 2] * brightness_factor, 0, 255)
    
    # Конвертируем обратно в RGB
    return Image.fromarray(hsv_array.astype(np.uint8), 'HSV').convert('RGB')

def apply_levels_adjustment(image: Image.Image):
    """Применяет случайные изменения уровней (как в Photoshop)"""
    import numpy as np
    
    img_array = np.array(image)
    
    # Случайные изменения для каждого канала
    for channel in range(3):
        # Случайные точки черного, серого и белого
        black_point = random.randint(0, 50)
        white_point = random.randint(200, 255)
        gray_point = random.uniform(0.8, 1.2)
        
        # Применяем изменения уровней
        channel_data = img_array[:, :, channel].astype(np.float32)
        
        # Нормализуем к диапазону 0-1
        channel_data = channel_data / 255.0
        
        # Применяем черную и белую точки
        channel_data = np.clip((channel_data - black_point/255.0) / (white_point/255.0 - black_point/255.0), 0, 1)
        
        # Применяем гамма-коррекцию
        channel_data = np.power(channel_data, gray_point)
        
        # Возвращаем к диапазону 0-255
        img_array[:, :, channel] = np.clip(channel_data * 255, 0, 255)
    
    return Image.fromarray(img_array.astype(np.uint8))

def process_image_copy_new(input_path: str, output_path: str, copy_index: int, add_frames: bool, 
                          add_filters: bool, add_rotation: bool, change_size: bool, user_id: int = None, target_size: tuple = None):
    """Обрабатывает одну копию изображения"""
    try:
        logger.info(f"Начинаю обработку копии изображения {copy_index + 1}: {input_path} -> {output_path}")
        
        # Проверяем существование входного файла
        if not os.path.exists(input_path):
            logger.error(f"Входной файл не найден: {input_path}")
            return False
        
        # Создаем директорию для выходного файла
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Загружаем изображение
        with Image.open(input_path) as image:
            # Конвертируем в RGB если необходимо
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Применяем уникальные модификации
            modified_image = apply_unique_image_modifications(
                image, copy_index, add_frames, add_filters, add_rotation, change_size, target_size
            )
            
            # Создаем папку temp если не существует
            os.makedirs(TEMP_DIR, exist_ok=True)
            
            # Очищаем старые временные файлы
            cleanup_old_temp_images(TEMP_DIR)
            
            # Сохраняем изображение
            modified_image.save(output_path, 'JPEG', quality=95, optimize=True)
            
            logger.info(f"Копия изображения {copy_index + 1} успешно создана: {output_path}")
            return True
        
    except Exception as e:
        logger.error(f"Ошибка при создании копии изображения {copy_index + 1}: {str(e)}")
        return False
