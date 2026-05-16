"""
Модуль системы инвентаря с классами для каждого предмета.
Архитектура: базовый класс Item + конкретные предметы + InventoryManager.
"""
import pygame
import random
from enum import Enum
from abc import ABC, abstractmethod

from constants import TILE_SIZE, MAP_SCALE


class ItemType(Enum):
    """Типы предметов инвентаря. Приведения: летающие/ходящие — пока не реализовано."""
    FLASHLIGHT = "фонарик"       # реализовано при регулировке освещения
    RED_DUST = "красная пыль"    # основной спрайт есть; нет спрайта, меняющего структуру. Только для летающих приведений
    SALT = "соль"                # только для ходящих приведений
    PROJECTOR = "проектор"       # ставится в комнате, нельзя на проходах
    BATTERY = "аккумулятор"      # одна охота на аккумулятор (питание проектора)
    CROSS = "крест"              # убирает приведение с карты на время. TODO: добавить звук
    BLOOD = "кровь"              # хилит. Купить, затем выбрать для применения
    RADIO = "радио"              # запрос состояния и местоположения призрака
    EMF = "эмп"                  # скан уровней ЭМП 1..5
    UV_FLASHLIGHT = "уф фонарь"  # подсветка следов


class Item(ABC):
    """Базовый класс для всех предметов инвентаря"""
    
    def __init__(self, item_type: ItemType):
        self.item_type = item_type
        self.name = item_type.value
    
    @abstractmethod
    def use(self, game):
        """Использование предмета. Возвращает True, если использование успешно"""
        pass
    
    def is_owned(self, game) -> bool:
        """Проверка, куплен ли предмет"""
        return game.inventory.get(self.name, False)


class Flashlight(Item):
    """Фонарик — пассивный предмет, регулировка освещения реализована в другом месте"""

    def __init__(self):
        super().__init__(ItemType.FLASHLIGHT)

    def use(self, game):
        # Освещение уже реализовано при регулировке (game.vignette_radius и т.п.)
        game.inventory_manager.active_hand_item = self.item_type
        return True


class Radio(Item):
    """Радиоприемник — попытка получить ответ призрака."""

    def __init__(self):
        super().__init__(ItemType.RADIO)

    def use(self, game):
        ok, text = game.ghost_manager.ask_radio(game.player_rect)
        game._show_game_info(text, 1800 if ok else 1200)
        if ok:
            game.progress_event("radio_answer", 1)
        return True


class EmfDetector(Item):
    """ЭМП-детектор — показывает уровень 1..5 рядом с игроком."""

    def __init__(self):
        super().__init__(ItemType.EMF)

    def use(self, game):
        level, text = game.ghost_manager.scan_emf(game.player_rect)
        game._show_game_info(text, 1600 if level < 5 else 2200)
        return True


class UVFlashlight(Item):
    """УФ-фонарь — переключает подсветку следов."""

    def __init__(self):
        super().__init__(ItemType.UV_FLASHLIGHT)

    def use(self, game):
        game.uv_mode = not getattr(game, "uv_mode", False)
        game._show_game_info(f"УФ-режим: {'вкл' if game.uv_mode else 'выкл'}", 900)
        return True


class Battery(Item):
    """Аккумулятор — одна охота на один аккумулятор. Потребляется проектором."""

    def __init__(self):
        super().__init__(ItemType.BATTERY)

    def use(self, game):
        # Аккумулятор не используется напрямую — его тратит проектор
        return False


class Blood(Item):
    """Кровь — хилит. Купить, затем выбрать для применения."""
    
    def __init__(self):
        super().__init__(ItemType.BLOOD)
        self.heal_amounts = {
            0: 4,  # Лёгкая
            1: 3,  # Нормальная
            2: 2,  # Сложная
            3: 1   # Хардкор
        }
    
    def use(self, game):
        if game.inventory_manager.get_count(self.item_type) <= 0:
            return False
        heal = self.heal_amounts.get(game.difficulty_index, 3)
        game.player_hp = min(5, game.player_hp + heal)
        game.inventory_manager.decrease_count(self.item_type)
        return True


