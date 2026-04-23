"""
Модуль для работы с приведениями в игре.
FSM система движения основана на определении комнат по стенам.
Включает A* алгоритм для поиска кратчайшего пути.
"""
import pygame
import random
import math
import os
from configparser import ConfigParser
from enum import Enum
from constants import TILE_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT, MAP_SCALE
import heapq


def _to_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "да"}


def _to_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return default


class GhostAbilitiesConfig:
    """Читает ghost_abilities.ini: профили ghost_* (скорости, флаги движения, улики/ЭМП и т.д.)."""

    BOOL_KEYS = (
        "can_fly",
        "can_walk",
        "can_phase_walls",
        "can_teleport",
        "amp",
        "ultraviolet",
        "ghostorb",
        "radio",
    )
    FLOAT_KEYS = ("speed", "patrol_speed", "chase_speed", "search_speed")

    DEFAULTS = {
        "display_name": "",
        "can_fly": False,
        "can_walk": True,
        "can_phase_walls": False,
        "can_teleport": False,
        "speed": 3.0,
        "patrol_speed": 2.0,
        "chase_speed": 2.0,
        "search_speed": 2.0,
        "amp": False,
        "ultraviolet": False,
        "ghostorb": False,
        "radio": False,
    }

    def __init__(self, ini_path=None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.ini_path = ini_path or os.path.join(base_dir, "ghost_abilities.ini")
        self.parser = ConfigParser()
        self.profiles = {"default": self.DEFAULTS.copy()}
        self._load()

    def _parse_section(self, section):
        profile = self.DEFAULTS.copy()
        for key in self.BOOL_KEYS:
            if self.parser.has_option(section, key):
                profile[key] = _to_bool(self.parser.get(section, key), self.DEFAULTS[key])
        for key in self.FLOAT_KEYS:
            if self.parser.has_option(section, key):
                profile[key] = _to_float(self.parser.get(section, key), self.DEFAULTS[key])
        if self.parser.has_option(section, "display_name"):
            profile["display_name"] = self.parser.get(section, "display_name", fallback="").strip()
        return profile

    def _load(self):
        if not os.path.isfile(self.ini_path):
            print(f"[GhostConfig] INI не найден: {self.ini_path}. Используются значения по умолчанию.")
            return
        self.parser.read(self.ini_path, encoding="utf-8")
        for section in self.parser.sections():
            if not section.startswith("ghost_"):
                continue
            profile_name = section.replace("ghost_", "", 1).strip()
            if not profile_name:
                continue
            self.profiles[profile_name] = self._parse_section(section)

    def get_profile(self, profile_name):
        base = self.profiles.get("default", self.DEFAULTS.copy()).copy()
        specific = self.profiles.get(profile_name, {})
        base.update(specific)
        return base

    def random_profile_name(self):
        """Случайный профиль из INI; секция ghost_default только база для merge и не выбирается."""
        names = [k for k in self.profiles.keys() if k != "default"]
        return random.choice(names) if names else "default"


class Node:
    """Узел для A* алгоритма"""
    def __init__(self, x, y, g_cost=0, h_cost=0, parent=None):
        self.x = x
        self.y = y
        self.g_cost = g_cost  # Стоимость от старта
        self.h_cost = h_cost  # Эвристическая стоимость до цели
        self.f_cost = g_cost + h_cost  # Общая стоимость
        self.parent = parent
    
    def __lt__(self, other):
        return self.f_cost < other.f_cost
    
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

class AStar:
    """A* алгоритм для поиска пути"""
    def __init__(self, grid_size=16):
        self.grid_size = grid_size
    
    def heuristic(self, node, goal):
        """Манхэттенское расстояние как эвристика"""
        return abs(node.x - goal.x) + abs(node.y - goal.y)
    
    def get_neighbors(self, node, walls, level_hitboxes, screen_width, screen_height):
        """Получает соседние узлы"""
        neighbors = []
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)]
        
        for dx, dy in directions:
            new_x = node.x + dx * self.grid_size
            new_y = node.y + dy * self.grid_size
            
            # Проверяем границы экрана
            if (new_x < 0 or new_x >= screen_width or 
                new_y < 0 or new_y >= screen_height):
                continue
            
            # Проверяем коллизии со стенами И хитбоксами
            # Используем размер приведения (TILE_SIZE) для проверки коллизий
            test_rect = pygame.Rect(new_x - TILE_SIZE//2, new_y - TILE_SIZE//2, 
                                  TILE_SIZE, TILE_SIZE)
            collision = False
            
            # Проверяем стены
            for wall_rect, _ in walls:
                if test_rect.colliderect(wall_rect):
                    collision = True
                    break
            
            # Проверяем хитбоксы
            if not collision:
                for hitbox_rect in level_hitboxes:
                    if test_rect.colliderect(hitbox_rect):
                        collision = True
                        break
            
            if not collision:
                # Диагональное движение стоит больше
                cost = 14 if abs(dx) + abs(dy) == 2 else 10
                neighbors.append(Node(new_x, new_y, cost, 0))
        
        return neighbors
    
    def find_path(self, start_pos, goal_pos, walls, level_hitboxes=None, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT):
        """Находит путь от start_pos до goal_pos"""
        if level_hitboxes is None:
            level_hitboxes = []
            
        # Привязываем к сетке
        start_x = (start_pos[0] // self.grid_size) * self.grid_size
        start_y = (start_pos[1] // self.grid_size) * self.grid_size
        goal_x = (goal_pos[0] // self.grid_size) * self.grid_size
        goal_y = (goal_pos[1] // self.grid_size) * self.grid_size
        
        start_node = Node(start_x, start_y)
        goal_node = Node(goal_x, goal_y)
        
        open_list = []
        closed_set = set()
        
        heapq.heappush(open_list, start_node)
        
        max_iterations = 1000  # Ограничение для производительности
        iterations = 0
        
        while open_list and iterations < max_iterations:
            iterations += 1
            current = heapq.heappop(open_list)
            
            if current == goal_node:
                # Восстанавливаем путь
                path = []
                while current:
                    path.append((current.x, current.y))
                    current = current.parent
                return path[::-1]  # Возвращаем в правильном порядке
            
            closed_set.add((current.x, current.y))
            
            for neighbor in self.get_neighbors(current, walls, level_hitboxes, screen_width, screen_height):
                if (neighbor.x, neighbor.y) in closed_set:
                    continue
                
                neighbor.g_cost = current.g_cost + neighbor.g_cost
                neighbor.h_cost = self.heuristic(neighbor, goal_node)
                neighbor.f_cost = neighbor.g_cost + neighbor.h_cost
                neighbor.parent = current
                
                # Проверяем, есть ли уже лучший путь к этому узлу
                better_path_exists = False
                for open_node in open_list:
                    if (open_node.x == neighbor.x and open_node.y == neighbor.y and 
                        open_node.g_cost <= neighbor.g_cost):
                        better_path_exists = True
                        break
                
                if not better_path_exists:
                    heapq.heappush(open_list, neighbor)
        
        return []  # Путь не найден

class GhostState(Enum):
    """Состояния приведения"""
    IDLE = "idle"           # Бездействие
    PATROL = "patrol"       # Патрулирование
    WANDER = "wander"       # Блуждание между комнатами
    SEARCH = "search"       # Поиск игрока
    CHASE = "chase"         # Преследование игрока
    RETURN = "return"       # Возврат домой
    INVISIBLE = "invisible" # Невидимость (исчезновение)

class Room:
    """Простое представление области/комнаты"""
    def __init__(self, x, y, width, height, room_id):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.room_id = room_id
        self.rect = pygame.Rect(x, y, width, height)
    
    def contains_point(self, x, y):
        """Проверяет, находится ли точка в области"""
        return self.rect.collidepoint(x, y)
    
    def get_random_point(self, margin=None):
        """Возвращает случайную точку внутри области"""
        m = int(30 * MAP_SCALE) if margin is None else margin
        return (
            random.randint(self.x + m, self.x + self.width - m),
            random.randint(self.y + m, self.y + self.height - m)
        )
    
    def get_center(self):
        """Возвращает центр области"""
        return (self.x + self.width // 2, self.y + self.height // 2)

class Ghost:
    def __init__(self, x, y, ghost_sprite, rooms, home_room_id=0, abilities=None, ghost_kind="default"):
        self.x = x
        self.y = y
        self.rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        self.sprite = ghost_sprite
        self.rooms = rooms
        self.home_room_id = home_room_id
        self.ghost_kind = ghost_kind
        # Пример: значения из INI записываем на экземпляр (урок «чтение конфига»).
        # Поведение призрака от них пока не зависит — следующий этап.
        abilities = abilities or {}
        self.can_fly = abilities.get("can_fly", False)
        self.can_walk = abilities.get("can_walk", True)
        self.can_phase_walls = abilities.get("can_phase_walls", False)
        self.can_teleport = abilities.get("can_teleport", False)
        self.display_name = (abilities.get("display_name") or "").strip() or ghost_kind
        self.amp = abilities.get("amp", False)
        self.ultraviolet = abilities.get("ultraviolet", False)
        self.ghostorb = abilities.get("ghostorb", False)
        self.radio = abilities.get("radio", False)
        self.aggression = 10  # 0..100, обновляется в update()
        
        # FSM состояние - НАЧИНАЕМ НЕВИДИМЫМ
        self.state = GhostState.INVISIBLE
        self.state_timer = 0
        
        # Параметры движения (из ghost_abilities.ini / профиля)
        self.speed = _to_float(abilities.get("speed"), 3.0)
        self.patrol_speed = _to_float(abilities.get("patrol_speed"), 2.0)
        self.chase_speed = _to_float(abilities.get("chase_speed"), 2.0)
        self.search_speed = _to_float(abilities.get("search_speed"), 2.0)
        # A* алгоритм
        self.astar = AStar(grid_size=32)  # Увеличено с 16 до 32 для ускорения
        self.current_path = []
        self.path_index = 0
        
        # Целевая точка
        self.target_x = None
        self.target_y = None
        
        # Улучшенное патрулирование
        self.patrol_points = []
        self.current_patrol_index = 0
        self.patrol_rooms = []  # Комнаты для патрулирования
        self.patrol_change_timer = 0
        self._generate_smart_patrol_points()
        
        # Таймеры (сокращенные для быстрого тестирования)
        self.idle_duration = random.randint(30, 90)  # 0.5-1.5 секунды
        self.patrol_duration = random.randint(180, 360)  # 3-6 секунд
        self.room_change_duration = random.randint(300, 600)  # 5-10 секунд
        
        # Таймеры для исчезновения/появления (в кадрах, 60 FPS)
        self.invisibility_timer = 0  # Таймер до следующего исчезновения
        self.invisibility_duration = 0  # Длительность текущего исчезновения
        
        # НАЧАЛЬНОЕ ПОЯВЛЕНИЕ: 30-90 секунд после старта уровня
        self.initial_appear_time = random.randint(30 * 60, 90 * 60)  # 30-90 секунд
        self.is_first_appearance = True  # Флаг первого появления
        
        # После первого появления: 30-60 секунд до исчезновения
        self.time_until_invisible = random.randint(2 * 60, 5 * 60)
        self.invisible_duration_range = (2 * 60, 5 * 60)  # 15-30 секунд невидимости
        
        # Пауза после появления (приведение стоит на месте ~1 секунду)
        self.appear_freeze_timer = 0
        self.appear_freeze_duration = 60  # 1 секунда при 60 FPS
        self.is_frozen_after_appear = False
        
        # Прозрачность для эффекта призрачности
        self.alpha = random.randint(150, 200)
        self.base_alpha = self.alpha  # Сохраняем базовую прозрачность
        # Начинаем полностью невидимым
        if self.sprite:
            self.sprite.set_alpha(0)
        
        # Анимация спавна
        self.spawn_animation = None
        self.spawn_animation_frame = 0
        self.spawn_animation_timer = 0
        self.spawn_animation_speed = 300  # мс между кадрами (25 кадров × 300мс = 7.5 сек)
        self.is_playing_spawn = False
        self._load_spawn_animation()
    
    def _load_spawn_animation(self):
        """Загрузка анимации спавна из GIF"""
        import os
        from PIL import Image
        
        gif_path = os.path.join("sprite_parts", "spawn.gif")
        gif = Image.open(gif_path)
        self.spawn_animation = []
        
        # Извлекаем все кадры из GIF
        try:
            while True:
                # Конвертируем кадр в RGBA и масштабируем до размера призрака
                frame = gif.convert("RGBA").resize((TILE_SIZE, TILE_SIZE), Image.Resampling.LANCZOS)
                
                # Конвертируем PIL Image в Pygame Surface
                pygame_surface = pygame.image.fromstring(frame.tobytes(), frame.size, frame.mode)
                self.spawn_animation.append(pygame_surface)
                
                # Переходим к следующему кадру
                gif.seek(gif.tell() + 1)
        except EOFError:
            pass  # Достигли конца GIF
    
    def _generate_smart_patrol_points(self):
        """Генерирует умные точки патрулирования в разных комнатах"""
        if not self.rooms:
            return
        
        # Определяем комнаты для патрулирования
        self.patrol_rooms = []
        
        # Всегда включаем домашнюю комнату
        if self.home_room_id < len(self.rooms):
            self.patrol_rooms.append(self.home_room_id)
        
        # Добавляем другие комнаты для разнообразия
        available_rooms = list(range(len(self.rooms)))
        if self.home_room_id in available_rooms:
            available_rooms.remove(self.home_room_id)
        
        # Добавляем 1-3 случайные комнаты в зависимости от общего количества
        num_extra_rooms = min(random.randint(1, 3), len(available_rooms))
        if num_extra_rooms > 0:
            extra_rooms = random.sample(available_rooms, num_extra_rooms)
            self.patrol_rooms.extend(extra_rooms)
        
        # Генерируем точки для каждой комнаты
        self.patrol_points = []
        for room_id in self.patrol_rooms:
            if room_id < len(self.rooms):
                room = self.rooms[room_id]
                # 2-4 точки на комнату
                num_points = random.randint(2, 4)
                for _ in range(num_points):
                    point = room.get_random_point()
                    self.patrol_points.append(point)
        
    
    
    def get_current_room_id(self):
        """Определяет, в какой области находится приведение"""
        ghost_center = self.rect.center
        for i, room in enumerate(self.rooms):
            if room.contains_point(ghost_center[0], ghost_center[1]):
                return i
        return -1  # Не в области
    
    def get_player_room_id(self, player_rect):
        """Определяет, в какой области находится игрок"""
        player_center = player_rect.center
        for i, room in enumerate(self.rooms):
            if room.contains_point(player_center[0], player_center[1]):
                return i
        return -1  # Не в области
    
    def is_same_room_as_player(self, player_rect):
        """Проверяет, находятся ли приведение и игрок в одной области"""
        ghost_room = self.get_current_room_id()
        player_room = self.get_player_room_id(player_rect)
        return ghost_room != -1 and ghost_room == player_room
    
    def get_distance_to_player(self, player_rect):
        """Возвращает расстояние до игрока"""
        ghost_center = self.rect.center
        player_center = player_rect.center
        return math.sqrt((ghost_center[0] - player_center[0]) ** 2 + 
                        (ghost_center[1] - player_center[1]) ** 2)
    
    
    def set_target_with_pathfinding(
        self,
        target_x,
        target_y,
        walls,
        level_hitboxes,
        world_width=SCREEN_WIDTH,
        world_height=SCREEN_HEIGHT,
    ):
        """Устанавливает цель с использованием A* для поиска пути"""
        start_pos = (self.rect.centerx, self.rect.centery)
        goal_pos = (target_x, target_y)
        
        path = self.astar.find_path(
            start_pos,
            goal_pos,
            walls,
            level_hitboxes,
            screen_width=world_width,
            screen_height=world_height,
        )
        
        if path and len(path) > 1:
            self.current_path = path
            self.path_index = 1  # Начинаем с первой точки (0 - это текущая позиция)
            self.target_x, self.target_y = self.current_path[self.path_index]
            return True
        else:
            # Если путь не найден, двигаемся напрямую
            self.current_path = []
            self.path_index = 0
            self.target_x = target_x
            self.target_y = target_y
            return False
    
    def move_along_path(self, speed=None, walls=None, level_hitboxes=None, projector_zones=None):
        """Движение по найденному пути. projector_zones — призрак не заходит в эти круги."""
        if walls is None:
            walls = []
        if level_hitboxes is None:
            level_hitboxes = []
        pz = projector_zones or []
        if not self.current_path or self.path_index >= len(self.current_path):
            return self.move_towards_target(speed, walls, level_hitboxes, pz)
        
        if speed is None:
            speed = self.speed
        
        # Двигаемся к текущей точке пути
        current_target = self.current_path[self.path_index]
        dx = current_target[0] - self.rect.centerx
        dy = current_target[1] - self.rect.centery
        distance = math.sqrt(dx * dx + dy * dy)
        
        if distance < speed:
            # Достигли текущей точки — проверяем, не внутри стены ли она
            old_x, old_y = self.rect.centerx, self.rect.centery
            self.rect.centerx = current_target[0]
            self.rect.centery = current_target[1]
            if self._intersects_any_wall(walls) or self._intersects_any_hitbox(level_hitboxes) or self._in_projector_zone(pz):
                self.rect.centerx, self.rect.centery = old_x, old_y
                self.current_path = []
                self.path_index = 0
                self.target_x = self.target_y = None
                return False
            self.x, self.y = self.rect.x, self.rect.y
            self.path_index += 1
            if self.path_index >= len(self.current_path):
                self.current_path = []
                self.path_index = 0
                return True
            self.target_x, self.target_y = self.current_path[self.path_index]
            return False
        
        # Двигаемся по осям отдельно — меньше шанс пройти сквозь стену
        dx = (dx / distance) * speed
        dy = (dy / distance) * speed
        
        old_x, old_y = self.rect.centerx, self.rect.centery
        self.rect.centerx += dx
        if self._intersects_any_wall(walls) or self._intersects_any_hitbox(level_hitboxes) or self._in_projector_zone(pz):
            self.rect.centerx = old_x
        self.rect.centery += dy
        if self._intersects_any_wall(walls) or self._intersects_any_hitbox(level_hitboxes) or self._in_projector_zone(pz):
            self.rect.centery = old_y
        self.x, self.y = self.rect.x, self.rect.y
        return False
    
    def _in_projector_zone(self, zones):
        """Точка rect.center внутри любого круга (cx, cy, radius)?"""
        for cx, cy, r in zones:
            dx = self.rect.centerx - cx
            dy = self.rect.centery - cy
            if dx*dx + dy*dy <= r*r:
                return True
        return False
    
    def _intersects_any_wall(self, walls):
        for wall_rect, _ in walls:
            if self.rect.colliderect(wall_rect):
                return True
        return False
    
    def _intersects_any_hitbox(self, hitboxes):
        for h in hitboxes:
            if self.rect.colliderect(h):
                return True
        return False

    def move_towards_target(self, speed=None, walls=None, level_hitboxes=None, projector_zones=None):
        """Движение к целевой точке (простое, без A*)"""
        if walls is None:
            walls = []
        if level_hitboxes is None:
            level_hitboxes = []
        pz = projector_zones or []
        if self.target_x is None or self.target_y is None:
            return False
        
        if speed is None:
            speed = self.speed
        
        # Вычисляем направление
        dx = self.target_x - self.rect.centerx
        dy = self.target_y - self.rect.centery
        distance = math.sqrt(dx * dx + dy * dy)
        
        if distance < speed:
            old_x, old_y = self.rect.centerx, self.rect.centery
            self.rect.centerx = self.target_x
            self.rect.centery = self.target_y
            if self._intersects_any_wall(walls) or self._intersects_any_hitbox(level_hitboxes) or self._in_projector_zone(pz):
                self.rect.centerx, self.rect.centery = old_x, old_y
            self.x, self.y = self.rect.x, self.rect.y
            return True
        
        dx = (dx / distance) * speed
        dy = (dy / distance) * speed
        old_x, old_y = self.rect.centerx, self.rect.centery
        self.rect.centerx += dx
        if self._intersects_any_wall(walls) or self._intersects_any_hitbox(level_hitboxes) or self._in_projector_zone(pz):
            self.rect.centerx = old_x
        self.rect.centery += dy
        if self._intersects_any_wall(walls) or self._intersects_any_hitbox(level_hitboxes) or self._in_projector_zone(pz):
            self.rect.centery = old_y
        self.x = self.rect.x
        self.y = self.rect.y
        return False
    
    def update_state(self, player_rect, walls, debug_mode=False):
        """Обновляет состояние FSM с подробным логированием"""
        previous_state = self.state
        self.state_timer += 1
        current_room = self.get_current_room_id()
        distance_to_player = self.get_distance_to_player(player_rect)
        same_room_as_player = self.is_same_room_as_player(player_rect)
        
        # Обработка анимации спавна
        if self.is_playing_spawn:
            current_time = pygame.time.get_ticks()
            if current_time - self.spawn_animation_timer >= self.spawn_animation_speed:
                self.spawn_animation_timer = current_time
                self.spawn_animation_frame += 1
                if self.spawn_animation_frame >= len(self.spawn_animation):
                    self.is_playing_spawn = False
                    self.spawn_animation_frame = 0
                    if self.sprite:
                        self.sprite.set_alpha(self.base_alpha)
            return
        
        # Обработка паузы после появления (приведение стоит на месте)
        if self.is_frozen_after_appear:
            self.appear_freeze_timer += 1
            if self.appear_freeze_timer >= self.appear_freeze_duration:
                self.is_frozen_after_appear = False
                self.appear_freeze_timer = 0
            return
        
        # Обработка механизма исчезновения/появления
        if self.state != GhostState.INVISIBLE:
            self.invisibility_timer += 1
            if self.invisibility_timer >= self.time_until_invisible:
                # Время исчезнуть
                self.state = GhostState.INVISIBLE
                self.state_timer = 0
                self.invisibility_duration = random.randint(*self.invisible_duration_range)
                if debug_mode:
                    print(f"[FSM] {previous_state.value} -> INVISIBLE: Приведение исчезает на {self.invisibility_duration // 60} секунд")
                # Делаем полностью невидимым
                if self.sprite:
                    self.sprite.set_alpha(0)
        else:
            # Мы в состоянии невидимости
            self.state_timer += 1
            
            # Определяем время до появления
            if self.is_first_appearance:
                # Первое появление: ждём 30-90 секунд
                appear_time = self.initial_appear_time
            else:
                # Последующие появления: ждём invisibility_duration
                appear_time = self.invisibility_duration
            
            if self.state_timer >= appear_time:
                # Появляемся!
                self.state = GhostState.IDLE  # Начинаем с IDLE, чтобы стоять на месте
                self.state_timer = 0
                self.invisibility_timer = 0
                self.time_until_invisible = random.randint(30 * 60, 60 * 60)
                
                # Включаем паузу после появления (~1 секунда)
                self.is_frozen_after_appear = True
                self.appear_freeze_timer = 0
                
                # Если это было первое появление, отмечаем
                if self.is_first_appearance:
                    self.is_first_appearance = False
                    self.invisibility_duration = random.randint(*self.invisible_duration_range)
                    
                    # ЗАПУСКАЕМ АНИМАЦИЮ СПАВНА при первом появлении
                    if self.spawn_animation:
                        self.is_playing_spawn = True
                        self.spawn_animation_frame = 0
                        self.spawn_animation_timer = pygame.time.get_ticks()
                else:
                    if debug_mode:
                        print(f"[FSM] INVISIBLE -> IDLE: Приведение вернулось, стоит на месте 1 сек, следующее исчезновение через {self.time_until_invisible // 60} секунд")
                
                if not self.is_playing_spawn and self.sprite:
                    self.sprite.set_alpha(self.base_alpha)
                return
        
        # Отладочная информация каждые 180 кадров (3 секунды)
        if debug_mode and self.state_timer % 180 == 0:
            player_room = self.get_player_room_id(player_rect)
            print(f"[FSM Debug] State={self.state.value}, GhostRoom={current_room}, HomeRoom={self.home_room_id}, PlayerRoom={player_room}, SameRoom={same_room_as_player}, Distance={distance_to_player:.1f}px, Timer={self.state_timer}")
        
        # Упрощенная машина состояний
        
        if self.state == GhostState.IDLE:
            if self.state_timer >= self.idle_duration:
                if same_room_as_player:
                    self.state = GhostState.CHASE
                    self.state_timer = 0
                    if debug_mode:
                        print(f"[FSM] IDLE -> CHASE: Игрок в той же комнате ({current_room}), начинаем погоню")
                else:
                    self.state = GhostState.PATROL
                    self.state_timer = 0
                    if debug_mode:
                        print(f"[FSM] IDLE -> PATROL: Игрок в другой комнате (Ghost={current_room}, Player={self.get_player_room_id(player_rect)}), начинаем патруль")
        
        elif self.state == GhostState.PATROL:
            if same_room_as_player:
                self.state = GhostState.CHASE
                self.state_timer = 0
                if debug_mode:
                    print(f"[FSM] PATROL -> CHASE: Обнаружен игрок в той же комнате ({current_room}), расстояние {distance_to_player:.1f}px")
            elif self.state_timer >= self.patrol_duration:
                # Иногда переходим в другую комнату
                if random.random() < 0.3:  # 30% шанс сменить комнату
                    self.state = GhostState.WANDER
                    self.state_timer = 0
                    if debug_mode:
                        print(f"[FSM] PATROL -> WANDER: Патруль завершен, переходим в другую комнату (текущая={current_room})")
                else:
                    self.state = GhostState.IDLE
                    self.state_timer = 0
                    if debug_mode:
                        print(f"[FSM] PATROL -> IDLE: Патруль завершен, отдыхаем")
        
        elif self.state == GhostState.WANDER:
            if same_room_as_player:
                self.state = GhostState.CHASE
                self.state_timer = 0
                if debug_mode:
                    print(f"[FSM] WANDER -> CHASE: Во время блуждания обнаружен игрок в комнате {current_room}")
            elif self.state_timer >= 300:  # 5 секунд блуждания
                # Остаемся в текущей комнате и начинаем патрулировать
                self.state = GhostState.PATROL
                self.state_timer = 0
                # Иногда обновляем домашнюю комнату на текущую
                new_home = self.get_current_room_id()
                if new_home != -1 and random.random() < 0.6:  # 60% шанс остаться
                    old_home = self.home_room_id
                    self.home_room_id = new_home
                    self._generate_smart_patrol_points()
                    if debug_mode:
                        print(f"[FSM] WANDER -> PATROL: Блуждание завершено, остаемся в комнате {new_home} (было {old_home})")
                else:
                    if debug_mode:
                        print(f"[FSM] WANDER -> PATROL: Блуждание завершено, возвращаемся к патрулю в комнате {self.home_room_id}")
        
        elif self.state == GhostState.CHASE:
            if not same_room_as_player:
                self.state = GhostState.SEARCH
                self.state_timer = 0
                if debug_mode:
                    player_room = self.get_player_room_id(player_rect)
                    print(f"[FSM] CHASE -> SEARCH: Игрок ушел в другую комнату (Ghost={current_room}, Player={player_room}), ищем")
            elif distance_to_player > 600:  # Увеличена дистанция для более длинной погони
                # Остаемся в текущей комнате и патрулируем
                self.state = GhostState.PATROL
                self.state_timer = 0
                # Обновляем домашнюю комнату на текущую
                new_home = self.get_current_room_id()
                if new_home != -1:
                    old_home = self.home_room_id
                    self.home_room_id = new_home
                    self._generate_smart_patrol_points()
                    if debug_mode:
                        print(f"[FSM] CHASE -> PATROL: Игрок слишком далеко ({distance_to_player:.1f}px > 600px), патрулируем в комнате {new_home} (было {old_home})")
                else:
                    if debug_mode:
                        print(f"[FSM] CHASE -> PATROL: Игрок слишком далеко ({distance_to_player:.1f}px > 600px), патрулируем")
        
        elif self.state == GhostState.SEARCH:
            if same_room_as_player:
                self.state = GhostState.CHASE
                self.state_timer = 0
                if debug_mode:
                    print(f"[FSM] SEARCH -> CHASE: Найден игрок в комнате {current_room}, возобновляем погоню")
            elif self.state_timer >= 180:  # 3 секунды поиска
                # Остаемся в текущей комнате и патрулируем
                self.state = GhostState.PATROL
                self.state_timer = 0
                # Обновляем домашнюю комнату на текущую
                new_home = self.get_current_room_id()
                if new_home != -1:
                    old_home = self.home_room_id
                    self.home_room_id = new_home
                    self._generate_smart_patrol_points()
                    if debug_mode:
                        print(f"[FSM] SEARCH -> PATROL: Поиск завершен (3 сек), патрулируем в комнате {new_home} (было {old_home})")
                else:
                    if debug_mode:
                        print(f"[FSM] SEARCH -> PATROL: Поиск завершен (3 сек), патрулируем")
        
        elif self.state == GhostState.RETURN:
            # Возвращаемся домой (редко используется)
            if current_room == self.home_room_id:
                self.state = GhostState.PATROL
                self.state_timer = 0
                if debug_mode:
                    print(f"[FSM] RETURN -> PATROL: Вернулись домой в комнату {self.home_room_id}")
            elif self.state_timer >= 300:  # 5 секунд на возврат
                # Если долго не можем вернуться, остаемся где есть
                self.state = GhostState.PATROL
                self.state_timer = 0
                new_home = self.get_current_room_id()
                if new_home != -1:
                    old_home = self.home_room_id
                    self.home_room_id = new_home
                    self._generate_smart_patrol_points()
                    if debug_mode:
                        print(f"[FSM] RETURN -> PATROL: Не смогли вернуться домой за 5 сек, остаемся в комнате {new_home} (было {old_home})")
    
    def update_movement(
        self,
        player_rect,
        walls,
        level_hitboxes,
        projector_zones=None,
        world_width=SCREEN_WIDTH,
        world_height=SCREEN_HEIGHT,
    ):
        """Обновляет движение в зависимости от состояния. projector_zones — призраки не заходят в эти круги."""
        pz = projector_zones or []
        if self.state == GhostState.INVISIBLE:
            return
        if self.is_frozen_after_appear or self.is_playing_spawn:
            return
        
        if self.state == GhostState.IDLE:
            # Стоим на месте
            pass
        
        elif self.state == GhostState.PATROL:
            # Умное патрулирование с A*
            self.patrol_change_timer += 1
            
            if self.patrol_points:
                if self.target_x is None or self.target_y is None:
                    target_point = self.patrol_points[self.current_patrol_index]
                    self.set_target_with_pathfinding(
                        target_point[0],
                        target_point[1],
                        walls,
                        level_hitboxes,
                        world_width,
                        world_height,
                    )
                
                if self.move_along_path(self.patrol_speed, walls, level_hitboxes, pz):
                    # Достигли точки, переходим к следующей
                    self.current_patrol_index = (self.current_patrol_index + 1) % len(self.patrol_points)
                    
                    # Периодически меняем маршрут патрулирования
                    if self.patrol_change_timer >= self.room_change_duration:
                        self.patrol_change_timer = 0
                        self._generate_smart_patrol_points()
                        self.current_patrol_index = 0  # Сбрасываем индекс
                    
                    if self.current_patrol_index < len(self.patrol_points):
                        next_point = self.patrol_points[self.current_patrol_index]
                        self.set_target_with_pathfinding(
                            next_point[0],
                            next_point[1],
                            walls,
                            level_hitboxes,
                            world_width,
                            world_height,
                        )
            else:
                self._generate_smart_patrol_points()
        
        elif self.state == GhostState.WANDER:
            # Блуждание между комнатами с A*
            if (self.target_x is None or self.target_y is None):
                # Выбираем случайную комнату для исследования
                available_rooms = list(range(len(self.rooms)))
                if len(available_rooms) > 1:
                    # Убираем текущую комнату из выбора иногда
                    current_room_id = self.get_current_room_id()
                    if current_room_id != -1 and random.random() < 0.7:  # 70% шанс пойти в другую комнату
                        available_rooms.remove(current_room_id)
                
                target_room_id = random.choice(available_rooms)
                target_room = self.rooms[target_room_id]
                wander_point = target_room.get_random_point()
                self.set_target_with_pathfinding(
                    wander_point[0],
                    wander_point[1],
                    walls,
                    level_hitboxes,
                    world_width,
                    world_height,
                )
            
            if self.move_along_path(self.speed * 0.8, walls, level_hitboxes, pz):
                # Достигли цели, выбираем новую
                self.target_x = None
                self.target_y = None
                self.current_path = []
        
        elif self.state == GhostState.SEARCH:
            # Движемся к игроку с A*
            player_pos = (player_rect.centerx, player_rect.centery)
            if (self.target_x != player_pos[0] or self.target_y != player_pos[1]):
                self.set_target_with_pathfinding(
                    player_pos[0],
                    player_pos[1],
                    walls,
                    level_hitboxes,
                    world_width,
                    world_height,
                )
            self.move_along_path(self.search_speed, walls, level_hitboxes, pz)
        
        elif self.state == GhostState.CHASE:
            # Быстро преследуем игрока с A*
            player_pos = (player_rect.centerx, player_rect.centery)
            # Обновляем путь чаще для более точного преследования
            if (self.target_x is None or self.target_y is None or 
                abs(self.target_x - player_pos[0]) > 50 or 
                abs(self.target_y - player_pos[1]) > 50):
                self.set_target_with_pathfinding(
                    player_pos[0],
                    player_pos[1],
                    walls,
                    level_hitboxes,
                    world_width,
                    world_height,
                )
            self.move_along_path(self.chase_speed, walls, level_hitboxes, pz)
        
        elif self.state == GhostState.RETURN:
            # Возвращаемся в домашнюю область с A*
            if self.home_room_id < len(self.rooms):
                home_room = self.rooms[self.home_room_id]
                home_center = home_room.get_center()
                if (self.target_x != home_center[0] or self.target_y != home_center[1]):
                    self.set_target_with_pathfinding(
                        home_center[0],
                        home_center[1],
                        walls,
                        level_hitboxes,
                        world_width,
                        world_height,
                    )
                self.move_along_path(self.speed * 1.2, walls, level_hitboxes, pz)

    
    
    def update(
        self,
        player_rect,
        walls,
        level_hitboxes,
        debug_mode=False,
        projector_zones=None,
        world_width=SCREEN_WIDTH,
        world_height=SCREEN_HEIGHT,
    ):
        """Обновляет приведение с FSM"""
        self.update_state(player_rect, walls, debug_mode)
        pz = projector_zones or []
        self.update_movement(
            player_rect,
            walls,
            level_hitboxes,
            pz,
            world_width=world_width,
            world_height=world_height,
        )
        
        # Проверяем коллизии со стенами и хитбоксами
        self._check_wall_collisions(walls)
        self._check_hitbox_collisions(level_hitboxes)
        self._update_aggression(player_rect)

    def _update_aggression(self, player_rect):
        """Обновляет условный уровень агрессии призрака (для радиоприемника)."""
        state_base = {
            GhostState.INVISIBLE: 5,
            GhostState.IDLE: 20,
            GhostState.PATROL: 35,
            GhostState.WANDER: 45,
            GhostState.SEARCH: 60,
            GhostState.CHASE: 85,
            GhostState.RETURN: 40,
        }
        base = state_base.get(self.state, 25)
        distance = self.get_distance_to_player(player_rect)
        proximity_bonus = max(0, int((350 - min(distance, 350)) / 6))
        noise = random.randint(-4, 4)
        self.aggression = max(0, min(100, base + proximity_bonus + noise))
    
    def _check_wall_collisions(self, walls):
        """Проверка коллизий со стенами. Цикл, пока не выйдем из всех стен."""
        for _ in range(5):
            collided = False
            for wall_rect, _ in walls:
                if self.rect.colliderect(wall_rect):
                    overlap_left = self.rect.right - wall_rect.left
                    overlap_right = wall_rect.right - self.rect.left
                    overlap_top = self.rect.bottom - wall_rect.top
                    overlap_bottom = wall_rect.bottom - self.rect.top
                    min_overlap = min(overlap_left, overlap_right, overlap_top, overlap_bottom)
                    if min_overlap == overlap_left:
                        self.rect.right = wall_rect.left
                    elif min_overlap == overlap_right:
                        self.rect.left = wall_rect.right
                    elif min_overlap == overlap_top:
                        self.rect.bottom = wall_rect.top
                    else:
                        self.rect.top = wall_rect.bottom
                    self.x, self.y = self.rect.x, self.rect.y
                    self.current_path = []
                    self.path_index = 0
                    self.target_x = self.target_y = None
                    collided = True
                    break
            if not collided:
                break
    
    def _check_hitbox_collisions(self, level_hitboxes):
        """Проверка коллизий с хитбоксами. Цикл до полного выхода."""
        for _ in range(5):
            collided = False
            for hitbox_rect in level_hitboxes:
                if self.rect.colliderect(hitbox_rect):
                    overlap_left = self.rect.right - hitbox_rect.left
                    overlap_right = hitbox_rect.right - self.rect.left
                    overlap_top = self.rect.bottom - hitbox_rect.top
                    overlap_bottom = hitbox_rect.bottom - self.rect.top
                    min_overlap = min(overlap_left, overlap_right, overlap_top, overlap_bottom)
                    if min_overlap == overlap_left:
                        self.rect.right = hitbox_rect.left
                    elif min_overlap == overlap_right:
                        self.rect.left = hitbox_rect.right
                    elif min_overlap == overlap_top:
                        self.rect.bottom = hitbox_rect.top
                    else:
                        self.rect.top = hitbox_rect.bottom
                    self.x, self.y = self.rect.x, self.rect.y
                    self.current_path = []
                    self.path_index = 0
                    self.target_x = self.target_y = None
                    collided = True
                    break
            if not collided:
                break
    
    def draw(self, screen, camera_x=0, camera_y=0):
        """Отрисовывает приведение"""
        if self.is_playing_spawn and self.spawn_animation:
            if 0 <= self.spawn_animation_frame < len(self.spawn_animation):
                frame = self.spawn_animation[self.spawn_animation_frame]
                screen.blit(frame, (self.rect.x - camera_x, self.rect.y - camera_y))
            return
        
        if self.state == GhostState.INVISIBLE:
            return
        
        if self.sprite:
            screen.blit(self.sprite, (self.rect.x - camera_x, self.rect.y - camera_y))


class GhostManager:
    def __init__(self):
        self.ghosts = []
        self.ghost_sprite = None
        self.max_ghosts = 1  # Всегда только одно приведение
        self.rooms = []
        self.debug_mode = False
        self.abilities_config = GhostAbilitiesConfig()
        self.footprints = []  # [{"x": int, "y": int, "ttl": int}]
        self.emf_hotspot = None  # {"x": int, "y": int, "level": int, "ttl": int}

    def load_ghost_sprite(self):
        """Загружает спрайт приведения"""
        import assets
        self.ghost_sprite = assets.load_ghost_sprite()
    
    def create_rooms_from_level_data(self, level_data):
        """Создает комнаты из данных уровня (JSON).
        
        Если в level_data есть "rooms", использует их.
        Иначе создает одну большую комнату по умолчанию.
        """
        self.rooms = []
        
        if level_data and "rooms" in level_data and level_data["rooms"]:
            # Читаем комнаты из JSON
            for room_data in level_data["rooms"]:
                room = Room(
                    room_data["x"],
                    room_data["y"],
                    room_data["width"],
                    room_data["height"],
                    room_data.get("room_id", len(self.rooms))
                )
                self.rooms.append(room)
            print(f"Загружено {len(self.rooms)} комнат из уровня")
        else:
            # Fallback: создаем одну большую комнату
            self.rooms.append(
                Room(
                    int(50 * MAP_SCALE),
                    int(100 * MAP_SCALE),
                    int((SCREEN_WIDTH - 100) * MAP_SCALE),
                    int((SCREEN_HEIGHT - 150) * MAP_SCALE),
                    0,
                )
            )
            print("Комнаты не найдены в уровне, создана одна большая комната по умолчанию")
        
    
    def spawn_ghosts_from_level(self, ghost_spawns, walls, level_hitboxes, level_data=None):
        """Спавнит одно приведение из данных уровня с FSM. Тип призрака — случайный профиль из ghost_abilities.ini."""
        self.ghosts.clear()
        self.footprints.clear()
        self.emf_hotspot = None
        
        if not self.ghost_sprite:
            self.load_ghost_sprite()
        
        # Создаем комнаты из данных уровня (если есть) или по умолчанию
        self.create_rooms_from_level_data(level_data)
        
        if not ghost_spawns or not self.ghost_sprite:
            print("Нет доступных спавнов или спрайта приведения")
            return
        
        # Всегда спавним только одно приведение
        selected_spawn = random.choice(ghost_spawns)
        spawn_x, spawn_y = selected_spawn
        
        # Определяем домашнюю область для приведения
        home_room_id = 0
        for i, room in enumerate(self.rooms):
            if room.contains_point(spawn_x, spawn_y):
                home_room_id = i
                break
        
        ghost_kind = self.abilities_config.random_profile_name()
        abilities = self.abilities_config.get_profile(ghost_kind)
        ghost = Ghost(
            spawn_x,
            spawn_y,
            self.ghost_sprite.copy(),
            self.rooms,
            home_room_id,
            abilities=abilities,
            ghost_kind=ghost_kind,
        )
        self.ghosts.append(ghost)
        
        print(
            f"Заспавнено 1 приведение [{ghost.display_name}] (профиль {ghost_kind}) на ({spawn_x}, {spawn_y}). "
            f"Скорости: {ghost.speed}/{ghost.patrol_speed}/{ghost.chase_speed}/{ghost.search_speed}. "
            f"Флаги: fly={ghost.can_fly}, walk={ghost.can_walk}, phase={ghost.can_phase_walls}, tp={ghost.can_teleport}; "
            f"улики: amp={ghost.amp}, uv={ghost.ultraviolet}, orb={ghost.ghostorb}, radio={ghost.radio}."
        )
    
    def update(
        self,
        player_rect,
        walls,
        level_hitboxes,
        projector_zones=None,
        world_width=SCREEN_WIDTH,
        world_height=SCREEN_HEIGHT,
    ):
        """Обновляет всех приведений с FSM. projector_zones: [(cx, cy, radius), ...] — зоны, куда призраки не заходят."""
        pz = projector_zones or []
        for ghost in self.ghosts:
            ghost.update(
                player_rect,
                walls,
                level_hitboxes,
                self.debug_mode,
                projector_zones=pz,
                world_width=world_width,
                world_height=world_height,
            )
            self._update_ghost_abilities_runtime(ghost)
        self._tick_runtime_effects()

    def _update_ghost_abilities_runtime(self, ghost):
        """Генерирует runtime-события: следы и ЭМП-всплески."""
        if ghost.state == GhostState.INVISIBLE:
            return

        # Следы: только для ходячих, шанс зависит от "типа" (через скорость/поведение).
        if ghost.can_walk and random.random() < 0.015:
            self.footprints.append(
                {
                    "x": int(ghost.rect.centerx + random.randint(-10, 10)),
                    "y": int(ghost.rect.centery + random.randint(-10, 10)),
                    "ttl": random.randint(7 * 60, 14 * 60),
                }
            )

        # ЭМП: взаимодействие/бросок/проявление в зависимости от состояния.
        event_level = None
        if ghost.state in (GhostState.IDLE, GhostState.PATROL) and random.random() < 0.008:
            event_level = 2  # взаимодействие
        elif ghost.state in (GhostState.WANDER, GhostState.SEARCH) and random.random() < 0.010:
            event_level = 3  # бросок предмета
        elif ghost.state == GhostState.CHASE and random.random() < 0.012:
            event_level = 4  # проявление

        if event_level is not None:
            # Улика ЭМП-5: 25% шанс заменить уровни 2-4, если у призрака есть amp.
            if ghost.amp and random.random() < 0.25:
                event_level = 5
            self.emf_hotspot = {
                "x": int(ghost.rect.centerx),
                "y": int(ghost.rect.centery),
                "level": event_level,
                "ttl": random.randint(3 * 60, 6 * 60),
            }

    def _tick_runtime_effects(self):
        """Старение следов и ЭМП-событий."""
        for mark in self.footprints:
            mark["ttl"] -= 1
        self.footprints = [m for m in self.footprints if m["ttl"] > 0]

        if self.emf_hotspot:
            self.emf_hotspot["ttl"] -= 1
            if self.emf_hotspot["ttl"] <= 0:
                self.emf_hotspot = None

    def ask_radio(self, player_rect):
        """Ответ радиоприемника. Возвращает (ok, text)."""
        if not self.ghosts:
            return False, "Радио: тишина."
        ghost = self.ghosts[0]
        if ghost.state == GhostState.INVISIBLE:
            return False, "Радио: только белый шум."
        if not ghost.radio:
            return False, "Радио: ответа нет."

        current_room = ghost.get_current_room_id()
        player_room = ghost.get_player_room_id(player_rect)
        room_hint = "рядом с тобой" if current_room == player_room else f"в комнате {current_room}"

        if ghost.aggression >= 75:
            mood = "очень агрессивен"
        elif ghost.aggression >= 45:
            mood = "насторожен"
        else:
            mood = "спокоен"

        phrases = [
            f"Радио: «Я {room_hint}...»",
            f"Радио: «Состояние: {mood}.»",
            f"Радио: «Слышу тебя... {room_hint}.»",
        ]
        return True, random.choice(phrases)

    def scan_emf(self, player_rect, radius=220):
        """Скан ЭМП рядом с игроком. Возвращает (level, text)."""
        level = 1
        px, py = player_rect.centerx, player_rect.centery
        if self.emf_hotspot:
            dx = self.emf_hotspot["x"] - px
            dy = self.emf_hotspot["y"] - py
            if math.hypot(dx, dy) <= radius:
                level = max(level, int(self.emf_hotspot["level"]))
        if self.ghosts:
            ghost = self.ghosts[0]
            if ghost.state != GhostState.INVISIBLE:
                dist = math.hypot(ghost.rect.centerx - px, ghost.rect.centery - py)
                if dist <= radius:
                    # Фоновая активность рядом с призраком.
                    if ghost.state in (GhostState.CHASE, GhostState.SEARCH):
                        level = max(level, 2)
                    if ghost.state == GhostState.CHASE:
                        level = max(level, 3)
        descriptions = {
            1: "ЭМП: уровень 1 (фон).",
            2: "ЭМП: уровень 2 (взаимодействие).",
            3: "ЭМП: уровень 3 (бросок предмета).",
            4: "ЭМП: уровень 4 (проявление).",
            5: "ЭМП: уровень 5 (улика!).",
        }
        return level, descriptions.get(level, "ЭМП: уровень 1.")

    def draw_footprints(self, screen, uv_enabled=False, camera_x=0, camera_y=0):
        """Рисует следы. В УФ-режиме контраст выше."""
        if not self.footprints:
            return
        color = (170, 60, 220) if uv_enabled else (110, 70, 140)
        alpha = 200 if uv_enabled else 120
        for mark in self.footprints:
            s = pygame.Surface((12, 7), pygame.SRCALPHA)
            s.fill((color[0], color[1], color[2], alpha))
            screen.blit(s, (mark["x"] - camera_x, mark["y"] - camera_y))
    
    def draw(self, screen, camera_x=0, camera_y=0):
        """Отрисовывает всех приведений и (в debug-режиме) комнаты."""
        # Сначала — приведения
        for ghost in self.ghosts:
            ghost.draw(screen, camera_x=camera_x, camera_y=camera_y)

        # Режим отладки комнат
        if self.debug_mode and self.rooms:
            # Полупрозрачный слой для отрисовки комнат
            debug_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            font = pygame.font.Font(None, 24)

            for room in self.rooms:
                # Полупрозрачная заливка комнаты
                color_fill = (0, 255, 0, 40)   # мягкий зелёный
                color_border = (0, 200, 0, 180)
                room_screen_rect = room.rect.move(-camera_x, -camera_y)
                pygame.draw.rect(debug_surface, color_fill, room_screen_rect)
                pygame.draw.rect(debug_surface, color_border, room_screen_rect, 2)

                # Подпись номера комнаты в центре
                label = font.render(str(room.room_id), True, (255, 255, 255))
                label_rect = label.get_rect(center=room_screen_rect.center)
                debug_surface.blit(label, label_rect)

            # Выводим слой поверх экрана
            screen.blit(debug_surface, (0, 0))
    
    def check_player_collision(self, player_rect):
        """Проверяет столкновение с игроком (невидимые и только появившиеся приведения не считаются)"""
        for ghost in self.ghosts:
            # Не считаем коллизию если:
            # - Приведение невидимо
            # - Приведение только появилось и стоит на месте (1 секунда паузы)
            if ghost.state == GhostState.INVISIBLE:
                continue
            if ghost.is_frozen_after_appear:
                continue
            if ghost.rect.colliderect(player_rect):
                return True
        return False
    
    def toggle_debug(self):
        """Переключает режим отладки для приведений"""
        self.debug_mode = not self.debug_mode
        state = "ВКЛ" if self.debug_mode else "ВЫКЛ"
        print(f"[Ghost Debug] Режим отладки: {state}")
    