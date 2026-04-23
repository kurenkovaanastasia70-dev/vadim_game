import pygame
from constants import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    FPS,
    TILE_SIZE,
    MAP_SCALE,
    WHITE,
    BLACK,
    GRAY,
    DARK_GRAY,
    LIGHT_GRAY,
    RED,
    GREEN,
    BLUE,
)
import os
import json
TOP_BAR = 100
MOVE_STEP = max(10, (TILE_SIZE * MAP_SCALE) // 3)  # шаг движения в масштабе карты

# HUD инвентаря (только экран): один источник правды для draws.py и handlers.py
INVENTORY_ITEMS_PER_ROW = 6
INVENTORY_X_START = 52
INVENTORY_X_STEP = 82
INVENTORY_CIRCLE_RADIUS = 26
INVENTORY_MARGIN_BOTTOM = 20
INVENTORY_ROW_STEP = 88


def inventory_slot_screen(index):
    """
    Центр круга слота инвентаря и радиус в экранных координатах.
    Ряд 0 — ближе к низу экрана, следующие ряды — выше.
    """
    row = index // INVENTORY_ITEMS_PER_ROW
    col = index % INVENTORY_ITEMS_PER_ROW
    cy = (
        SCREEN_HEIGHT
        - INVENTORY_MARGIN_BOTTOM
        - INVENTORY_CIRCLE_RADIUS
        - row * INVENTORY_ROW_STEP
    )
    cx = INVENTORY_X_START + col * INVENTORY_X_STEP
    return cx, cy, INVENTORY_CIRCLE_RADIUS


def check_collision(player_rect, walls):
    for wall_rect, wall_color in walls:
        if player_rect.colliderect(wall_rect):
            return True
    return False
def check_collision_with_hitboxes(player_rect, hitboxes):
    """
    Проверяет столкновение игрока с хитбоксами.
    Возвращает True, если есть столкновение.
    """
    for hitbox_rect in hitboxes:
        if player_rect.colliderect(hitbox_rect):
            return True
    return False
def check_collisioncomp(player_rect, comp_rect):

    if comp_rect and player_rect.colliderect(comp_rect):
            return True
    return False


def update_player_movement(game):
    """
    Обновляет движение игрока с плавным перемещением и проверкой столкновений.
    """
    current_time = pygame.time.get_ticks()
    
    # Уменьшаем задержку для более плавного движения
    move_delay = game.move_delay//2  # Делим на 2 для плавности
    
    if current_time - game.move_timer >= move_delay:
        dx, dy = 0, 0

        # Определяем направление движения (поддержка диагоналей)
        keys = pygame.key.get_pressed()  # Получаем текущее состояние клавиш
        step = MOVE_STEP // 2 if keys[pygame.K_LSHIFT] else MOVE_STEP  # Замедление при Shift

        left = game.keys_pressed[pygame.K_LEFT] or game.keys_pressed[pygame.K_a]
        right = game.keys_pressed[pygame.K_RIGHT] or game.keys_pressed[pygame.K_d]
        up = game.keys_pressed[pygame.K_UP] or game.keys_pressed[pygame.K_w]
        down = game.keys_pressed[pygame.K_DOWN] or game.keys_pressed[pygame.K_s]

        if left:
            dx -= step
        if right:
            dx += step
        if up:
            dy -= step
        if down:
            dy += step

        # Направление спрайта выбираем по последнему ненулевому смещению
        if dx < 0:
            game.player_direction = "left"
        elif dx > 0:
            game.player_direction = "right"
        if dy < 0:
            game.player_direction = "up"
        elif dy > 0:
            game.player_direction = "down"
        game.moving = False
        if dx != 0 or dy != 0:
            # Пробуем переместиться по X и Y
            for axis, delta in [("x", dx), ("y", dy)]:
                if delta == 0:
                    continue
                new_rect = game.player_rect.move(delta if axis == "x" else 0, delta if axis == "y" else 0)
                top_margin = int(TOP_BAR * MAP_SCALE)
                if (0 <= new_rect.x <= game.world_width - game.player_size and
                    top_margin <= new_rect.y <= game.world_height - game.player_size and
                    not check_collision(new_rect, game.walls) and
                    not check_collisioncomp(new_rect, game.computer_rect) and
                    not check_collision_with_hitboxes(new_rect, game.level_hitboxes)):
                    setattr(game.player_rect, axis, new_rect.x if axis == "x" else new_rect.y)
                    game.moving = True
            
            game.move_timer = current_time
        else:
            game.moving = False
    # Проверяем близость к компьютеру (зона взаимодействия, не «центр–центр»:
    # коллизия с rect компьютера не даёт подойти к центру ближе ~половины суммы размеров,
    # поэтому старый порог 100 px на увеличенной карте почти никогда не срабатывал.)
    if game.computer_rect:
        pad = int(48 * MAP_SCALE)
        zone = game.computer_rect.inflate(pad * 2, pad * 2)
        game.near_computer = zone.colliderect(game.player_rect)
        if game.near_computer:
            if game.computer_open:
                game.computer = game.computer_open
        else:
            if game.computer_closed:
                game.computer = game.computer_closed
    else:
        game.near_computer = False
    game.update_camera()









def generate_walls():
    """
    Создает стены для первого уровня, разделяющие карту на три комнаты.
    
    СТРУКТУРА КОМНАТ:
    - Вертикальная стена посередине экрана разделяет карту на левую и правую части
    - Горизонтальная стена в правой части делит её пополам на две комнаты
    
    Рабочая область:
    - Ширина: 0 до SCREEN_WIDTH (по всему экрану)
    - Высота: от TOP_BARRIER (100) до SCREEN_HEIGHT (768)
    
    Комнаты:
    - Комната 1 (левая):          x от 0 до ~512, y от 100 до 768 (вся левая половина)
    - Комната 2 (правая верхняя): x от ~512 до 1024, y от 100 до ~434
    - Комната 3 (правая нижняя):  x от ~512 до 1024, y от ~434 до 768
    
    Стены:
    - Вертикальная стена: разделяет левую и правую части (посередине экрана, x ≈ 512)
    - Горизонтальная стена: разделяет правую часть на верхнюю и нижнюю (y ≈ 434, только в правой части)
    
    Проходы:
    - В вертикальной стене есть проход для перехода между левой и правой частями
    - В горизонтальной стене есть проход для перехода между верхней и нижней правыми комнатами
    - Ширина проходов 100px (достаточно для персонажа размером 50px)
    """
    walls = []
    
    # Рабочая область (по всему экрану)
    work_area_width = SCREEN_WIDTH
    work_area_height = SCREEN_HEIGHT - TOP_BAR
    
    # Середина экрана по ширине (разделяет левую и правую части)
    middle_x = work_area_width // 2
    
    # Середина правой части по высоте (разделяет верхнюю и нижнюю правые комнаты)
    right_middle_y = TOP_BAR + work_area_height // 2
    
    # Толщина стен
    wall_thickness = 30
    
    # Ширина прохода между комнатами (достаточно для персонажа размером 50px)
    passage_width = 100
    
    # Цвет стен - коричневый
    wall_color = (139, 90, 43)  # Коричневый
    
    # ВЕРТИКАЛЬНАЯ СТЕНА: разделяет левую и правую части (посередине экрана)
    vertical_wall_x = middle_x - wall_thickness // 2
    
    # Проход в вертикальной стене (в средней части по высоте)
    vertical_passage_y_start = TOP_BAR + work_area_height // 2 - passage_width // 2
    vertical_passage_y_end = vertical_passage_y_start + passage_width
    
    # Верхняя часть вертикальной стены
    if vertical_passage_y_start > TOP_BAR:
        vertical_wall_top = pygame.Rect(
            vertical_wall_x,
            TOP_BAR,
            wall_thickness,
            vertical_passage_y_start - TOP_BAR
        )
        walls.append((vertical_wall_top, wall_color))
    
    # Нижняя часть вертикальной стены (после прохода)
    if vertical_passage_y_end < SCREEN_HEIGHT:
        vertical_wall_bottom = pygame.Rect(
            vertical_wall_x,
            vertical_passage_y_end,
            wall_thickness,
            SCREEN_HEIGHT - vertical_passage_y_end
        )
        walls.append((vertical_wall_bottom, wall_color))
    
    # ГОРИЗОНТАЛЬНАЯ СТЕНА: разделяет правую часть на верхнюю и нижнюю комнаты
    horizontal_wall_y = right_middle_y - wall_thickness // 2 +150
    
    # Проход в горизонтальной стене (в правой части по ширине)
    # Проход начинается на некотором расстоянии от вертикальной стены
    horizontal_passage_x_start = middle_x + 150  # Проход начинается на 150px от вертикальной стены
    horizontal_passage_x_end = horizontal_passage_x_start + passage_width
    
    # Левая часть горизонтальной стены (от вертикальной стены до прохода)
    if horizontal_passage_x_start > middle_x:
        horizontal_wall_left = pygame.Rect(
            middle_x,
            horizontal_wall_y,
            horizontal_passage_x_start - middle_x,
            wall_thickness
        )
        walls.append((horizontal_wall_left, wall_color))
    
    # Правая часть горизонтальной стены (от прохода до правого края экрана)
    if horizontal_passage_x_end < SCREEN_WIDTH:
        horizontal_wall_right = pygame.Rect(
            horizontal_passage_x_end,
            horizontal_wall_y,
            SCREEN_WIDTH - horizontal_passage_x_end,
            wall_thickness
        )
        walls.append((horizontal_wall_right, wall_color))
    
    return walls

def load_level_from_json(file_part):
    try:
        with open(file_part, 'r', encoding= "utf-8") as f:
            level_data = json.load(f)
        return level_data

    except Exception as e:
        print (f"ммысрраошчрорвпаывапвгаспенглорсиавапргщзлшогпнекуа")
        return None


def scale_level_data(level_data, scale=MAP_SCALE):
    """
    Масштабирует координаты уровня из JSON (заданы в базовых пикселях 1× экрана).
    """
    if not level_data or scale <= 1:
        return
    for w in level_data.get("walls", []):
        for k in ("x", "y", "width", "height"):
            if k in w and w[k] is not None:
                w[k] = int(w[k] * scale)
    for hb in level_data.get("hitboxes", []):
        for k in ("x", "y", "width", "height"):
            if k in hb and hb[k] is not None:
                hb[k] = int(hb[k] * scale)
    comp = level_data.get("computer")
    if comp:
        for k in ("x", "y", "width", "height"):
            if k in comp and comp[k] is not None:
                comp[k] = int(comp[k] * scale)
    for sp in level_data.get("ghost_spawns", []):
        if isinstance(sp, dict):
            if "x" in sp and sp["x"] is not None:
                sp["x"] = int(sp["x"] * scale)
            if "y" in sp and sp["y"] is not None:
                sp["y"] = int(sp["y"] * scale)
    for room in level_data.get("rooms", []):
        for k in ("x", "y", "width", "height"):
            if k in room and room[k] is not None:
                room[k] = int(room[k] * scale)
    for key in ("world_width", "world_height"):
        if key in level_data and level_data[key] is not None:
            level_data[key] = int(level_data[key] * scale)


def add_map_boundary_walls(walls, world_width, world_height, scale=MAP_SCALE):
    """
    Стены по периметру мира — карта конечная, за пределы фона выйти нельзя.
    """
    border_color = (139, 90, 43)
    thickness = max(24, int(16 * scale))
    top_band = int(TOP_BAR * scale)
    out = list(walls)
    out.append((pygame.Rect(0, 0, world_width, top_band), border_color))
    out.append((pygame.Rect(0, world_height - thickness, world_width, thickness), border_color))
    out.append((pygame.Rect(0, 0, thickness, world_height), border_color))
    out.append((pygame.Rect(world_width - thickness, 0, thickness, world_height), border_color))
    return out


def generate_walls(level_data):
    walls = []
    if level_data and "walls" in level_data:
        for wall in level_data['walls']:
            rect=pygame.Rect(wall["x"],wall["y"],wall["width"],wall["height"])
            color=tuple(wall.get("color",[139,90,43]))
            walls.append((rect,color))
        return walls
def get_computer_from_level(level_data):
    """
    Получает позицию компьютера из данных уровня.
    Возвращает pygame.Rect или None.
    """
    if level_data and "computer" in level_data:
        comp = level_data["computer"]
        if comp is not None:  # Проверяем, что computer не None
            try:
                rect = pygame.Rect(
                    comp["x"],
                    comp["y"],
                    comp["width"],
                    comp["height"]
                )
                print(f"DEBUG: Компьютер из JSON - x={comp['x']}, y={comp['y']}, width={comp['width']}, height={comp['height']}")
                return rect
            except (KeyError, TypeError) as e:
                print(f"Ошибка при создании Rect для компьютера: {e}, данные: {comp}")
                return None
        else:
            print("DEBUG: computer в level_data равен None")
    else:
        print(f"DEBUG: computer не найден в level_data. Ключи: {level_data.keys() if level_data else 'level_data is None'}")
    return None


def get_hitboxes_from_level(level_data):
    """
    Получает хитбоксы из данных уровня.
    Возвращает список pygame.Rect.
    """
    hitboxes = []
    if level_data and "hitboxes" in level_data:
        for hitbox in level_data["hitboxes"]:
            rect = pygame.Rect(
                hitbox["x"],
                hitbox["y"],
                hitbox["width"],
                hitbox["height"]
            )
            hitboxes.append(rect)
    return hitboxes

def get_ghost_spawns_from_level(level_data):
    """
    Получает точки спавна приведений из данных уровня.
    Возвращает список координат [(x, y), ...].
    """
    spawns = []
    if level_data and "ghost_spawns" in level_data:
        for spawn in level_data["ghost_spawns"]:
            spawns.append((spawn["x"], spawn["y"]))
    return spawns


