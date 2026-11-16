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


class DebugOverlay:
    """Render a small, non-interactive diagnostics panel."""

    PANEL_POSITION = (16, 16)
    PANEL_SIZE = (340, 154)
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

    def draw(self, screen: pygame.Surface, snapshot: DebugSnapshot) -> None:
        self._ensure_fonts()
        panel = pygame.Surface(self.PANEL_SIZE, pygame.SRCALPHA)
        panel.fill(self.BACKGROUND)
        pygame.draw.rect(panel, self.BORDER, panel.get_rect(), 2, border_radius=6)

        title = self._title_font.render("DEVELOPER MODE [F3]", True, self.TITLE)
        panel.blit(title, (14, 11))

        x, y = snapshot.player_position
        lines = (
            f"FPS: {snapshot.fps:.1f}",
            f"Player: ({x}, {y})",
            f"Active objects: {snapshot.active_objects}",
            f"Enemy state: {snapshot.enemy_state}",
        )
        for index, line in enumerate(lines):
            text = self._font.render(line, True, self.TEXT)
            panel.blit(text, (14, 43 + index * 25))

        screen.blit(panel, self.PANEL_POSITION)


class DeveloperMode:
    """Own the F3 state and expose diagnostics without changing gameplay."""

    def __init__(self) -> None:
        self.enabled = False
        self.overlay = DebugOverlay()

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
        return DebugSnapshot(
            fps=fps,
            player_position=(int(player_rect.centerx), int(player_rect.centery)),
            active_objects=self._active_object_count(game),
            enemy_state=self._enemy_state(game),
        )

    def draw(self, screen: pygame.Surface, game) -> None:
        if self.enabled:
            self.overlay.draw(screen, self.snapshot(game))
