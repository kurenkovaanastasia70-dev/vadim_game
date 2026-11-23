"""Toggleable diagnostics overlay for the running game."""

from dataclasses import dataclass
from typing import Optional

import pygame

from constants import FPS
from devtools.renderer import DebugRenderer
from devtools.scenarios import SCENARIOS, ScenarioManager
from gamestate import GameState


STATE_LABELS = {
    "NONE": "НЕТ",
    "UNKNOWN": "НЕИЗВЕСТНО",
    "IDLE": "ОЖИДАНИЕ",
    "PATROL": "ПАТРУЛЬ",
    "WANDER": "БЛУЖДАНИЕ",
    "SEARCH": "ПОИСК",
    "CHASE": "ПОГОНЯ",
    "RETURN": "ВОЗВРАЩЕНИЕ",
    "INVISIBLE": "НЕВИДИМ",
}


def state_label(state: Optional[str]) -> str:
    if state is None:
        return "--"
    return STATE_LABELS.get(state, state)


@dataclass(frozen=True)
class DebugSnapshot:
    """Values displayed by the overlay for the current frame."""

    fps: float
    player_position: tuple[int, int]
    active_objects: int
    enemy_state: str
    enemy_previous_state: Optional[str]
    enemy_position: Optional[tuple[int, int]]
    enemy_distance: Optional[float]
    enemy_state_seconds: float
    detail_lines: tuple[str, ...]


