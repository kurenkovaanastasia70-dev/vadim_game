import pygame
from constants import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    FPS,
    TILE_SIZE,
    WHITE,
    BLACK,
    GRAY,
    DARK_GRAY,
    LIGHT_GRAY,
    RED,
    GREEN,
    BLUE,
)   

class Button:
    def __init__(self, x, y, width, height, text, color = GRAY, hover_color = LIGHT_GRAY):
        self.rect = pygame.Rect(x,y, width, height)
        self.text = text 
        self.color = color                  # Основной цвет
        self.hover_color = hover_color      # Цвет при наведении
        self.current_color = color          # Текущий цвет (может меняться)
        # Создаем шрифт для текста кнопки (None = системный шрифт, 36 = размер)
        self.font = pygame.font.Font(None, 36)
    def draw(self,screen):
        pygame.draw.rect(screen, self.current_color, self.rect)
        #Todo: сделать возможность полупрозрачных кнопок, в класс передать ещё и цвет рамки
        pygame.draw.rect(screen, BLACK, self.rect, 2)
        text_surface = self.font.render(self.text, False, BLACK)
        text_rect = text_surface.get_rect(center = self.rect.center)
        screen.blit(text_surface, text_rect)
    def handle_event(self, event):
        if event.type== pygame.MOUSEMOTION:
            if self.rect.collidepoint(event.pos):
                self.current_color = self.hover_color
            else: 
                self.current_color = self.color
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                return True
        return False

class PinButton(Button):
    """Кнопка в виде пина для пробковой доски"""
    def __init__(self, x, y, pin_image, text):
        # Инициализируем родительский класс
        width = pin_image.get_width() if pin_image else 200
        height = pin_image.get_height() if pin_image else 80
        super().__init__(x, y, width, height, text)
        
        self.pin_image = pin_image
        self.font = pygame.font.Font(None, 20)  # Переопределяем размер шрифта
        
    def draw(self, screen):
        if self.pin_image:
            # Рисуем пин
            screen.blit(self.pin_image, self.rect)
            # Добавляем надпись НА бумажке пина
            text_surface = self.font.render(self.text, True, BLACK)
            text_rect = text_surface.get_rect(center=self.rect.center)
            screen.blit(text_surface, text_rect)
        else:
            # Fallback - используем родительский метод
            super().draw(screen)