import pygame
import random
import math
import sys
import os
import json

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
from button import Button, PinButton
from gamestate import GameState
import draws
import handlers
import mechanics
import assets
from ghost import GhostManager, EVIDENCE_PROFILE_KEYS
from inventory_system import InventoryManager
import level_config
from progression import (
    GoogleSheetsAchievementTableProvider,
    LocalAchievementTableProvider,
    TaskAchievementManager,
)

pygame.init()

EVIDENCE_UNKNOWN = "unknown"
EVIDENCE_CONFIRMED = "confirmed"
EVIDENCE_EXCLUDED = "excluded"
EVIDENCE_STATES = (EVIDENCE_UNKNOWN, EVIDENCE_CONFIRMED, EVIDENCE_EXCLUDED)
DIFFICULTY_CONFIG = {
    0: {
        "name": "Лёгкая",
        "activity_gain_multiplier": 0.75,
        "activity_decay_per_second": 2.4,
        "ghost_speed_multiplier": 0.90,
        "hunt_cooldown_seconds": 90,
        "hunt_duration_seconds": 25,
        "radio_time_error_seconds": 5,
        "event_chance_multiplier": 0.70,
        "reward_bonus": 0,
        "blood_heal": 4,
        # Как Amateur в Phasmophobia: медленный drain, длинный setup, охота с ~50%.
        "sanity_drain_multiplier": 0.70,
        "hunt_sanity_threshold": 50,
        "setup_phase_seconds": 90,
        "sanity_pill_restore": 40,
    },
    1: {
        "name": "Нормальная",
        "activity_gain_multiplier": 1.00,
        "activity_decay_per_second": 1.7,
        "ghost_speed_multiplier": 1.00,
        "hunt_cooldown_seconds": 75,
        "hunt_duration_seconds": 35,
        "radio_time_error_seconds": 8,
        "event_chance_multiplier": 1.00,
        "reward_bonus": 20,
        "blood_heal": 3,
        "sanity_drain_multiplier": 1.00,
        "hunt_sanity_threshold": 50,
        "setup_phase_seconds": 60,
        "sanity_pill_restore": 35,
    },
    2: {
        "name": "Сложная",
        "activity_gain_multiplier": 1.25,
        "activity_decay_per_second": 1.2,
        "ghost_speed_multiplier": 1.12,
        "hunt_cooldown_seconds": 60,
        "hunt_duration_seconds": 45,
        "radio_time_error_seconds": 12,
        "event_chance_multiplier": 1.25,
        "reward_bonus": 40,
        "blood_heal": 2,
        "sanity_drain_multiplier": 1.50,
        "hunt_sanity_threshold": 50,
        "setup_phase_seconds": 30,
        "sanity_pill_restore": 25,
    },
    3: {
        "name": "Хардкор",
        "activity_gain_multiplier": 1.55,
        "activity_decay_per_second": 0.8,
        "ghost_speed_multiplier": 1.25,
        "hunt_cooldown_seconds": 45,
        "hunt_duration_seconds": 60,
        "radio_time_error_seconds": 18,
        "event_chance_multiplier": 1.60,
        "reward_bonus": 60,
        "blood_heal": 1,
        "sanity_drain_multiplier": 2.00,
        "hunt_sanity_threshold": 50,
        "setup_phase_seconds": 0,
        "sanity_pill_restore": 20,
    },
}

