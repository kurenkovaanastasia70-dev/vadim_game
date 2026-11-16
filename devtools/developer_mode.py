"""Toggleable diagnostics overlay for the running game."""

from dataclasses import dataclass
from typing import Optional

import pygame


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


class DebugOverlay:
    """Render a small, non-interactive diagnostics panel."""

    PANEL_MARGIN = 16
    PANEL_SIZE = (390, 178)
    BACKGROUND = (10, 14, 20, 205)
    BORDER = (80, 220, 150, 255)
    TEXT = (235, 245, 240)
    TITLE = (110, 245, 175)

    def __init__(self) -> None:
        self._font: Optional[pygame.font.Font] = None
        self._title_font: Optional[pygame.font.Font] = None

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font = pygame.font.Font(None, 25)
            self._title_font = pygame.font.Font(None, 27)

    @classmethod
    def panel_position(cls, screen: pygame.Surface) -> tuple[int, int]:
        return (
            max(0, screen.get_width() - cls.PANEL_SIZE[0] - cls.PANEL_MARGIN),
            max(0, screen.get_height() - cls.PANEL_SIZE[1] - cls.PANEL_MARGIN),
        )

    def draw(self, screen: pygame.Surface, snapshot: DebugSnapshot) -> None:
        self._ensure_fonts()
        panel = pygame.Surface(self.PANEL_SIZE, pygame.SRCALPHA)
        panel.fill(self.BACKGROUND)
        pygame.draw.rect(panel, self.BORDER, panel.get_rect(), 2, border_radius=6)

        title = self._title_font.render("DEVELOPER MODE [F3]", True, self.TITLE)
        panel.blit(title, (14, 11))

        player_x, player_y = snapshot.player_position
        previous_state = snapshot.enemy_previous_state or "--"
        if snapshot.enemy_position is None:
            enemy_line = "Ghost: not spawned"
        else:
            enemy_x, enemy_y = snapshot.enemy_position
            enemy_line = (
                f"Ghost: ({enemy_x}, {enemy_y})  "
                f"distance: {snapshot.enemy_distance:.0f} px"
            )
        lines = (
            f"FPS: {snapshot.fps:.1f}  |  Active objects: {snapshot.active_objects}",
            f"Player: ({player_x}, {player_y})",
            enemy_line,
            f"State: {previous_state} -> {snapshot.enemy_state}",
            f"Time in state: {snapshot.enemy_state_seconds:.1f} s",
        )
        for index, line in enumerate(lines):
            text = self._font.render(line, True, self.TEXT)
            panel.blit(text, (14, 43 + index * 25))

        screen.blit(panel, self.panel_position(screen))


class DeveloperMode:
    """Own the F3 state and expose diagnostics without changing gameplay."""

    def __init__(self) -> None:
        self.enabled = False
        self.overlay = DebugOverlay()
        self._observed_enemy_state: Optional[str] = None
        self._previous_enemy_state: Optional[str] = None
        self._state_changed_at_ms = pygame.time.get_ticks()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
            self.enabled = not self.enabled

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

    def _observe_enemy_state(self, game) -> tuple[str, Optional[str], float]:
        current_state = self._enemy_state(game)
        now = pygame.time.get_ticks()
        if self._observed_enemy_state is None:
            self._observed_enemy_state = current_state
            self._state_changed_at_ms = now
        elif current_state != self._observed_enemy_state:
            self._previous_enemy_state = self._observed_enemy_state
            self._observed_enemy_state = current_state
            self._state_changed_at_ms = now
        seconds = max(0.0, (now - self._state_changed_at_ms) / 1000.0)
        return current_state, self._previous_enemy_state, seconds

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
        )

    def draw(self, screen: pygame.Surface, game) -> None:
        if self.enabled:
            self.overlay.draw(screen, self.snapshot(game))
