#!/usr/bin/env python3
"""
Тест для проверки функциональности lossless сжатия видео
"""

import os
import sys
import tempfile
import shutil
import asyncio
from moviepy.editor import VideoFileClip, ColorClip
from video_processor import generate_random_compression_settings, VideoProcessor

def create_test_video(output_path, duration=3):
    """Создает простое тестовое видео"""
    # Создаем простое цветное видео
    clip = ColorClip(size=(640, 480), color=(255, 0, 0), duration=duration)
    clip = clip.set_fps(24)
    clip.write_videofile(output_path, verbose=False, logger=None)
    clip.close()

def test_lossless_compression():
    """Тестирует функцию генерации настроек с lossless режимом"""
    print("Тестирование lossless сжатия...")
    
    # Тестируем генерацию настроек для разных копий
    lossless_count = 0
    lossy_count = 0
    
    for i in range(20):  # Тестируем 20 копий
        settings = generate_random_compression_settings(i)
        
        # Проверяем структуру настроек
        required_keys = ['width', 'height', 'fps', 'audio_bitrate', 'ffmpeg_params']
        for key in required_keys:
            assert key in settings, f"Отсутствует ключ {key} в настройках"
        
        # Проверяем наличие CRF в ffmpeg_params
        ffmpeg_params = settings['ffmpeg_params']
        crf_found = False
        for j in range(len(ffmpeg_params)):
            if ffmpeg_params[j] == '-crf':
                crf_value = int(ffmpeg_params[j + 1])
                if crf_value == 0:
                    lossless_count += 1
                    print(f"Копия {i}: LOSSLESS (CRF=0)")
                else:
                    lossy_count += 1
                    print(f"Копия {i}: LOSSY (CRF={crf_value})")
                crf_found = True
                break
        
        assert crf_found, f"CRF не найден в ffmpeg_params для копии {i}"
    
    print(f"\nРезультаты теста:")
    print(f"Lossless копий: {lossless_count}")
    print(f"Lossy копий: {lossy_count}")
    print(f"Процент lossless: {lossless_count / 20 * 100:.1f}%")
    
    # Проверяем что есть и lossless и lossy копии
    assert lossless_count > 0, "Не найдено ни одной lossless копии"
    assert lossy_count > 0, "Не найдено ни одной lossy копии"
    
    print("✓ Тест генерации настроек прошел успешно")

async def test_video_processing_with_lossless():
    """Тестирует обработку видео с lossless копиями"""
    print("\nТестирование обработки видео с lossless копиями...")
    
    # Создаем временную директорию
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Создаем тестовое видео
        input_video = os.path.join(temp_dir, "test_input.mp4")
        create_test_video(input_video)
        
        print(f"Создано тестовое видео: {input_video}")
        
        # Обрабатываем видео
        processor = VideoProcessor()
        result = await processor.process_video(
            input_path=input_video,
            user_id=12345,
            copies=5,
            add_frames=True,
            compress=True
        )
        
        # Проверяем результат
        if isinstance(result, list) and len(result) > 0:
            print(f"Создано {len(result)} копий видео")
            
            # Проверяем размеры файлов
            file_sizes = []
            for video_path in result:
                if os.path.exists(video_path):
                    size = os.path.getsize(video_path)
                    file_sizes.append(size)
                    print(f"Файл: {os.path.basename(video_path)}, размер: {size} байт")
            
            # Проверяем что есть файлы разных размеров
            unique_sizes = len(set(file_sizes))
            print(f"Уникальных размеров файлов: {unique_sizes}")
            
            if unique_sizes > 1:
                print("✓ Файлы имеют разные размеры - сжатие работает корректно")
            else:
                print("⚠ Все файлы имеют одинаковый размер")
            
            # Очищаем созданные файлы
            for video_path in result:
                if os.path.exists(video_path):
                    os.remove(video_path)
            
            print("✓ Тест обработки видео прошел успешно")
            return True
        else:
            print("✗ Ошибка при обработке видео")
            return False
            
    except Exception as e:
        print(f"✗ Ошибка при обработке видео: {e}")
        return False
    finally:
        # Удаляем временную директорию
        shutil.rmtree(temp_dir, ignore_errors=True)

async def main():
    """Главная функция для запуска тестов"""
    try:
        test_lossless_compression()
        success = await test_video_processing_with_lossless()
        if success:
            print("\n🎉 Все тесты прошли успешно!")
        else:
            print("\n❌ Некоторые тесты не прошли")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())