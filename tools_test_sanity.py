"""Быстрые проверки формул sanity без открытия окна игры."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.display.set_mode((1, 1))

from constants import FPS
from main_work import (
    Game,
    SANITY_DARK_DRAIN_PER_SECOND,
    SANITY_SETUP_DRAIN_FACTOR,
    SANITY_SETUP_FLOOR,
)


def approx(a, b, eps=0.08):
    return abs(a - b) <= eps


def main():
    game = Game()
    game.difficulty_index = 1  # нормальная: multiplier 1.0, setup 60s
    game.inventory["фонарик"] = False
    game.flashlight_on = False
    game.reset_sanity(start_setup=True)

    assert game.player_sanity == 100.0
    assert game.is_setup_phase()
    assert not game.can_ghost_attempt_hunt()

    # 1 секунда в темноте во время setup.
    for _ in range(FPS):
        game.tick_sanity()
    expected = 100.0 - SANITY_DARK_DRAIN_PER_SECOND * 1.0 * SANITY_SETUP_DRAIN_FACTOR
    assert approx(game.player_sanity, expected), (game.player_sanity, expected)
    assert game.player_sanity >= SANITY_SETUP_FLOOR

    # Как в Phasmophobia: включённый фонарик НЕ останавливает пассивный drain.
    game.inventory["фонарик"] = True
    game.flashlight_on = True
    lit_before = game.player_sanity
    for _ in range(FPS):
        game.tick_sanity()
    expected_with_light = lit_before - SANITY_DARK_DRAIN_PER_SECOND * 1.0 * SANITY_SETUP_DRAIN_FACTOR
    assert approx(game.player_sanity, expected_with_light), (game.player_sanity, expected_with_light)
    assert game.player_sanity < lit_before

    # После setup и sanity < 50 охота разрешена.
    game.setup_phase_ticks = 0
    game.player_sanity = 49.0
    assert game.can_ghost_attempt_hunt()
    game.player_sanity = 50.0
    assert not game.can_ghost_attempt_hunt()

    # Burst drain.
    game.drain_sanity(10, reason="test")
    assert approx(game.player_sanity, 40.0, eps=0.001)

    print("sanity tests OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        pygame.quit()
