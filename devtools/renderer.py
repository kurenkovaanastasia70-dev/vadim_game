"""Quiet outlines of the geometry used by game rules."""

import pygame

from constants import MAP_SCALE


class DebugRenderer:
    def __init__(self):
        self.hitboxes = False
        self.zones = False
        self.selection = False

    def draw(self, screen, game):
        scenario = game.developer_mode.scenarios
        scenario_id = scenario.current[0] if scenario.current else None
        if not (self.hitboxes or self.zones or self.selection or scenario.current):
            return

        layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        focus = game.player_rect.inflate(520, 420)
        inventory = game.inventory_manager
        camera_x, camera_y = game.camera_x, game.camera_y

        def outline(rect, color, width=1):
            if rect and rect.colliderect(focus):
                view = rect.move(-camera_x, -camera_y)
                if view.colliderect(screen.get_rect()):
                    pygame.draw.rect(layer, color, view, width)

        if self.hitboxes:
            if scenario_id is None:
                for wall, _ in game.walls:
                    outline(wall, (245, 125, 125, 100))
                for rect in game.level_hitboxes:
                    outline(rect, (245, 165, 110, 100))
                for item in [*inventory.placed_items, *inventory.dropped_items]:
                    outline(item.rect, (120, 195, 235, 160))
            elif scenario_id == "two_objects":
                for item in inventory.dropped_items:
                    outline(item.rect, (120, 195, 235, 180), 2)
            elif scenario_id == "ghost_detection":
                for ghost in game.ghost_manager.ghosts:
                    outline(ghost.rect, (245, 210, 125, 190), 2)

        if self.zones:
            if game.computer_rect:
                pad = int(48 * MAP_SCALE)
                outline(game.computer_rect.inflate(pad * 2, pad * 2), (160, 145, 235, 155))
            for x, y, radius in inventory.get_projector_zones():
                if focus.collidepoint(x, y):
                    pygame.draw.circle(layer, (160, 145, 235, 155), (int(x - camera_x), int(y - camera_y)), int(radius), 1)
            if scenario_id == "ghost_detection":
                ghost = game.ghost_manager.ghosts[0]
                room_id = ghost.get_current_room_id()
                if 0 <= room_id < len(ghost.rooms):
                    outline(ghost.rooms[room_id].rect, (245, 210, 125, 125))

        if self.selection:
            mouse = pygame.mouse.get_pos()
            world = (mouse[0] + camera_x, mouse[1] + camera_y)
            candidates = [item for item in reversed(inventory.dropped_items) if item.rect.collidepoint(world)]
            if inventory.placed_projector and inventory.placed_projector.rect.collidepoint(world):
                candidates.append(inventory.placed_projector)
            candidates += [item for item in reversed(inventory.placed_items) if item.rect.collidepoint(world)]
            for item in candidates:
                outline(item.rect, (245, 210, 125, 210), 2)
            if candidates:
                outline(candidates[0].rect, (125, 235, 190, 235), 3)

        if scenario.current or self.hitboxes:
            outline(game.player_rect, (125, 235, 190, 220), 2)
        if scenario.current and scenario.target_rect:
            outline(scenario.target_rect, (255, 245, 180, 220), 2)
        screen.blit(layer, (0, 0))
