"""
Модуль системы инвентаря с классами для каждого предмета.
Архитектура: базовый класс Item + конкретные предметы + InventoryManager.
"""
import pygame
import random
import math
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
    THERMOMETER = "градусник"    # показывает температуру текущей комнаты
    CANDLE = "свеча"             # firelight: снижает пассивный drain в радиусе


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
        if self.item_type in game.inventory_manager.item_counts:
            return game.inventory_manager.get_count(self.item_type) > 0
        return game.inventory.get(self.name, False)


class Flashlight(Item):
    """Фонарик — включает/выключает видимость. Как в Phasmophobia, sanity от него не защищает."""

    def __init__(self):
        super().__init__(ItemType.FLASHLIGHT)

    def use(self, game):
        if not game.inventory.get(self.item_type.value, False):
            return False
        game.inventory_manager.active_hand_item = self.item_type
        game.flashlight_on = not bool(getattr(game, "flashlight_on", False))
        if hasattr(game, "_show_game_info"):
            game._show_game_info(
                f"Фонарик: {'вкл' if game.flashlight_on else 'выкл'} "
                f"(видимость {'лучше' if game.flashlight_on else 'хуже'}; рассудок всё равно падает)",
                1200,
            )
        return True


class Radio(Item):
    """Радиоприемник — попытка получить ответ призрака."""

    def __init__(self):
        super().__init__(ItemType.RADIO)

    def use(self, game):
        if game.inventory_manager.get_count(self.item_type) <= 0:
            return False
        now = pygame.time.get_ticks()
        cooldown_until = getattr(game, "radio_cooldown_until", 0)
        if now < cooldown_until:
            game._show_game_info("Радио: помехи, подожди настройки.", 900)
            return True
        game.radio_cooldown_until = now + getattr(game, "radio_cooldown_ms", 3000)
        ok, text = game.ghost_manager.ask_radio(game.player_rect)
        hunt_text = game.get_hunt_radio_text(ok) if hasattr(game, "get_hunt_radio_text") else ""
        if hunt_text:
            text = f"{text}\n{hunt_text}"
        if hasattr(game, "trigger_radio_feedback"):
            game.trigger_radio_feedback(ok)
        game._show_game_info(text, 2400 if ok else 1700)
        if ok:
            game.progress_event("radio_answer", 1)
        if hasattr(game, "increase_ghost_activity"):
            game.increase_ghost_activity(9 if ok else 5, "radio")
        if hasattr(game, "drain_sanity"):
            # Контакт через spirit box / радио в Phasmophobia тоже бьёт по sanity.
            game.drain_sanity(5.0 if ok else 2.0, reason="radio")
        # Учебный cursed possession: радио может вызвать cursed hunt (wiki: только от cursed items).
        if (
            hasattr(game, "try_start_cursed_hunt_from_possession")
            and not getattr(game, "is_setup_phase", lambda: False)()
            and random.random() < 0.22
        ):
            game.try_start_cursed_hunt_from_possession(source="радио")
        game.inventory_manager.decrease_count(self.item_type)
        return True


class EmfDetector(Item):
    """ЭМП-детектор — показывает уровень 1..5 рядом с игроком."""

    def __init__(self):
        super().__init__(ItemType.EMF)

    def use(self, game):
        level, text = game.ghost_manager.scan_emf(game.player_rect)
        game._show_game_info(text, 1600 if level < 5 else 2200)
        if hasattr(game, "increase_ghost_activity"):
            game.increase_ghost_activity(3 + level, "emf")
        return True


class UVFlashlight(Item):
    """УФ-фонарь — переключает подсветку следов."""

    def __init__(self):
        super().__init__(ItemType.UV_FLASHLIGHT)

    def use(self, game):
        game.uv_mode = not getattr(game, "uv_mode", False)
        game._show_game_info(f"УФ-режим: {'вкл' if game.uv_mode else 'выкл'}", 900)
        if game.uv_mode and hasattr(game, "increase_ghost_activity"):
            game.increase_ghost_activity(3, "uv")
        return True


