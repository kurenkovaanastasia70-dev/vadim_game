import pygame
import random
import sys
import os
import json

from constants import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    FPS,
    TILE_SIZE,
    MAP_SCALE,
    SHOP_RIGHT_COLUMN_X,
    SHOP_RIGHT_BUTTON_WIDTH,
    WHITE,
    BLACK,
    GRAY,
    DARK_GRAY,
    LIGHT_GRAY,
    RED,
    GREEN,
    BLUE,
)
from button import Button, PinButton
from gamestate import GameState
import draws
import handlers
import mechanics
import assets
from ghost import GhostManager, EVIDENCE_PROFILE_KEYS
from inventory_system import InventoryManager
import level_config

pygame.init()

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
        pygame.display.set_caption("(:")
        self.clock = pygame.time.Clock()
        self.running=True
        self.state = GameState.MENU
        self.state_stack = []
        self.previous_state = None
        self.fullscreen = True
        self.volume = 50
        self.difficulty_levels = ["Лёгкая","Сормальная","Сложная","ХАРДКОР"]
        self.difficulty_index = 1
        self.difficulty_selected = False
        self.save_file = "save.json"
        self.saves = self.load_saves()
        self.selected_save_slot = None
        
        # Загружаем пины для меню
        self.pin_images = assets.load_pin_images()
        
        # Загружаем фон пробковой доски один раз (после создания экрана)
        # Размер берется из реального экрана
        self.cork_board_bg = assets.load_cork_board(
            screen_width=self.screen.get_width(),
            screen_height=self.screen.get_height()
        )
        
        self.menu_buttons = [
            PinButton(200, 250, self.pin_images.get("pin_1"), "Начать игру"),
            PinButton(600, 180, self.pin_images.get("pin_2"), "Настройки"),
            PinButton(400, 320, self.pin_images.get("pin_2"), "Как играть"),
            PinButton(150, 450, self.pin_images.get("pin_3"), "Сохранить"),
            PinButton(650, 400, self.pin_images.get("pin_1"), "Выход")
        ]
        self.howto_back_button = Button(50, 50, 160, 44, "Назад", RED)
        # Журнал улик: ЭМП / УФ / радио и флаг панели
        self.journal_open = False
        self.journal_evidence = self.default_journal_evidence()
        self.loaded_journal_evidence = None
        
        # Создание кнопок для магазина
        self.shop_buttons = [
            Button(50, 50, 150, 40, "Назад", RED),
            Button(50, 100, 200, 40, "Купить фонарик", GREEN),
            Button(50, 150, 200, 40, "Купить красную пыль", BLUE),
            Button(50, 200, 200, 40, "Купить соль", GRAY),
            Button(50, 250, 200, 40, "Купить проектор", GREEN),
            Button(50, 300, 200, 40, "Купить аккумулятор", GREEN),
            Button(50, 350, 200, 40, "Купить крест", GREEN),
            Button(50, 400, 200, 40, "Купить кровь", GREEN),
            Button(SHOP_RIGHT_COLUMN_X, 92, SHOP_RIGHT_BUTTON_WIDTH, 40, "Купить радио", BLUE),
            Button(SHOP_RIGHT_COLUMN_X, 172, SHOP_RIGHT_BUTTON_WIDTH, 40, "Купить ЭМП", BLUE),
            Button(SHOP_RIGHT_COLUMN_X, 252, SHOP_RIGHT_BUTTON_WIDTH, 40, "Купить УФ фонарь", BLUE),
        ]
        
        # Создание кнопок для настроек
        self.settings_buttons = [
            Button(50, 50, 150, 40, "Назад", RED),
            Button(50, 100, 200, 40, "Громкость: 50%", GRAY),
            Button(50, 150, 200, 40, "Полноэкранный режим: вкл", GRAY),
            Button(50, 200, 200, 40, "Сбросить настройки", RED)
        ]
        
        # Создание кнопок для игрового экрана
        self.game_buttons = [
            Button(SCREEN_WIDTH - 150, 50, 100, 40, "Меню", RED),
            Button(SCREEN_WIDTH - 150, 100, 100, 40, "Магазин", BLUE)
        ]

        self.player_money = 100
        self.player_level = 1
        self.player_hp = 5
        self.hit_invincible_until = 0

        self.level_background_colors = [
            (0, 0, 0),     # базовый темный фон
            (8, 10, 28),   # темно-синий оттенок
            (10, 28, 10),  # темно-зеленый оттенок
            (28, 10, 10)   # темно-красный оттенок
        ]
        # Кнопки выбора сложности
        self.difficulty_buttons = [
            Button(SCREEN_WIDTH//2 - 150, 200, 300, 50, "Лёгкая", GRAY),
            Button(SCREEN_WIDTH//2 - 150, 270, 300, 50, "Нормальная", GRAY),
            Button(SCREEN_WIDTH//2 - 150, 340, 300, 50, "Сложная", GRAY),
            Button(SCREEN_WIDTH//2 - 150, 410, 300, 50, "Хардкор", RED),
            Button(SCREEN_WIDTH//2 - 100, 500, 200, 50, "Назад", RED)
        ]

        # Кнопки экрана сохранений
        self.saves_buttons = [
            Button(50, 100, 200, 40, "Слот 1", GRAY),
            Button(50, 150, 200, 40, "Слот 2", GRAY),
            Button(50, 200, 200, 40, "Слот 3", GRAY),
            Button(50, 250, 200, 40, "Назад", RED)
        ]

        # Кнопки удаления для слотов 1-3 (иконка корзины)
        self.saves_delete_buttons = [
            Button(260, 100, 40, 40, "", RED),
            Button(260, 150, 40, 40, "", RED),
            Button(260, 200, 40, 40, "", RED)
        ]
        # Кнопка "Новая игра" на экране сохранений
        self.saves_new_button = Button(50, 300, 200, 40, "Новая игра", GREEN)
        # Загрузка изображения корзины
        self.trash_icon = None

        self.start_x = int(2 * TILE_SIZE * MAP_SCALE)
        self.start_y = int((3 * TILE_SIZE + mechanics.TOP_BAR) * MAP_SCALE)
        self.player_size = int(TILE_SIZE * MAP_SCALE)
        self.player_rect = pygame.Rect(self.start_x, self.start_y, self.player_size, self.player_size)
        self.world_width = int(SCREEN_WIDTH * MAP_SCALE)
        self.world_height = int(SCREEN_HEIGHT * MAP_SCALE)
        self.camera_x = 0
        self.camera_y = 0


        # ЗАГОТОВКА: Система спрайтов персонажа (16 спрайтов)
        self.player_direction = "down"  # down, up, left, right
        self.player_animation_frame = 0
        self.animation_timer = 0
        self.animation_speed = 120  # мс между кадрами


        # Инвентарь игрока (покупается 1 раз, сбрасывается после уровня)
        self.inventory = {
            "фонарик": False,
            "красная пыль": False,
            "соль": False,
            "проектор": False,
            "аккумулятор": False,
            "крест": False,
            "кровь": False,
            "радио": False,
            "эмп": False,
            "уф фонарь": False,
        }
        self.inventory_items = [
            "фонарик",
            "красная пыль",
            "соль",
            "проектор",
            "аккумулятор",
            "крест",
            "кровь",
            "радио",
            "эмп",
            "уф фонарь",
        ]

        # Состояние для плавного движения
        self.keys_pressed = {
            pygame.K_LEFT: False,
            pygame.K_RIGHT: False,
            pygame.K_UP: False,
            pygame.K_DOWN: False,
            pygame.K_a: False,
            pygame.K_d: False,
            pygame.K_w: False,
            pygame.K_s: False
        }
        self.move_timer = 0
        self.move_delay = 150  # миллисекунды между движениями
        
        # Состояние для диалога сохранения
        self.show_save_prompt = False
        self.save_prompt_buttons = [
            Button(SCREEN_WIDTH//2 - 100, SCREEN_HEIGHT//2 + 20, 80, 40, "Да", GREEN),
            Button(SCREEN_WIDTH//2 + 20, SCREEN_HEIGHT//2 + 20, 80, 40, "Нет", RED)
        ]
        self.moving = False
        # Временное информационное сообщение (малый диалог)
        self.info_message = None
        self.info_until = 0
        self.uv_mode = False

        self.inventory_images = assets.load_inventory_images()
        self.trash_icon = assets.load_trash_icon()
        self.player_sprites = assets.load_player_sprites()
        
        # Менеджер приведений
        self.ghost_manager = GhostManager()
        
        # Менеджер инвентаря
        self.inventory_manager = InventoryManager(self)
        
        # Генерация стен на карте (по умолчанию или из уровня)
        self.level_data = None
        self.level_file = None # Путь к файлу уровня
        self.current_level_id = None  # Идентификатор уровня из реестра
        self.walls = []
        self.ghost_spawns = []  # Спавны приведений
        self.computer_closed = assets.load_computer_closed()
        self.computer_open = assets.load_computer_open()
        
        self.level_hitboxes = []  # Хитбоксы из уровня
        self.vignette_texture = None
        self.vignette_radius = 200
        # Компьютер для магазина
    
        self.computer = self.computer_closed
        # Позиция компьютера в правом нижнем углу
        self.computer_rect = None
        if self.computer:
            computer_size = int(80 * MAP_SCALE)
            margin = int(20 * MAP_SCALE)
            self.computer_rect = pygame.Rect(
                self.world_width - computer_size - margin,
                self.world_height - computer_size - margin,
                computer_size,
                computer_size
            )
        self.near_computer = False  # Флаг близости к компьютеру
        self.update_camera()

    def update_camera(self):
        """Обновляет смещение камеры, центрируя экран на игроке в пределах мира."""
        target_x = self.player_rect.centerx - SCREEN_WIDTH // 2
        target_y = self.player_rect.centery - SCREEN_HEIGHT // 2
        self.camera_x = max(0, min(target_x, self.world_width - SCREEN_WIDTH))
        self.camera_y = max(0, min(target_y, self.world_height - SCREEN_HEIGHT))

    def _show_game_info(self, text, duration_ms=1800):
        self.info_message = text
        self.info_until = pygame.time.get_ticks() + duration_ms

    def default_journal_evidence(self):
        return {k: False for k in EVIDENCE_PROFILE_KEYS}

    def normalize_journal_evidence(self, value):
        if not isinstance(value, dict):
            return self.default_journal_evidence()
        return {k: bool(value.get(k, False)) for k in EVIDENCE_PROFILE_KEYS}

    def use_radio(self):
        """Спросить у призрака через радиоприемник."""
        if not self.inventory.get("радио", False):
            self._show_game_info("Радио не куплено.", 900)
            return
        ok, text = self.ghost_manager.ask_radio(self.player_rect)
        self._show_game_info(text, 1800 if ok else 1200)

    def use_emf(self):
        """Скан ЭМП рядом с игроком."""
        if not self.inventory.get("эмп", False):
            self._show_game_info("ЭМП не куплен.", 900)
            return
        level, text = self.ghost_manager.scan_emf(self.player_rect)
        self._show_game_info(text, 1600 if level < 5 else 2200)

    def toggle_uv_mode(self):
        """УФ-режим подсветки следов (визуализация улик)."""
        if not self.inventory.get("уф фонарь", False):
            self._show_game_info("УФ фонарь не куплен.", 900)
            return
        self.uv_mode = not self.uv_mode
        self._show_game_info(f"УФ-режим: {'вкл' if self.uv_mode else 'выкл'}", 900)


    def reset_inventory(self):
        """ Сброс инвентаря после прохождения уровня"""
        for item in self.inventory:
            self.inventory[item] = False
    def load_level(self, level_file_path):
        """
        Загружает уровень из JSON файла.
        """
        self.level_data = mechanics.load_level_from_json(level_file_path)
        if self.level_data:
            self.level_file = level_file_path
            self.bg_level1 = None
            mechanics.scale_level_data(self.level_data, MAP_SCALE)
            self.world_width = int(self.level_data.get("world_width", SCREEN_WIDTH * MAP_SCALE))
            self.world_height = int(self.level_data.get("world_height", SCREEN_HEIGHT * MAP_SCALE))
            # Загружаем стены
            self.walls = mechanics.generate_walls(self.level_data)
            self.walls = mechanics.add_map_boundary_walls(
                self.walls, self.world_width, self.world_height, MAP_SCALE
            )
            # Загружаем хитбоксы
            self.level_hitboxes = mechanics.get_hitboxes_from_level(self.level_data)
            # Загружаем спавны приведений
            self.ghost_spawns = mechanics.get_ghost_spawns_from_level(self.level_data)
            # Спавним приведений (передаем level_data для чтения комнат)
            self.ghost_manager.spawn_ghosts_from_level(
                self.ghost_spawns,
                self.walls,
                self.level_hitboxes,
                self.level_data,
            )
            # Загружаем компьютер
            computer_rect = mechanics.get_computer_from_level(self.level_data)
            if computer_rect:
                self.computer_rect = computer_rect
                print(f"Компьютер загружен из уровня: x={computer_rect.x}, y={computer_rect.y}")
            else:
                # Если компьютера нет в уровне, используем дефолтную позицию
                if self.computer and not self.computer_rect:
                    computer_size = int(80 * MAP_SCALE)
                    margin = int(20 * MAP_SCALE)
                    self.computer_rect = pygame.Rect(
                        self.world_width - computer_size - margin,
                        self.world_height - computer_size - margin,
                        computer_size,
                        computer_size
                    )
                    print("Используется дефолтная позиция компьютера")
                self.computer = self.computer_closed
                self.near_computer = False
            print(f"Уровень загружен: {level_file_path}")
            self.journal_open = False
            if self.loaded_journal_evidence is not None:
                self.journal_evidence = self.loaded_journal_evidence
                self.loaded_journal_evidence = None
            else:
                self.journal_evidence = self.default_journal_evidence()
            # Создаём текстуру виньетки для эффекта затемнения (один раз при загрузке)
            self._create_vignette_texture()
            self.update_camera()
        else:
            print(f"Не удалось загрузить уровень: {level_file_path}")
            self._create_vignette_texture()  # Эффект затемнения всегда при входе в уровень
            self.update_camera()
    
    def _create_vignette_texture(self):
        """Создаёт текстуру затемнения: центр прозрачный (видно игру), края — благородная тёмная дымка."""
        size = 10240
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2
        visible_radius = 120   # Небольшой круг вокруг игрока
        falloff_radius = 220   # Плавный переход к полной дымке
        
        # Благородный глубокий тёмно-синий/фиолетовый оттенок вместо серой пыли
        # Создаёт атмосферу таинственности
        fog_color = (15, 12, 35)  # Глубокий индиго
        
        for x in range(0, size, 4):
            for y in range(0, size, 4):
                d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                if d < visible_radius:
                    alpha = 0
                elif d < falloff_radius:
                    t = (d - visible_radius) / (falloff_radius - visible_radius)
                    alpha = min(230, int(230 * (t ** 1.2)))  # Чуть менее непрозрачно
                else:
                    alpha = 230  # Не полностью непрозрачно для атмосферы
                s.fill((fog_color[0], fog_color[1], fog_color[2], alpha), (x, y, 4, 4))
        self.vignette_texture = s
    
    def _create_clipped_vignette_overlay(self):
        """Создаёт оверлей с кругом видимости, обрезанным по границам комнаты."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        
        fog_r, fog_g, fog_b = 15, 12, 35
        max_alpha = 220
        
        # Заполняем весь экран туманом
        overlay.fill((fog_r, fog_g, fog_b, max_alpha))
        
        # Определяем текущую комнату игрока
        player_room = None
        if hasattr(self, 'level_data') and self.level_data and 'rooms' in self.level_data:
            for room_data in self.level_data['rooms']:
                room_rect = pygame.Rect(room_data['x'], room_data['y'], 
                                        room_data['width'], room_data['height'])
                if room_rect.collidepoint(self.player_rect.centerx, self.player_rect.centery):
                    player_room = room_rect
                    break
        
        # Параметры круга видимости
        player_cx = self.player_rect.centerx - self.camera_x
        player_cy = self.player_rect.centery - self.camera_y
        visible_radius = 120
        falloff_radius = 200
        
        # Рисуем круг видимости с градиентом, но только внутри комнаты
        for y in range(0, SCREEN_HEIGHT, 3):
            for x in range(0, SCREEN_WIDTH, 3):
                # Проверяем, находится ли пиксель внутри комнаты
                world_x = x + self.camera_x
                world_y = y + self.camera_y
                in_room = player_room is None or player_room.collidepoint(world_x, world_y)
                
                if not in_room:
                    # За пределами комнаты — полный туман
                    continue
                
                # Расстояние до игрока
                d = ((x - player_cx) ** 2 + (y - player_cy) ** 2) ** 0.5
                
                if d < visible_radius:
                    # Полностью видимая зона
                    alpha = 0
                elif d < falloff_radius:
                    # Градиентная зона
                    t = (d - visible_radius) / (falloff_radius - visible_radius)
                    alpha = int(max_alpha * (t ** 1.5))
                else:
                    # За пределами круга внутри комнаты — туман
                    continue
                
                # Рисуем пиксель с нужной прозрачностью
                overlay.fill((fog_r, fog_g, fog_b, alpha), (x, y, 3, 3))
        
        return overlay
    
    def _create_room_visibility_overlay(self):
        """Создаёт оверлей для системы видимости комнат (при наличии фонарика) с плавным градиентом."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        
        # Благородный тёмно-синий/фиолетовый для скрытых комнат
        fog_r, fog_g, fog_b = 15, 12, 35
        max_alpha = 210
        
        # Заполняем весь экран туманом
        overlay.fill((fog_r, fog_g, fog_b, max_alpha))
        
        # Определяем, в какой комнате находится игрок
        player_room = None
        if hasattr(self, 'level_data') and self.level_data and 'rooms' in self.level_data:
            for room_data in self.level_data['rooms']:
                room_rect = pygame.Rect(room_data['x'], room_data['y'], 
                                        room_data['width'], room_data['height'])
                if room_rect.collidepoint(self.player_rect.centerx, self.player_rect.centery):
                    player_room = room_rect
                    break
        
        # Если игрок в комнате - делаем эту комнату видимой с плавным градиентом
        if player_room:
            # Ширина градиентной зоны
            gradient_width = 80
            
            # Внутренняя полностью видимая область (чуть меньше комнаты)
            inner_rect = player_room.inflate(-20, -20)
            
            # Внешняя граница градиента
            outer_rect = player_room.inflate(gradient_width * 2, gradient_width * 2)
            
            # Рисуем градиент от внешней границы к внутренней
            total_steps = gradient_width + 10  # Количество шагов градиента
            
            for step in range(total_steps, -1, -1):
                # Интерполяция от outer_rect к inner_rect
                t = step / total_steps  # 1.0 = внешний край, 0.0 = внутренний край
                
                # Плавная кривая для более естественного градиента (ease-in-out)
                t_smooth = t * t * (3 - 2 * t)
                
                # Альфа: от max_alpha (внешний) до 0 (внутренний)
                alpha = int(max_alpha * t_smooth)
                
                # Размер текущего прямоугольника
                width_diff = outer_rect.width - inner_rect.width
                height_diff = outer_rect.height - inner_rect.height
                
                current_width = inner_rect.width + int(width_diff * t)
                current_height = inner_rect.height + int(height_diff * t)
                
                current_x = inner_rect.centerx - current_width // 2
                current_y = inner_rect.centery - current_height // 2
                
                current_rect = pygame.Rect(
                    current_x - self.camera_x,
                    current_y - self.camera_y,
                    current_width,
                    current_height
                )
                
                # Рисуем прямоугольник с текущей альфой
                pygame.draw.rect(overlay, (fog_r, fog_g, fog_b, alpha), current_rect)
            
            # Финальная полностью прозрачная внутренняя область
            inner_screen_rect = pygame.Rect(
                inner_rect.x - self.camera_x,
                inner_rect.y - self.camera_y,
                inner_rect.width,
                inner_rect.height
            )
            pygame.draw.rect(overlay, (0, 0, 0, 0), inner_screen_rect)
        
        return overlay
        
      
    
    def load_level_by_id(self, level_id):
        """
        Загружает уровень по его строковому идентификатору из реестра уровней.
        """
        level_path = level_config.get_level_file_path(level_id)
        if not level_path or not os.path.exists(level_path):
            print(f"Уровень с id '{level_id}' не найден или файл отсутствует")
            return

        self.current_level_id = level_id
        # Загружаем данные уровня через существующую функцию
        self.load_level(level_path)

    def load_level_for_current_level(self):
        """
        Загружает уровень на основе текущего номера уровня (player_level),
        используя реестр уровней. При отсутствии записи в реестре
        используется старый механизм поиска levelN.json / level.json.
        """
        # 1) Пытаемся найти уровень в реестре
        level_path = level_config.get_level_file_path_by_number(self.player_level)
        if level_path and os.path.exists(level_path):
            meta = level_config.get_level_by_number(self.player_level)
            if meta:
                self.current_level_id = meta.get("id")
            self.load_level(level_path)
            return

        # 2) Фолбэк: старое поведение по файлам
        level_files = [
            f"level{self.player_level}.json",  # level1.json, level2.json и т.д.
            "level.json",  # Дефолтный уровень
        ]

        for level_file in level_files:
            if os.path.exists(level_file):
                self.current_level_id = None
                self.load_level(level_file)
                break

    def reset_player_position(self):
        """Сбрасывает позицию персонажа на начальную (НЕ сбрасывает HP!)"""
        self.player_rect.x = self.start_x
        self.player_rect.y = self.start_y
        self.moving = False
        # HP НЕ сбрасываем здесь — они сохраняются между уровнями
        self.hit_invincible_until = 0
        for key in self.keys_pressed:
            self.keys_pressed[key] = False
        self.update_camera()
    
    def reset_for_new_game(self):
        """Полный сброс для новой игры"""
        self.player_hp = 5
        self.player_money = 100
        self.player_level = 1
        self.reset_inventory()
        self.reset_player_position()
        self.journal_open = False
        self.journal_evidence = self.default_journal_evidence()
        self.loaded_journal_evidence = None
    
        
    def buy_item(self, item_name, cost):
        """Покупка предмета в магазине"""
        #Todo: реализовать систему выкидывания при переполнении стека предметов
        if self.player_money >= cost and not self.inventory[item_name]:
            self.player_money -= cost
            self.inventory[item_name] = True
            return True
        return False

    def load_saves(self):
        try:
            with open(self.save_file, 'r', encoding = 'utf-8') as f: 
                return json.load(f)
        except:
            return {"slot1": None, "slot2": None, "slot3": None}

    def save_game(self, slot):
        from inventory_system import ItemType
        item_counts_serial = {
            "BATTERY": self.inventory_manager.item_counts.get(ItemType.BATTERY, 0),
            "BLOOD": self.inventory_manager.item_counts.get(ItemType.BLOOD, 0),
            "CROSS": self.inventory_manager.item_counts.get(ItemType.CROSS, 0),
            "RED_DUST": self.inventory_manager.item_counts.get(ItemType.RED_DUST, 0),
            "SALT": self.inventory_manager.item_counts.get(ItemType.SALT, 0)
        }
        save_data = {
            "level": self.player_level,
            "hp": self.player_hp,
            "money": self.player_money,
            "inventory": self.inventory.copy(),
            "item_counts": item_counts_serial,
            "journal_evidence": self.normalize_journal_evidence(self.journal_evidence),
            "difficulty": self.difficulty_index,
            "difficulty_selected": self.difficulty_selected
        }
        self.saves[f"slot{slot}"] = save_data
        with open(self.save_file, 'w', encoding ='utf-8') as f:
            json.dump(self.saves, f, ensure_ascii = False, indent =2 )
        self.selected_save_slot = slot

    def load_game(self, slot):
        save_data = self.saves.get(f"slot{slot}")
        if save_data:
            self.player_level = save_data["level"]
            self.difficulty_index = save_data["difficulty"]
            self.difficulty_selected = save_data["difficulty_selected"]
            self.selected_save_slot = slot
            # Загружаем HP и деньги (с fallback для старых сохранений)
            self.player_hp = save_data.get("hp", 5)
            self.player_money = save_data.get("money", 100)
            self.journal_evidence = self.normalize_journal_evidence(save_data.get("journal_evidence"))
            self.loaded_journal_evidence = self.journal_evidence.copy()
            # Загружаем инвентарь (с fallback для старых сохранений)
            saved_inventory = save_data.get("inventory", None)
            if saved_inventory:
                self.inventory = saved_inventory.copy()
            else:
                self.reset_inventory()
            
            # Загружаем количество предметов (аккумуляторы, кровь)
            saved_counts = save_data.get("item_counts", None)
            if saved_counts:
                from inventory_system import ItemType
                self.inventory_manager.item_counts[ItemType.BATTERY] = saved_counts.get("BATTERY", saved_counts.get("аккумулятор", 0))
                self.inventory_manager.item_counts[ItemType.BLOOD] = saved_counts.get("BLOOD", 0)
                self.inventory_manager.item_counts[ItemType.CROSS] = saved_counts.get("CROSS", 0)
                self.inventory_manager.item_counts[ItemType.RED_DUST] = saved_counts.get("RED_DUST", 0)
                self.inventory_manager.item_counts[ItemType.SALT] = saved_counts.get("SALT", 0)
            else:
                from inventory_system import ItemType
                self.inventory_manager.item_counts[ItemType.BATTERY] = 0
                self.inventory_manager.item_counts[ItemType.BLOOD] = 0
                self.inventory_manager.item_counts[ItemType.CROSS] = 0
                self.inventory_manager.item_counts[ItemType.RED_DUST] = 0
                self.inventory_manager.item_counts[ItemType.SALT] = 0
            
            return True
        return False

    def delete_save(self, slot):
        key = f"slot{slot}"
        if key in self.saves:
            self.saves[key] = None
            with open(self.save_file, 'w', encoding='utf-8') as f:
                json.dump(self.saves, f, ensure_ascii=False, indent=2)
        if self.selected_save_slot == slot:
            self.selected_save_slot = None
    

    def apply_display_mode(self):
        flags = pygame.FULLSCREEN if self.fullscreen else 0
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), flags)
        # Перезагружаем фон меню под новый размер экрана
        self.cork_board_bg = assets.load_cork_board(
            screen_width=self.screen.get_width(),
            screen_height=self.screen.get_height()
        )

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.apply_display_mode()
        self.update_settings_button_texts()

    def exit_game(self):
        self.running = False

    def set_state(self, new_state, reset_stack = False):
        if reset_stack:
            self.state_stack.clear()
        if new_state != self.state:
            self.previous_state = self.state
            # Останавливаем движение при выходе из игры
            if self.state == GameState.GAME and new_state != GameState.GAME:
                self.moving = False
                for key in self.keys_pressed:
                    self.keys_pressed[key] = False
            self.state = new_state
            # Сбрасываем позицию персонажа при переходе в игру
            if new_state == GameState.GAME:
                self.reset_player_position()
                # Перезагружаем уровень для текущего уровня
                self.load_level_for_current_level()

    def push_state(self, new_state):
        if new_state != self.state:
            self.state_stack.append(self.state)
            self.previous_state = self.state
            # Останавливаем движение при выходе из игры
            if self.state == GameState.GAME and new_state != GameState.GAME:
                self.moving = False
                for key in self.keys_pressed:
                    self.keys_pressed[key] = False
            self.state = new_state
            # Сбрасываем позицию персонажа при переходе в игру
            if new_state == GameState.GAME:
                self.reset_player_position()
                # Перезагружаем уровень для текущего уровня
                self.load_level_for_current_level()
    def go_back(self):
        if self.state_stack:
            target_state = self.state_stack.pop()
            self.previous_state = self.state
            self.state = target_state
        else:
            self.set_state(GameState.MENU, reset_stack = True)

    def change_state(self, new_state):
        if new_state != self.state:
            self.previous_state = self.state
            self.state = new_state

    def update_settings_button_texts(self):
        # Индексы: 0 Назад, 1 Громкость, 2 Полноэкранный, 3 Сброс
        self.settings_buttons[1].text = f"Громкость: {self.volume}%"
        self.settings_buttons[2].text = "Полноэкранный: Вкл" if self.fullscreen else "Полноэкранный: Выкл"

    def draw(self):
        if self.state == GameState.MENU:
            draws.draw_menu(self)
        elif self.state == GameState.GAME:
            if not self.show_save_prompt:
                mechanics.update_player_movement(self)
                pz = self.inventory_manager.get_projector_zones()
                self.ghost_manager.update(
                    self.player_rect,
                    self.walls,
                    self.level_hitboxes,
                    projector_zones=pz,
                    world_width=self.world_width,
                    world_height=self.world_height,
                )
                # Столкновение с приведением — отнимаем HP
                now = pygame.time.get_ticks()
                if self.ghost_manager.check_player_collision(self.player_rect) and now >= self.hit_invincible_until:
                    self.player_hp = max(0, self.player_hp - 1)
                    self.hit_invincible_until = now + 1500
            else:
                self.moving = False
                for key in self.keys_pressed:
                    self.keys_pressed[key]=False
            draws.draw_game(self)
        elif self.state == GameState.SHOP:
            self.moving = False
            draws.draw_shop(self)
        elif self.state == GameState.SETTINGS:
            draws.draw_settings(self)
        elif self.state == GameState.DIFF:
            draws.draw_difficulty(self)
        elif self.state == GameState.SAVES:
            draws.draw_saves(self)
        elif self.state == GameState.HOWTO:
            draws.draw_howto(self)
        # Отображаем информационное сообщение поверх всех экранов
        if self.info_message and pygame.time.get_ticks() < self.info_until:
            # Полупрозрачный фон
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            overlay.set_alpha(128)
            overlay.fill(BLACK)
            self.screen.blit(overlay, (0, 0))
            
            # Диалоговое окно для сообщения
            info_rect = pygame.Rect(SCREEN_WIDTH//2 - 300, SCREEN_HEIGHT//2 - 40, 600, 80)
            pygame.draw.rect(self.screen, DARK_GRAY, info_rect)
            pygame.draw.rect(self.screen, WHITE, info_rect, 3)
            
            info_font = pygame.font.Font(None, 32)
            info_text = info_font.render(self.info_message, True, WHITE)
            info_text_rect = info_text.get_rect(center=info_rect.center)
            self.screen.blit(info_text, info_text_rect)
        elif self.info_message and pygame.time.get_ticks() >= self.info_until:
            self.info_message = None
        
        pygame.display.flip()
    def run(self):
        while self.running:
            handlers.handle_event(self)
            
            if self.state == GameState.GAME:
                self.inventory_manager.update_placed_items()
                self.inventory_manager.update_projector()
            
            self.draw()

            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()
if __name__ == "__main__":
    game = Game()
    game.run()