class DebugOverlay:
    """A single compact panel for diagnostics and scenario controls."""

    PANEL_MARGIN = 12
    PANEL_WIDTH = 370
    COLLAPSED_HEIGHT = 278
    EXPANDED_HEIGHT = 350
    SCENARIO_EXTRA_HEIGHT = 76
    BACKGROUND = (12, 18, 24, 225)
    BORDER = (80, 105, 110)
    TEXT = (225, 232, 230)
    MUTED = (155, 173, 175)
    ACCENT = (125, 220, 183)

    def __init__(self) -> None:
        self._font: Optional[pygame.font.Font] = None
        self._title_font: Optional[pygame.font.Font] = None

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font = pygame.font.Font(None, 21)
            self._title_font = pygame.font.Font(None, 23)

    @classmethod
    def panel_size(cls, expanded: bool = False, scenario_active: bool = False) -> tuple[int, int]:
        height = cls.EXPANDED_HEIGHT if expanded else cls.COLLAPSED_HEIGHT
        if scenario_active:
            height += cls.SCENARIO_EXTRA_HEIGHT
        return cls.PANEL_WIDTH, height

    @classmethod
    def panel_position(
        cls, screen: pygame.Surface, expanded: bool = False, scenario_active: bool = False
    ) -> tuple[int, int]:
        panel_width, panel_height = cls.panel_size(expanded, scenario_active)
        return (
            max(0, screen.get_width() - panel_width - cls.PANEL_MARGIN),
            max(0, screen.get_height() - panel_height - cls.PANEL_MARGIN),
        )

    @classmethod
    def details_button_rect(
        cls, screen: pygame.Surface, expanded: bool = False, scenario_active: bool = False
    ) -> pygame.Rect:
        return cls.button_rects(screen, expanded, scenario_active)["details"]

    @classmethod
    def button_rects(
        cls, screen: pygame.Surface, expanded: bool = False, scenario_active: bool = False
    ) -> dict[str, pygame.Rect]:
        x, y = cls.panel_position(screen, expanded, scenario_active)
        keys = ("hitboxes", "zones", "selection")
        buttons = {
            key: pygame.Rect(x + 12 + i * 116, y + 158, 110, 26)
            for i, key in enumerate(keys)
        }
        action_y = 292 if scenario_active else 216
        buttons.update({
            key: pygame.Rect(x + 12 + i * 87, y + action_y, 82, 26)
            for i, key in enumerate(("choose", "check", "reset", "exit"))
        })
        buttons["details"] = pygame.Rect(x + 12, y + action_y + 33, cls.PANEL_WIDTH - 24, 22)
        return buttons

    @staticmethod
    def picker_rows(screen):
        x = (screen.get_width() - 550) // 2
        y = (screen.get_height() - 430) // 2
        return [pygame.Rect(x + 18, y + 69 + i * 66, 514, 58) for i in range(len(SCENARIOS))]

    def draw_picker(self, screen):
        self._ensure_fonts()
        veil = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        veil.fill((4, 8, 12, 175))
        screen.blit(veil, (0, 0))
        x = (screen.get_width() - 550) // 2
        y = (screen.get_height() - 430) // 2
        pygame.draw.rect(screen, (16, 23, 30), (x, y, 550, 430), border_radius=9)
        pygame.draw.rect(screen, self.BORDER, (x, y, 550, 430), 1, border_radius=9)
        screen.blit(self._title_font.render("ВЫБЕРИТЕ ПРОВЕРКУ", True, self.ACCENT), (x + 20, y + 16))
        screen.blit(self._font.render("Выберите мышью или нажмите 1–5  ·  Esc — закрыть", True, self.MUTED), (x + 20, y + 42))
        for index, (rect, scenario) in enumerate(zip(self.picker_rows(screen), SCENARIOS)):
            pygame.draw.rect(screen, (32, 44, 50), rect, border_radius=5)
            screen.blit(self._title_font.render(f"{index + 1}. {scenario[1]}", True, self.TEXT), (rect.x + 12, rect.y + 6))
            screen.blit(self._font.render(f"Проверка: {scenario[3]}", True, self.MUTED), (rect.x + 12, rect.y + 31))

    def _button(self, panel, rect, label, active=False, disabled=False):
        color = (37, 87, 74) if active else (38, 51, 58)
        if disabled:
            color = (26, 34, 40)
        pygame.draw.rect(panel, color, rect, border_radius=4)
        text_color = self.ACCENT if active else (105, 120, 125) if disabled else self.TEXT
        label_surface = self._font.render(label, True, text_color)
        panel.blit(label_surface, label_surface.get_rect(center=rect.center))

    def draw(
        self, screen: pygame.Surface, snapshot: DebugSnapshot, expanded: bool = False,
        renderer=None, scenario=None, result=None,
    ) -> None:
        self._ensure_fonts()
        active = scenario is not None
        panel = pygame.Surface(self.panel_size(expanded, active), pygame.SRCALPHA)
        panel.fill(self.BACKGROUND)
        pygame.draw.rect(panel, self.BORDER, panel.get_rect(), 1, border_radius=7)
        panel.blit(self._title_font.render("РЕЖИМ РАЗРАБОТЧИКА", True, self.ACCENT), (14, 10))
        panel.blit(self._font.render("F3 · закрыть", True, self.MUTED), (263, 12))
        pygame.draw.line(panel, self.BORDER, (12, 37), (358, 37))

        player_x, player_y = snapshot.player_position
        previous_state = state_label(snapshot.enemy_previous_state)
        current_state = state_label(snapshot.enemy_state)
        if snapshot.enemy_position is None:
            enemy_line = "Призрак  —"
        else:
            enemy_x, enemy_y = snapshot.enemy_position
            enemy_line = f"Призрак  {enemy_x}, {enemy_y}   ·   {snapshot.enemy_distance:.0f} пкс"
        lines = (
            f"FPS  {snapshot.fps:.1f}     ·     Объекты  {snapshot.active_objects}",
            f"Игрок  {player_x}, {player_y}",
            enemy_line,
            f"{previous_state}  >  {current_state}     ·     {snapshot.enemy_state_seconds:.1f} с",
        )
        for index, line in enumerate(lines):
            text = self._font.render(line, True, self.TEXT)
            panel.blit(text, (14, 48 + index * 23))

        pygame.draw.line(panel, self.BORDER, (12, 146), (358, 146))
        for index, (key, label) in enumerate((
            ("hitboxes", "Контуры · F6"), ("zones", "Зоны · F7"), ("selection", "Выбор · F8")
        )):
            self._button(panel, pygame.Rect(12 + index * 116, 158, 110, 26), label, getattr(renderer, key, False))

        if active:
            panel.blit(self._font.render(scenario[1], True, self.ACCENT), (14, 192))
            panel.blit(self._font.render(f"Действие: {scenario[2]}", True, self.TEXT), (14, 216))
            panel.blit(self._font.render(f"Ожидаемо: {scenario[3]}", True, self.TEXT), (14, 240))
            status = ("PASS · " if result[0] else "FAIL · ") + result[1] if result else "Проверка ещё не запущена"
            color = self.ACCENT if result and result[0] else (245, 130, 125) if result else self.MUTED
            panel.blit(self._font.render(status, True, color), (14, 264))
        else:
            panel.blit(self._font.render("Сценарий не выбран", True, self.MUTED), (14, 192))
        action_y = 292 if active else 216
        for index, (label, disabled) in enumerate((
            ("Выбрать", False), ("Тест", not active),
            ("Сброс", not active), ("Выход", not active)
        )):
            self._button(panel, pygame.Rect(12 + index * 87, action_y, 82, 26), label, disabled=disabled)

        pygame.draw.line(panel, self.BORDER, (12, action_y + 31), (358, action_y + 31))
        marker = "−" if expanded else "+"
        panel.blit(self._font.render(f"{marker}  Состояние призрака", True, self.ACCENT), (14, action_y + 35))

        if expanded:
            for index, line in enumerate(snapshot.detail_lines):
                text = self._font.render(line, True, self.TEXT)
                panel.blit(text, (14, action_y + 62 + index * 22))

        screen.blit(panel, self.panel_position(screen, expanded, active))


