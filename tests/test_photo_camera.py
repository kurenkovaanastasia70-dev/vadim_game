import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.display.set_mode((1, 1))

from gamestate import GameState
from ghost import GhostState
from handlers import handle_game_events
from main_work import Game
from photo_camera import capture_ghost_photo, photo_zone


class DummyGhost:
    def __init__(self, rect, state=GhostState.IDLE):
        self.rect = pygame.Rect(rect)
        self.state = state
        self.sprite = pygame.Surface((10, 10), pygame.SRCALPHA)


class PhotoCameraTests(unittest.TestCase):
    def test_photo_zone_is_square_in_front_of_player(self):
        player = pygame.Rect(100, 100, 40, 40)

        right = photo_zone(player, "right", size=120)
        up = photo_zone(player, "up", size=120)

        self.assertEqual(right.size, (120, 120))
        self.assertEqual(right.midleft, player.midright)
        self.assertEqual(up.midbottom, player.midtop)

    def test_visible_ghost_gets_rarity_from_one_to_three(self):
        player = pygame.Rect(100, 100, 40, 40)
        close = DummyGhost((145, 110, 20, 20))
        far_corner = DummyGhost((235, 155, 20, 20))

        close_photo = capture_ghost_photo(player, "right", [close], size=140)
        far_photo = capture_ghost_photo(player, "right", [far_corner], size=140)

        self.assertTrue(close_photo.captured)
        self.assertEqual(close_photo.rarity, 3)
        self.assertTrue(far_photo.captured)
        self.assertEqual(far_photo.rarity, 1)

    def test_invisible_ghost_is_not_captured(self):
        player = pygame.Rect(100, 100, 40, 40)
        ghost = DummyGhost((145, 110, 20, 20), state=GhostState.INVISIBLE)

        photo = capture_ghost_photo(player, "right", [ghost], size=140)

        self.assertFalse(photo.captured)
        self.assertEqual(photo.rarity, 0)

    def test_camera_is_always_available_on_c_key(self):
        game = Game()
        game.set_state(GameState.GAME)
        game.load_level_by_id("level_1")
        game.player_direction = "right"
        ghost = game.ghost_manager.ghosts[0]
        ghost.state = GhostState.IDLE
        ghost.rect.center = (game.player_rect.right + 45, game.player_rect.centery)
        if ghost.sprite:
            ghost.sprite.set_alpha(255)

        handle_game_events(game, pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_c}))

        self.assertEqual(len(game.photo_album), 1)
        self.assertIn(game.photo_album[0]["rarity"], (1, 2, 3))


if __name__ == "__main__":
    unittest.main()