class Projector(Item):
    """Проектор — ставится на карте, питается аккумулятором, создаёт круглую зону. Призраки не заходят в зону."""
    
    def __init__(self):
        super().__init__(ItemType.PROJECTOR)
    
    def use(self, game):
        game.inventory_manager.start_placement(ItemType.PROJECTOR)
        return True


PROJECTOR_ZONE_RADIUS = 90  # радиус зоны, меньше самой маленькой комнаты (эмпирическое значение)
BATTERY_DURATION_TICKS = 60 * 60 * 2  # одна охота ≈ 2 мин при 60 FPS


class PlacedProjector:
    """Размещённый проектор. Клик по нему — перемещение. Питание — навести аккумулятор (клик при наличии батареи)."""
    def __init__(self, x, y, sprite):
        self.x, self.y = x, y
        self.sprite = sprite
        self.radius = PROJECTOR_ZONE_RADIUS
        half = PLACED_ITEM_SIZE // 2
        self.rect = pygame.Rect(x - half, y - half, PLACED_ITEM_SIZE, PLACED_ITEM_SIZE)
        self.powered = False
        self.battery_remaining = 0  # тиков до разряда
        self.is_moving = False  # при перемещении не работает
    
    def power(self, game):
        if not self.is_moving and game.inventory_manager.get_count(ItemType.BATTERY) > 0:
            game.inventory_manager.decrease_count(ItemType.BATTERY)
            self.powered = True
            self.battery_remaining = BATTERY_DURATION_TICKS
            return True
        return False
    
    def update(self):
        if self.powered and self.battery_remaining > 0:
            self.battery_remaining -= 1
            if self.battery_remaining <= 0:
                self.powered = False
    
    def draw(self, screen, debug_mode=False, camera_x=0, camera_y=0):
        if self.sprite:
            spr = self.sprite.copy()
            if not self.powered:
                spr.set_alpha(140)
            elif self.battery_remaining < BATTERY_DURATION_TICKS // 4:
                spr.set_alpha(180)  # почти разряжен — тусклее
            spr_rect = spr.get_rect(center=(self.x - camera_x, self.y - camera_y))
            screen.blit(spr, spr_rect)
        if debug_mode and self.powered and not self.is_moving:
            pygame.draw.circle(
                screen,
                (0, 255, 100),
                (int(self.x - camera_x), int(self.y - camera_y)),
                self.radius,
                2
            )
        # Визуализация разряда — полупрозрачный круг, сужается при разряде
        if self.powered and self.battery_remaining > 0:
            fill_alpha = int(40 * self.battery_remaining / BATTERY_DURATION_TICKS)
            s = pygame.Surface((self.radius * 2, self.radius * 2))
            s.set_alpha(max(10, fill_alpha))
            s.fill((0, 200, 80))
            r = s.get_rect(center=(self.x - camera_x, self.y - camera_y))
            screen.blit(s, r)


class Cross(Item):
    """Крест — убирает приведение с карты на определённое время. TODO: добавить звук при использовании"""
    
    def __init__(self):
        super().__init__(ItemType.CROSS)
    
    def use(self, game):
        if game.inventory_manager.get_count(self.item_type) <= 0:
            return False
        game.inventory_manager.decrease_count(self.item_type)
        from ghost import GhostState
        for ghost in game.ghost_manager.ghosts:
            if ghost.state != GhostState.INVISIBLE:
                ghost.state = GhostState.INVISIBLE
                ghost.state_timer = 0
                ghost.invisibility_duration = random.randint(15 * 60, 30 * 60)
                if ghost.sprite:
                    ghost.sprite.set_alpha(0)
        return True


class PlaceableItem(Item):
    """Базовый класс для размещаемых предметов (пыль, соль)"""
    
    def __init__(self, item_type: ItemType, sprite_active, sprite_triggered):
        super().__init__(item_type)
        self.sprite_active = sprite_active
        self.sprite_triggered = sprite_triggered
    
    def use(self, game):
        if game.inventory_manager.get_count(self.item_type) <= 0:
            return False
        game.inventory_manager.start_placement(self.item_type)
        return True
    
    def create_placed_instance(self, x, y):
        """Создаёт экземпляр размещённого предмета на карте"""
        return PlacedItem(x, y, self.item_type, self.sprite_active, self.sprite_triggered)