class DeveloperMode:
    """Own the F3 state and expose diagnostics without changing gameplay."""

    def __init__(self) -> None:
        self.enabled = False
        self.details_expanded = False
        self.overlay = DebugOverlay()
        self.renderer = DebugRenderer()
        self.scenarios = ScenarioManager()
        self.scenario_picker_open = False
        self._observed_enemy_state: Optional[str] = None
        self._previous_enemy_state: Optional[str] = None
        self._state_changed_at_ms = pygame.time.get_ticks()
        self._last_transition_reason = "ожидаем смену состояния"

    def handle_event(
        self, event: pygame.event.Event, screen: Optional[pygame.Surface] = None, game=None
    ) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
            self.enabled = not self.enabled
            if not self.enabled:
                self.scenario_picker_open = False
            return True
        if self.enabled and self.scenario_picker_open:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_F4):
                    self.scenario_picker_open = False
                elif pygame.K_1 <= event.key <= pygame.K_5 and game is not None:
                    self._select_scenario(game, event.key - pygame.K_1)
                return True
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and screen is not None and game is not None:
                for index, rect in enumerate(self.overlay.picker_rows(screen)):
                    if rect.collidepoint(event.pos):
                        self._select_scenario(game, index)
                        break
                return True
            return True
        if self.enabled and game is not None and event.type == pygame.KEYDOWN:
            actions = {
                pygame.K_F4: lambda: self._open_picker(game),
                pygame.K_F5: lambda: self.scenarios.reset(game),
                pygame.K_F6: lambda: self._toggle("hitboxes"),
                pygame.K_F7: lambda: self._toggle("zones"),
                pygame.K_F8: lambda: self._toggle("selection"),
                pygame.K_F9: lambda: self.scenarios.exit(game),
            }
            if event.key in actions:
                actions[event.key]()
                return True
        if self.enabled and game is not None and screen is not None and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in self.overlay.button_rects(screen, self.details_expanded, bool(self.scenarios.current)).items():
                if rect.collidepoint(event.pos):
                    if key == "choose":
                        self._open_picker(game)
                    elif key == "check":
                        self.scenarios.check(game)
                    elif key == "reset":
                        self.scenarios.reset(game)
                    elif key == "exit":
                        self.scenarios.exit(game)
                    elif key == "details":
                        self.details_expanded = not self.details_expanded
                    else:
                        self._toggle(key)
                    return True
        if self.enabled and game is None and screen is not None and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.overlay.details_button_rect(screen, self.details_expanded).collidepoint(event.pos):
                self.details_expanded = not self.details_expanded
                return True
        return False

    def _open_picker(self, game):
        if game.state == GameState.GAME or self.scenarios.current:
            self.scenario_picker_open = True
            for key in game.keys_pressed:
                game.keys_pressed[key] = False

    def _select_scenario(self, game, index):
        if self.scenarios.select(game, index):
            self.scenario_picker_open = False
            scenario_id = self.scenarios.current[0]
            self.renderer.hitboxes = scenario_id in ("collision_wall", "two_objects", "ghost_detection")
            self.renderer.zones = scenario_id in ("interaction_edge", "ghost_detection")
            self.renderer.selection = scenario_id == "two_objects"

    def _toggle(self, layer):
        setattr(self.renderer, layer, not getattr(self.renderer, layer))

    @staticmethod
    def _enemy_state(game) -> str:
        ghosts = getattr(getattr(game, "ghost_manager", None), "ghosts", [])
        if not ghosts:
            return "NONE"

        state = getattr(ghosts[0], "state", None)
        if state is None:
            return "UNKNOWN"
        return str(getattr(state, "name", getattr(state, "value", state))).upper()

    @staticmethod
    def _enemy_position(game) -> Optional[tuple[int, int]]:
        ghosts = getattr(getattr(game, "ghost_manager", None), "ghosts", [])
        if not ghosts:
            return None
        rect = getattr(ghosts[0], "rect", None)
        if rect is None:
            return None
        return int(rect.centerx), int(rect.centery)

    @staticmethod
    def _first_ghost(game):
        ghosts = getattr(getattr(game, "ghost_manager", None), "ghosts", [])
        return ghosts[0] if ghosts else None

    @staticmethod
    def _same_room(ghost, player_rect) -> Optional[bool]:
        checker = getattr(ghost, "is_same_room_as_player", None)
        if not callable(checker):
            return None
        try:
            return bool(checker(player_rect))
        except (AttributeError, TypeError, ValueError):
            return None

    def _transition_reason(self, previous: str, current: str, game) -> str:
        ghost = self._first_ghost(game)
        if ghost is None:
            return "призрак удалён со сцены"
        player_rect = getattr(game, "player_rect", pygame.Rect(0, 0, 0, 0))
        same_room = self._same_room(ghost, player_rect)
        distance = pygame.Vector2(player_rect.center).distance_to(ghost.rect.center)

        if current == "INVISIBLE":
            return "истёк таймер видимости"
        if previous == "INVISIBLE" and current == "IDLE":
            return "истёк таймер появления"
        if current == "CHASE":
            if getattr(game, "hunt_active_ticks", 0) > 0:
                return "началась охота"
            if same_room:
                return "игрок обнаружен в той же комнате"
        if previous == "CHASE" and current == "SEARCH":
            return "игрок покинул комнату призрака"
        if previous == "CHASE" and current == "PATROL":
            return f"расстояние до игрока больше 600 пкс ({distance:.0f})"
        if previous == "SEARCH" and current == "PATROL":
            return "истёк трёхсекундный таймер поиска"
        if previous == "WANDER" and current == "PATROL":
            return "истёк пятисекундный таймер блуждания"
        if previous == "RETURN" and current == "PATROL":
            return "достигнут дом или истёк таймер возврата"
        if previous == "IDLE" and current == "PATROL":
            return "истёк таймер ожидания; игрок в другой комнате"
        if previous == "PATROL" and current in ("IDLE", "WANDER"):
            return "истёк таймер патруля; выбран случайный переход"
        return "состояние изменено игровой логикой"

    def _observe_enemy_state(self, game) -> tuple[str, Optional[str], float]:
        current_state = self._enemy_state(game)
        now = pygame.time.get_ticks()
        if self._observed_enemy_state is None:
            self._observed_enemy_state = current_state
            self._state_changed_at_ms = now
        elif current_state != self._observed_enemy_state:
            self._previous_enemy_state = self._observed_enemy_state
            self._last_transition_reason = self._transition_reason(
                self._observed_enemy_state, current_state, game
            )
            self._observed_enemy_state = current_state
            self._state_changed_at_ms = now
        seconds = max(0.0, (now - self._state_changed_at_ms) / 1000.0)
        return current_state, self._previous_enemy_state, seconds

    @staticmethod
    def _frames_left(ghost, duration_attribute: str, fallback: int) -> float:
        duration = int(getattr(ghost, duration_attribute, fallback))
        elapsed = int(getattr(ghost, "state_timer", 0))
        return max(0, duration - elapsed) / FPS

    def _detail_lines(self, game, state: str) -> tuple[str, ...]:
        ghost = self._first_ghost(game)
        if ghost is None:
            return (
                f"Причина: {self._last_transition_reason}",
                "Далее: ожидаем появления призрака",
                "Видимость: таймер недоступен",
            )

        if state == "INVISIBLE":
            duration = (
                getattr(ghost, "initial_appear_time", 0)
                if getattr(ghost, "is_first_appearance", False)
                else getattr(ghost, "invisibility_duration", 0)
            )
            seconds = max(0, duration - getattr(ghost, "state_timer", 0)) / FPS
            next_hint = f"Далее: ОЖИДАНИЕ примерно через {seconds:.1f} с"
            visibility_hint = "Видимость: призрак скрыт"
        elif state == "IDLE":
            seconds = self._frames_left(ghost, "idle_duration", 60)
            next_hint = f"Далее: ПОГОНЯ/ПАТРУЛЬ примерно через {seconds:.1f} с"
            visibility_hint = self._visible_timer_hint(ghost)
        elif state == "PATROL":
            seconds = self._frames_left(ghost, "patrol_duration", 270)
            next_hint = f"Далее: ПОГОНЯ при обнаружении; иначе через {seconds:.1f} с"
            visibility_hint = self._visible_timer_hint(ghost)
        elif state == "WANDER":
            seconds = self._frames_left(ghost, "unused", 300)
            next_hint = f"Далее: ПОГОНЯ или ПАТРУЛЬ через {seconds:.1f} с"
            visibility_hint = self._visible_timer_hint(ghost)
        elif state == "CHASE":
            next_hint = "Далее: ПОИСК при смене комнаты; ПАТРУЛЬ после 600 пкс"
            visibility_hint = self._visible_timer_hint(ghost)
        elif state == "SEARCH":
            seconds = self._frames_left(ghost, "unused", 180)
            next_hint = f"Далее: ПОГОНЯ или ПАТРУЛЬ через {seconds:.1f} с"
            visibility_hint = self._visible_timer_hint(ghost)
        elif state == "RETURN":
            seconds = self._frames_left(ghost, "unused", 300)
            next_hint = f"Далее: ПАТРУЛЬ дома или через {seconds:.1f} с"
            visibility_hint = self._visible_timer_hint(ghost)
        else:
            next_hint = "Далее: правило перехода недоступно"
            visibility_hint = "Видимость: таймер недоступен"

        return (
            f"Причина: {self._last_transition_reason}",
            next_hint,
            visibility_hint,
        )

    @staticmethod
    def _visible_timer_hint(ghost) -> str:
        remaining = max(
            0,
            int(getattr(ghost, "time_until_invisible", 0))
            - int(getattr(ghost, "invisibility_timer", 0)),
        )
        return f"Видимость: исчезнет примерно через {remaining / FPS:.1f} с"

    @staticmethod
    def _active_object_count(game) -> int:
        ghost_manager = getattr(game, "ghost_manager", None)
        inventory_manager = getattr(game, "inventory_manager", None)
        collections = (
            getattr(ghost_manager, "ghosts", []),
            getattr(inventory_manager, "placed_items", []),
            getattr(inventory_manager, "dropped_items", []),
        )
        return sum(len(collection) for collection in collections if collection is not None)

    def snapshot(self, game) -> DebugSnapshot:
        player_rect = getattr(game, "player_rect", pygame.Rect(0, 0, 0, 0))
        clock = getattr(game, "clock", None)
        fps = clock.get_fps() if clock is not None else 0.0
        enemy_state, previous_state, state_seconds = self._observe_enemy_state(game)
        enemy_position = self._enemy_position(game)
        enemy_distance = None
        if enemy_position is not None:
            enemy_distance = pygame.Vector2(player_rect.center).distance_to(enemy_position)
        return DebugSnapshot(
            fps=fps,
            player_position=(int(player_rect.centerx), int(player_rect.centery)),
            active_objects=self._active_object_count(game),
            enemy_state=enemy_state,
            enemy_previous_state=previous_state,
            enemy_position=enemy_position,
            enemy_distance=enemy_distance,
            enemy_state_seconds=state_seconds,
            detail_lines=self._detail_lines(game, enemy_state),
        )

    def draw(self, screen: pygame.Surface, game) -> None:
        if self.enabled:
            if game.state == GameState.GAME:
                self.renderer.draw(screen, game)
            self.overlay.draw(
                screen, self.snapshot(game), expanded=self.details_expanded,
                renderer=self.renderer, scenario=self.scenarios.current,
                result=self.scenarios.result,
            )
            if self.scenario_picker_open:
                self.overlay.draw_picker(screen)
