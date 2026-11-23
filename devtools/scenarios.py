"""Repeatable, session-only starting conditions for manual diagnosis."""

import random

import pygame

from constants import MAP_SCALE
from gamestate import GameState
from ghost import GhostState
from inventory_system import DroppedInventoryItem, ItemType


SCENARIOS = (
    ("collision_wall", "Стена · попробуйте пройти"),
    ("interaction_edge", "Граница · нажмите E"),
    ("two_objects", "Два предмета · кликните"),
    ("ghost_detection", "Обнаружение · ждите погоню"),
    ("event_completion", "Событие · угадайте вид в журнале"),
)


class ScenarioManager:
    def __init__(self):
        self.index = -1
        self.original_slot = None
        self.level_file = None
        self.original_random_state = None

    @property
    def current(self):
        return SCENARIOS[self.index] if self.index >= 0 else None

    def next(self, game):
        if self.index < 0:
            if game.state != GameState.GAME or not game.level_file:
                return False
            self.original_slot = game.selected_save_slot
            self.level_file = game.level_file
            self.original_random_state = random.getstate()
        self.index = (self.index + 1) % len(SCENARIOS)
        self.reset(game)
        return True

    def reset(self, game):
        if self.index < 0:
            return False
        # Save methods already guard on this slot. Keep it detached for the entire scenario.
        game.selected_save_slot = None
        random.seed(7300 + self.index)
        game.load_level(self.level_file)
        game.selected_save_slot = None
        game.set_state(GameState.GAME, reset_stack=True)
        game.journal_open = False
        game.inventory_manager.dropped_items.clear()
        game.inventory_manager.placed_items.clear()
        game.inventory_manager.placed_projector = None
        game.hunt_active_ticks = 0
        for key in game.keys_pressed:
            game.keys_pressed[key] = False
        game.player_hp = 5
        game.player_rect.topleft = (game.start_x, game.start_y)

        scenario_id = self.current[0]
        if scenario_id == "collision_wall" and game.walls:
            wall = next(
                (rect for rect, _ in game.walls if 0 < rect.left < game.world_width - game.player_rect.width and rect.height > game.player_rect.height),
                game.walls[0][0],
            )
            game.player_rect.midright = (wall.left - 1, wall.centery)
        elif scenario_id == "interaction_edge" and game.computer_rect:
            pad = int(48 * MAP_SCALE)
            zone = game.computer_rect.inflate(pad * 2, pad * 2)
            game.player_rect.midright = (zone.left, zone.centery)
        elif scenario_id == "two_objects":
            x, y = game.player_rect.center
            items = game.inventory_manager.dropped_items
            items.append(DroppedInventoryItem(x + 90, y, ItemType.EMF))
            items.append(DroppedInventoryItem(x + 105, y, ItemType.RADIO))
        elif scenario_id == "ghost_detection" and game.ghost_manager.ghosts:
            ghost = game.ghost_manager.ghosts[0]
            room_id = ghost.get_current_room_id()
            if 0 <= room_id < len(ghost.rooms):
                room = ghost.rooms[room_id]
                game.player_rect.center = room.get_center()
            ghost.state = GhostState.PATROL
            ghost.state_timer = 0
            ghost.is_frozen_after_appear = False
            ghost.is_playing_spawn = False
            ghost.invisibility_timer = 0
            if ghost.sprite:
                ghost.sprite.set_alpha(ghost.base_alpha)
        elif scenario_id == "event_completion" and game.ghost_manager.ghosts:
            ghost = game.ghost_manager.ghosts[0]
            ghost.state = GhostState.IDLE
            ghost.is_frozen_after_appear = False
            ghost.is_playing_spawn = False
            ghost.invisibility_timer = 0
            if ghost.sprite:
                ghost.sprite.set_alpha(ghost.base_alpha)

        game.update_camera()
        return True

    def exit(self, game):
        if self.index < 0:
            return False
        slot = self.original_slot
        self.index = -1
        if self.original_random_state is not None:
            random.setstate(self.original_random_state)
            self.original_random_state = None
        if slot is not None and game.load_game(slot):
            game.load_level_for_current_level()
            game.set_state(GameState.GAME, reset_stack=True)
        else:
            game.selected_save_slot = None
            game.set_state(GameState.MENU, reset_stack=True)
        return True
