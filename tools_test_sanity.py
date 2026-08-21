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
    SANITY_GHOST_EVENT_DRAIN,
    SANITY_CANDLE_DRAIN_FACTOR,
)
from inventory_system import ItemType


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

    # Свеча (firelight) сильно снижает пассивный drain.
    game.spawn_lit_candle(game.player_rect.centerx, game.player_rect.centery)
    assert game.is_near_firelight()
    candle_before = game.player_sanity
    for _ in range(FPS):
        game.tick_sanity()
    expected_candle = candle_before - (
        SANITY_DARK_DRAIN_PER_SECOND * SANITY_CANDLE_DRAIN_FACTOR * SANITY_SETUP_DRAIN_FACTOR
    )
    assert approx(game.player_sanity, expected_candle), (game.player_sanity, expected_candle)

    # После setup и sanity < 50 охота разрешена.
    game.setup_phase_ticks = 0
    game.player_sanity = 49.0
    assert game.can_ghost_attempt_hunt()
    game.player_sanity = 50.0
    assert not game.can_ghost_attempt_hunt()

    # Burst drain.
    game.drain_sanity(10, reason="test")
    assert approx(game.player_sanity, 40.0, eps=0.001)

    # restore_sanity остаётся как общий API (предмета «таблетки» больше нет).
    restored = game.restore_sanity(35, reason="test")
    assert approx(restored, 75.0, eps=0.001)

    # Ghost event: появление призрака, контакт −10%, исчезновение без контакта — 0.
    from ghost import Ghost, Room

    game.player_sanity = 80.0
    game.ghost_manager.rooms = [Room(0, 0, 800, 600, 0)]
    sprite = pygame.Surface((40, 40), pygame.SRCALPHA)
    sprite.fill((200, 200, 220, 180))
    ghost = Ghost(100, 100, sprite, game.ghost_manager.rooms, home_room_id=0)
    game.ghost_manager.ghosts = [ghost]

    assert game.start_ghost_appearance_event()
    assert game.ghost_event_active
    assert ghost.in_appearance_event
    assert ghost.state.value != "invisible"

    # Ставим призрака прямо на игрока → контакт.
    ghost.rect.center = game.player_rect.center
    ghost.x, ghost.y = ghost.rect.x, ghost.rect.y
    game.tick_ghost_appearance_event()
    assert not game.ghost_event_active
    assert not ghost.in_appearance_event
    assert approx(game.player_sanity, 80.0 - SANITY_GHOST_EVENT_DRAIN, eps=0.001)

    # Таймаут без контакта — sanity не меняется.
    game.player_sanity = 80.0
    assert game.start_ghost_appearance_event()
    ghost.rect.center = (game.player_rect.centerx + 400, game.player_rect.centery + 400)
    ghost.x, ghost.y = ghost.rect.x, ghost.rect.y
    game.ghost_event_ticks_left = 1
    game.tick_ghost_appearance_event()
    assert not game.ghost_event_active
    assert approx(game.player_sanity, 80.0, eps=0.001)

    # Анонс конца setup: баннер + радио, без старого toast-only.
    game.setup_phase_ticks = 1
    game.tick_sanity()
    assert game.setup_phase_ticks == 0
    assert game.setup_complete_banner_until > 0
    assert game.radio_announcement

    # Свеча зарегистрирована; таблеток как предмета нет.
    assert ItemType.CANDLE in game.inventory_manager.item_counts
    assert not any(t.value == "таблетки" for t in ItemType)

    # Анти-фарм: повторная победа по тому же level_id — урезанная награда.
    from main_work import REPEAT_LEVEL_REWARD_FACTOR
    game.current_level_id = "level_1"
    game.rewarded_level_ids = set()
    money_before = game.player_money
    game.enter_win("тест")
    first_reward = game.win_report["reward"]
    assert first_reward > 0
    assert not game.win_report.get("reward_is_repeat")
    assert game.player_money == money_before + first_reward
    game.enter_win("тест")
    second_reward = game.win_report["reward"]
    expected_repeat = max(1, int(round(first_reward * REPEAT_LEVEL_REWARD_FACTOR)))
    assert second_reward == expected_repeat
    assert game.win_report.get("reward_is_repeat")
    assert game.player_money == money_before + first_reward + second_reward

    # Cursed hunt (wiki): ignores sanity/cooldown; grace 1s; +20s contract extension.
    from main_work import CURSED_HUNT_EXTENSION_SECONDS, CURSED_HUNT_GRACE_SECONDS
    game.setup_phase_ticks = 0
    game.player_sanity = 100.0
    game.hunt_cooldown_ticks = 999 * FPS
    game.contract_hunt_extension_seconds = 0
    assert not game.can_ghost_attempt_hunt()
    assert game.start_activity_hunt(cursed=True)
    assert game.hunt_is_cursed
    assert game.contract_hunt_extension_seconds == CURSED_HUNT_EXTENSION_SECONDS
    assert game.hunt_grace_ticks == CURSED_HUNT_GRACE_SECONDS * FPS
    base = int(game.difficulty_config()["hunt_duration_seconds"])
    assert game.hunt_active_ticks == (base + CURSED_HUNT_EXTENSION_SECONDS) * FPS

    print("sanity tests OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        pygame.quit()
