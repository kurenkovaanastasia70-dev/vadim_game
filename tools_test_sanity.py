"""Быстрые проверки формул sanity без открытия окна игры."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.display.set_mode((1, 1))

from constants import FPS
from gamestate import GameState
from main_work import (
    Game,
    SANITY_DARK_DRAIN_PER_SECOND,
    SANITY_SETUP_DRAIN_FACTOR,
    SANITY_SETUP_FLOOR,
    SANITY_CANDLE_DRAIN_FACTOR,
)
from inventory_system import ItemType, get_max_carried_items


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

    # Анонс конца setup: баннер + радио, без старого toast-only.
    game.setup_phase_ticks = 1
    game.tick_sanity()
    assert game.setup_phase_ticks == 0
    assert game.setup_complete_banner_until > 0
    assert game.radio_announcement

    # Свеча зарегистрирована; таблеток как предмета нет.
    assert ItemType.CANDLE in game.inventory_manager.item_counts
    assert not any(t.value == "таблетки" for t in ItemType)

    # Задания сессии → player_money; каталог по уровню.
    game.current_level_id = "level_1"
    game.player_money = 10
    game.tasks = game.progress_manager.new_tasks_for_level("level_1")
    assert any(t["id"] == "l1_buy_1" for t in game.tasks)
    game.progress_event("buy_item", 1)
    assert game.player_money == 10 + 25

    # Глобальный трек — только ачивка, без global_money.
    game.achievements_table = game.progress_manager.new_state()[1]
    radio_ach = next(a for a in game.achievements_table if a["event_key"] == "radio_answer")
    radio_ach["progress"] = radio_ach["target"] - 1
    before = game.global_money
    game.progress_event("radio_answer", 1)
    assert radio_ach["unlocked"]
    assert game.global_money == before
    assert hasattr(game, "achievements_panel_open")

    game.current_level_id = "level_1"
    game.player_level = 1
    game.win_next_level_id = None
    game.open_boost_pick(purpose="start")
    assert game.state == GameState.BOOST_PICK
    game.selected_boost_id = "starter_candle"
    money_before = game.player_money
    assert game.equip_selected_boost_and_advance()
    assert game.state == GameState.GAME
    assert game.current_level_id == "level_1"
    assert game.equipped_boost == "starter_candle"
    assert game.player_money == money_before
    assert game.inventory_manager.get_count(ItemType.CANDLE) >= 1

    # Между уровнями: один буст + Экипировать.
    game.win_next_level_id = "level_2"
    game.open_boost_pick()
    assert game.state == GameState.BOOST_PICK
    game.selected_boost_id = None
    assert game.equip_selected_boost_and_advance() is False
    game.selected_boost_id = "extra_slot"
    money_before = game.player_money
    assert game.equip_selected_boost_and_advance()
    assert game.equipped_boost == "extra_slot"
    assert get_max_carried_items(game) == 4
    assert game.player_money == money_before
    assert game.current_level_id == "level_2"

    game.player_level = 1
    game.current_level_id = "level_1"
    game.win_next_level_id = "level_2"
    game.selected_boost_id = "budget_boost"
    money_before = game.player_money
    assert game.equip_selected_boost_and_advance()
    assert game.equipped_boost == "budget_boost"
    assert game.player_money == money_before + 25

    game.equipped_boost = "starter_candle"
    game.reset_inventory()
    game.apply_equipped_boost_inventory()
    assert game.inventory_manager.get_count(ItemType.CANDLE) >= 1

    print("sanity tests OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        pygame.quit()
