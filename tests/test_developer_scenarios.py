"""Stage 2/3 integration checks against the real game objects."""

import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from gamestate import GameState
from ghost import GhostState
from main_work import Game


class DeveloperScenarioTests(unittest.TestCase):
    def setUp(self):
        self.game = Game()
        self.game.load_level_by_id("level_1")
        self.game.set_state(GameState.GAME)
        self.mode = self.game.developer_mode
        self.mode.enabled = True

    def test_five_scenarios_reset_to_the_same_start(self):
        with tempfile.TemporaryDirectory() as directory:
            save_file = os.path.join(directory, "save.json")
            self.game.save_file = save_file
            self.game.selected_save_slot = 1
            for index in range(5):
                self.assertTrue(self.mode.scenarios.select(self.game, index))
                self.assertEqual(self.mode.scenarios.index, index)
                first = (
                    self.game.player_rect.copy(),
                    [(ghost.rect.copy(), ghost.state) for ghost in self.game.ghost_manager.ghosts],
                    [(item.rect.copy(), item.item_type) for item in self.game.inventory_manager.dropped_items],
                )
                self.game.player_rect.move_ip(30, 30)
                self.assertTrue(self.mode.scenarios.reset(self.game))
                second = (
                    self.game.player_rect.copy(),
                    [(ghost.rect.copy(), ghost.state) for ghost in self.game.ghost_manager.ghosts],
                    [(item.rect.copy(), item.item_type) for item in self.game.inventory_manager.dropped_items],
                )
                self.assertEqual(first, second)
                self.assertIsNone(self.game.selected_save_slot)
            self.assertEqual(self.game.ghost_manager.ghosts[0].state, GhostState.IDLE)
            self.game.save_game(1)
            self.assertFalse(os.path.exists(save_file))

    def test_layers_draw_from_live_geometry(self):
        self.mode.scenarios.select(self.game, 0)
        screen = pygame.Surface((1024, 768))
        self.mode.draw(screen, self.game)
        self.mode.renderer.hitboxes = False
        self.mode.renderer.zones = False
        self.mode.renderer.selection = False
        self.mode.draw(screen, self.game)
        self.assertTrue(self.mode.scenarios.exit(self.game))
        self.assertEqual(self.game.state, GameState.MENU)

    def test_scenarios_check_real_game_rules(self):
        for index in range(5):
            with self.subTest(scenario=index):
                self.assertTrue(self.mode.scenarios.select(self.game, index))
                result = self.mode.scenarios.check(self.game)
                self.assertTrue(result[0], result[1])
                self.assertEqual(self.game.state, GameState.GAME)

    def test_picker_supports_direct_choice(self):
        screen = pygame.Surface((1024, 768))
        self.assertTrue(self.mode.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_F4}), screen, self.game))
        self.assertTrue(self.mode.scenario_picker_open)
        self.assertTrue(self.game.is_gameplay_paused())
        self.assertTrue(self.mode.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_3}), screen, self.game))
        self.assertEqual(self.mode.scenarios.current[0], "two_objects")
        self.assertFalse(self.mode.scenario_picker_open)


if __name__ == "__main__":
    unittest.main()
