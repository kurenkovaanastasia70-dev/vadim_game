"""Readable overlays for real collision, interaction and click geometry."""

import pygame

from constants import MAP_SCALE


class DebugRenderer:
    def __init__(self):
        self.hitboxes = False
        self.zones = False
        self.selection = False
        self.hint = "F6: стены  ·  F7: зоны  ·  F8: цель клика"

    def draw(self, screen, game):
        scenario = game.developer_mode.scenarios
        if not (self.hitboxes or self.zones or self.selection or scenario.current):
            self.hint = "F6: стены  ·  F7: зоны  ·  F8: цель клика"
            return

        layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        viewport = screen.get_rect()
        camera_x, camera_y = game.camera_x, game.camera_y
        inventory = game.inventory_manager

        def outline(rect, color, fill_alpha=0, width=2):
            if not rect:
                return False
            visible = rect.move(-camera_x, -camera_y).clip(viewport)
            if not visible:
                return False
            if fill_alpha:
                pygame.draw.rect(layer, (*color, fill_alpha), visible)
            pygame.draw.rect(layer, (*color, 155), visible, width)
            return True

        wall_count = 0
        zone_count = 0
        if self.hitboxes:
            for wall, _ in game.walls:
                wall_count += outline(wall, (235, 112, 106), 12, 1)
            for rect in game.level_hitboxes:
                wall_count += outline(rect, (242, 176, 97), 12, 1)
            for ghost in game.ghost_manager.ghosts:
                outline(ghost.rect, (244, 205, 110), 22)
            for item in [*inventory.placed_items, *inventory.dropped_items]:
                outline(item.rect, (114, 194, 232), 20)
            if inventory.placed_projector:
                outline(inventory.placed_projector.rect, (114, 194, 232), 20)
            if game.computer_rect:
                outline(game.computer_rect, (114, 194, 232), 20)
            outline(game.player_rect, (115, 227, 178), 16)

        if self.zones:
            if game.computer_rect:
                pad = int(48 * MAP_SCALE)
                zone_count += outline(game.computer_rect.inflate(pad * 2, pad * 2), (175, 143, 239), 24)
            for x, y, radius in inventory.get_projector_zones():
                center = (int(x - camera_x), int(y - camera_y))
                circle = pygame.Rect(center[0] - radius, center[1] - radius, radius * 2, radius * 2)
                if circle.colliderect(viewport):
                    pygame.draw.circle(layer, (175, 143, 239, 34), center, int(radius))
                    pygame.draw.circle(layer, (175, 143, 239, 220), center, int(radius), 2)
                    zone_count += 1
            if scenario.current and scenario.current[0] == "ghost_detection" and game.ghost_manager.ghosts:
                ghost = game.ghost_manager.ghosts[0]
                room_id = ghost.get_current_room_id()
                if 0 <= room_id < len(ghost.rooms):
                    zone_count += outline(ghost.rooms[room_id].rect, (244, 205, 110), 20)

        click_hint = None
        if self.selection:
            mouse = pygame.mouse.get_pos()
            world = (mouse[0] + camera_x, mouse[1] + camera_y)
            if inventory.placement_mode:
                click_hint = "F8: сейчас клик размещает предмет"
            else:
                dropped = [item for item in reversed(inventory.dropped_items) if item.rect.collidepoint(world)]
                placed = [item for item in reversed(inventory.placed_items) if item.rect.collidepoint(world)]
                projector = inventory.placed_projector
                candidates = dropped + ([projector] if projector and projector.rect.collidepoint(world) else []) + placed
                for item in candidates:
                    outline(item.rect, (244, 205, 110), 20)
                if candidates:
                    chosen = candidates[0]
                    outline(chosen.rect, (111, 239, 185), 52, 3)
                    name = getattr(getattr(chosen, "item_type", None), "value", "проектор")
                    click_hint = f"F8: клик выберет «{name}»"
                else:
                    click_hint = "F8: под курсором нет предмета"

        if scenario.current and scenario.target_rect and not (scenario.current[0] == "interaction_edge" and self.zones):
            outline(scenario.target_rect, (255, 225, 138), 12, 2)
        if scenario.current and not self.hitboxes:
            outline(game.player_rect, (115, 227, 178), 16)

        if click_hint:
            self.hint = click_hint
        elif self.zones:
            self.hint = f"F7: зон в кадре — {zone_count}" if zone_count else "F7: зоны сейчас за пределами экрана"
        elif self.hitboxes:
            self.hint = f"F6: препятствий в кадре — {wall_count}" if wall_count else "F6: препятствий в кадре нет"
        else:
            self.hint = "F6: стены  ·  F7: зоны  ·  F8: цель клика"
        # Diagnostics belong to the world; keep the game's HUD and this panel clean.
        layer.fill((0, 0, 0, 0), pygame.Rect(0, 0, screen.get_width(), 185))
        layer.fill((0, 0, 0, 0), pygame.Rect(0, screen.get_height() - 100, 270, 100))
        overlay = game.developer_mode.overlay
        panel_x, panel_y = overlay.panel_position(
            screen, game.developer_mode.details_expanded, bool(scenario.current)
        )
        panel_width, panel_height = overlay.panel_size(
            game.developer_mode.details_expanded, bool(scenario.current)
        )
        layer.fill((0, 0, 0, 0), pygame.Rect(panel_x, panel_y, panel_width, panel_height))
        screen.blit(layer, (0, 0))
