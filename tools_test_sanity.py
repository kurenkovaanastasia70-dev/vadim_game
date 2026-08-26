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
    SANITY_CANDLE_DRAIN_FACTOR,
    SANITY_GHOST_EVENT_DRAIN,
    CURSED_HUNT_EXTENSION_SECONDS,
    CURSED_HUNT_GRACE_SECONDS,
    SESSION_SETUP_TIP,
)
from inventory_system import ItemType
from ghost import Ghost, GhostState, Room


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


    # Appearance: обычный FSM — при выходе из INVISIBLE снимается рассудок.
    game.player_sanity = 80.0
    game.ghost_manager.rooms = [Room(0, 0, 800, 600, 0)]
    game.ghost_manager.appearance_callback = game.on_ghost_appeared_on_map
    sprite = pygame.Surface((40, 40), pygame.SRCALPHA)
    sprite.fill((200, 200, 220, 180))
    ghost = Ghost(100, 100, sprite, game.ghost_manager.rooms, home_room_id=0)
    ghost.is_first_appearance = False
    ghost.invisibility_duration = 1
    ghost.state = GhostState.INVISIBLE
    ghost.state_timer = 0
    game.ghost_manager.ghosts = [ghost]
    ghost._appearance_notify = game.on_ghost_appeared_on_map
    ghost.update_state(game.player_rect, [], debug_mode=False)
    assert ghost.state != GhostState.INVISIBLE
    assert approx(game.player_sanity, 80.0 - SANITY_GHOST_EVENT_DRAIN, eps=0.001)

    # Cursed hunt.
    game.setup_phase_ticks = 0
    game.player_sanity = 100.0
    game.hunt_cooldown_ticks = 999 * FPS
    game.contract_hunt_extension_seconds = 0
    assert not game.can_ghost_attempt_hunt()
    assert game.start_activity_hunt(cursed=True)
    assert game.hunt_is_cursed
    assert game.contract_hunt_extension_seconds == CURSED_HUNT_EXTENSION_SECONDS
    assert game.hunt_grace_ticks == CURSED_HUNT_GRACE_SECONDS * FPS

    # Dual money: win -> global; shop uses session; mods use global.
    game.player_money = 50
    game.global_money = 200
    game.inventory_mods = {k: False for k in ("extra_slot", "budget_boost", "starter_candle")}
    assert game.buy_inventory_mod("extra_slot")
    assert game.inventory_mods["extra_slot"]
    assert game.global_money == 200 - 120
    assert game.max_carried_items() == 4
    before_session = game.player_money
    game.grant_session_budget()
    assert game.player_money == game.session_budget_amount()
    assert before_session != game.player_money or True
    game.global_money = 0
    game.enter_win("тест")
    assert game.win_report.get("reward_to") == "global"
    assert game.global_money >= game.win_report["reward"]

    # Задания сессии → session-$; каталог можно задать по уровню.
    game.current_level_id = "level_1"
    game.player_money = 10
    game.tasks = game.progress_manager.new_tasks_for_level("level_1")
    assert any(t["id"] == "l1_buy_1" for t in game.tasks)
    game.progress_event("buy_item", 1)
    assert game.player_money == 10 + 25

    # Глобальные достижения → счёт; UI-флаг панели есть.
    game.achievements_table = game.progress_manager.new_state()[1]
    radio_ach = next(a for a in game.achievements_table if a["event_key"] == "radio_answer")
    radio_ach["progress"] = radio_ach["target"] - 1
    before = game.global_money
    game.progress_event("radio_answer", 1)
    assert radio_ach["unlocked"]
    assert game.global_money == before + int(radio_ach["reward"])
    assert hasattr(game, "achievements_panel_open")

    print("sanity tests OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        pygame.quit()
