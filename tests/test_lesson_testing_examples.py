"""Учебные примеры разных видов тестов для урока.

Каждый тест намеренно короткий и показывает один сценарий:
unit, integration, functional, smoke и regression.
"""

import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.display.set_mode((1, 1))

from gamestate import GameState
from level_config import get_next_level_id
from main_work import Game


class LessonTestingExamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Тесты не должны зависеть от порядка запуска других test-модулей.
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def new_game(self):
        game = Game()
        game.set_state(GameState.GAME)
        return game

    def test_unit_level_catalog_rule(self):
        """Unit: проверяем одно небольшое правило без создания игры."""
        self.assertEqual(get_next_level_id("level_1"), "level_2")
        self.assertIsNone(get_next_level_id("level_2"))

    def test_integration_save_and_load(self):
        """Integration: Game взаимодействует с JSON-сохранением."""
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = os.path.join(temp_dir, "save.json")
            game = self.new_game()
            game.save_file = save_path
            game.player_money = 77
            game.save_game(1)

            restored = self.new_game()
            restored.save_file = save_path
            restored.saves = restored.load_saves()

            self.assertTrue(restored.load_game(1))
            self.assertEqual(restored.player_money, 77)

    def test_functional_level_transition(self):
        """Functional: проверяем пользовательский сценарий перехода."""
        game = self.new_game()
        game.current_level_id = "level_1"
        game.player_level = 1
        game.win_next_level_id = "level_2"

        self.assertTrue(game.advance_to_next_level())
        self.assertEqual(game.current_level_id, "level_2")
        self.assertEqual(game.player_level, 2)
        self.assertEqual(game.state, GameState.GAME)

    def test_smoke_level_can_start_and_render(self):
        """Smoke: главный игровой сценарий запускается и рисует кадры."""
        game = self.new_game()
        game.load_level_by_id("level_1")

        for _ in range(3):
            game.draw()

        self.assertGreater(len(game.walls), 0)
        self.assertGreater(len(game.ghost_manager.ghosts), 0)
        self.assertIsNotNone(game.player_rect)

    def test_regression_corrupt_save_is_safe(self):
        """Regression: повреждённое сохранение не ломает запуск игры."""
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = os.path.join(temp_dir, "save.json")
            with open(save_path, "w", encoding="utf-8") as save_file:
                save_file.write("{not valid json")

            game = self.new_game()
            game.save_file = save_path

            self.assertEqual(
                game.load_saves(),
                {"slot1": None, "slot2": None, "slot3": None},
            )


if __name__ == "__main__":
    unittest.main()
