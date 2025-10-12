#!/usr/bin/env python3
"""
Тест для проверки уникальности генерации рамок
"""

import sys
import os
import time
import random
import hashlib

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_random_frame_generation():
    """Тестирует генерацию случайных параметров рамок"""
    
    # Расширенная палитра цветов (копия из video_processor.py)
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
    
    print("🧪 Тестирование генерации случайных рамок...")
    print(f"📊 Доступно цветов: {len(frame_colors)}")
    print("=" * 60)
    
    # Тестируем генерацию для разных копий
    results = []
    
    for test_run in range(3):  # 3 прогона теста
        print(f"\n🔄 Прогон {test_run + 1}:")
        run_results = []
        
        for copy_index in range(3):  # 3 копии
            # Генерируем случайные параметры (копия логики из video_processor.py)
            current_time = int(time.time() * 1000000)  # Микросекунды
            seed_string = f"{current_time}_{copy_index}_{random.randint(1, 999999)}"
            seed_hash = int(hashlib.md5(seed_string.encode()).hexdigest()[:8], 16)
            
            # Используем seed для генерации
            random.seed(seed_hash)
            
            # Случайный выбор цвета и толщины
            color = random.choice(frame_colors)
            frame_thickness = random.randint(3, 15)
            
            result = {
                'copy': copy_index + 1,
                'color': color,
                'thickness': frame_thickness,
                'seed': seed_hash
            }
            
            run_results.append(result)
            
            print(f"  📹 Копия {copy_index + 1}: цвет {color}, толщина {frame_thickness}px (seed: {seed_hash})")
            
            # Небольшая задержка для изменения времени
            time.sleep(0.001)
        
        results.append(run_results)
    
    # Анализ уникальности
    print("\n" + "=" * 60)
    print("📈 АНАЛИЗ УНИКАЛЬНОСТИ:")
    
    all_combinations = []
    for run in results:
        for result in run:
            combination = (result['color'], result['thickness'])
            all_combinations.append(combination)
    
    unique_combinations = set(all_combinations)
    
    print(f"🎯 Всего сгенерировано комбинаций: {len(all_combinations)}")
    print(f"✨ Уникальных комбинаций: {len(unique_combinations)}")
    print(f"📊 Процент уникальности: {len(unique_combinations)/len(all_combinations)*100:.1f}%")
    
    # Проверяем, что нет повторений в одном прогоне
    for i, run in enumerate(results):
        run_combinations = [(r['color'], r['thickness']) for r in run]
        unique_in_run = set(run_combinations)
        print(f"🔄 Прогон {i+1}: {len(unique_in_run)}/{len(run_combinations)} уникальных в рамках одного прогона")
    
    print("\n✅ Тест завершен!")
    
    if len(unique_combinations) >= len(all_combinations) * 0.8:  # 80% уникальности
        print("🎉 УСПЕХ: Высокий уровень уникальности!")
        return True
    else:
        print("⚠️  ВНИМАНИЕ: Низкий уровень уникальности!")
        return False

if __name__ == "__main__":
    success = test_random_frame_generation()
    sys.exit(0 if success else 1)