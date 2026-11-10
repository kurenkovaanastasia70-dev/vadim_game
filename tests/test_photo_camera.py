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
from photo_camera import (
    GHOST_DUPLICATE_REWARD,
    GHOST_UNIQUE_REWARD,
    PHOTO_JOURNAL_LIMIT,
    capture_ghost_photo,
    create_media_record,
    media_base_reward,
    photo_zone,
)


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
        money_before = game.player_money

        handle_game_events(game, pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_c}))

        self.assertEqual(len(game.photo_album), 1)
        self.assertIn(game.photo_album[0]["rarity"], (1, 2, 3))
        self.assertTrue(game.photo_album[0]["unique"])
        self.assertEqual(game.photo_album[0]["base_reward"], GHOST_UNIQUE_REWARD)
        self.assertEqual(game.player_money, money_before + GHOST_UNIQUE_REWARD * 2)

    def test_first_ghost_photo_is_unique_and_repeats_are_duplicates(self):
        player = pygame.Rect(100, 100, 40, 40)
        ghost = DummyGhost((145, 110, 20, 20))
        capture = capture_ghost_photo(player, "right", [ghost], size=140)

        unique = create_media_record(capture, [])
        duplicate = create_media_record(capture, [unique])

        self.assertTrue(unique["unique"])
        self.assertEqual(unique["base_reward"], GHOST_UNIQUE_REWARD)
        self.assertFalse(duplicate["unique"])
        self.assertEqual(duplicate["base_reward"], GHOST_DUPLICATE_REWARD)

    def test_media_reward_uses_difficulty_multiplier(self):
        game = Game()
        game.difficulty_index = 2
        game.photo_album = [
            {"subject": "ghost", "rarity": 3, "unique": True, "base_reward": GHOST_UNIQUE_REWARD},
            {"subject": "ghost", "rarity": 2, "unique": False, "base_reward": GHOST_DUPLICATE_REWARD},
        ]

        photo_reward = game.get_photo_reward_breakdown()
        level_reward = game.get_level_complete_reward_breakdown()

        self.assertEqual(media_base_reward(game.photo_album), 18)
        self.assertEqual(photo_reward["multiplier"], 3)
        self.assertEqual(photo_reward["total"], 54)
        self.assertEqual(level_reward["photo_reward"], 54)
        self.assertEqual(
            level_reward["total"],
            level_reward["base"] + level_reward["difficulty_bonus"] + level_reward["evidence_bonus"],
        )

    def test_only_five_valid_photos_fill_the_journal(self):
        game = Game()
        game.set_state(GameState.GAME)
        game.load_level_by_id("level_1")
        game.player_direction = "right"
        ghost = game.ghost_manager.ghosts[0]
        ghost.state = GhostState.IDLE
        ghost.rect.center = (game.player_rect.right + 45, game.player_rect.centery)
        if ghost.sprite:
            ghost.sprite.set_alpha(255)
        money_before = game.player_money

        for _ in range(PHOTO_JOURNAL_LIMIT + 2):
            game.camera_cooldown_until = 0
            game.take_photo()

        self.assertEqual(len(game.photo_album), PHOTO_JOURNAL_LIMIT)
        self.assertEqual(sum(1 for row in game.photo_album if row["unique"]), 1)
        expected = (GHOST_UNIQUE_REWARD + GHOST_DUPLICATE_REWARD * 4) * 2
        self.assertEqual(game.player_money, money_before + expected)


if __name__ == "__main__":
    unittest.main()
