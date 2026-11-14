import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.display.set_mode((1, 1))

import assets
import draws
from gamestate import GameState
from ghost import (
    EMF_EMISSION_TICKS,
    GhostManager,
    resolve_emf_level,
)
from inventory_system import ItemType
from main_work import Game


class EmfReaderTests(unittest.TestCase):
    def test_all_five_player_sprites_load(self):
        images = assets.load_emf_reader_images()

        self.assertEqual(set(images), {1, 2, 3, 4, 5})
        self.assertTrue(all(image.get_width() > 0 for image in images.values()))

    def test_level_five_only_replaces_two_or_three_for_evidence_ghost(self):
        self.assertEqual(resolve_emf_level(2, True, roll=0.10), 5)
        self.assertEqual(resolve_emf_level(3, True, roll=0.32), 5)
        self.assertEqual(resolve_emf_level(2, True, roll=0.50), 2)
        self.assertEqual(resolve_emf_level(3, False, roll=0.10), 3)
        self.assertEqual(resolve_emf_level(4, True, roll=0.10), 4)

    def test_reader_returns_nearby_hotspot_and_ignores_distant_one(self):
        manager = GhostManager.__new__(GhostManager)
        manager.ghosts = []
        manager.emf_hotspot = {"x": 120, "y": 120, "level": 4, "ttl": EMF_EMISSION_TICKS}
        player = pygame.Rect(100, 100, 40, 40)

        near_level, _ = manager.scan_emf(player, radius=220)
        far_level, _ = manager.scan_emf(player.move(1000, 1000), radius=220)

        self.assertEqual(near_level, 4)
        self.assertEqual(far_level, 1)

    def test_e_key_behavior_is_a_clear_on_off_toggle(self):
        game = Game()
        game.set_state(GameState.GAME)
        game.inventory[ItemType.EMF.value] = True

        self.assertTrue(game.inventory_manager.use_item(ItemType.EMF))
        self.assertTrue(game.emf_enabled)
        self.assertEqual(game.inventory_manager.active_hand_item, ItemType.EMF)
        self.assertTrue(game.emf_tutorial_shown)
        self.assertIn("ПКМ", game.info_message)

        game.info_message = None
        game.info_until = 0

        game.ghost_manager.emf_hotspot = {
            "x": game.player_rect.centerx,
            "y": game.player_rect.centery,
            "level": 5,
            "ttl": EMF_EMISSION_TICKS,
        }
        game.update_emf_reader()

        self.assertEqual(game.emf_level, 5)
        self.assertIn("улика", game.emf_text.lower())
        self.assertIsNone(game.info_message)

        game.screen.fill((0, 0, 0))
        draws._draw_emf_reader(game)
        sw, sh = game.screen.get_size()
        panel_top = max(116, sh // 2 - 90)
        self.assertEqual(game.screen.get_at((sw - 140, panel_top))[:3], (245, 65, 65))

        self.assertTrue(game.inventory_manager.use_item(ItemType.EMF))
        self.assertFalse(game.emf_enabled)
        self.assertEqual(game.emf_level, 1)
        self.assertIsNone(game.info_message)

        self.assertTrue(game.inventory_manager.use_item(ItemType.EMF))
        self.assertTrue(game.emf_enabled)
        self.assertIsNone(game.info_message)


if __name__ == "__main__":
    unittest.main()
