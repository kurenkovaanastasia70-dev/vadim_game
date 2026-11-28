"""Repeatable, session-only starting conditions for manual diagnosis."""

import random

import pygame

import mechanics
from constants import MAP_SCALE
from gamestate import GameState
from ghost import GhostState
from inventory_system import DroppedInventoryItem, ItemType


SCENARIOS = (
    ("collision_wall", "Столкновение со стеной", "Идите вправо к стене", "Стена останавливает игрока"),
    ("interaction_edge", "Граница взаимодействия", "Нажмите E снаружи и внутри зоны", "Магазин откроется только внутри"),
    ("two_objects", "Два предмета", "Кликните на перекрытие предметов", "Поднимется радио"),
    ("ghost_detection", "Обнаружение призраком", "Наблюдайте за состоянием призрака", "PATROL перейдёт в CHASE"),
    ("event_completion", "Завершение события", "Выберите верный вид в журнале", "Откроется экран победы"),
)


class ScenarioManager:
    def __init__(self):
        self.index = -1
        self.original_slot = None
        self.level_file = None
        self.original_random_state = None
        self.original_money = None
        self.original_global_money = None
        self.original_inventory = None
        self.original_counts = None
        self.target_rect = None
        self.result = None

    @property
    def current(self):
        return SCENARIOS[self.index] if self.index >= 0 else None

    def select(self, game, index):
        if not 0 <= index < len(SCENARIOS):
            return False
        if self.index < 0:
            if game.state != GameState.GAME or not game.level_file:
                return False
            self.original_slot = game.selected_save_slot
            self.level_file = game.level_file
            self.original_random_state = random.getstate()
            self.original_money = game.player_money
            self.original_global_money = game.global_money
            self.original_inventory = game.inventory.copy()
            self.original_counts = game.inventory_manager.item_counts.copy()
        self.index = index
        self.reset(game)
        return True

    def reset(self, game):
        if self.index < 0:
            return False
        self.result = None
        self.target_rect = None
        # No scenario action may reach the player's regular save slot.
        game.selected_save_slot = None
        random.seed(7300 + self.index)
        game.load_level(self.level_file)
        game.selected_save_slot = None
        game.set_state(GameState.GAME, reset_stack=True)
        game.journal_open = False
        game.show_save_prompt = False
        game.info_message = None
        game.info_until = 0
        game.player_money = self.original_money
        game.global_money = self.original_global_money
        game.inventory = self.original_inventory.copy()
        game.inventory_manager.item_counts = self.original_counts.copy()
        game.inventory_manager.reset_runtime_state(clear_counts=False)
        game.hunt_active_ticks = 0
        for key in game.keys_pressed:
            game.keys_pressed[key] = False
        game.player_hp = 5
        game.player_rect.topleft = (game.start_x, game.start_y)

        scenario_id = self.current[0]
        if scenario_id == "collision_wall" and game.walls:
            for wall, _ in game.walls:
                candidate = game.player_rect.copy()
                candidate.midright = (wall.left - 1, wall.centery)
                if (candidate.left >= 0 and candidate.top >= int(mechanics.TOP_BAR * MAP_SCALE)
                        and candidate.bottom <= game.world_height
                        and not mechanics.check_collision(candidate, game.walls)
                        and not mechanics.check_collision_with_hitboxes(candidate, game.level_hitboxes)):
                    game.player_rect = candidate
                    self.target_rect = wall.copy()
                    break
        elif scenario_id == "interaction_edge" and game.computer_rect:
            pad = int(48 * MAP_SCALE)
            zone = game.computer_rect.inflate(pad * 2, pad * 2)
            game.player_rect.midright = (zone.left, zone.centery)
            self.target_rect = zone
        elif scenario_id == "two_objects":
            x, y = game.player_rect.center
            items = game.inventory_manager.dropped_items
            items.append(DroppedInventoryItem(x + 90, y, ItemType.EMF))
            items.append(DroppedInventoryItem(x + 105, y, ItemType.RADIO))
            game.inventory[ItemType.EMF.value] = False
            game.inventory[ItemType.RADIO.value] = False
            self.target_rect = items[0].rect.union(items[1].rect)
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
            self.target_rect = ghost.rect
        elif scenario_id == "event_completion" and game.ghost_manager.ghosts:
            ghost = game.ghost_manager.ghosts[0]
            ghost.state = GhostState.IDLE
            ghost.is_frozen_after_appear = False
            ghost.is_playing_spawn = False
            ghost.invisibility_timer = 0
            if ghost.sprite:
                ghost.sprite.set_alpha(ghost.base_alpha)
            self.target_rect = ghost.rect

        game.update_camera()
        return True

    def check(self, game):
        """Run one real game rule from a fresh, reproducible setup."""
        if self.index < 0:
            return None
        self.reset(game)
        scenario_id = self.current[0]
        passed = False
        if scenario_id == "collision_wall" and self.target_rect:
            attempted = game.player_rect.move(mechanics.MOVE_STEP, 0)
            passed = (not game.player_rect.colliderect(self.target_rect)
                      and mechanics.check_collision(attempted, game.walls))
            detail = "Шаг упирается в стену" if passed else "Стена не блокирует шаг"
        elif scenario_id == "interaction_edge" and self.target_rect:
            outside = not game.interact_nearby() and game.state == GameState.GAME
            game.player_rect.move_ip(2, 0)
            inside = game.interact_nearby() and game.state == GameState.SHOP
            passed = outside and inside
            detail = "E работает только внутри зоны" if passed else "Граница взаимодействия работает неверно"
        elif scenario_id == "two_objects":
            items = game.inventory_manager.dropped_items
            overlap = items[0].rect.clip(items[1].rect)
            if overlap.width and overlap.height:
                game.inventory_manager.pick_dropped_item_at(*overlap.center)
                passed = (len(items) == 1 and items[0].item_type == ItemType.EMF
                          and game.inventory[ItemType.RADIO.value])
            detail = "Поднято радио — верхний элемент" if passed else "Выбран другой предмет"
        elif scenario_id == "ghost_detection" and game.ghost_manager.ghosts:
            ghost = game.ghost_manager.ghosts[0]
            ghost.update_state(game.player_rect, game.walls)
            passed = ghost.state == GhostState.CHASE
            detail = "PATROL → CHASE в одной комнате" if passed else "Призрак не начал погоню"
        elif scenario_id == "event_completion" and game.ghost_manager.ghosts:
            ghost = game.ghost_manager.ghosts[0]
            passed = game.submit_ghost_guess(ghost.ghost_kind) and game.state == GameState.WIN
            detail = "Верная догадка открыла победу" if passed else "Событие не завершилось"
        else:
            detail = "На уровне нет нужного объекта"
        self.reset(game)
        self.result = (passed, detail)
        return self.result

    def exit(self, game):
        if self.index < 0:
            return False
        slot = self.original_slot
        self.index = -1
        self.result = None
        self.target_rect = None
        if slot is not None and game.load_game(slot):
            game.load_level_for_current_level()
            game.set_state(GameState.GAME, reset_stack=True)
        else:
            game.selected_save_slot = None
            game.set_state(GameState.MENU, reset_stack=True)
        if self.original_random_state is not None:
            random.setstate(self.original_random_state)
            self.original_random_state = None
        return True