class Thermometer(Item):
    """Заглушка градусника: измерение рисуется в HUD после покупки."""

    def __init__(self):
        super().__init__(ItemType.THERMOMETER)

    def use(self, game):
        game.inventory_manager.active_hand_item = self.item_type
        if hasattr(game, "_show_game_info"):
            temperature = game.get_current_temperature_c() if hasattr(game, "get_current_temperature_c") else None
            if temperature is None:
                game._show_game_info("Градусник: нет данных.", 900)
            else:
                game._show_game_info(f"Градусник: {temperature:.1f} °C", 1100)
        return True


class Battery(Item):
    """Аккумулятор — одна охота на один аккумулятор. Потребляется проектором."""

    def __init__(self):
        super().__init__(ItemType.BATTERY)

    def use(self, game):
        game.inventory_manager.active_hand_item = self.item_type
        if hasattr(game, "_show_game_info"):
            game._show_game_info("Аккумулятор выбран: кликни по проектору.", 1100)
        return True


class Blood(Item):
    """Кровь — хилит. Купить, затем выбрать для применения."""
    
    def __init__(self):
        super().__init__(ItemType.BLOOD)
    
    def use(self, game):
        if game.inventory_manager.get_count(self.item_type) <= 0:
            return False
        if game.player_hp >= 5:
            if hasattr(game, "_show_game_info"):
                game._show_game_info("HP уже полные.", 900)
            return False
        heal = game.difficulty_config().get("blood_heal", 3) if hasattr(game, "difficulty_config") else 3
        game.player_hp = min(5, game.player_hp + heal)
        game.inventory_manager.decrease_count(self.item_type)
        return True


class Candle(Item):
    """Свеча — firelight: ставится у ног и снижает пассивный sanity drain в радиусе."""

    def __init__(self):
        super().__init__(ItemType.CANDLE)

    def use(self, game):
        if game.inventory_manager.get_count(self.item_type) <= 0:
            return False
        if hasattr(game, "spawn_lit_candle"):
            game.spawn_lit_candle(game.player_rect.centerx, game.player_rect.centery)
        game.inventory_manager.decrease_count(self.item_type)
        if hasattr(game, "_show_game_info"):
            game._show_game_info("Свеча зажжена. Рядом рассудок падает медленнее.", 1300)
        return True


class Projector(Item):
    """Проектор — ставится на карте, питается аккумулятором, создаёт круглую зону. Призраки не заходят в зону."""
    
    def __init__(self):
        super().__init__(ItemType.PROJECTOR)
    
    def use(self, game):
        game.inventory_manager.start_placement(ItemType.PROJECTOR)
        return True


PROJECTOR_ZONE_RADIUS = 160  # радиус зоны, меньше самой маленькой комнаты (эмпирическое значение)
BATTERY_DURATION_TICKS = 60 * 60 * 2  # одна охота ≈ 2 мин при 60 FPS
PLACED_ITEM_HITBOX_RATIO = 0.50
PLACED_ITEM_ICON_RATIO = 0.45
PLACEMENT_PREVIEW_RATIO = PLACED_ITEM_HITBOX_RATIO
PLACED_ITEM_HITBOX_SIZE = max(32, int(TILE_SIZE * MAP_SCALE * PLACED_ITEM_HITBOX_RATIO))
PLACEMENT_PREVIEW_SIZE = PLACED_ITEM_HITBOX_SIZE
MAX_CARRIED_ITEMS = 3


