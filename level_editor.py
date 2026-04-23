
"""
Редактор уровней для игры.
Позволяет создавать уровни с помощью графического интерфейса.
"""
import pygame
import json
import os
import tkinter as tk
from tkinter import filedialog
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, WHITE, BLACK, GRAY, DARK_GRAY, RED, GREEN, BLUE
from button import Button

# Верхняя запретная зона (как в игре)
TOP_BARRIER = 100

# Импортируем TOP_BARRIER из mechanics для отображения границ
TOP_BARRIER = 100  # Верхняя запретная зона (как в игре)

class LevelEditor:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Редактор уровней")
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Данные уровня
        self.level_data = {
            "background": None,  # Путь к файлу фона
            "walls": [],  # Список стен: [{"x": int, "y": int, "width": int, "height": int, "color": [r, g, b]}]
            "hitboxes": [],  # Список хитбоксов: [{"x": int, "y": int, "width": int, "height": int}]
            "computer": None,  # {"x": int, "y": int, "width": int, "height": int}
            "ghost_spawns": [],  # Список спавнов приведений: [{"x": int, "y": int}] (всегда спавнится одно)
            "rooms": []  # Список комнат: [{"x": int, "y": int, "width": int, "height": int, "room_id": int}]
        }
        
        # Загруженный фон
        self.background_image = None
        self.background_path = None
        
        # Режимы редактирования
        self.mode = "wall"  # "wall", "hitbox", "computer", "background", "ghost_spawn", "room"
        self.selected_wall = None
        self.selected_hitbox = None
        self.selected_ghost_spawn = None
        self.selected_room = None
        self.dragging = False
        self.resizing = False
        self.drag_offset = (0, 0)
        self.resize_corner = None  # "tl", "tr", "bl", "br" (top-left, top-right, bottom-left, bottom-right)
        self.room_drawing_start = None  # Начальная точка для рисования комнаты
        
        # Настройки сетки и размеров
        self.grid_size = 32  # Размер сетки для выравнивания
        self.show_grid = True
        self.wall_thickness = 32  # Толщина стен (фиксированная)
        self.wall_type = "horizontal"  # "horizontal" или "vertical"
        self.snap_enabled = True  # Привязка к сетке
        
        # Кнопки интерфейса
        self.buttons = [
    Button(10, 10, 70, 40, "Стена Г", GRAY),  # Горизонтальная стена
    Button(90, 10, 70, 40, "Стена В", GRAY),  # Вертикальная стена
    Button(170, 10, 70, 40, "Хитбокс", GRAY),
    Button(250, 10, 70, 40, "Компьютер", GRAY),
    Button(330, 10, 70, 40, "Приведение", GRAY),
    Button(410, 10, 70, 40, "Комната", GRAY),  # Новая кнопка для комнат
    Button(490, 10, 70, 40, "Фон", GRAY),
    Button(570, 10, 70, 40, "Сетка", GRAY),
    Button(650, 10, 70, 40, "Сохранить", GREEN),
    Button(730, 10, 70, 40, "Загрузить", BLUE),
    Button(810, 10, 70, 40, "Очистить", RED),
    Button(890, 10, 70, 40, "Удалить", RED),
    Button(970, 10, 54, 40, "Выход", RED)
]
        
        # Цвета для стен
        self.wall_color = (139, 90, 43)  # Коричневый
        
    def load_background(self):
        """Загружает фоновое изображение"""
        root = tk.Tk()
        root.withdraw()  # Скрываем главное окно tkinter
        file_path = filedialog.askopenfilename(
            title="Выберите фоновое изображение",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")]
        )
        root.destroy()
        
        if file_path:
            try:
                self.background_image = pygame.image.load(file_path).convert()
                self.background_image = pygame.transform.scale(
                    self.background_image, (SCREEN_WIDTH, SCREEN_HEIGHT)
                )
                self.background_path = file_path
                self.level_data["background"] = file_path
                print(f"Фон загружен: {file_path}")
            except Exception as e:
                print(f"Ошибка загрузки фона: {e}")
    
    def get_mouse_pos(self):
        """Получает позицию мыши"""
        return pygame.mouse.get_pos()
    
    def snap_to_grid(self, x, y):
        """Привязывает координаты к сетке"""
        if self.snap_enabled:
            return (x // self.grid_size) * self.grid_size, (y // self.grid_size) * self.grid_size
        return x, y
    
    def add_wall(self, x, y, wall_type=None):
        """Добавляет стену с фиксированной толщиной"""
        if wall_type is None:
            wall_type = self.wall_type
        
        # Привязываем к сетке
        x, y = self.snap_to_grid(x, y)
        
        # Определяем размеры в зависимости от типа стены
        if wall_type == "horizontal":
            # Горизонтальная стена: ширина переменная (минимум 64), высота фиксированная 32
            width = 64  # Начальная ширина
            height = self.wall_thickness
        else:  # vertical
            # Вертикальная стена: ширина фиксированная 32, высота переменная (минимум 64)
            width = self.wall_thickness
            height = 64  # Начальная высота
        
        wall = {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "color": list(self.wall_color),
            "type": wall_type  # Добавляем тип стены для правильного изменения размера
        }
        self.level_data["walls"].append(wall)
        return len(self.level_data["walls"]) - 1
    
    def add_hitbox(self, x, y, width=50, height=50):
        """Добавляет хитбокс"""
        hitbox = {
            "x": x,
            "y": y,
            "width": width,
            "height": height
        }
        self.level_data["hitboxes"].append(hitbox)
        return len(self.level_data["hitboxes"]) - 1
    
    def set_computer(self, x, y, width=80, height=80):
        """Устанавливает позицию компьютера"""
        # Привязываем к сетке
        x, y = self.snap_to_grid(x, y)
        
        self.level_data["computer"] = {
            "x": x,
            "y": y,
            "width": width,
            "height": height
        }
    
    def add_ghost_spawn(self, x, y):
        """Добавляет точку спавна приведения"""
        # Привязываем к сетке
        x, y = self.snap_to_grid(x, y)
        
        spawn = {
            "x": x,
            "y": y
        }
        self.level_data["ghost_spawns"].append(spawn)
        return len(self.level_data["ghost_spawns"]) - 1
    
    def add_room(self, x, y, width, height):
        """Добавляет комнату"""
        # Привязываем к сетке
        x, y = self.snap_to_grid(x, y)
        width = (width // self.grid_size) * self.grid_size
        height = (height // self.grid_size) * self.grid_size
        
        # Минимальный размер
        if width < self.grid_size:
            width = self.grid_size
        if height < self.grid_size:
            height = self.grid_size
        
        # Автоматически присваиваем room_id
        room_id = len(self.level_data["rooms"])
        
        room = {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "room_id": room_id
        }
        self.level_data["rooms"].append(room)
        return len(self.level_data["rooms"]) - 1
    
    def get_room_at_pos(self, pos):
        """Находит комнату по позиции"""
        for i, room in enumerate(self.level_data["rooms"]):
            rect = pygame.Rect(room["x"], room["y"], room["width"], room["height"])
            if rect.collidepoint(pos):
                return i
        return None
    
    def get_wall_at_pos(self, pos):
        """Находит стену по позиции"""
        for i, wall in enumerate(self.level_data["walls"]):
            rect = pygame.Rect(wall["x"], wall["y"], wall["width"], wall["height"])
            if rect.collidepoint(pos):
                return i
        return None
    
    def get_resize_corner(self, rect, pos, corner_size=10):
        """Определяет, какой угол прямоугольника находится под курсором"""
        corners = {
            "tl": (rect.x, rect.y),
            "tr": (rect.x + rect.width, rect.y),
            "bl": (rect.x, rect.y + rect.height),
            "br": (rect.x + rect.width, rect.y + rect.height)
        }
        for corner_name, corner_pos in corners.items():
            if abs(pos[0] - corner_pos[0]) < corner_size and abs(pos[1] - corner_pos[1]) < corner_size:
                return corner_name
        return None
    
    def get_hitbox_at_pos(self, pos):
        """Находит хитбокс по позиции"""
        for i, hitbox in enumerate(self.level_data["hitboxes"]):
            rect = pygame.Rect(hitbox["x"], hitbox["y"], hitbox["width"], hitbox["height"])
            if rect.collidepoint(pos):
                return i
        return None
    
    def get_computer_at_pos(self, pos):
        """Проверяет, попадает ли позиция в компьютер"""
        if self.level_data["computer"]:
            comp = self.level_data["computer"]
            rect = pygame.Rect(comp["x"], comp["y"], comp["width"], comp["height"])
            if rect.collidepoint(pos):
                return True
        return False
    
    def get_ghost_spawn_at_pos(self, pos):
        """Находит спавн приведения по позиции"""
        for i, spawn in enumerate(self.level_data["ghost_spawns"]):
            # Спавн представляем как круг радиусом 20 пикселей
            spawn_center = (spawn["x"] + 16, spawn["y"] + 16)  # Центр спавна
            distance = ((pos[0] - spawn_center[0]) ** 2 + (pos[1] - spawn_center[1]) ** 2) ** 0.5
            if distance <= 20:
                return i
        return None
    
    def delete_selected(self):
        """Удаляет выбранный объект"""
        if self.mode == "wall" and self.selected_wall is not None:
            if 0 <= self.selected_wall < len(self.level_data["walls"]):
                self.level_data["walls"].pop(self.selected_wall)
                self.selected_wall = None
        elif self.mode == "hitbox" and self.selected_hitbox is not None:
            if 0 <= self.selected_hitbox < len(self.level_data["hitboxes"]):
                self.level_data["hitboxes"].pop(self.selected_hitbox)
                self.selected_hitbox = None
        elif self.mode == "computer" and self.level_data["computer"]:
            self.level_data["computer"] = None
        elif self.mode == "ghost_spawn" and self.selected_ghost_spawn is not None:
            if 0 <= self.selected_ghost_spawn < len(self.level_data["ghost_spawns"]):
                self.level_data["ghost_spawns"].pop(self.selected_ghost_spawn)
                self.selected_ghost_spawn = None
        elif self.mode == "room" and self.selected_room is not None:
            if 0 <= self.selected_room < len(self.level_data["rooms"]):
                self.level_data["rooms"].pop(self.selected_room)
                # Пересчитываем room_id для оставшихся комнат
                for i, room in enumerate(self.level_data["rooms"]):
                    room["room_id"] = i
                self.selected_room = None
    
    def clear_all(self):
        """Очищает все объекты уровня"""
        self.level_data["walls"] = []
        self.level_data["hitboxes"] = []
        self.level_data["computer"] = None
        self.level_data["ghost_spawns"] = []
        self.level_data["rooms"] = []
        self.selected_wall = None
        self.selected_hitbox = None
        self.selected_ghost_spawn = None
        self.selected_room = None
    
    def save_level(self):
        """Сохраняет уровень в JSON файл"""
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.asksaveasfilename(
            title="Сохранить уровень",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        root.destroy()
        
        if file_path:
            try:
                # Подготавливаем данные для сохранения
                save_data = {
                    "background": None,
                    "walls": [],
                    "hitboxes": [],
                    "computer": None,
                    "ghost_spawns": [],
                    "rooms": []
                }
                
                # Сохраняем относительный путь к фону
                if self.background_path:
                    # Сохраняем только имя файла, если он в той же папке
                    json_dir = os.path.dirname(file_path)
                    bg_dir = os.path.dirname(self.background_path)
                    
                    if json_dir == bg_dir or bg_dir == "":
                        save_data["background"] = os.path.basename(self.background_path)
                    else:
                        # Пытаемся сделать относительный путь
                        try:
                            rel_path = os.path.relpath(self.background_path, json_dir)
                            save_data["background"] = rel_path
                        except:
                            save_data["background"] = self.background_path
                
                # Копируем стены
                save_data["walls"] = self.level_data["walls"].copy()
                
                # Копируем хитбоксы
                save_data["hitboxes"] = self.level_data["hitboxes"].copy()
                
                # Копируем компьютер
                if self.level_data["computer"]:
                    save_data["computer"] = self.level_data["computer"].copy()
                
                # Копируем спавны приведений
                save_data["ghost_spawns"] = self.level_data["ghost_spawns"].copy()
                
                # Копируем комнаты
                save_data["rooms"] = self.level_data["rooms"].copy()
                
                # Сохраняем в файл
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, ensure_ascii=False, indent=2)
                print(f"Уровень сохранен: {file_path}")
            except Exception as e:
                print(f"Ошибка сохранения: {e}")
                import traceback
                traceback.print_exc()
    
    def load_level(self):
        """Загружает уровень из JSON файла"""
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(
            title="Загрузить уровень",
            filetypes=[("JSON files", "*.json")]
        )
        root.destroy()
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.level_data = json.load(f)
                
                # Загружаем фон
                if self.level_data.get("background"):
                    bg_path = self.level_data["background"]
                    # Если относительный путь, ищем в той же папке что и JSON
                    if not os.path.isabs(bg_path):
                        bg_path = os.path.join(os.path.dirname(file_path), bg_path)
                    
                    if os.path.exists(bg_path):
                        self.background_image = pygame.image.load(bg_path).convert()
                        self.background_image = pygame.transform.scale(
                            self.background_image, (SCREEN_WIDTH, SCREEN_HEIGHT)
                        )
                        self.background_path = bg_path
                        print(f"Фон загружен: {bg_path}")
                    else:
                        print(f"Фон не найден: {bg_path}")
                
                # Инициализируем ghost_spawns если их нет в файле
                if "ghost_spawns" not in self.level_data:
                    self.level_data["ghost_spawns"] = []
                
                # Инициализируем rooms если их нет в файле
                if "rooms" not in self.level_data:
                    self.level_data["rooms"] = []
                
                # Добавляем тип стены для старых уровней
                for wall in self.level_data.get("walls", []):
                    if "type" not in wall:
                        # Определяем тип по размерам: если ширина больше высоты - горизонтальная
                        if wall["width"] >= wall["height"]:
                            wall["type"] = "horizontal"
                        else:
                            wall["type"] = "vertical"
                
                self.selected_wall = None
                self.selected_hitbox = None
                self.selected_ghost_spawn = None
                self.selected_room = None
                print(f"Уровень загружен: {file_path}")
            except Exception as e:
                print(f"Ошибка загрузки: {e}")
    
    def handle_events(self):
        """Обрабатывает события"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            # Обработка клавиатуры
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
            
            # Обработка кнопок
            for i, button in enumerate(self.buttons):
                if button.handle_event(event):
                    if i == 0:  # Стена горизонтальная
                        self.mode = "wall"
                        self.wall_type = "horizontal"
                        self.selected_wall = None
                        self.selected_hitbox = None
                        self.selected_ghost_spawn = None
                    elif i == 1:  # Стена вертикальная
                        self.mode = "wall"
                        self.wall_type = "vertical"
                        self.selected_wall = None
                        self.selected_hitbox = None
                        self.selected_ghost_spawn = None
                    elif i == 2:  # Хитбокс
                        self.mode = "hitbox"
                        self.selected_wall = None
                        self.selected_hitbox = None
                        self.selected_ghost_spawn = None
                    elif i == 3:  # Компьютер
                        self.mode = "computer"
                        self.selected_wall = None
                        self.selected_hitbox = None
                        self.selected_ghost_spawn = None
                    elif i == 4:  # Приведение
                        self.mode = "ghost_spawn"
                        self.selected_wall = None
                        self.selected_hitbox = None
                        self.selected_ghost_spawn = None
                        self.selected_room = None
                    elif i == 5:  # Комната
                        self.mode = "room"
                        self.selected_wall = None
                        self.selected_hitbox = None
                        self.selected_ghost_spawn = None
                        self.selected_room = None
                        self.room_drawing_start = None
                    elif i == 6:  # Фон
                        self.load_background()
                    elif i == 7:  # Сетка
                        self.show_grid = not self.show_grid
                    elif i == 8:  # Сохранить
                        self.save_level()
                    elif i == 9:  # Загрузить
                        self.load_level()
                    elif i == 10:  # Очистить
                        self.clear_all()
                    elif i == 11:  # Удалить
                        self.delete_selected()
                    elif i == 12:  # Выход
                        self.running = False
            
            # Обработка мыши
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Левая кнопка
                    pos = event.pos
                    # Проверяем, не кликнули ли по кнопкам
                    clicked_button = False
                    for button in self.buttons:
                        if button.rect.collidepoint(pos):
                            clicked_button = True
                            break
                    
                    if not clicked_button:
                        if self.mode == "wall":
                            # Проверяем, кликнули ли по существующей стене
                            wall_idx = self.get_wall_at_pos(pos)
                            if wall_idx is not None:
                                self.selected_wall = wall_idx
                                wall = self.level_data["walls"][wall_idx]
                                rect = pygame.Rect(wall["x"], wall["y"], wall["width"], wall["height"])
                                # Проверяем, кликнули ли по углу для изменения размера
                                corner = self.get_resize_corner(rect, pos)
                                if corner:
                                    self.resizing = True
                                    self.resize_corner = corner
                                    self.drag_offset = (pos[0], pos[1])
                                else:
                                    self.dragging = True
                                    self.drag_offset = (pos[0] - wall["x"], pos[1] - wall["y"])
                            else:
                                # Добавляем новую стену
                                self.add_wall(pos[0] - 32, pos[1] - 16)
                        elif self.mode == "hitbox":
                            # Проверяем, кликнули ли по существующему хитбоксу
                            hitbox_idx = self.get_hitbox_at_pos(pos)
                            if hitbox_idx is not None:
                                self.selected_hitbox = hitbox_idx
                                hitbox = self.level_data["hitboxes"][hitbox_idx]
                                rect = pygame.Rect(hitbox["x"], hitbox["y"], hitbox["width"], hitbox["height"])
                                # Проверяем, кликнули ли по углу для изменения размера
                                corner = self.get_resize_corner(rect, pos)
                                if corner:
                                    self.resizing = True
                                    self.resize_corner = corner
                                    self.drag_offset = (pos[0], pos[1])
                                else:
                                    self.dragging = True
                                    self.drag_offset = (pos[0] - hitbox["x"], pos[1] - hitbox["y"])
                            else:
                                # Добавляем новый хитбокс
                                self.add_hitbox(pos[0] - 25, pos[1] - 25)
                        elif self.mode == "computer":
                            # Устанавливаем позицию компьютера
                            self.set_computer(pos[0] - 40, pos[1] - 40)
                        elif self.mode == "ghost_spawn":
                            # Проверяем, кликнули ли по существующему спавну
                            spawn_idx = self.get_ghost_spawn_at_pos(pos)
                            if spawn_idx is not None:
                                self.selected_ghost_spawn = spawn_idx
                                spawn = self.level_data["ghost_spawns"][spawn_idx]
                                self.dragging = True
                                self.drag_offset = (pos[0] - spawn["x"], pos[1] - spawn["y"])
                            else:
                                # Добавляем новый спавн
                                self.add_ghost_spawn(pos[0] - 16, pos[1] - 16)
                        elif self.mode == "room":
                            # Проверяем, кликнули ли по существующей комнате
                            room_idx = self.get_room_at_pos(pos)
                            if room_idx is not None:
                                self.selected_room = room_idx
                                room = self.level_data["rooms"][room_idx]
                                rect = pygame.Rect(room["x"], room["y"], room["width"], room["height"])
                                # Проверяем, кликнули ли по углу для изменения размера
                                corner = self.get_resize_corner(rect, pos)
                                if corner:
                                    self.resizing = True
                                    self.resize_corner = corner
                                    self.drag_offset = (pos[0], pos[1])
                                else:
                                    self.dragging = True
                                    self.drag_offset = (pos[0] - room["x"], pos[1] - room["y"])
                            else:
                                # Начинаем рисование новой комнаты
                                self.room_drawing_start = pos
            
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    pos = event.pos
                    if self.mode == "room" and self.room_drawing_start:
                        # Завершаем рисование комнаты
                        start_x, start_y = self.room_drawing_start
                        end_x, end_y = pos
                        # Нормализуем координаты
                        x = min(start_x, end_x)
                        y = min(start_y, end_y)
                        width = abs(end_x - start_x)
                        height = abs(end_y - start_y)
                        if width > 0 and height > 0:
                            self.add_room(x, y, width, height)
                        self.room_drawing_start = None
                    self.dragging = False
                    self.resizing = False
                    self.resize_corner = None
            
            elif event.type == pygame.MOUSEMOTION:
                pos = event.pos
                if self.resizing:
                    if self.mode == "wall" and self.selected_wall is not None:
                        wall = self.level_data["walls"][self.selected_wall]
                        wall_type = wall.get("type", "horizontal")
                        old_x, old_y = wall["x"], wall["y"]
                        old_w, old_h = wall["width"], wall["height"]
                        
                        if wall_type == "horizontal":
                            # Горизонтальная стена: изменяем только ширину, высота остается 32
                            if self.resize_corner in ["tl", "bl"]:  # Левые углы
                                wall["width"] = old_w + (old_x - pos[0])
                                wall["x"] = pos[0]
                            elif self.resize_corner in ["tr", "br"]:  # Правые углы
                                wall["width"] = pos[0] - old_x
                            
                            # Минимальная ширина
                            if wall["width"] < self.wall_thickness:
                                wall["width"] = self.wall_thickness
                            
                            # Высота остается фиксированной
                            wall["height"] = self.wall_thickness
                            
                        else:  # vertical
                            # Вертикальная стена: изменяем только высоту, ширина остается 32
                            if self.resize_corner in ["tl", "tr"]:  # Верхние углы
                                wall["height"] = old_h + (old_y - pos[1])
                                wall["y"] = pos[1]
                            elif self.resize_corner in ["bl", "br"]:  # Нижние углы
                                wall["height"] = pos[1] - old_y
                            
                            # Минимальная высота
                            if wall["height"] < self.wall_thickness:
                                wall["height"] = self.wall_thickness
                            
                            # Ширина остается фиксированной
                            wall["width"] = self.wall_thickness
                    
                    elif self.mode == "hitbox" and self.selected_hitbox is not None:
                        hitbox = self.level_data["hitboxes"][self.selected_hitbox]
                        old_x, old_y = hitbox["x"], hitbox["y"]
                        old_w, old_h = hitbox["width"], hitbox["height"]
                        
                        if self.resize_corner == "tl":  # Верхний левый
                            hitbox["width"] = old_w + (old_x - pos[0])
                            hitbox["height"] = old_h + (old_y - pos[1])
                            hitbox["x"] = pos[0]
                            hitbox["y"] = pos[1]
                        elif self.resize_corner == "tr":  # Верхний правый
                            hitbox["width"] = pos[0] - old_x
                            hitbox["height"] = old_h + (old_y - pos[1])
                            hitbox["y"] = pos[1]
                        elif self.resize_corner == "bl":  # Нижний левый
                            hitbox["width"] = old_w + (old_x - pos[0])
                            hitbox["height"] = pos[1] - old_y
                            hitbox["x"] = pos[0]
                        elif self.resize_corner == "br":  # Нижний правый
                            hitbox["width"] = pos[0] - old_x
                            hitbox["height"] = pos[1] - old_y
                        
                        # Минимальный размер
                        if hitbox["width"] < 10:
                            hitbox["width"] = 10
                        if hitbox["height"] < 10:
                            hitbox["height"] = 10
                    
                    elif self.mode == "room" and self.selected_room is not None:
                        room = self.level_data["rooms"][self.selected_room]
                        old_x, old_y = room["x"], room["y"]
                        old_w, old_h = room["width"], room["height"]
                        
                        if self.resize_corner == "tl":  # Верхний левый
                            room["width"] = old_w + (old_x - pos[0])
                            room["height"] = old_h + (old_y - pos[1])
                            room["x"] = pos[0]
                            room["y"] = pos[1]
                        elif self.resize_corner == "tr":  # Верхний правый
                            room["width"] = pos[0] - old_x
                            room["height"] = old_h + (old_y - pos[1])
                            room["y"] = pos[1]
                        elif self.resize_corner == "bl":  # Нижний левый
                            room["width"] = old_w + (old_x - pos[0])
                            room["height"] = pos[1] - old_y
                            room["x"] = pos[0]
                        elif self.resize_corner == "br":  # Нижний правый
                            room["width"] = pos[0] - old_x
                            room["height"] = pos[1] - old_y
                        
                        # Привязываем к сетке
                        room["x"], room["y"] = self.snap_to_grid(room["x"], room["y"])
                        room["width"] = (room["width"] // self.grid_size) * self.grid_size
                        room["height"] = (room["height"] // self.grid_size) * self.grid_size
                        
                        # Минимальный размер
                        if room["width"] < self.grid_size:
                            room["width"] = self.grid_size
                        if room["height"] < self.grid_size:
                            room["height"] = self.grid_size
                
                elif self.dragging:
                    if self.mode == "wall" and self.selected_wall is not None:
                        wall = self.level_data["walls"][self.selected_wall]
                        wall["x"] = pos[0] - self.drag_offset[0]
                        wall["y"] = pos[1] - self.drag_offset[1]
                    elif self.mode == "hitbox" and self.selected_hitbox is not None:
                        hitbox = self.level_data["hitboxes"][self.selected_hitbox]
                        hitbox["x"] = pos[0] - self.drag_offset[0]
                        hitbox["y"] = pos[1] - self.drag_offset[1]
                    elif self.mode == "computer" and self.level_data["computer"]:
                        comp = self.level_data["computer"]
                        comp["x"] = pos[0] - 40
                        comp["y"] = pos[1] - 40
                    elif self.mode == "ghost_spawn" and self.selected_ghost_spawn is not None:
                        spawn = self.level_data["ghost_spawns"][self.selected_ghost_spawn]
                        spawn["x"] = pos[0] - self.drag_offset[0]
                        spawn["y"] = pos[1] - self.drag_offset[1]
                        # Привязываем к сетке
                        spawn["x"], spawn["y"] = self.snap_to_grid(spawn["x"], spawn["y"])
                    elif self.mode == "room" and self.selected_room is not None and self.dragging:
                        room = self.level_data["rooms"][self.selected_room]
                        room["x"] = pos[0] - self.drag_offset[0]
                        room["y"] = pos[1] - self.drag_offset[1]
                        # Привязываем к сетке
                        room["x"], room["y"] = self.snap_to_grid(room["x"], room["y"])
    
    def draw(self):
        """Отрисовывает редактор"""
        # Фон
        if self.background_image:
            self.screen.blit(self.background_image, (0, 0))
        else:
            self.screen.fill(BLACK)
        
        # Отрисовка сетки (если включена)
        if self.show_grid:
            for x in range(0, SCREEN_WIDTH, self.grid_size):
                pygame.draw.line(self.screen, (50, 50, 50), (x, TOP_BARRIER), (x, SCREEN_HEIGHT), 1)
            for y in range(TOP_BARRIER, SCREEN_HEIGHT, self.grid_size):
                pygame.draw.line(self.screen, (50, 50, 50), (0, y), (SCREEN_WIDTH, y), 1)
        
        # Визуальные границы рабочей области (как в игре)
        # Верхняя запретная зона
        barrier_rect = pygame.Rect(0, 0, SCREEN_WIDTH, TOP_BARRIER)
        barrier_surface = pygame.Surface((SCREEN_WIDTH, TOP_BARRIER))
        barrier_surface.set_alpha(100)
        barrier_surface.fill((255, 0, 0))  # Полупрозрачный красный
        self.screen.blit(barrier_surface, (0, 0))
        pygame.draw.line(self.screen, RED, (0, TOP_BARRIER), (SCREEN_WIDTH, TOP_BARRIER), 2)
        
        # Текст с информацией о границах
        font_info = pygame.font.Font(None, 20)
        info_text = font_info.render(f"Рабочая область: x=0-{SCREEN_WIDTH}, y={TOP_BARRIER}-{SCREEN_HEIGHT}", True, WHITE)
        self.screen.blit(info_text, (10, TOP_BARRIER + 5))
        
        # Отрисовка хитбоксов (полупрозрачные красные)
        for i, hitbox in enumerate(self.level_data["hitboxes"]):
            color = RED if i == self.selected_hitbox else (255, 0, 0, 128)
            rect = pygame.Rect(hitbox["x"], hitbox["y"], hitbox["width"], hitbox["height"])
            surface = pygame.Surface((hitbox["width"], hitbox["height"]))
            surface.set_alpha(128)
            surface.fill(RED)
            self.screen.blit(surface, (hitbox["x"], hitbox["y"]))
            pygame.draw.rect(self.screen, RED, rect, 2)
            # Рисуем углы для изменения размера, если хитбокс выбран
            if i == self.selected_hitbox:
                corner_size = 8
                corners = [
                    (rect.x, rect.y),  # tl
                    (rect.x + rect.width, rect.y),  # tr
                    (rect.x, rect.y + rect.height),  # bl
                    (rect.x + rect.width, rect.y + rect.height)  # br
                ]
                for corner_pos in corners:
                    pygame.draw.circle(self.screen, GREEN, corner_pos, corner_size)
                    pygame.draw.circle(self.screen, WHITE, corner_pos, corner_size, 2)
        
        # Отрисовка стен
        for i, wall in enumerate(self.level_data["walls"]):
            color = tuple(wall["color"])
            if i == self.selected_wall:
                # Выделяем выбранную стену
                color = (min(255, color[0] + 50), min(255, color[1] + 50), min(255, color[2] + 50))
            rect = pygame.Rect(wall["x"], wall["y"], wall["width"], wall["height"])
            pygame.draw.rect(self.screen, color, rect)
            pygame.draw.rect(self.screen, WHITE, rect, 2)
            # Рисуем углы для изменения размера, если стена выбрана
            if i == self.selected_wall:
                corner_size = 8
                corners = [
                    (rect.x, rect.y),  # tl
                    (rect.x + rect.width, rect.y),  # tr
                    (rect.x, rect.y + rect.height),  # bl
                    (rect.x + rect.width, rect.y + rect.height)  # br
                ]
                for corner_pos in corners:
                    pygame.draw.circle(self.screen, GREEN, corner_pos, corner_size)
                    pygame.draw.circle(self.screen, WHITE, corner_pos, corner_size, 2)
        
        # Отрисовка компьютера
        if self.level_data["computer"]:
            comp = self.level_data["computer"]
            rect = pygame.Rect(comp["x"], comp["y"], comp["width"], comp["height"])
            pygame.draw.rect(self.screen, BLUE, rect)
            pygame.draw.rect(self.screen, WHITE, rect, 2)
            # Текст "Компьютер"
            font = pygame.font.Font(None, 24)
            text = font.render("Компьютер", True, WHITE)
            self.screen.blit(text, (comp["x"] + 5, comp["y"] + 5))
        
        # Отрисовка спавнов приведений
        for i, spawn in enumerate(self.level_data["ghost_spawns"]):
            color = (255, 255, 0) if i == self.selected_ghost_spawn else (200, 200, 0)  # Желтый
            center = (spawn["x"] + 16, spawn["y"] + 16)
            pygame.draw.circle(self.screen, color, center, 20)
            pygame.draw.circle(self.screen, WHITE, center, 20, 2)
            # Рисуем крестик в центре
            pygame.draw.line(self.screen, WHITE, (center[0] - 10, center[1]), (center[0] + 10, center[1]), 2)
            pygame.draw.line(self.screen, WHITE, (center[0], center[1] - 10), (center[0], center[1] + 10), 2)
            # Текст "G" для Ghost
            font = pygame.font.Font(None, 24)
            text = font.render("G", True, WHITE)
            text_rect = text.get_rect(center=center)
            self.screen.blit(text, text_rect)
        
        # Отрисовка комнат (полупрозрачные зеленые прямоугольники)
        for i, room in enumerate(self.level_data["rooms"]):
            color_fill = (0, 255, 0, 60) if i == self.selected_room else (0, 200, 0, 40)
            color_border = (0, 255, 0) if i == self.selected_room else (0, 200, 0)
            rect = pygame.Rect(room["x"], room["y"], room["width"], room["height"])
            # Полупрозрачная заливка
            surface = pygame.Surface((room["width"], room["height"]), pygame.SRCALPHA)
            surface.fill(color_fill)
            self.screen.blit(surface, (room["x"], room["y"]))
            # Рамка
            pygame.draw.rect(self.screen, color_border, rect, 2)
            # Номер комнаты
            font = pygame.font.Font(None, 24)
            text = font.render(str(room["room_id"]), True, WHITE)
            text_rect = text.get_rect(center=rect.center)
            self.screen.blit(text, text_rect)
            # Рисуем углы для изменения размера, если комната выбрана
            if i == self.selected_room:
                corner_size = 8
                corners = [
                    (rect.x, rect.y),  # tl
                    (rect.x + rect.width, rect.y),  # tr
                    (rect.x, rect.y + rect.height),  # bl
                    (rect.x + rect.width, rect.height + rect.y)  # br
                ]
                for corner_pos in corners:
                    pygame.draw.circle(self.screen, GREEN, corner_pos, corner_size)
                    pygame.draw.circle(self.screen, WHITE, corner_pos, corner_size, 2)
        
        # Отрисовка комнаты в процессе рисования
        if self.mode == "room" and self.room_drawing_start:
            mouse_pos = pygame.mouse.get_pos()
            start_x, start_y = self.room_drawing_start
            end_x, end_y = mouse_pos
            x = min(start_x, end_x)
            y = min(start_y, end_y)
            width = abs(end_x - start_x)
            height = abs(end_y - start_y)
            if width > 0 and height > 0:
                preview_rect = pygame.Rect(x, y, width, height)
                preview_surface = pygame.Surface((width, height), pygame.SRCALPHA)
                preview_surface.fill((0, 255, 0, 30))
                self.screen.blit(preview_surface, (x, y))
                pygame.draw.rect(self.screen, (0, 255, 0), preview_rect, 2)
        
        # Отрисовка кнопок
        for i, button in enumerate(self.buttons):
            # Подсвечиваем активную кнопку режима
            if i == 0 and self.mode == "wall" and self.wall_type == "horizontal":  # Горизонтальная стена
                button.color = GREEN
            elif i == 1 and self.mode == "wall" and self.wall_type == "vertical":  # Вертикальная стена
                button.color = GREEN
            elif i == 2 and self.mode == "hitbox":  # Хитбокс
                button.color = GREEN
            elif i == 3 and self.mode == "computer":  # Компьютер
                button.color = GREEN
            elif i == 4 and self.mode == "ghost_spawn":  # Приведение
                button.color = GREEN
            elif i == 5 and self.mode == "room":  # Комната
                button.color = GREEN
            elif i == 7 and self.show_grid:  # Кнопка сетки
                button.color = GREEN
            elif i < 8:
                button.color = GRAY
            button.draw(self.screen)
        
        # Информация о режиме и настройках
        font = pygame.font.Font(None, 24)
        wall_info = f"стена {self.wall_type}" if self.mode == "wall" else self.mode
        mode_text = f"Режим: {wall_info} | Сетка: {'ВКЛ' if self.show_grid else 'ВЫКЛ'} | Толщина стен: {self.wall_thickness}px"
        text_surface = font.render(mode_text, True, WHITE)
        self.screen.blit(text_surface, (10, SCREEN_HEIGHT - 60))
        
        # Статистика объектов
        ghost_spawns_count = len(self.level_data['ghost_spawns'])
        rooms_count = len(self.level_data['rooms'])
        ghost_text = f"(1 приведение)" if ghost_spawns_count > 0 else "(нет приведения)"
        stats_text = f"Стены: {len(self.level_data['walls'])} | Хитбоксы: {len(self.level_data['hitboxes'])} | Спавны: {ghost_spawns_count} {ghost_text} | Комнаты: {rooms_count}"
        stats_surface = font.render(stats_text, True, WHITE)
        self.screen.blit(stats_surface, (10, SCREEN_HEIGHT - 30))
    
    def run(self):
        """Запускает редактор"""
        while self.running:
            self.handle_events()
            self.draw()
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()

if __name__ == "__main__":
    editor = LevelEditor()
    editor.run()

