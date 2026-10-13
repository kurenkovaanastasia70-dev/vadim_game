"""GUI smoke test for the stable game baseline.

The script opens a real SDL window, drives the same Pygame event handlers as
the player, renders each screen, and stores screenshots in the OS temp folder.
It never touches the repository save.json.
"""

import os
import tempfile
import time

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from gamestate import GameState
from handlers import handle_event
from main_work import Game


def click(game, position):
    pygame.event.post(
        pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {"pos": position, "button": 1},
        )
    )
    handle_event(game)


def key(game, key_code, event_type=pygame.KEYDOWN):
    pygame.event.post(pygame.event.Event(event_type, {"key": key_code}))
    handle_event(game)


def main():
    pygame.init()
    game = Game()
    screenshot_dir = os.path.join(tempfile.gettempdir(), "vadim_game_gui_smoke")
    os.makedirs(screenshot_dir, exist_ok=True)
    game.save_file = os.path.join(screenshot_dir, "gui_save.json")
    game.saves = {"slot1": None, "slot2": None, "slot3": None}
    game.selected_save_slot = None
    game.fullscreen = False
    game.apply_display_mode()

    screenshots = []

    def render(name):
        game.draw()
        pygame.time.wait(250)
        path = os.path.join(screenshot_dir, f"{name}.png")
        pygame.image.save(game.screen, path)
        screenshots.append(path)

    render("01_menu")
    click(game, game.menu_buttons[0].rect.center)
    assert game.state == GameState.SAVES, game.state
    render("02_saves")

    click(game, game.saves_new_button.rect.center)
    assert game.state == GameState.DIFF, game.state
    render("03_difficulty")

    click(game, game.difficulty_buttons[1].rect.center)
    assert game.state == GameState.BOOST_PICK, game.state
    render("04_boost_pick")

    click(game, game.boost_skip_button.rect.center)
    assert game.state == GameState.GAME, game.state
    render("05_game")

    start_position = game.player_rect.center
    key(game, pygame.K_d)
    for _ in range(8):
        game.draw()
        pygame.time.wait(30)
    key(game, pygame.K_d, pygame.KEYUP)
    assert game.player_rect.center != start_position
    render("06_game_after_movement")

    key(game, pygame.K_j)
    assert game.journal_open
    render("07_journal")
    key(game, pygame.K_ESCAPE)
    assert not game.journal_open
    click(game, game.game_buttons[0].rect.center)
    assert game.show_save_prompt
    render("08_save_prompt")
    click(game, game.save_prompt_buttons[1].rect.center)
    assert game.state == GameState.MENU
    render("09_menu_after_back")

    game.running = False
    pygame.quit()
    print("GUI smoke test OK")
    for path in screenshots:
        print(path)


if __name__ == "__main__":
    main()