class PlacedProjector:
    """Размещённый проектор. Клик по нему — перемещение. Питание — навести аккумулятор (клик при наличии батареи)."""
    def __init__(self, x, y, sprite):
        self.x, self.y = x, y
        self.sprite = sprite
        self.radius = PROJECTOR_ZONE_RADIUS
        half = PLACED_ITEM_HITBOX_SIZE // 2
        self.rect = pygame.Rect(x - half, y - half, PLACED_ITEM_HITBOX_SIZE, PLACED_ITEM_HITBOX_SIZE)
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
        if self.powered and not self.is_moving:
            center = (int(self.x - camera_x), int(self.y - camera_y))
            pygame.draw.circle(screen, (95, 230, 190), center, self.radius, 2)
            pygame.draw.circle(screen, (210, 255, 235), center, max(6, self.radius // 16), 1)
        if self.sprite:
            spr = self.sprite.copy()
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
        if hasattr(game, "ghost_activity"):
            game.ghost_activity = max(0.0, game.ghost_activity - 28)
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


PLACED_ITEM_SIZE = PLACED_ITEM_HITBOX_SIZE  # совместимость со старым кодом

class PlacedItem:
    """Экземпляр размещённого предмета на карте.
    Срабатывает при коллизии с призраком. Пока is_flying не реализован — пыль и соль срабатывают от всех призраков."""
    
    def __init__(self, x, y, item_type, sprite_active, sprite_triggered):
        self.x = x
        self.y = y
        self.item_type = item_type
        half = PLACED_ITEM_HITBOX_SIZE // 2
        self.rect = pygame.Rect(x - half, y - half, PLACED_ITEM_HITBOX_SIZE, PLACED_ITEM_HITBOX_SIZE)
        
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

    def to_dict(self):
        return {
            "type": self.item_type.name,
            "x": self.x,
            "y": self.y,
            "triggered": self.triggered,
        }
    
    def draw(self, screen, camera_x=0, camera_y=0):
        """Отрисовка предмета"""
        if self.current_sprite:
            sprite_copy = self.current_sprite.copy()
            sprite_copy.set_alpha(self.alpha)
            sprite_rect = sprite_copy.get_rect(center=(self.x - camera_x, self.y - camera_y))
            screen.blit(sprite_copy, sprite_rect)


class DroppedInventoryItem:
    def __init__(self, x, y, item_type):
        self.x = int(x)
        self.y = int(y)
        self.item_type = item_type
        self.radius = max(26, int(TILE_SIZE * MAP_SCALE * 0.28))
        self.rect = pygame.Rect(0, 0, self.radius * 2, self.radius * 2)
        self.rect.center = (self.x, self.y)
        self.throw_active = False
        self.throw_pending = False
        self.throw_start = (self.x, self.y)
        self.throw_end = (self.x, self.y)
        self.throw_started_ms = 0
        self.throw_delay_until_ms = 0
        self.throw_duration_ms = 480
        self.throw_arc_height = 48
        self.throw_spin = 0.0
        self.draw_offset_y = 0.0
        self.impact_until_ms = 0
        self.particles = []

    def move_to(self, x, y):
        """Мгновенный перенос (сохранения / fallback)."""
        self.throw_active = False
        self.throw_pending = False
        self.draw_offset_y = 0.0
        self.throw_spin = 0.0
        self.x = int(x)
        self.y = int(y)
        self.rect.center = (self.x, self.y)

    def start_throw(self, x, y, delay_ms=0, duration_ms=None):
        """Запускает полёт по дуге к новой точке в комнате."""
        self.throw_start = (self.x, self.y)
        self.throw_end = (int(x), int(y))
        self.throw_duration_ms = int(duration_ms if duration_ms is not None else random.randint(420, 680))
        self.throw_arc_height = random.randint(36, 64)
        self.throw_spin = 0.0
        self.draw_offset_y = 0.0
        now = pygame.time.get_ticks()
        self.throw_delay_until_ms = now + max(0, int(delay_ms))
        self.throw_started_ms = self.throw_delay_until_ms
        self.throw_pending = delay_ms > 0
        self.throw_active = delay_ms <= 0
        if self.throw_active:
            self.throw_started_ms = now

    def _spawn_impact_particles(self):
        self.particles = []
        for _ in range(10):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(1.2, 3.8)
            self.particles.append(
                {
                    "x": float(self.x),
                    "y": float(self.y),
                    "vx": math.cos(angle) * speed,
                    "vy": math.sin(angle) * speed - random.uniform(0.8, 2.2),
                    "life": random.randint(14, 26),
                    "ttl": 0,
                    "size": random.randint(2, 4),
                    "color": random.choice(
                        ((180, 230, 255), (255, 220, 140), (210, 245, 255), (255, 255, 255))
                    ),
                }
            )

    def update(self):
        now = pygame.time.get_ticks()
        if self.throw_pending and now >= self.throw_delay_until_ms:
            self.throw_pending = False
            self.throw_active = True
            self.throw_started_ms = now

        if self.throw_active:
            t = (now - self.throw_started_ms) / max(1, self.throw_duration_ms)
            if t >= 1.0:
                self.throw_active = False
                self.x, self.y = self.throw_end
                self.rect.center = (self.x, self.y)
                self.draw_offset_y = 0.0
                self.throw_spin = 0.0
                self.impact_until_ms = now + 320
                self._spawn_impact_particles()
            else:
                ease = 1.0 - (1.0 - t) ** 2
                x = self.throw_start[0] + (self.throw_end[0] - self.throw_start[0]) * ease
                y = self.throw_start[1] + (self.throw_end[1] - self.throw_start[1]) * ease
                self.draw_offset_y = -math.sin(t * math.pi) * self.throw_arc_height
                self.throw_spin = t * 540.0
                self.x, self.y = int(x), int(y)
                self.rect.center = (self.x, self.y)

        alive = []
        for particle in self.particles:
            particle["ttl"] += 1
            if particle["ttl"] >= particle["life"]:
                continue
            particle["x"] += particle["vx"]
            particle["y"] += particle["vy"]
            particle["vy"] += 0.18
            alive.append(particle)
        self.particles = alive

    def to_dict(self):
        return {
            "type": self.item_type.name,
            "x": self.x,
            "y": self.y,
        }

    def draw(self, screen, icon=None, camera_x=0, camera_y=0):
        now = pygame.time.get_ticks()
        phase = now * 0.004 + (self.x + self.y) * 0.01
        bob = 0 if (self.throw_active or self.throw_pending) else math.sin(phase) * 4
        pulse = (math.sin(phase * 0.8) + 1.0) * 0.5
        cx = int(self.x - camera_x)
        cy = int(self.y - camera_y + bob + self.draw_offset_y)
        size = self.radius * 2
        panel = pygame.Surface((size + 18, size + 18), pygame.SRCALPHA)
        center = (panel.get_width() // 2, panel.get_height() // 2)
        shadow_scale = 1.0 - min(0.55, abs(self.draw_offset_y) / 120.0)
        shadow_w = int(self.radius * (1.5 - pulse * 0.15) * shadow_scale)
        shadow_h = max(4, int(self.radius * 0.32 * shadow_scale))
        shadow = pygame.Surface((max(2, shadow_w * 2), max(2, shadow_h * 2)), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, int(92 * shadow_scale)), shadow.get_rect())
        screen.blit(
            shadow,
            shadow.get_rect(center=(int(self.x - camera_x), int(self.y - camera_y + self.radius * 0.72))),
        )

        glow_alpha = int(56 + pulse * 30)
        if now < self.impact_until_ms:
            impact_t = 1.0 - (self.impact_until_ms - now) / 320.0
            glow_alpha = min(220, glow_alpha + int(90 * (1.0 - abs(impact_t - 0.35) * 2)))
            ring = pygame.Surface((size + 40, size + 40), pygame.SRCALPHA)
            ring_r = int(self.radius + 6 + impact_t * 18)
            pygame.draw.circle(ring, (255, 230, 150, max(0, 160 - int(impact_t * 160))), ring.get_rect().center, ring_r, 2)
            screen.blit(ring, ring.get_rect(center=(cx, int(self.y - camera_y))))

        pygame.draw.circle(panel, (120, 210, 230, glow_alpha), center, self.radius + 8)
        pygame.draw.circle(panel, (235, 245, 255, 145), center, self.radius + 2)
        pygame.draw.circle(panel, (22, 30, 34, 205), center, self.radius)
        pygame.draw.circle(panel, (158, 222, 236, 210), center, self.radius, 2)

        if self.throw_active and abs(self.throw_spin) > 0.1:
            panel = pygame.transform.rotate(panel, self.throw_spin)
        screen.blit(panel, panel.get_rect(center=(cx, cy)))

        if icon:
            fitted = pygame.transform.smoothscale(icon, (max(22, size - 16), max(22, size - 16)))
            if self.throw_active and abs(self.throw_spin) > 0.1:
                fitted = pygame.transform.rotate(fitted, self.throw_spin)
            fitted.set_alpha(238)
            screen.blit(fitted, fitted.get_rect(center=(cx, cy)))
        else:
            font = pygame.font.Font(None, 24)
            label = font.render(self.item_type.value[:1].upper(), True, (228, 242, 246))
            screen.blit(label, label.get_rect(center=(cx, cy)))

        for particle in self.particles:
            life_left = 1.0 - particle["ttl"] / max(1, particle["life"])
            radius = max(1, int(particle["size"] * life_left))
            alpha = max(0, min(255, int(220 * life_left)))
            blob = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(blob, (*particle["color"], alpha), (radius + 1, radius + 1), radius)
            screen.blit(
                blob,
                blob.get_rect(center=(int(particle["x"] - camera_x), int(particle["y"] - camera_y))),
            )


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
            ItemType.CANDLE: Candle(),
            ItemType.RADIO: Radio(),
            ItemType.EMF: EmfDetector(),
            ItemType.UV_FLASHLIGHT: UVFlashlight(),
            ItemType.THERMOMETER: Thermometer(),
            ItemType.RED_DUST: RedDust(dust_active, dust_triggered),
            ItemType.SALT: Salt(salt_active, salt_triggered)
        }
        
        # Счётчики для расходных предметов
        self.item_counts = {
            ItemType.BATTERY: 0,
            ItemType.BLOOD: 0,
            ItemType.CANDLE: 0,
            ItemType.CROSS: 0,
            ItemType.RED_DUST: 0,
            ItemType.SALT: 0,
            ItemType.RADIO: 0
        }
        
        # Размещённые предметы на карте
        self.placed_items = []
        self.moving_placed_item = None
        self.dropped_items = []
        
        # Режим размещения
        self.placement_mode = False
        self.selected_item_type = None

    def pick_existing_item_at(self, x, y) -> bool:
        if self.placement_mode:
            return False
        if self.placed_projector and self.placed_projector.rect.collidepoint(x, y):
            self.moving_projector = self.placed_projector
            self.placed_projector = None
            self.moving_projector.is_moving = True
            self.placement_mode = True
            self.selected_item_type = ItemType.PROJECTOR
            return True
        for i in range(len(self.placed_items) - 1, -1, -1):
            item = self.placed_items[i]
            if item.rect.collidepoint(x, y):
                self.moving_placed_item = self.placed_items.pop(i)
                self.placement_mode = True
                self.selected_item_type = item.item_type
                return True
        return False

    def is_consumable(self, item_type: ItemType) -> bool:
        return item_type in self.item_counts

    def visible_inventory_names(self):
        names = []
        for item_name in self.game.inventory_items:
            item_type = self.item_type_from_name(item_name)
            if item_type is None:
                continue
            if self.is_consumable(item_type):
                if self.get_count(item_type) > 0:
                    names.append(item_name)
            elif self.game.inventory.get(item_name, False):
                names.append(item_name)
        return names

    def carried_slots_count(self):
        return len(self.visible_inventory_names())

    def can_receive_item(self, item_type):
        if item_type is None:
            return False
        if self.is_consumable(item_type) and self.get_count(item_type) > 0:
            return True
        if not self.is_consumable(item_type) and self.game.inventory.get(item_type.value, False):
            return True
        return self.carried_slots_count() < MAX_CARRIED_ITEMS

    def receive_item(self, item_type, amount=1):
        if not self.can_receive_item(item_type):
            if hasattr(self.game, "_show_game_info"):
                self.game._show_game_info("Инвентарь полон: максимум 3 предмета.", 1200)
            return False
        self.game.inventory[item_type.value] = True
        if self.is_consumable(item_type):
            self.increase_count(item_type, amount)
        if hasattr(self.game, "autosave_current_slot"):
            self.game.autosave_current_slot()
        return True

    def item_type_from_name(self, item_name):
        for item_type in ItemType:
            if item_type.value == item_name:
                return item_type
        return None

    def reset_runtime_state(self, clear_counts=True):
        if clear_counts:
            for item_type in self.item_counts:
                self.item_counts[item_type] = 0
        self.placed_items.clear()
        self.dropped_items.clear()
        self.moving_placed_item = None
        self.placed_projector = None
        self.moving_projector = None
        self.placement_mode = False
        self.selected_item_type = None
        self.active_hand_item = None

    def serialize_runtime_state(self):
        projector = None
        if self.placed_projector:
            projector = {
                "x": self.placed_projector.x,
                "y": self.placed_projector.y,
                "powered": self.placed_projector.powered,
                "battery_remaining": self.placed_projector.battery_remaining,
            }
        return {
            "placed_items": [item.to_dict() for item in self.placed_items],
            "placed_projector": projector,
            "dropped_items": [item.to_dict() for item in self.dropped_items],
        }

    def restore_runtime_state(self, data):
        self.reset_runtime_state(clear_counts=False)
        if not isinstance(data, dict):
            return
        for raw in data.get("placed_items", []):
            if not isinstance(raw, dict):
                continue
            item_type_name = raw.get("type")
            item_type = ItemType.__members__.get(item_type_name)
            item = self.items.get(item_type)
            if not isinstance(item, PlaceableItem):
                continue
            placed = item.create_placed_instance(raw.get("x", 0), raw.get("y", 0))
            if raw.get("triggered"):
                placed.trigger()
            self.placed_items.append(placed)
        raw_projector = data.get("placed_projector")
        if isinstance(raw_projector, dict):
            projector = PlacedProjector(
                raw_projector.get("x", 0),
                raw_projector.get("y", 0),
                self.projector_sprite,
            )
            projector.powered = bool(raw_projector.get("powered", False))
            projector.battery_remaining = max(0, int(raw_projector.get("battery_remaining", 0)))
            self.placed_projector = projector
        for raw in data.get("dropped_items", []):
            if not isinstance(raw, dict):
                continue
            item_type = ItemType.__members__.get(raw.get("type"))
            if item_type is None:
                continue
            self.dropped_items.append(DroppedInventoryItem(raw.get("x", 0), raw.get("y", 0), item_type))
    
    def get_count(self, item_type: ItemType) -> int:
        """Получить количество расходного предмета"""
        return self.item_counts.get(item_type, 0)
    
    def increase_count(self, item_type: ItemType, amount=1):
        """Увеличить количество предмета"""
        if item_type in self.item_counts:
            self.item_counts[item_type] += amount
            if hasattr(self.game, "autosave_current_slot"):
                self.game.autosave_current_slot()
    
    def decrease_count(self, item_type: ItemType, amount=1):
        """Уменьшить количество предмета"""
        if item_type in self.item_counts:
            self.item_counts[item_type] = max(0, self.item_counts[item_type] - amount)
            if hasattr(self.game, "autosave_current_slot"):
                self.game.autosave_current_slot()
    
    def use_item(self, item_type: ItemType) -> bool:
        """Использовать предмет"""
        item = self.items.get(item_type)
        if item and item.is_owned(self.game):
            ok = item.use(self.game)
            if ok and item_type in (ItemType.FLASHLIGHT, ItemType.PROJECTOR, ItemType.RED_DUST, ItemType.SALT, ItemType.BATTERY):
                self.active_hand_item = item_type
            return ok
        if hasattr(self.game, "_show_game_info"):
            self.game._show_game_info("Предмет не куплен.", 900)
        return False
    
    def use_item_by_index(self, index: int) -> bool:
        """Использовать предмет по индексу в купленных предметах"""
        purchased_items = self.visible_inventory_names()
        if 0 <= index < len(purchased_items):
            item_name = purchased_items[index]
            item_type = self.item_type_from_name(item_name)
            if item_type:
                return self.use_item(item_type)
        return False

    def _drop_point_near_player(self):
        px, py = self.game.player_rect.center
        direction = getattr(self.game, "player_direction", "down")
        offset = int(TILE_SIZE * MAP_SCALE * 0.55)
        dx, dy = 0, offset
        if direction == "left":
            dx, dy = -offset, 0
        elif direction == "right":
            dx, dy = offset, 0
        elif direction == "up":
            dx, dy = 0, -offset
        x = max(20, min(getattr(self.game, "world_width", px), px + dx))
        y = max(20, min(getattr(self.game, "world_height", py), py + dy))
        return x, y

    def drop_item_by_index(self, index):
        names = self.visible_inventory_names()
        if not (0 <= index < len(names)):
            return False
        item_type = self.item_type_from_name(names[index])
        if item_type is None:
            return False
        x, y = self._drop_point_near_player()
        if self.is_consumable(item_type):
            if self.get_count(item_type) <= 0:
                return False
            self.decrease_count(item_type)
            if self.get_count(item_type) <= 0:
                self.game.inventory[item_type.value] = False
        else:
            self.game.inventory[item_type.value] = False
        if self.active_hand_item == item_type:
            self.active_hand_item = None
        self.dropped_items.append(DroppedInventoryItem(x, y, item_type))
        if hasattr(self.game, "_show_game_info"):
            self.game._show_game_info("Предмет оставлен на полу.", 900)
        if hasattr(self.game, "autosave_current_slot"):
            self.game.autosave_current_slot()
        return True

    def pick_dropped_item_at(self, x, y):
        if self.placement_mode:
            return False
        for i in range(len(self.dropped_items) - 1, -1, -1):
            dropped = self.dropped_items[i]
            if not dropped.rect.collidepoint(x, y):
                continue
            if not self.receive_item(dropped.item_type):
                return True
            self.dropped_items.pop(i)
            if hasattr(self.game, "_show_game_info"):
                self.game._show_game_info("Предмет поднят.", 800)
            return True
        return False
    
    def start_placement(self, item_type: ItemType):
        """Начать режим размещения предмета"""
        self.placement_mode = True
        self.selected_item_type = item_type
    
    def cancel_placement(self):
        """Отменить режим размещения"""
        if self.moving_placed_item:
            self.placed_items.append(self.moving_placed_item)
            self.moving_placed_item = None
        if self.moving_projector:
            self.moving_projector.is_moving = False
            self.placed_projector = self.moving_projector
            self.moving_projector = None
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
        half = PLACED_ITEM_HITBOX_SIZE // 2
        test = pygame.Rect(x - half, y - half, PLACED_ITEM_HITBOX_SIZE, PLACED_ITEM_HITBOX_SIZE)
        for wall_rect, _ in getattr(g, 'walls', []):
            if test.colliderect(wall_rect):
                return False
        for hb in getattr(g, 'level_hitboxes', []):
            if test.colliderect(hb):
                return False
        if self._placement_line_blocked(x, y):
            return False
        return True

    def _placement_line_blocked(self, x, y) -> bool:
        g = self.game
        start = g.player_rect.center
        end = (int(x), int(y))
        for wall_rect, _ in getattr(g, 'walls', []):
            if wall_rect.clipline(start, end):
                return True
        for hb in getattr(g, 'level_hitboxes', []):
            if hb.clipline(start, end):
                return True
        return False

    def _get_valid_placement_cells(self):
        """Список координат (center_x, center_y) клеток, куда можно разместить предмет."""
        cell = TILE_SIZE * MAP_SCALE
        g = self.game
        if not hasattr(g, 'player_rect') or not hasattr(g, 'walls'):
            return []
        px, py = g.player_rect.centerx // cell, g.player_rect.centery // cell
        half = PLACED_ITEM_HITBOX_SIZE // 2
        valid = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                cx, cy = (px + dx) * cell + cell // 2, (py + dy) * cell + cell // 2
                test = pygame.Rect(cx - half, cy - half, PLACED_ITEM_HITBOX_SIZE, PLACED_ITEM_HITBOX_SIZE)
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
                if ok and self._placement_line_blocked(cx, cy):
                    ok = False
                if ok:
                    valid.append((cx, cy))
        return valid

    def _placement_cell_at(self, x, y):
        """Возвращает центр подсвеченной клетки под кликом или None."""
        half = PLACED_ITEM_HITBOX_SIZE // 2
        for cx, cy in self._get_valid_placement_cells():
            cell_rect = pygame.Rect(
                cx - half,
                cy - half,
                PLACED_ITEM_HITBOX_SIZE,
                PLACED_ITEM_HITBOX_SIZE,
            )
            if cell_rect.collidepoint(x, y):
                return cx, cy
        return None

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
            placement_cell = self._placement_cell_at(x, y)
            if not placement_cell:
                return False
            x, y = placement_cell
            if self.moving_projector:
                self.moving_projector.x, self.moving_projector.y = x, y
                half = PLACED_ITEM_HITBOX_SIZE // 2
                self.moving_projector.rect = pygame.Rect(x - half, y - half, PLACED_ITEM_HITBOX_SIZE, PLACED_ITEM_HITBOX_SIZE)
                self.moving_projector.is_moving = False
                self.placed_projector = self.moving_projector
                self.moving_projector = None
            else:
                self.placed_projector = PlacedProjector(x, y, self.projector_sprite)
            if hasattr(self.game, "increase_ghost_activity"):
                self.game.increase_ghost_activity(7, "projector")
            self.cancel_placement()
            if hasattr(self.game, "autosave_current_slot"):
                self.game.autosave_current_slot()
            return True
        
        item = self.items.get(self.selected_item_type)
        if isinstance(item, PlaceableItem):
            placement_cell = self._placement_cell_at(x, y)
            if not placement_cell:
                return False
            x, y = placement_cell
            if self.moving_placed_item:
                self.moving_placed_item.x = x
                self.moving_placed_item.y = y
                half = PLACED_ITEM_HITBOX_SIZE // 2
                self.moving_placed_item.rect = pygame.Rect(
                    x - half, y - half, PLACED_ITEM_HITBOX_SIZE, PLACED_ITEM_HITBOX_SIZE
                )
                self.placed_items.append(self.moving_placed_item)
                self.moving_placed_item = None
                self.cancel_placement()
                return True
            if self.get_count(self.selected_item_type) <= 0:
                self.cancel_placement()
                return False
            placed = item.create_placed_instance(x, y)
            self.placed_items.append(placed)
            self.decrease_count(self.selected_item_type)
            if self.selected_item_type == ItemType.SALT:
                self.game.progress_event("use_salt", 1)
            if hasattr(self.game, "increase_ghost_activity"):
                amount = 5 if self.selected_item_type == ItemType.SALT else 6
                self.game.increase_ghost_activity(amount, "place_item")
            self.cancel_placement()
            if hasattr(self.game, "autosave_current_slot"):
                self.game.autosave_current_slot()
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
                    half = PLACED_ITEM_HITBOX_SIZE // 2
                    r = pygame.Rect(
                        cx - half - camera_x,
                        cy - half - camera_y,
                        PLACED_ITEM_HITBOX_SIZE,
                        PLACED_ITEM_HITBOX_SIZE
                    )
                    s = pygame.Surface((PLACED_ITEM_HITBOX_SIZE, PLACED_ITEM_HITBOX_SIZE))
                    s.set_alpha(60)
                    s.fill((100, 150, 255))
                    screen.blit(s, r)
                    pygame.draw.rect(screen, (80, 120, 200), r, 2)
                mouse_x, mouse_y = pygame.mouse.get_pos()
                preview = self.projector_sprite.copy()
                screen.blit(preview, preview.get_rect(center=(mouse_x, mouse_y)))
            else:
                item = self.items.get(self.selected_item_type)
                if isinstance(item, PlaceableItem):
                    for cx, cy in self._get_valid_placement_cells():
                        half = PLACED_ITEM_HITBOX_SIZE // 2
                        r = pygame.Rect(
                            cx - half - camera_x,
                            cy - half - camera_y,
                            PLACED_ITEM_HITBOX_SIZE,
                            PLACED_ITEM_HITBOX_SIZE
                        )
                        s = pygame.Surface((PLACED_ITEM_HITBOX_SIZE, PLACED_ITEM_HITBOX_SIZE))
                        s.set_alpha(60)
                        s.fill((0, 255, 100))
                        screen.blit(s, r)
                        pygame.draw.rect(screen, (0, 200, 80), r, 2)
                    mouse_x, mouse_y = pygame.mouse.get_pos()
                    preview_source = self.moving_placed_item.current_sprite if self.moving_placed_item else item.sprite_active
                    preview = preview_source.copy()
                    screen.blit(preview, preview.get_rect(center=(mouse_x, mouse_y)))

    def update_dropped_items(self):
        """Обновляет анимации бросков и частиц у предметов на полу."""
        for item in self.dropped_items:
            item.update()

    def draw_dropped_items(self, screen, camera_x=0, camera_y=0):
        for item in self.dropped_items:
            item.draw(
                screen,
                icon=self.game.inventory_images.get(item.item_type.value),
                camera_x=camera_x,
                camera_y=camera_y,
            )
    
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
            if self.active_hand_item != ItemType.BATTERY:
                return False
            if self.placed_projector.power(self.game):
                if hasattr(self.game, "_show_game_info"):
                    self.game._show_game_info(f"Проектор включён. Радиус: {self.placed_projector.radius}px.", 1300)
                self.active_hand_item = None
                if hasattr(self.game, "autosave_current_slot"):
                    self.game.autosave_current_slot()
                return True
            if hasattr(self.game, "_show_game_info"):
                self.game._show_game_info("Нет аккумулятора.", 1000)
            return True
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
                    if hasattr(self.game, "autosave_current_slot"):
                        self.game.autosave_current_slot()
                    break
