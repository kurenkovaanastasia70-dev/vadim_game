"""World-space outlines of geometry actually used by gameplay."""

import pygame

from constants import MAP_SCALE


class DebugRenderer:
    def __init__(self):
        self.hitboxes = False
        self.zones = False
        self.selection = False

    def draw(self, screen, game):
        offset = (-game.camera_x, -game.camera_y)
        inventory = game.inventory_manager
        if self.hitboxes:
            pygame.draw.rect(screen, (70, 240, 100), game.player_rect.move(offset), 2)
            for wall, _ in game.walls:
                pygame.draw.rect(screen, (245, 95, 80), wall.move(offset), 2)
            for rect in game.level_hitboxes:
                pygame.draw.rect(screen, (245, 150, 70), rect.move(offset), 2)
            for ghost in game.ghost_manager.ghosts:
                pygame.draw.rect(screen, (255, 215, 65), ghost.rect.move(offset), 2)
            for item in [*inventory.placed_items, *inventory.dropped_items]:
                pygame.draw.rect(screen, (90, 210, 245), item.rect.move(offset), 2)
            projector = inventory.placed_projector
            if projector:
                pygame.draw.rect(screen, (90, 210, 245), projector.rect.move(offset), 2)
            if game.computer_rect:
                pygame.draw.rect(screen, (90, 210, 245), game.computer_rect.move(offset), 2)

        if self.zones:
            if game.computer_rect:
                pad = int(48 * MAP_SCALE)
                zone = game.computer_rect.inflate(pad * 2, pad * 2)
                pygame.draw.rect(screen, (170, 100, 245), zone.move(offset), 2)
            for x, y, radius in inventory.get_projector_zones():
                pygame.draw.circle(screen, (170, 100, 245), (int(x + offset[0]), int(y + offset[1])), int(radius), 2)
            # Ghost detection uses room membership, not a distance threshold.
            for ghost in game.ghost_manager.ghosts:
                room_id = ghost.get_current_room_id()
                if 0 <= room_id < len(ghost.rooms):
                    room = ghost.rooms[room_id]
                    pygame.draw.rect(screen, (255, 215, 65), pygame.Rect(room.x, room.y, room.width, room.height).move(offset), 1)

        if self.selection:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            world = (mouse_x - offset[0], mouse_y - offset[1])
            candidates = [item for item in reversed(inventory.dropped_items) if item.rect.collidepoint(world)]
            if inventory.placed_projector and inventory.placed_projector.rect.collidepoint(world):
                candidates.append(inventory.placed_projector)
            candidates += [item for item in reversed(inventory.placed_items) if item.rect.collidepoint(world)]
            for item in candidates:
                pygame.draw.rect(screen, (255, 225, 100), item.rect.move(offset), 2)
            if candidates:
                pygame.draw.rect(screen, (255, 255, 255), candidates[0].rect.move(offset), 3)
                font = pygame.font.Font(None, 22)
                label = font.render("Выбор: 1-й по порядку клика; score отсутствует", True, (255, 255, 255))
                screen.blit(label, (max(0, mouse_x - label.get_width()), max(0, mouse_y - 25)))
