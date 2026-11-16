"""Toggleable diagnostics overlay for the running game."""

from dataclasses import dataclass
from typing import Optional

import pygame

from constants import FPS


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
    """Render diagnostics with a small clickable details control."""

    PANEL_MARGIN = 16
    PANEL_WIDTH = 410
    COLLAPSED_HEIGHT = 205
    EXPANDED_HEIGHT = 285
    DETAILS_BUTTON_Y = 171
    DETAILS_BUTTON_HEIGHT = 24
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
    def panel_size(cls, expanded: bool = False) -> tuple[int, int]:
        height = cls.EXPANDED_HEIGHT if expanded else cls.COLLAPSED_HEIGHT
        return cls.PANEL_WIDTH, height

    @classmethod
    def panel_position(
        cls, screen: pygame.Surface, expanded: bool = False
    ) -> tuple[int, int]:
        panel_width, panel_height = cls.panel_size(expanded)
        return (
            max(0, screen.get_width() - panel_width - cls.PANEL_MARGIN),
            max(0, screen.get_height() - panel_height - cls.PANEL_MARGIN),
        )

    @classmethod
    def details_button_rect(
        cls, screen: pygame.Surface, expanded: bool = False
    ) -> pygame.Rect:
        panel_x, panel_y = cls.panel_position(screen, expanded)
        return pygame.Rect(
            panel_x + 10,
            panel_y + cls.DETAILS_BUTTON_Y,
            cls.PANEL_WIDTH - 20,
            cls.DETAILS_BUTTON_HEIGHT,
        )

    def draw(
        self, screen: pygame.Surface, snapshot: DebugSnapshot, expanded: bool = False
    ) -> None:
        self._ensure_fonts()
        panel = pygame.Surface(self.panel_size(expanded), pygame.SRCALPHA)
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

        button_rect = pygame.Rect(
            10,
            self.DETAILS_BUTTON_Y,
            self.PANEL_WIDTH - 20,
            self.DETAILS_BUTTON_HEIGHT,
        )
        pygame.draw.rect(panel, (35, 65, 58, 230), button_rect, border_radius=4)
        marker = "[-]" if expanded else "[+]"
        button_text = self._font.render(
            f"{marker} Ghost state details (click)", True, self.TITLE
        )
        panel.blit(button_text, (16, self.DETAILS_BUTTON_Y + 2))

        if expanded:
            pygame.draw.line(panel, self.BORDER, (12, 203), (398, 203), 1)
            for index, line in enumerate(snapshot.detail_lines):
                text = self._font.render(line, True, self.TEXT)
                panel.blit(text, (14, 211 + index * 23))

        screen.blit(panel, self.panel_position(screen, expanded))


class DeveloperMode:
    """Own the F3 state and expose diagnostics without changing gameplay."""

    def __init__(self) -> None:
        self.enabled = False
        self.details_expanded = False
        self.overlay = DebugOverlay()
        self._observed_enemy_state: Optional[str] = None
        self._previous_enemy_state: Optional[str] = None
        self._state_changed_at_ms = pygame.time.get_ticks()
        self._last_transition_reason = "Waiting for a state transition"

    def handle_event(
        self, event: pygame.event.Event, screen: Optional[pygame.Surface] = None
    ) -> bool:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
            self.enabled = not self.enabled
            return True
        if (
            self.enabled
            and screen is not None
            and event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.overlay.details_button_rect(
                screen, self.details_expanded
            ).collidepoint(event.pos)
        ):
            self.details_expanded = not self.details_expanded
            return True
        return False

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
            return "Ghost was removed from the scene"
        player_rect = getattr(game, "player_rect", pygame.Rect(0, 0, 0, 0))
        same_room = self._same_room(ghost, player_rect)
        distance = pygame.Vector2(player_rect.center).distance_to(ghost.rect.center)

        if current == "INVISIBLE":
            return "visibility timer expired"
        if previous == "INVISIBLE" and current == "IDLE":
            return "appearance timer expired"
        if current == "CHASE":
            if getattr(game, "hunt_active_ticks", 0) > 0:
                return "hunt started"
            if same_room:
                return "player detected in the same room"
        if previous == "CHASE" and current == "SEARCH":
            return "player left the ghost's room"
        if previous == "CHASE" and current == "PATROL":
            return f"player distance exceeded 600 px ({distance:.0f})"
        if previous == "SEARCH" and current == "PATROL":
            return "3-second search timer expired"
        if previous == "WANDER" and current == "PATROL":
            return "5-second wander timer expired"
        if previous == "RETURN" and current == "PATROL":
            return "home reached or 5-second return timer expired"
        if previous == "IDLE" and current == "PATROL":
            return "idle timer expired; player is in another room"
        if previous == "PATROL" and current in ("IDLE", "WANDER"):
            return "patrol timer expired; random branch selected"
        return "state changed by game logic"

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
                f"Reason: {self._last_transition_reason}",
                "Next: waiting for a ghost to spawn",
                "Visibility: no timer available",
            )

        if state == "INVISIBLE":
            duration = (
                getattr(ghost, "initial_appear_time", 0)
                if getattr(ghost, "is_first_appearance", False)
                else getattr(ghost, "invisibility_duration", 0)
            )
            seconds = max(0, duration - getattr(ghost, "state_timer", 0)) / FPS
            next_hint = f"Next: IDLE in ~{seconds:.1f} s (appearance)"
            visibility_hint = "Visibility: hidden"
        elif state == "IDLE":
            seconds = self._frames_left(ghost, "idle_duration", 60)
            next_hint = f"Next: CHASE/PATROL in ~{seconds:.1f} s"
            visibility_hint = self._visible_timer_hint(ghost)
        elif state == "PATROL":
            seconds = self._frames_left(ghost, "patrol_duration", 270)
            next_hint = f"Next: CHASE on detection; otherwise ~{seconds:.1f} s"
            visibility_hint = self._visible_timer_hint(ghost)
        elif state == "WANDER":
            seconds = self._frames_left(ghost, "unused", 300)
            next_hint = f"Next: CHASE on detection; PATROL in ~{seconds:.1f} s"
            visibility_hint = self._visible_timer_hint(ghost)
        elif state == "CHASE":
            next_hint = "Next: SEARCH if room changes; PATROL beyond 600 px"
            visibility_hint = self._visible_timer_hint(ghost)
        elif state == "SEARCH":
            seconds = self._frames_left(ghost, "unused", 180)
            next_hint = f"Next: CHASE on detection; PATROL in ~{seconds:.1f} s"
            visibility_hint = self._visible_timer_hint(ghost)
        elif state == "RETURN":
            seconds = self._frames_left(ghost, "unused", 300)
            next_hint = f"Next: PATROL at home or in ~{seconds:.1f} s"
            visibility_hint = self._visible_timer_hint(ghost)
        else:
            next_hint = "Next: no transition rule available"
            visibility_hint = "Visibility: no timer available"

        return (
            f"Reason: {self._last_transition_reason}",
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
        return f"Visibility: disappears in ~{remaining / FPS:.1f} s"

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
            self.overlay.draw(
                screen, self.snapshot(game), expanded=self.details_expanded
            )
