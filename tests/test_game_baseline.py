"""Регрессионные проверки стабильного baseline игры.

Тесты работают без окна и не создают save.json: игровой объект получает
временное состояние прямо в памяти.
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
from ghost import GhostState
from inventory_system import DroppedInventoryItem, ItemType
from level_config import get_level_file_path, get_next_level_id, get_level_index
from main_work import Game
from project_paths import ACHIEVEMENTS_FILE, PROJECT_ROOT, SAVE_FILE


class GameBaselineTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def new_game(self):
        game = Game()
        game.set_state(GameState.GAME)
        return game

    def test_level_catalog_is_complete_and_loads(self):
        index = get_level_index()
        self.assertIn("level_1", index)
        self.assertIn("level_2", index)
        self.assertEqual(get_next_level_id("level_1"), "level_2")
        self.assertIsNone(get_next_level_id("level_2"))

        game = self.new_game()
        for level_id in ("level_1", "level_2"):
            self.assertTrue(get_level_file_path(level_id))
            game.load_level_by_id(level_id)
            self.assertTrue(game.level_data)
            self.assertGreater(len(game.walls), 0)
            self.assertGreater(len(game.ghost_manager.ghosts), 0)
            self.assertIsNotNone(game.player_rect)

    def test_runtime_resources_do_not_depend_on_working_directory(self):
        previous_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                os.chdir(temp_dir)
                game = self.new_game()
                game.load_level_by_id("level_1")
                game.draw()
            finally:
                os.chdir(previous_cwd)

        self.assertTrue(all(game.pin_images.values()))
        self.assertIsNotNone(game.cork_board_bg)
        self.assertIsNotNone(game.bg_level1)
        self.assertGreater(len(game.ghost_manager.ghosts), 0)
        fallback = game.progress_manager.achievement_provider.fallback_provider
        self.assertEqual(os.path.abspath(fallback.csv_path), str(ACHIEVEMENTS_FILE))
        self.assertEqual(os.path.abspath(game.save_file), str(SAVE_FILE))
        self.assertEqual(PROJECT_ROOT, ACHIEVEMENTS_FILE.parent.parent)

    def test_headless_gameplay_frames_are_stable(self):
        game = self.new_game()
        game.load_level_by_id("level_1")
        for _ in range(30):
            game.draw()
        self.assertEqual(game.state, GameState.GAME)
        self.assertGreater(len(game.ghost_manager.ghosts), 0)

    def test_inventory_items_have_safe_use_paths(self):
        game = self.new_game()
        game.load_level_by_id("level_1")
        manager = game.inventory_manager

        manager.item_counts[ItemType.FLASHLIGHT] = 1
        game.inventory[ItemType.FLASHLIGHT.value] = True
        self.assertTrue(manager.use_item(ItemType.FLASHLIGHT))
        self.assertTrue(game.flashlight_on)

        manager.item_counts[ItemType.UV_FLASHLIGHT] = 1
        self.assertTrue(manager.use_item(ItemType.UV_FLASHLIGHT))
        self.assertTrue(game.uv_mode)

        manager.item_counts[ItemType.EMF] = 1
        self.assertTrue(manager.use_item(ItemType.EMF))

        manager.item_counts[ItemType.THERMOMETER] = 1
        self.assertTrue(manager.use_item(ItemType.THERMOMETER))

        manager.item_counts[ItemType.CANDLE] = 1
        candle_before = manager.get_count(ItemType.CANDLE)
        self.assertTrue(manager.use_item(ItemType.CANDLE))
        self.assertEqual(manager.get_count(ItemType.CANDLE), candle_before - 1)
        self.assertTrue(game.lit_candles)

        manager.item_counts[ItemType.BLOOD] = 1
        game.player_hp = 2
        self.assertTrue(manager.use_item(ItemType.BLOOD))
        self.assertGreater(game.player_hp, 2)

        manager.item_counts[ItemType.RADIO] = 1
        radio_before = manager.get_count(ItemType.RADIO)
        self.assertTrue(manager.use_item(ItemType.RADIO))
        self.assertEqual(manager.get_count(ItemType.RADIO), radio_before - 1)

        manager.item_counts[ItemType.PROJECTOR] = 1
        self.assertTrue(manager.use_item(ItemType.PROJECTOR))
        self.assertEqual(manager.active_hand_item, ItemType.PROJECTOR)

    def test_projector_can_be_placed_and_powered(self):
        game = self.new_game()
        game.load_level_by_id("level_1")
        manager = game.inventory_manager
        manager.item_counts[ItemType.PROJECTOR] = 1
        manager.item_counts[ItemType.BATTERY] = 1
        manager.start_placement(ItemType.PROJECTOR)
        valid_cells = manager._get_valid_placement_cells()
        self.assertTrue(valid_cells)
        self.assertTrue(manager.place_item(*valid_cells[0]))
        self.assertIsNotNone(manager.placed_projector)
        manager.active_hand_item = ItemType.BATTERY
        self.assertTrue(manager.try_power_projector(manager.placed_projector.x, manager.placed_projector.y))
        self.assertTrue(manager.placed_projector.powered)
        self.assertTrue(manager.get_projector_zones())

    def test_reusing_projector_moves_existing_projector_without_losing_charge(self):
        game = self.new_game()
        game.load_level_by_id("level_1")
        manager = game.inventory_manager
        game.inventory[ItemType.PROJECTOR.value] = True
        manager.start_placement(ItemType.PROJECTOR)
        first_cell = manager._get_valid_placement_cells()[0]
        self.assertTrue(manager.place_item(*first_cell))
        projector = manager.placed_projector
        projector.powered = True
        projector.battery_remaining = 1234

        self.assertTrue(manager.use_item(ItemType.PROJECTOR))
        self.assertIs(manager.moving_projector, projector)
        second_cell = manager._get_valid_placement_cells()[0]
        self.assertTrue(manager.place_item(*second_cell))

        self.assertIs(manager.placed_projector, projector)
        self.assertTrue(projector.powered)
        self.assertEqual(projector.battery_remaining, 1234)

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = os.path.join(temp_dir, "save.json")
            game = self.new_game()
            game.save_file = save_path
            game.player_level = 2
            game.current_level_id = "level_2"
            game.player_hp = 3
            game.player_money = 77
            game.inventory_manager.item_counts[ItemType.BATTERY] = 2
            game.save_game(1)

            restored = self.new_game()
            restored.save_file = save_path
            restored.saves = restored.load_saves()
            self.assertTrue(restored.load_game(1))
            restored.load_level_for_current_level()
            self.assertEqual(restored.player_level, 2)
            self.assertEqual(restored.current_level_id, "level_2")
            self.assertEqual(restored.player_hp, 3)
            self.assertEqual(restored.player_money, 77)
            self.assertEqual(restored.inventory_manager.get_count(ItemType.BATTERY), 2)

    def test_corrupt_save_falls_back_to_empty_slots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = os.path.join(temp_dir, "save.json")
            with open(save_path, "w", encoding="utf-8") as save_file:
                save_file.write("{not valid json")
            game = self.new_game()
            game.save_file = save_path
            self.assertEqual(game.load_saves(), {"slot1": None, "slot2": None, "slot3": None})

    def test_runtime_state_round_trip_in_memory(self):
        game = self.new_game()
        game.load_level_by_id("level_1")
        manager = game.inventory_manager
        manager.item_counts[ItemType.BATTERY] = 2
        manager.item_counts[ItemType.SALT] = 1
        manager.placed_items.clear()
        manager.dropped_items = [DroppedInventoryItem(120, 140, ItemType.SALT)]
        inventory_state = manager.serialize_runtime_state()
        ghost_state = game.ghost_manager.serialize_runtime_state()

        manager.reset_runtime_state(clear_counts=True)
        self.assertEqual(manager.get_count(ItemType.BATTERY), 0)
        manager.restore_runtime_state(inventory_state)
        game.ghost_manager.restore_runtime_state(ghost_state)
        self.assertEqual(len(manager.dropped_items), 1)
        self.assertEqual(manager.dropped_items[0].item_type, ItemType.SALT)
        self.assertEqual(len(game.ghost_manager.ghosts), 1)

    def test_picking_up_item_autosaves_after_removing_floor_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            game = self.new_game()
            game.save_file = os.path.join(temp_dir, "save.json")
            game.saves = {"slot1": None, "slot2": None, "slot3": None}
            game.selected_save_slot = 1
            manager = game.inventory_manager
            manager.dropped_items = [DroppedInventoryItem(120, 140, ItemType.SALT)]

            self.assertTrue(manager.pick_dropped_item_at(120, 140))

            saved = game.load_saves()["slot1"]
            self.assertEqual(saved["item_counts"]["SALT"], 1)
            self.assertEqual(saved["inventory_runtime"]["dropped_items"], [])

    def test_dropping_uv_flashlight_disables_uv_mode(self):
        game = self.new_game()
        game.inventory[ItemType.UV_FLASHLIGHT.value] = True
        game.uv_mode = True
        uv_index = game.inventory_manager.visible_inventory_names().index(ItemType.UV_FLASHLIGHT.value)

        self.assertTrue(game.inventory_manager.drop_item_by_index(uv_index))

        self.assertFalse(game.inventory[ItemType.UV_FLASHLIGHT.value])
        self.assertFalse(game.uv_mode)

    def test_level_transition_keeps_campaign_consistent(self):
        game = self.new_game()
        game.current_level_id = "level_1"
        game.player_level = 1
        game.win_next_level_id = "level_2"
        self.assertTrue(game.advance_to_next_level())
        self.assertEqual(game.current_level_id, "level_2")
        self.assertEqual(game.player_level, 2)
        self.assertEqual(game.state, GameState.GAME)
        self.assertEqual(game.setup_phase_ticks, game.difficulty_config()["setup_phase_seconds"] * 60)

    def test_ghost_state_machine_has_known_states(self):
        game = self.new_game()
        game.load_level_by_id("level_1")
        ghost = game.ghost_manager.ghosts[0]
        self.assertIn(ghost.state, set(GhostState))
        ghost.update_state(game.player_rect, game.walls)
        self.assertIn(ghost.state, set(GhostState))


if __name__ == "__main__":
    unittest.main()
