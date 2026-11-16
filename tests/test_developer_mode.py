import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from devtools.developer_mode import DeveloperMode
from ghost import GhostState


class ClockStub:
    def get_fps(self):
        return 59.5


class DeveloperModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    def test_f3_toggles_repeatedly_without_consuming_other_keys(self):
        mode = DeveloperMode()
        f3_event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_F3})

        for press_number in range(1, 11):
            mode.handle_event(f3_event)
            self.assertEqual(mode.enabled, press_number % 2 == 1)

        other_event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_w})
        mode.handle_event(other_event)
        self.assertFalse(mode.enabled)

    def test_snapshot_uses_live_game_values(self):
        game = SimpleNamespace(
            clock=ClockStub(),
            player_rect=pygame.Rect(100, 200, 40, 60),
            ghost_manager=SimpleNamespace(
                ghosts=[SimpleNamespace(state=GhostState.CHASE)]
            ),
            inventory_manager=SimpleNamespace(
                placed_items=[object(), object()],
                dropped_items=[object()],
            ),
        )

        snapshot = DeveloperMode().snapshot(game)

        self.assertEqual(snapshot.fps, 59.5)
        self.assertEqual(snapshot.player_position, (120, 230))
        self.assertEqual(snapshot.active_objects, 4)
        self.assertEqual(snapshot.enemy_state, "CHASE")

    def test_missing_enemy_is_reported(self):
        game = SimpleNamespace(
            clock=ClockStub(),
            player_rect=pygame.Rect(0, 0, 20, 20),
            ghost_manager=SimpleNamespace(ghosts=[]),
            inventory_manager=SimpleNamespace(placed_items=[], dropped_items=[]),
        )

        self.assertEqual(DeveloperMode().snapshot(game).enemy_state, "NONE")


if __name__ == "__main__":
    unittest.main()