class RedDust(PlaceableItem):
    """Красная пыль — срабатывает при контакте. sprite_active=redsand to level.png, sprite_triggered=redsand dif.png (загружаются в assets.load_placement_sprites)"""
    
    def __init__(self, sprite_active, sprite_triggered):
        super().__init__(ItemType.RED_DUST, sprite_active, sprite_triggered)


class Salt(PlaceableItem):
    """Соль — только для ходящих приведений. Срабатывает при проходе.
    TODO: приведения пока не разделены на летающих/ходящих."""
    
    def __init__(self, sprite_active, sprite_triggered):
        super().__init__(ItemType.SALT, sprite_active, sprite_triggered)


PLACED_ITEM_SIZE = 50  # размер размещённого предмета на карте

class PlacedItem:
    """Экземпляр размещённого предмета на карте.
    Срабатывает при коллизии с призраком. Пока is_flying не реализован — пыль и соль срабатывают от всех призраков."""
    
    def __init__(self, x, y, item_type, sprite_active, sprite_triggered):
        self.x = x
        self.y = y
        self.item_type = item_type
        half = PLACED_ITEM_SIZE // 2
        self.rect = pygame.Rect(x - half, y - half, PLACED_ITEM_SIZE, PLACED_ITEM_SIZE)
        
        self.sprite_active = sprite_active
        self.sprite_triggered = sprite_triggered
        self.current_sprite = sprite_active
        self.alpha = 255
        self.triggered = False
    
    def trigger(self):
        """Срабатывание при контакте призрака. Пока без проверки is_flying/is_walking."""
        if not self.triggered and self.sprite_triggered:
            self.triggered = True
            self.current_sprite = self.sprite_triggered
    
    def draw(self, screen, camera_x=0, camera_y=0):
        """Отрисовка предмета"""
        if self.current_sprite:
            sprite_copy = self.current_sprite.copy()
            sprite_copy.set_alpha(self.alpha)
            sprite_rect = sprite_copy.get_rect(center=(self.x - camera_x, self.y - camera_y))
            screen.blit(sprite_copy, sprite_rect)