# Базовый пассивный drain в темноте (%/сек) для "маленькой карты", как в Phasmophobia.
SANITY_DARK_DRAIN_PER_SECOND = 0.12
SANITY_SETUP_DRAIN_FACTOR = 0.70
SANITY_SETUP_FLOOR = 50.0
SANITY_NEAR_GHOST_DRAIN_PER_SECOND = 0.20
SANITY_HUNT_DRAIN_PER_SECOND = 0.35
# Ghost event: появление призрака (manifestation). −10% только при контакте.
SANITY_GHOST_EVENT_DRAIN = 10.0
SANITY_GHOST_EVENT_DURATION_SECONDS = 5.5
SANITY_GHOST_EVENT_APPROACH_SPEED = 1.7
SANITY_GHOST_EVENT_SPAWN_DISTANCE = 150
# Свеча (firelight): сильно снижает пассивный drain в радиусе, но не как потолочный свет.
SANITY_CANDLE_DRAIN_FACTOR = 0.20
SANITY_CANDLE_RADIUS = 140
SANITY_CANDLE_DURATION_SECONDS = 90

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
        self.difficulty_levels = ["Лёгкая","Нормальная","Сложная","ХАРДКОР"]
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
            PinButton(150, 260, self.pin_images.get("pin_1"), "Начать дело"),
            PinButton(620, 205, self.pin_images.get("pin_2"), "Настройки"),
            PinButton(405, 335, self.pin_images.get("pin_2"), "Как играть"),
            PinButton(160, 500, self.pin_images.get("pin_3"), "Слоты"),
            PinButton(675, 470, self.pin_images.get("pin_1"), "Выход"),
        ]
        self.howto_back_button = Button(50, 50, 160, 44, "Назад", RED)
        # Журнал улик: ЭМП / УФ / радио и флаг панели
        self.journal_open = False
        self.journal_reset_confirm = False
        self.journal_evidence = self.default_journal_evidence()
        self.discovered_evidence = self.default_discovered_evidence()
        self.loaded_journal_evidence = None
        
        # Создание кнопок для магазина
        self.shop_buttons = [
            Button(36, 28, 120, 36, "Назад", RED),
            Button(286, 156, 116, 32, "Купить", GREEN),
            Button(286, 258, 116, 32, "Купить", BLUE),
            Button(286, 360, 116, 32, "Купить", GRAY),
            Button(286, 462, 116, 32, "Купить", GREEN),
            Button(286, 564, 116, 32, "Купить", GREEN),
            Button(794, 156, 116, 32, "Купить", GREEN),
            Button(794, 258, 116, 32, "Купить", GREEN),
            Button(794, 360, 116, 32, "Купить", BLUE),
            Button(794, 462, 116, 32, "Купить", BLUE),
            Button(794, 564, 116, 32, "Купить", BLUE),
            Button(794, 650, 116, 32, "Купить", BLUE),
            Button(286, 650, 116, 32, "Купить", GREEN),
            Button(570, 650, 116, 32, "Купить", GREEN),
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
            Button(SCREEN_WIDTH - 120, 16, 98, 38, "Меню", RED),
        ]
        self.journal_button = Button(SCREEN_WIDTH - 172, 62, 150, 38, "Дело  J", GREEN)
        self.game_over_buttons = [
            Button(SCREEN_WIDTH // 2 - 120, SCREEN_HEIGHT // 2 + 40, 240, 46, "Заново", GREEN),
            Button(SCREEN_WIDTH // 2 - 120, SCREEN_HEIGHT // 2 + 100, 240, 46, "В меню", RED),
        ]
        self.win_buttons = [
            Button(SCREEN_WIDTH // 2 - 120, SCREEN_HEIGHT // 2 + 52, 240, 46, "Заново", GREEN),
            Button(SCREEN_WIDTH // 2 - 120, SCREEN_HEIGHT // 2 + 112, 240, 46, "В меню", BLUE),
        ]
        self.game_over_reason = "hp"
        self.win_ghost_name = ""
        self.win_next_level_id = None
        self.win_report = {}

        self.player_money = 100
        self.player_level = 1
        self.player_hp = 5
        self.player_sanity = 100.0
        self.flashlight_on = False
        self.setup_phase_ticks = 0
        self.sanity_low_warned = False
        self.loaded_sanity_state = None
        self.setup_complete_banner_until = 0
        self.setup_timer_hint_until = 0
        self.setup_timer_shop_seen = False
        self.radio_announcement = None
        self.ghost_event_active = False
        self.ghost_event_ticks_left = 0
        self.lit_candles = []
        self.radio_cooldown_until = 0
        self.radio_cooldown_ms = 3000
        self.radio_feedback_until = 0
        self.radio_feedback_ok = False
        self.radio_static_sound = None
        self.hit_invincible_until = 0
        local_ach_provider = LocalAchievementTableProvider(
            os.path.join("local_lessons", "achievements_catalog.csv")
        )
        sheets_url = os.getenv("GOOGLE_SHEETS_ACHIEVEMENTS_CSV_URL", "").strip()
        ach_provider = GoogleSheetsAchievementTableProvider(sheets_url, local_ach_provider)
        self.progress_manager = TaskAchievementManager(self, ach_provider)
        self.tasks, self.achievements_table = self.progress_manager.new_state()

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
        self.player_visual_size = int(TILE_SIZE * MAP_SCALE)
        self.player_size = max(24, int(self.player_visual_size * 0.68))
        self.player_rect = pygame.Rect(0, 0, self.player_size, self.player_size)
        self.player_rect.center = (
            self.start_x + self.player_visual_size // 2,
            self.start_y + self.player_visual_size // 2,
        )
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
            "градусник": False,
            "таблетки": False,
            "свеча": False,
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
            "градусник",
            "таблетки",
            "свеча",
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
        self.loaded_inventory_runtime = None
        self.loaded_hunt_state = None
        self.loaded_ghost_state = None
        self.loaded_activity_state = None
        self.ghost_activity = 0.0
        self.activity_event_cooldown_ticks = 0
        self.activity_flash_until = 0
        self.hunt_cooldown_ticks = 0
        self.hunt_active_ticks = 0
        self.reset_hunt_timer()

        self.inventory_images = assets.load_inventory_images()
        self.trash_icon = assets.load_trash_icon()
        self.player_sprites = assets.load_player_sprites()
        self.radio_static_sound = assets.load_radio_static_sound()
        
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

        self.ghost_activity = 0
        self.activity_event_cooldown_ticks = 0
        self.activity_flash_until = 0

    def is_gameplay_paused(self):
        return bool(self.show_save_prompt or self.journal_open or self.state in (GameState.GAME_OVER, GameState.WIN))

    def update_camera(self):
        """Обновляет смещение камеры, центрируя экран на игроке в пределах мира."""
        target_x = self.player_rect.centerx - SCREEN_WIDTH // 2
        target_y = self.player_rect.centery - SCREEN_HEIGHT // 2
        self.camera_x = max(0, min(target_x, self.world_width - SCREEN_WIDTH))
        self.camera_y = max(0, min(target_y, self.world_height - SCREEN_HEIGHT))

    def nearest_visible_ghost_distance(self):
        """Возвращает расстояние до ближайшего видимого призрака или None."""
        ghosts = getattr(self.ghost_manager, "ghosts", [])
        if not ghosts:
            return None

        nearest = None
        for ghost in ghosts:
            state_name = getattr(getattr(ghost, "state", None), "name", "")
            if state_name == "INVISIBLE" or getattr(ghost, "is_frozen_after_appear", False):
                continue
            dist = self.player_rect.centerx - ghost.rect.centerx, self.player_rect.centery - ghost.rect.centery
            distance = (dist[0] ** 2 + dist[1] ** 2) ** 0.5
            nearest = distance if nearest is None else min(nearest, distance)
        return nearest

    def threat_level(self):
        """0.0 спокойствие, 1.0 максимальная тревога рядом с призраком или во время охоты."""
        distance = self.nearest_visible_ghost_distance()
        proximity = 0.0
        if distance is not None:
            proximity = max(0.0, min(1.0, 1.0 - distance / 520.0))

        hunt_pressure = 0.0
        if getattr(self, "hunt_active_ticks", 0) > 0:
            hunt_pressure = 0.45
        activity_pressure = max(0.0, min(1.0, getattr(self, "ghost_activity", 0.0) / 100.0))
        if pygame.time.get_ticks() < getattr(self, "activity_flash_until", 0):
            activity_pressure = min(1.0, activity_pressure + 0.18)
        return max(proximity, hunt_pressure, activity_pressure)

    def _show_game_info(self, text, duration_ms=1800):
        self.info_message = text
        self.info_until = pygame.time.get_ticks() + duration_ms

    def trigger_radio_feedback(self, ok, announcement=None):
        self.radio_feedback_ok = bool(ok)
        self.radio_feedback_until = pygame.time.get_ticks() + (2200 if announcement else 900)
        self.radio_announcement = announcement
        if self.radio_static_sound:
            self.radio_static_sound.set_volume(max(0, min(100, self.volume)) / 100)
            self.radio_static_sound.play()

    def apply_volume(self):
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(max(0, min(100, self.volume)) / 100)

    def is_gameplay_paused(self):
        return bool(self.show_save_prompt or self.journal_open or self.state in (GameState.GAME_OVER, GameState.WIN))

    def difficulty_config(self):
        return DIFFICULTY_CONFIG.get(self.difficulty_index, DIFFICULTY_CONFIG[1])

    def current_ghost_activity_multiplier(self):
        ghosts = getattr(self.ghost_manager, "ghosts", [])
        if not ghosts:
            return 1.0
        return max(0.2, float(getattr(ghosts[0], "activity_gain", 1.0)))

    def apply_difficulty_to_ghosts(self):
        cfg = self.difficulty_config()
        multiplier = cfg["ghost_speed_multiplier"]
        for ghost in getattr(self.ghost_manager, "ghosts", []):
            if hasattr(ghost, "set_difficulty_speed_multiplier"):
                ghost.set_difficulty_speed_multiplier(multiplier)

    def increase_ghost_activity(self, amount, reason="event"):
        cfg = self.difficulty_config()
        gain = amount * cfg["activity_gain_multiplier"] * self.current_ghost_activity_multiplier()
        before = self.ghost_activity
        self.ghost_activity = max(0.0, min(100.0, self.ghost_activity + gain))
        if int(before // 25) != int(self.ghost_activity // 25):
            self.activity_flash_until = pygame.time.get_ticks() + 650
        return self.ghost_activity

    def tick_ghost_activity(self):
        cfg = self.difficulty_config()
        decay = cfg["activity_decay_per_second"] / FPS
        if self.hunt_active_ticks > 0:
            decay *= 0.25
        self.ghost_activity = max(0.0, self.ghost_activity - decay)

        distance = self.nearest_visible_ghost_distance()
        if distance is not None and distance < 260:
            self.increase_ghost_activity(0.035, "near_ghost")

        if self.activity_event_cooldown_ticks > 0:
            self.activity_event_cooldown_ticks -= 1

        if self.ghost_activity >= 75 and self.activity_event_cooldown_ticks <= 0:
            # Как в Phasmophobia: чем ниже рассудок, тем чаще ghost events.
            sanity_factor = 1.0 + max(0.0, (100.0 - float(self.player_sanity)) / 100.0)
            chance = 0.012 * cfg["event_chance_multiplier"] * sanity_factor
            if random.random() < chance:
                self.trigger_activity_event()

        if self.ghost_activity >= 100 and self.hunt_active_ticks <= 0:
            if self.can_ghost_attempt_hunt():
                self.start_activity_hunt()
            else:
                # Как в Phasmophobia: высокая активность без низкого sanity не стартует охоту.
                self.ghost_activity = 96.0

    def trigger_activity_event(self):
        self.activity_event_cooldown_ticks = 10 * FPS
        self.activity_flash_until = pygame.time.get_ticks() + 1000
        # Как в Phasmo: appearance-ивент. Sanity падает только при контакте с призраком.
        started = self.start_ghost_appearance_event()
        if started:
            self._show_game_info(random.choice([
                "Призрак проявился рядом.",
                "Ты видишь силуэт привидения.",
                "Привидение появилось и идёт к тебе.",
                "Холод — призрак материализовался.",
            ]), 1300)
        else:
            self._show_game_info(random.choice([
                "Температура резко упала.",
                "Связь искажается.",
                "Где-то рядом сдвинулся предмет.",
                "Воздух стал тяжелым.",
            ]), 1300)

    def start_ghost_appearance_event(self):
        """Как manifestation ghost event в Phasmo: призрак появляется рядом и идёт к игроку."""
        if not self.ghost_manager.ghosts:
            return False
        ghost = self.ghost_manager.ghosts[0]
        px = float(self.player_rect.centerx)
        py = float(self.player_rect.centery)
        angle = random.uniform(0, math.tau)
        sx = px + math.cos(angle) * SANITY_GHOST_EVENT_SPAWN_DISTANCE
        sy = py + math.sin(angle) * SANITY_GHOST_EVENT_SPAWN_DISTANCE
        duration = int(SANITY_GHOST_EVENT_DURATION_SECONDS * FPS)
        if hasattr(ghost, "begin_appearance_event"):
            ghost.begin_appearance_event(sx, sy, duration)
        else:
            ghost.rect.center = (int(sx), int(sy))
            ghost.x, ghost.y = ghost.rect.x, ghost.rect.y
            from ghost import GhostState
            ghost.state = GhostState.IDLE
            if ghost.sprite:
                ghost.sprite.set_alpha(getattr(ghost, "base_alpha", 180))
        self.ghost_event_active = True
        self.ghost_event_ticks_left = duration
        return True

    def ghost_event_sanity_drain_amount(self):
        """Базово −10%, как в Phasmo; профиль может удвоить (Oni-like)."""
        amount = SANITY_GHOST_EVENT_DRAIN
        if self.ghost_manager.ghosts:
            ghost = self.ghost_manager.ghosts[0]
            mult = float(getattr(ghost, "ghost_event_sanity_mult", 1.0) or 1.0)
            amount *= max(0.5, mult)
        return amount

    def end_ghost_appearance_event(self, hissed=False):
        """Завершает appearance-ивент: призрак снова исчезает."""
        self.ghost_event_active = False
        self.ghost_event_ticks_left = 0
        if not self.ghost_manager.ghosts:
            return
        ghost = self.ghost_manager.ghosts[0]
        if hasattr(ghost, "end_appearance_event"):
            ghost.end_appearance_event()
        else:
            from ghost import GhostState
            ghost.state = GhostState.INVISIBLE
            if ghost.sprite:
                ghost.sprite.set_alpha(0)

    def tick_ghost_appearance_event(self):
        """Двигает проявившегося призрака к игроку; контакт = −10% sanity + шипение."""
        if not getattr(self, "ghost_event_active", False):
            return
        if not self.ghost_manager.ghosts:
            self.end_ghost_appearance_event(hissed=False)
            return

        ghost = self.ghost_manager.ghosts[0]
        px = float(self.player_rect.centerx)
        py = float(self.player_rect.centery)
        gx = float(ghost.rect.centerx)
        gy = float(ghost.rect.centery)
        dx = px - gx
        dy = py - gy
        dist = math.hypot(dx, dy)
        if dist > 1.0:
            step = SANITY_GHOST_EVENT_APPROACH_SPEED
            ghost.rect.centerx = int(gx + (dx / dist) * step)
            ghost.rect.centery = int(gy + (dy / dist) * step)
            ghost.x, ghost.y = ghost.rect.x, ghost.rect.y

        # Контакт с проявившимся призраком (не охота — HP не снимаем).
        if ghost.rect.colliderect(self.player_rect):
            drained = self.ghost_event_sanity_drain_amount()
            self.drain_sanity(drained, reason="ghost_event")
            self.increase_ghost_activity(8, "ghost_event_hit")
            self._show_game_info(
                f"Шипение! Призрак коснулся тебя и исчез. −{int(round(drained))}% рассудка.",
                1600,
            )
            self.end_ghost_appearance_event(hissed=True)
            return

        self.ghost_event_ticks_left -= 1
        if self.ghost_event_ticks_left <= 0:
            # Как в Phasmo: исчез без контакта — sanity не трогаем.
            self._show_game_info("Призрак растворился в воздухе.", 1100)
            self.end_ghost_appearance_event(hissed=False)

    def spawn_lit_candle(self, x, y):
        """Ставит lit firelight на карту (анти-drain в радиусе)."""
        if not hasattr(self, "lit_candles") or self.lit_candles is None:
            self.lit_candles = []
        self.lit_candles.append({
            "x": float(x),
            "y": float(y),
            "ticks_left": int(SANITY_CANDLE_DURATION_SECONDS * FPS),
        })

    def tick_lit_candles(self):
        candles = getattr(self, "lit_candles", None) or []
        alive = []
        for candle in candles:
            candle["ticks_left"] -= 1
            if candle["ticks_left"] > 0:
                alive.append(candle)
        self.lit_candles = alive

    def is_near_firelight(self):
        """Есть ли рядом горящая свеча (firelight из Phasmophobia)."""
        px = float(self.player_rect.centerx)
        py = float(self.player_rect.centery)
        for candle in getattr(self, "lit_candles", None) or []:
            if math.hypot(px - candle["x"], py - candle["y"]) <= SANITY_CANDLE_RADIUS:
                return True
        return False

    def start_activity_hunt(self):
        if not self.can_ghost_attempt_hunt():
            return False
        cfg = self.difficulty_config()
        self.hunt_active_ticks = cfg["hunt_duration_seconds"] * FPS
        self.hunt_cooldown_ticks = cfg["hunt_cooldown_seconds"] * FPS
        self.ghost_activity = 55.0
        self.activity_event_cooldown_ticks = 12 * FPS
        self.activity_flash_until = pygame.time.get_ticks() + 1200
        if getattr(self, "ghost_event_active", False):
            self.end_ghost_appearance_event(hissed=False)
        self._show_game_info("Активность достигла пика. Охота началась.", 1800)
        return True

    def reset_hunt_timer(self):
        self.hunt_cooldown_ticks = self.difficulty_config()["hunt_cooldown_seconds"] * FPS
        self.hunt_active_ticks = 0

    def tick_hunt_timer(self):
        if self.hunt_active_ticks > 0:
            self.hunt_active_ticks -= 1
            if self.hunt_active_ticks <= 0:
                self.reset_hunt_timer()
            return
        if self.hunt_cooldown_ticks > 0:
            self.hunt_cooldown_ticks -= 1
            if self.hunt_cooldown_ticks <= 0:
                if self.can_ghost_attempt_hunt():
                    self.hunt_active_ticks = self.difficulty_config()["hunt_duration_seconds"] * FPS
                    self._show_game_info("Охота началась.", 1400)
                else:
                    # Пока рассудок высокий — переводим таймер в ожидание, а не в охоту.
                    self.hunt_cooldown_ticks = max(1, 5 * FPS)

    def get_hunt_radio_text(self, radio_ok=True):
        if self.hunt_active_ticks > 0:
            return "Оно здесь. Охота уже началась."
        seconds = max(0, self.hunt_cooldown_ticks // FPS)
        error = self.difficulty_config()["radio_time_error_seconds"]
        approx = max(0, seconds + random.randint(-error, error))
        minutes = approx // 60
        rest = approx % 60
        if not radio_ok and self.difficulty_index >= 2:
            return "До охоты: сигнал искажён."
        if seconds <= 10:
            return f"До охоты: ~{minutes:02d}:{rest:02d}. Активность рядом."
        return f"До охоты: ~{minutes:02d}:{rest:02d}."

    def serialize_hunt_state(self):
        return {
            "cooldown_ticks": self.hunt_cooldown_ticks,
            "active_ticks": self.hunt_active_ticks,
        }

    def restore_hunt_state(self, data):
        if not isinstance(data, dict):
            self.reset_hunt_timer()
            return
        self.hunt_cooldown_ticks = max(0, int(data.get("cooldown_ticks", 0)))
        self.hunt_active_ticks = max(0, int(data.get("active_ticks", 0)))

    def get_player_room_id(self):
        if self.level_data and "rooms" in self.level_data:
            for i, room_data in enumerate(self.level_data["rooms"]):
                room_rect = pygame.Rect(
                    room_data["x"],
                    room_data["y"],
                    room_data["width"],
                    room_data["height"],
                )
                if room_rect.collidepoint(self.player_rect.center):
                    return i
        return -1

    def get_current_temperature_c(self):
        player_room_id = self.get_player_room_id()

        if not hasattr(self, "_room_temperatures_c"):
            self._room_temperatures_c = {}
        if not hasattr(self, "_room_temperature_next_update_ms"):
            self._room_temperature_next_update_ms = {}

        update_interval_ms = 2000
        now = pygame.time.get_ticks()

        if player_room_id not in self._room_temperatures_c:
            self._room_temperatures_c[player_room_id] = random.uniform(18.0, 22.5)
            self._room_temperature_next_update_ms[player_room_id] = now + update_interval_ms

        ghosts = getattr(self.ghost_manager, "ghosts", [])
        ghost = ghosts[0] if ghosts else None
        home_room_id = getattr(ghost, "home_room_id", -2) if ghost else -2
        is_ghost_home_room = player_room_id == home_room_id
        has_freezing = bool(getattr(ghost, "freezing_temperature", False)) if ghost else False

        if now >= self._room_temperature_next_update_ms.get(player_room_id, 0):
            current_temp = self._room_temperatures_c[player_room_id]

            if is_ghost_home_room:
                decrease = random.uniform(0.3, 1.0)
                min_temp = -5.0 if has_freezing else 6.0
                current_temp = max(min_temp, current_temp - decrease)
            else:
                fluctuation = random.uniform(-0.6, 0.6)
                current_temp = max(16.0, min(24.0, current_temp + fluctuation))

            self._room_temperatures_c[player_room_id] = current_temp
            self._room_temperature_next_update_ms[player_room_id] = now + update_interval_ms

        return round(self._room_temperatures_c[player_room_id], 1)

    def default_journal_evidence(self):
        return {k: EVIDENCE_UNKNOWN for k in EVIDENCE_PROFILE_KEYS}

    def default_discovered_evidence(self):
        return set()

    def _refresh_discovered_evidence(self):
        self.discovered_evidence = {
            k for k in EVIDENCE_PROFILE_KEYS if self.journal_evidence.get(k) == EVIDENCE_CONFIRMED
        }

    def normalize_journal_evidence(self, value):
        if not isinstance(value, dict):
            return self.default_journal_evidence()
        normalized = {}
        for k in EVIDENCE_PROFILE_KEYS:
            raw = value.get(k, EVIDENCE_UNKNOWN)
            if raw is True:
                state = EVIDENCE_CONFIRMED
            elif raw is False:
                state = EVIDENCE_UNKNOWN
            elif raw in EVIDENCE_STATES:
                state = raw
            else:
                state = EVIDENCE_UNKNOWN
            normalized[k] = state
        return normalized

    def cycle_journal_evidence_state(self, key):
        if key not in self.journal_evidence:
            return
        cur = self.journal_evidence.get(key, EVIDENCE_UNKNOWN)
        if cur == EVIDENCE_UNKNOWN:
            nxt = EVIDENCE_CONFIRMED
        elif cur == EVIDENCE_CONFIRMED:
            nxt = EVIDENCE_EXCLUDED
        else:
            nxt = EVIDENCE_UNKNOWN
        self.journal_evidence[key] = nxt
        self._refresh_discovered_evidence()

    def reset_journal_evidence(self):
        self.journal_evidence = self.default_journal_evidence()
        self._refresh_discovered_evidence()

    def use_radio(self):
        """Спросить у призрака через радиоприемник."""
        from inventory_system import ItemType
        return self.inventory_manager.use_item(ItemType.RADIO)

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
        self.inventory_manager.reset_runtime_state(clear_counts=True)
        self.uv_mode = False

    def reset_ghost_activity(self):
        self.ghost_activity = 0.0
        self.activity_event_cooldown_ticks = 0
        self.activity_flash_until = 0

    def reset_sanity(self, start_setup=True):
        """Сбрасывает рассудок к 100% и опционально запускает setup-фазу как в Phasmophobia."""
        self.player_sanity = 100.0
        self.sanity_low_warned = False
        self.flashlight_on = bool(self.inventory.get("фонарик", False))
        self.ghost_event_active = False
        self.ghost_event_ticks_left = 0
        self.lit_candles = []
        self.setup_complete_banner_until = 0
        self.setup_timer_hint_until = 0
        self.setup_timer_shop_seen = False
        self.radio_announcement = None
        if start_setup:
            self.start_setup_phase()
        else:
            self.setup_phase_ticks = 0

    def start_setup_phase(self):
        seconds = int(self.difficulty_config().get("setup_phase_seconds", 0) or 0)
        self.setup_phase_ticks = max(0, seconds * FPS)
        self.setup_complete_banner_until = 0
        self.setup_timer_shop_seen = False
        # Подсказка: таймер живёт в компьютере — игрок должен его открыть.
        if self.setup_phase_ticks > 0:
            self.setup_timer_hint_until = pygame.time.get_ticks() + 20000
        else:
            self.setup_timer_hint_until = 0

    def is_setup_phase(self):
        return getattr(self, "setup_phase_ticks", 0) > 0

    def announce_setup_complete(self):
        """Конец setup: 00:00 на компьютере + радио-анонс + баннер (прямоугольники не пересекаются)."""
        self.setup_complete_banner_until = pygame.time.get_ticks() + 3200
        self.setup_timer_hint_until = 0
        self.trigger_radio_feedback(
            True,
            announcement="База: фаза подготовки окончена. Призрак теперь может начать охоту.",
        )

    def is_flashlight_lit(self):
        """Фонарик куплен и включён. Даёт видимость, но в Phasmophobia НЕ останавливает sanity drain."""
        return bool(self.inventory.get("фонарик", False) and getattr(self, "flashlight_on", False))

    def is_in_darkness_for_sanity(self):
        """
        Для sanity: пока нет комнатных выключателей, расследование считается "тёмной зоной".
        Как в Phasmophobia: обычный фонарик не блокирует пассивный drain.
        """
        return True

    def hunt_sanity_threshold(self):
        return float(self.difficulty_config().get("hunt_sanity_threshold", 50))

    def can_ghost_attempt_hunt(self):
        """Как в Phasmophobia: охота возможна только ниже порога рассудка и вне setup-фазы."""
        if self.is_setup_phase():
            return False
        return self.player_sanity < self.hunt_sanity_threshold()

    def drain_sanity(self, amount, reason="event"):
        """Списывает рассудок. Во время setup не опускает ниже 50%."""
        if amount <= 0:
            return self.player_sanity
        before = self.player_sanity
        self.player_sanity = max(0.0, self.player_sanity - float(amount))
        if self.is_setup_phase():
            self.player_sanity = max(SANITY_SETUP_FLOOR, self.player_sanity)
        if before >= self.hunt_sanity_threshold() > self.player_sanity and not self.sanity_low_warned:
            self.sanity_low_warned = True
            self._show_game_info("Рассудок ниже 50%. Охота теперь возможна.", 1600)
        return self.player_sanity

    def restore_sanity(self, amount, reason="pills"):
        """Восстанавливает рассудок (таблетки и т.п.), не выше 100%."""
        if amount <= 0:
            return self.player_sanity
        self.player_sanity = min(100.0, self.player_sanity + float(amount))
        if self.player_sanity >= self.hunt_sanity_threshold():
            self.sanity_low_warned = False
        return self.player_sanity

    def tick_setup_phase_clock(self):
        """Только countdown setup (для магазина/компьютера без пассивного drain)."""
        if self.setup_phase_ticks <= 0:
            return
        self.setup_phase_ticks -= 1
        if self.setup_phase_ticks == 0:
            self.announce_setup_complete()

    def tick_sanity(self):
        """Пассивный расход рассудка по правилам Phasmophobia (фонарик не спасает sanity)."""
        self.tick_setup_phase_clock()

        cfg = self.difficulty_config()
        drain = 0.0

        # 1) Базовый drain на локации без потолочного света комнаты.
        # Фонарик тут намеренно не проверяем: в Phasmo он не останавливает sanity.
        # Свеча (firelight) сильно снижает, но не обнуляет drain полностью.
        if self.is_in_darkness_for_sanity():
            dark = SANITY_DARK_DRAIN_PER_SECOND
            if self.is_near_firelight():
                dark *= SANITY_CANDLE_DRAIN_FACTOR
            drain += dark

        # 2) Видимый призрак рядом дополнительно давит на психику.
        distance = self.nearest_visible_ghost_distance()
        if distance is not None and distance < 220:
            drain += SANITY_NEAR_GHOST_DRAIN_PER_SECOND

        # 3) Во время охоты рассудок падает быстрее.
        if self.hunt_active_ticks > 0:
            drain += SANITY_HUNT_DRAIN_PER_SECOND

        if drain <= 0:
            return self.player_sanity

        drain *= float(cfg.get("sanity_drain_multiplier", 1.0))
        if self.is_setup_phase():
            drain *= SANITY_SETUP_DRAIN_FACTOR

        return self.drain_sanity(drain / FPS, reason="passive")

    def get_next_level_id(self):
        """Возвращает следующий уровень для текущей позиции кампании."""
        level_id = self.current_level_id
        if not level_id:
            meta = level_config.get_level_by_number(self.player_level)
            level_id = meta.get("id") if meta else None
        return level_config.get_next_level_id(level_id)

    def has_next_level(self):
        return bool(getattr(self, "win_next_level_id", None) or self.get_next_level_id())

    def get_level_name(self, level_id=None):
        level_id = level_id or self.current_level_id
        meta = level_config.get_level_index().get(level_id) if level_id else None
        if not meta:
            meta = level_config.get_level_by_number(self.player_level)
        return meta.get("name", f"Уровень {self.player_level}") if meta else f"Уровень {self.player_level}"

    def get_level_complete_reward_breakdown(self):
        """Считает денежную награду за победу: база + сложность + бонус за подтверждённые улики."""
        base = 80 + max(0, self.player_level - 1) * 35
        difficulty_bonus = int(self.difficulty_config()["reward_bonus"])
        confirmed_count = sum(
            1 for state in self.journal_evidence.values() if state == EVIDENCE_CONFIRMED
        )
        evidence_bonus = confirmed_count * 15
        total = base + difficulty_bonus + evidence_bonus
        return {
            "base": base,
            "difficulty_bonus": difficulty_bonus,
            "evidence_bonus": evidence_bonus,
            "confirmed_count": confirmed_count,
            "total": total,
        }

    def get_level_complete_reward(self):
        return self.get_level_complete_reward_breakdown()["total"]

    def configure_win_buttons(self):
        if self.has_next_level():
            self.win_buttons = [
                Button(SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 + 158, 300, 46, "Следующий уровень", GREEN),
                Button(SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 + 216, 300, 46, "Заново", GRAY),
                Button(SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 + 274, 300, 46, "В меню", BLUE),
            ]
        else:
            self.win_buttons = [
                Button(SCREEN_WIDTH // 2 - 130, SCREEN_HEIGHT // 2 + 186, 260, 46, "Заново", GREEN),
                Button(SCREEN_WIDTH // 2 - 130, SCREEN_HEIGHT // 2 + 246, 260, 46, "В меню", BLUE),
            ]

    def advance_to_next_level(self):
        """Переходит на следующий уровень из levels_index.json."""
        next_level_id = self.get_next_level_id()
        if not next_level_id:
            self._show_game_info("Это был последний доступный уровень.", 1600)
            return False

        next_meta = level_config.get_level_index().get(next_level_id, {})
        self.player_level = int(next_meta.get("number", self.player_level + 1))
        self.current_level_id = next_level_id
        self.win_next_level_id = None
        self.reset_inventory()
        self.reset_journal_evidence()
        self.loaded_journal_evidence = None
        self.loaded_inventory_runtime = None
        self.loaded_hunt_state = None
        self.loaded_ghost_state = None
        self.loaded_activity_state = None
        self.reset_ghost_activity()
        self.loaded_sanity_state = None
        self.reset_sanity(start_setup=True)
        self.set_state(GameState.GAME, reset_stack=True)
        if self.selected_save_slot:
            self.save_game(self.selected_save_slot)
        return True

    def restart_current_level(self):
        """Перезапускает текущий уровень, не сбрасывая кампанию на первый уровень."""
        self.game_over_reason = "hp"
        self.player_hp = 5
        self.win_next_level_id = None
        self.win_report = {}
        self.reset_inventory()
        self.reset_player_position()
        self.journal_open = False
        self.journal_reset_confirm = False
        self.reset_journal_evidence()
        self.loaded_journal_evidence = None
        self.loaded_inventory_runtime = None
        self.loaded_hunt_state = None
        self.loaded_ghost_state = None
        self.loaded_activity_state = None
        self.loaded_sanity_state = None
        self.radio_cooldown_until = 0
        self.reset_hunt_timer()
        self.reset_ghost_activity()
        self.reset_sanity(start_setup=True)
        self.set_state(GameState.GAME, reset_stack=True)

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
            self.journal_reset_confirm = False
            if self.loaded_journal_evidence is not None:
                self.journal_evidence = self.loaded_journal_evidence
                self.loaded_journal_evidence = None
            else:
                self.journal_evidence = self.default_journal_evidence()
            self._refresh_discovered_evidence()
            if self.loaded_inventory_runtime is not None:
                self.inventory_manager.restore_runtime_state(self.loaded_inventory_runtime)
                self.loaded_inventory_runtime = None
            else:
                self.inventory_manager.reset_runtime_state(clear_counts=False)
            if self.loaded_hunt_state is not None:
                self.restore_hunt_state(self.loaded_hunt_state)
                self.loaded_hunt_state = None
            else:
                self.reset_hunt_timer()
            if self.loaded_ghost_state is not None:
                self.ghost_manager.restore_runtime_state(self.loaded_ghost_state)
                self.loaded_ghost_state = None
            if self.loaded_activity_state is not None:
                try:
                    self.ghost_activity = max(0.0, min(100.0, float(self.loaded_activity_state)))
                except (TypeError, ValueError):
                    self.reset_ghost_activity()
                self.loaded_activity_state = None
            else:
                self.reset_ghost_activity()
            if self.loaded_sanity_state is not None:
                try:
                    self.player_sanity = max(0.0, min(100.0, float(self.loaded_sanity_state.get("sanity", 100))))
                    self.flashlight_on = bool(self.loaded_sanity_state.get("flashlight_on", self.inventory.get("фонарик", False)))
                    self.setup_phase_ticks = max(0, int(self.loaded_sanity_state.get("setup_phase_ticks", 0)))
                    self.sanity_low_warned = bool(self.loaded_sanity_state.get("sanity_low_warned", False))
                except (TypeError, ValueError, AttributeError):
                    self.reset_sanity(start_setup=True)
                self.loaded_sanity_state = None
            else:
                self.reset_sanity(start_setup=True)
            self.apply_difficulty_to_ghosts()
            # Создаём текстуру виньетки для эффекта затемнения (один раз при загрузке)
            self.vignette_texture = None
            self.update_camera()
        else:
            print(f"Не удалось загрузить уровень: {level_file_path}")
            self.vignette_texture = None  # Эффект затемнения всегда при входе в уровень
            self.update_camera()
    
    def _create_vignette_texture(self):
        self.vignette_texture = None

    def _create_clipped_vignette_overlay(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        fog_r, fog_g, fog_b = 15, 12, 35
        max_alpha = 220
        overlay.fill((fog_r, fog_g, fog_b, max_alpha))

        player_cx = self.player_rect.centerx - self.camera_x
        player_cy = self.player_rect.centery - self.camera_y
        visible_radius = 120
        falloff_radius = 200

        for y in range(0, SCREEN_HEIGHT, 3):
            for x in range(0, SCREEN_WIDTH, 3):
                d = ((x - player_cx) ** 2 + (y - player_cy) ** 2) ** 0.5
                if d < visible_radius:
                    alpha = 0
                elif d < falloff_radius:
                    t = (d - visible_radius) / (falloff_radius - visible_radius)
                    alpha = int(max_alpha * (t ** 1.5))
                else:
                    continue
                overlay.fill((fog_r, fog_g, fog_b, alpha), (x, y, 3, 3))

        return overlay

    def _create_room_visibility_overlay(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((15, 12, 35, 210))

        player_room = None
        if self.level_data and "rooms" in self.level_data:
            for room_data in self.level_data["rooms"]:
                room_rect = pygame.Rect(
                    room_data["x"],
                    room_data["y"],
                    room_data["width"],
                    room_data["height"],
                )
                if room_rect.collidepoint(self.player_rect.center):
                    player_room = room_rect
                    break

        if player_room:
            screen_room = player_room.move(-self.camera_x, -self.camera_y)
            pygame.draw.rect(overlay, (0, 0, 0, 0), screen_room)
        else:
            return self._create_clipped_vignette_overlay()

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
        self.player_rect.center = (
            self.start_x + self.player_visual_size // 2,
            self.start_y + self.player_visual_size // 2,
        )
        self.moving = False
        # HP НЕ сбрасываем здесь — они сохраняются между уровнями
        self.hit_invincible_until = 0
        for key in self.keys_pressed:
            self.keys_pressed[key] = False
        self.update_camera()
    
    def reset_for_new_game(self):
        """Полный сброс для новой игры"""
        self.game_over_reason = "hp"
        self.player_hp = 5
        self.player_money = 100
        self.player_level = 1
        self.reset_inventory()
        self.reset_player_position()
        self.journal_open = False
        self.journal_reset_confirm = False
        self.reset_journal_evidence()
        self.loaded_journal_evidence = None
        self.loaded_inventory_runtime = None
        self.loaded_hunt_state = None
        self.loaded_ghost_state = None
        self.loaded_activity_state = None
        self.loaded_sanity_state = None
        self.radio_cooldown_until = 0
        self.reset_hunt_timer()
        self.reset_ghost_activity()
        self.reset_sanity(start_setup=True)
        self.tasks, self.achievements_table = self.progress_manager.new_state()
    
        
    def buy_item(self, item_name, cost):
        """Покупка предмета в магазине"""
        #Todo: реализовать систему выкидывания при переполнении стека предметов
        item_type = self.inventory_manager.item_type_from_name(item_name)
        is_consumable = item_type in self.inventory_manager.item_counts if item_type else False
        if item_type and not self.inventory_manager.can_receive_item(item_type):
            self._show_game_info("Инвентарь полон: максимум 3 предмета.", 1200)
            return False
        if self.player_money >= cost and (is_consumable or not self.inventory.get(item_name, False)):
            self.player_money -= cost
            self.inventory[item_name] = True
            if item_name == "фонарик":
                self.flashlight_on = True
            if is_consumable:
                self.inventory_manager.increase_count(item_type)
            self.progress_event("buy_item", 1)
            return True
        return False

    def progress_event(self, event_key, value=1):
        result = self.progress_manager.progress_event(event_key, value)
        if result.messages:
            self._show_game_info(result.messages[0], 1500)
        self.autosave_current_slot()

    def autosave_current_slot(self):
        if self.selected_save_slot:
            self.save_game(self.selected_save_slot)

    def submit_ghost_guess(self, profile_id):
        actual = None
        ghost_name = profile_id
        if self.ghost_manager.ghosts:
            actual = self.ghost_manager.ghosts[0].ghost_kind
            ghost_name = self.ghost_manager.ghosts[0].display_name
        if profile_id == actual:
            self.enter_win(ghost_name)
            return True
        self.enter_game_over(reason="wrong_ghost")
        return False

    def enter_win(self, ghost_name=""):
        self.win_ghost_name = ghost_name or "призрак"
        self.win_next_level_id = self.get_next_level_id()
        breakdown = self.get_level_complete_reward_breakdown()
        reward = breakdown["total"]
        self.player_money += reward
        next_meta = level_config.get_level_index().get(self.win_next_level_id, {}) if self.win_next_level_id else {}
        found_evidence = [
            key for key, state in self.journal_evidence.items()
            if state == EVIDENCE_CONFIRMED
        ]
        self.win_report = {
            "level_name": self.get_level_name(),
            "found_evidence": found_evidence,
            "reward": reward,
            "reward_base": breakdown["base"],
            "reward_difficulty_bonus": breakdown["difficulty_bonus"],
            "reward_evidence_bonus": breakdown["evidence_bonus"],
            "confirmed_count": breakdown["confirmed_count"],
            "money_after": self.player_money,
            "next_level_name": next_meta.get("name") if next_meta else None,
        }
        self.win_entered_at = pygame.time.get_ticks()
        self.configure_win_buttons()
        self.moving = False
        self.show_save_prompt = False
        self.info_message = None
        self.info_until = 0
        self.journal_open = False
        self.journal_reset_confirm = False
        self.inventory_manager.cancel_placement()
        for key in self.keys_pressed:
            self.keys_pressed[key] = False
        if self.selected_save_slot:
            self.save_game(self.selected_save_slot)
        self.set_state(GameState.WIN)

    def enter_game_over(self, reason="hp"):
        self.game_over_reason = reason
        self.moving = False
        self.show_save_prompt = False
        self.info_message = None
        self.info_until = 0
        self.journal_open = False
        self.journal_reset_confirm = False
        self.inventory_manager.cancel_placement()
        for key in self.keys_pressed:
            self.keys_pressed[key] = False
        self.set_state(GameState.GAME_OVER)

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
            "SALT": self.inventory_manager.item_counts.get(ItemType.SALT, 0),
            "RADIO": self.inventory_manager.item_counts.get(ItemType.RADIO, 0)
        }
        save_data = {
            "level": self.player_level,
            "hp": self.player_hp,
            "money": self.player_money,
            "sanity": round(float(getattr(self, "player_sanity", 100.0)), 2),
            "flashlight_on": bool(getattr(self, "flashlight_on", False)),
            "setup_phase_ticks": int(getattr(self, "setup_phase_ticks", 0)),
            "sanity_low_warned": bool(getattr(self, "sanity_low_warned", False)),
            "inventory": self.inventory.copy(),
            "item_counts": item_counts_serial,
            "inventory_runtime": self.inventory_manager.serialize_runtime_state(),
            "hunt_state": self.serialize_hunt_state(),
            "ghost_activity": round(float(getattr(self, "ghost_activity", 0.0)), 2),
            "ghost_state": self.ghost_manager.serialize_runtime_state(),
            "journal_evidence": self.normalize_journal_evidence(self.journal_evidence),
            "discovered_evidence": sorted(self.discovered_evidence),
            "difficulty": self.difficulty_index,
            "difficulty_selected": self.difficulty_selected,
            "tasks": self.tasks,
            "achievements_table": self.achievements_table,
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
            saved_inventory = save_data.get("inventory") or {}
            default_light = bool(saved_inventory.get("фонарик", False))
            self.loaded_sanity_state = {
                "sanity": save_data.get("sanity", 100.0),
                "flashlight_on": save_data.get("flashlight_on", default_light),
                "setup_phase_ticks": save_data.get("setup_phase_ticks", 0),
                "sanity_low_warned": save_data.get("sanity_low_warned", False),
            }
            self.journal_evidence = self.normalize_journal_evidence(save_data.get("journal_evidence"))
            saved_discovered = save_data.get("discovered_evidence")
            if isinstance(saved_discovered, list):
                self.discovered_evidence = {k for k in saved_discovered if k in EVIDENCE_PROFILE_KEYS}
            else:
                self.discovered_evidence = self.default_discovered_evidence()
            self._refresh_discovered_evidence()
            self.loaded_journal_evidence = self.journal_evidence.copy()
            # Загружаем инвентарь (с fallback для старых сохранений)
            saved_inventory = save_data.get("inventory", None)
            if saved_inventory:
                base_inventory = {key: False for key in self.inventory_items}
                base_inventory.update(saved_inventory)
                self.inventory = base_inventory
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
                self.inventory_manager.item_counts[ItemType.RADIO] = saved_counts.get("RADIO", int(self.inventory.get("радио", False)))
            else:
                from inventory_system import ItemType
                self.inventory_manager.item_counts[ItemType.BATTERY] = 0
                self.inventory_manager.item_counts[ItemType.BLOOD] = 0
                self.inventory_manager.item_counts[ItemType.CROSS] = 0
                self.inventory_manager.item_counts[ItemType.RED_DUST] = 0
                self.inventory_manager.item_counts[ItemType.SALT] = 0
                self.inventory_manager.item_counts[ItemType.RADIO] = int(self.inventory.get("радио", False))
            self.tasks, self.achievements_table = self.progress_manager.normalize_state(
                save_data.get("tasks"),
                save_data.get("achievements_table"),
            )
            self.loaded_inventory_runtime = save_data.get("inventory_runtime")
            self.loaded_hunt_state = save_data.get("hunt_state")
            self.loaded_ghost_state = save_data.get("ghost_state")
            self.loaded_activity_state = save_data.get("ghost_activity", 0.0)
            
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
            if not self.is_gameplay_paused():
                mechanics.update_player_movement(self)
                self.tick_sanity()
                self.tick_lit_candles()
                self.tick_ghost_appearance_event()
                self.tick_hunt_timer()
                self.tick_ghost_activity()
                pz = self.inventory_manager.get_projector_zones()
                self.ghost_manager.update(
                    self.player_rect,
                    self.walls,
                    self.level_hitboxes,
                    projector_zones=pz,
                    dropped_items=self.inventory_manager.dropped_items,
                    world_width=self.world_width,
                    world_height=self.world_height,
                )
                self.inventory_manager.update_dropped_items()
                throw_event = getattr(self.ghost_manager, "last_throw_event", None)
                if throw_event:
                    self.ghost_manager.last_throw_event = None
                    if throw_event.get("room_id") == self.get_player_room_id():
                        count = int(throw_event.get("count", 1) or 1)
                        word = "предмет" if count == 1 else ("предмета" if count == 2 else "предметов")
                        self._show_game_info(f"Призрак разбросал {count} {word}!", 1200)
                        self.drain_sanity(2.0, reason="item_throw")
                # Столкновение с приведением — отнимаем HP (не во время appearance ghost event).
                now = pygame.time.get_ticks()
                if (
                    not getattr(self, "ghost_event_active", False)
                    and self.ghost_manager.check_player_collision(self.player_rect)
                    and now >= self.hit_invincible_until
                ):
                    self.player_hp = max(0, self.player_hp - 1)
                    self.hit_invincible_until = now + 1500
                    self.increase_ghost_activity(12, "player_hit")
                    self.drain_sanity(10.0, reason="ghost_hit")
                    self.progress_event("take_hit", 1)
                    if self.player_hp <= 0:
                        self.enter_game_over()
                        draws.draw_game_over(self)
                        pygame.display.flip()
                        return
            else:
                self.moving = False
                for key in self.keys_pressed:
                    self.keys_pressed[key]=False
            draws.draw_game(self)
        elif self.state == GameState.SHOP:
            self.moving = False
            # Как таймер в фургоне Phasmo: countdown идёт, пока смотришь «компьютер».
            if self.player_hp > 0:
                self.tick_setup_phase_clock()
            draws.draw_shop(self)
        elif self.state == GameState.SETTINGS:
            draws.draw_settings(self)
        elif self.state == GameState.DIFF:
            draws.draw_difficulty(self)
        elif self.state == GameState.SAVES:
            draws.draw_saves(self)
        elif self.state == GameState.HOWTO:
            draws.draw_howto(self)
        elif self.state == GameState.GAME_OVER:
            self.moving = False
            draws.draw_game_over(self)
        elif self.state == GameState.WIN:
            self.moving = False
            draws.draw_win(self)
        # Отображаем информационное сообщение поверх всех экранов
        if self.info_message and pygame.time.get_ticks() < self.info_until:
            # Полупрозрачный фон
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            overlay.set_alpha(128)
            overlay.fill(BLACK)
            self.screen.blit(overlay, (0, 0))
            
            # Диалоговое окно для сообщения
            lines = str(self.info_message).splitlines() or [str(self.info_message)]
            line_height = 30
            info_rect = pygame.Rect(
                SCREEN_WIDTH // 2 - 330,
                SCREEN_HEIGHT // 2 - max(45, 18 + len(lines) * line_height // 2),
                660,
                max(84, 36 + len(lines) * line_height),
            )
            pygame.draw.rect(self.screen, DARK_GRAY, info_rect)
            pygame.draw.rect(self.screen, WHITE, info_rect, 3)
            
            info_font = pygame.font.Font(None, 32)
            start_y = info_rect.centery - (len(lines) - 1) * line_height // 2
            for i, line in enumerate(lines):
                info_text = info_font.render(line, True, WHITE)
                info_text_rect = info_text.get_rect(center=(info_rect.centerx, start_y + i * line_height))
                self.screen.blit(info_text, info_text_rect)
        elif self.info_message and pygame.time.get_ticks() >= self.info_until:
            self.info_message = None
        
        pygame.display.flip()
    def run(self):
        while self.running:
            handlers.handle_event(self)
            
            if self.state == GameState.GAME and self.player_hp > 0 and not self.is_gameplay_paused():
                self.inventory_manager.update_placed_items()
                self.inventory_manager.update_projector()
            elif self.state == GameState.GAME:
                # Даже на паузе журнала доигрываем уже начатый бросок.
                self.inventory_manager.update_dropped_items()
            
            self.draw()

            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()
if __name__ == "__main__":
    game = Game()
    game.run()