class InventoryManager:
    """Менеджер инвентаря - управляет всеми предметами и их использованием"""
    
    def __init__(self, game):
        self.game = game
        self.active_hand_item = None
        
        # Загружаем спрайты для размещаемых предметов из assets
        import assets
        dust_active, dust_triggered, salt_active, salt_triggered = assets.load_placement_sprites()
        self.projector_sprite = assets.load_projector_sprite()
        self.placed_projector = None  # максимум один на карте
        self.moving_projector = None  # при перемещении
        
        # Создаём экземпляры всех предметов
        self.items = {
            ItemType.FLASHLIGHT: Flashlight(),
            ItemType.BATTERY: Battery(),
            ItemType.PROJECTOR: Projector(),
            ItemType.CROSS: Cross(),
            ItemType.BLOOD: Blood(),
            ItemType.RADIO: Radio(),
            ItemType.EMF: EmfDetector(),
            ItemType.UV_FLASHLIGHT: UVFlashlight(),
            ItemType.RED_DUST: RedDust(dust_active, dust_triggered),
            ItemType.SALT: Salt(salt_active, salt_triggered)
        }
        
        # Счётчики для расходных предметов
        self.item_counts = {
            ItemType.BATTERY: 0,
            ItemType.BLOOD: 0,
            ItemType.CROSS: 0,
            ItemType.RED_DUST: 0,
            ItemType.SALT: 0
        }
        
        # Размещённые предметы на карте
        self.placed_items = []
        
        # Режим размещения
        self.placement_mode = False
        self.selected_item_type = None
    
    def get_count(self, item_type: ItemType) -> int:
        """Получить количество расходного предмета"""
        return self.item_counts.get(item_type, 0)
    
    def increase_count(self, item_type: ItemType, amount=1):
        """Увеличить количество предмета"""
        if item_type in self.item_counts:
            self.item_counts[item_type] += amount
    
    def decrease_count(self, item_type: ItemType, amount=1):
        """Уменьшить количество предмета"""
        if item_type in self.item_counts:
            self.item_counts[item_type] = max(0, self.item_counts[item_type] - amount)
    
    def use_item(self, item_type: ItemType) -> bool:
        """Использовать предмет"""
        item = self.items.get(item_type)
        if item and item.is_owned(self.game):
            ok = item.use(self.game)
            if ok:
                self.active_hand_item = item_type
            return ok
        return False
    
    def use_item_by_index(self, index: int) -> bool:
        """Использовать предмет по индексу в купленных предметах"""
        purchased_items = [item for item in self.game.inventory_items if self.game.inventory[item]]
        if 0 <= index < len(purchased_items):
            item_name = purchased_items[index]
            # Найти ItemType по имени
            for item_type in ItemType:
                if item_type.value == item_name:
                    return self.use_item(item_type)
        return False
    
    def start_placement(self, item_type: ItemType):
        """Начать режим размещения предмета"""
        self.placement_mode = True
        self.selected_item_type = item_type
    
    def cancel_placement(self):
        """Отменить режим размещения"""
        self.placement_mode = False
        self.selected_item_type = None
    
    def _can_place_at(self, x, y) -> bool:
        """Пыль и соль — только в соседних ячейках от игрока, не через стены."""
        cell = TILE_SIZE * MAP_SCALE
        g = self.game
        if not hasattr(g, 'player_rect') or not hasattr(g, 'walls'):
            return True
        px, py = g.player_rect.centerx // cell, g.player_rect.centery // cell
        cx, cy = x // cell, y // cell
        if abs(cx - px) > 1 or abs(cy - py) > 1:
            return False  # не соседняя ячейка
        half = PLACED_ITEM_SIZE // 2
        test = pygame.Rect(x - half, y - half, PLACED_ITEM_SIZE, PLACED_ITEM_SIZE)
        for wall_rect, _ in getattr(g, 'walls', []):
            if test.colliderect(wall_rect):
                return False
        for hb in getattr(g, 'level_hitboxes', []):
            if test.colliderect(hb):
                return False
        return True

    def _get_valid_placement_cells(self):
        """Список координат (center_x, center_y) клеток, куда можно разместить предмет."""
        cell = TILE_SIZE * MAP_SCALE
        g = self.game
        if not hasattr(g, 'player_rect') or not hasattr(g, 'walls'):
            return []
        px, py = g.player_rect.centerx // cell, g.player_rect.centery // cell
        half = PLACED_ITEM_SIZE // 2
        valid = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                cx, cy = (px + dx) * cell + cell // 2, (py + dy) * cell + cell // 2
                test = pygame.Rect(cx - half, cy - half, PLACED_ITEM_SIZE, PLACED_ITEM_SIZE)
                ok = True
                for wall_rect, _ in getattr(g, 'walls', []):
                    if test.colliderect(wall_rect):
                        ok = False
                        break
                if ok:
                    for hb in getattr(g, 'level_hitboxes', []):
                        if test.colliderect(hb):
                            ok = False
                            break
                if ok:
                    valid.append((cx, cy))
        return valid

    def place_item(self, x, y) -> bool:
        """Разместить предмет на карте. Пыль/соль — только в соседних ячейках. Проектор — аналогично."""
        if not self.placement_mode or not self.selected_item_type:
            return False
        
        # Проектор: размещение или перемещение
        if self.selected_item_type == ItemType.PROJECTOR:
            # Клик по уже размещённому проектору — поднимаем для перемещения
            if self.placed_projector and self.placed_projector.rect.collidepoint(x, y):
                self.moving_projector = self.placed_projector
                self.placed_projector = None
                self.moving_projector.is_moving = True
                return False  # не отменяем placement_mode
            if not self._can_place_at(x, y):
                return False
            if self.moving_projector:
                self.moving_projector.x, self.moving_projector.y = x, y
                half = PLACED_ITEM_SIZE // 2
                self.moving_projector.rect = pygame.Rect(x - half, y - half, PLACED_ITEM_SIZE, PLACED_ITEM_SIZE)
                self.moving_projector.is_moving = False
                self.placed_projector = self.moving_projector
                self.moving_projector = None
            else:
                self.placed_projector = PlacedProjector(x, y, self.projector_sprite)
            self.cancel_placement()
            return True
        
        item = self.items.get(self.selected_item_type)
        if isinstance(item, PlaceableItem):
            if self.get_count(self.selected_item_type) <= 0:
                self.cancel_placement()
                return False
            if not self._can_place_at(x, y):
                return False
            placed = item.create_placed_instance(x, y)
            self.placed_items.append(placed)
            self.decrease_count(self.selected_item_type)
            if self.selected_item_type == ItemType.SALT:
                self.game.progress_event("use_salt", 1)
            self.cancel_placement()
            return True
        
        return False
    
    def draw(self, screen, camera_x=0, camera_y=0):
        """Отрисовка размещённых предметов и предпросмотра"""
        # Размещённые предметы
        for item in self.placed_items:
            item.draw(screen, camera_x=camera_x, camera_y=camera_y)
        
        # Проектор
        debug = getattr(self.game.ghost_manager, 'debug_mode', False)
        if self.placed_projector:
            self.placed_projector.draw(
                screen,
                debug_mode=debug,
                camera_x=camera_x,
                camera_y=camera_y
            )
        
        # Режим размещения
        if self.placement_mode and self.selected_item_type:
            if self.selected_item_type == ItemType.PROJECTOR:
                for cx, cy in self._get_valid_placement_cells():
                    half = PLACED_ITEM_SIZE // 2
                    r = pygame.Rect(
                        cx - half - camera_x,
                        cy - half - camera_y,
                        PLACED_ITEM_SIZE,
                        PLACED_ITEM_SIZE
                    )
                    s = pygame.Surface((PLACED_ITEM_SIZE, PLACED_ITEM_SIZE))
                    s.set_alpha(60)
                    s.fill((100, 150, 255))
                    screen.blit(s, r)
                    pygame.draw.rect(screen, (80, 120, 200), r, 2)
                mouse_x, mouse_y = pygame.mouse.get_pos()
                preview = self.projector_sprite.copy()
                preview.set_alpha(180)
                screen.blit(preview, preview.get_rect(center=(mouse_x, mouse_y)))
            else:
                item = self.items.get(self.selected_item_type)
                if isinstance(item, PlaceableItem):
                    for cx, cy in self._get_valid_placement_cells():
                        half = PLACED_ITEM_SIZE // 2
                        r = pygame.Rect(
                            cx - half - camera_x,
                            cy - half - camera_y,
                            PLACED_ITEM_SIZE,
                            PLACED_ITEM_SIZE
                        )
                        s = pygame.Surface((PLACED_ITEM_SIZE, PLACED_ITEM_SIZE))
                        s.set_alpha(60)
                        s.fill((0, 255, 100))
                        screen.blit(s, r)
                        pygame.draw.rect(screen, (0, 200, 80), r, 2)
                    mouse_x, mouse_y = pygame.mouse.get_pos()
                    preview = item.sprite_active.copy()
                    preview.set_alpha(180)
                    screen.blit(preview, preview.get_rect(center=(mouse_x, mouse_y)))
    
    def get_projector_zones(self):
        """Зоны активных проекторов (cx, cy, radius) для призраков."""
        zones = []
        if self.placed_projector and self.placed_projector.powered and not self.placed_projector.is_moving:
            zones.append((self.placed_projector.x, self.placed_projector.y, self.placed_projector.radius))
        return zones
    
    def update_projector(self):
        """Разряд аккумулятора проектора."""
        if self.placed_projector:
            self.placed_projector.update()
    
    def try_power_projector(self, x, y) -> bool:
        """Попытка зарядить проектор кликом. Возвращает True если заряжен."""
        if self.placed_projector and self.placed_projector.rect.collidepoint(x, y):
            return self.placed_projector.power(self.game)
        return False
    
    def update_placed_items(self):
        """Проверка коллизий призраков с размещёнными предметами. Пыль и соль срабатывают от всех призраков (is_flying не реализован)."""
        from ghost import GhostState
        for item in self.placed_items:
            if item.triggered:
                continue
            for ghost in getattr(self.game.ghost_manager, 'ghosts', []):
                if ghost.state == GhostState.INVISIBLE:
                    continue
                if ghost.rect.colliderect(item.rect):
                    item.trigger()
                    break
