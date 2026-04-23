"""
Модуль для загрузки изображений.
Оригинальный код перенесён сюда без изменений.
"""
import pygame
import os
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, TILE_SIZE, MAP_SCALE
def load_computer_open():
    """
    Загружает изображение компьютера для магазина.
    """
    try:
        # Загружаем PNG с альфа-каналом
        computer_img = pygame.image.load("assets/comp-2.png")
        
        # Если изображение имеет альфа-канал, используем convert_alpha()
        if computer_img.get_flags() & pygame.SRCALPHA:
            computer_img = computer_img.convert_alpha()
        else:
            # Иначе конвертируем и устанавливаем прозрачность
            computer_img = computer_img.convert()
            computer_img.set_colorkey((255, 255, 255))  # белый прозрачный
            computer_img = computer_img.convert_alpha()
        
        # Масштабируем до нужного размера
        computer_img = pygame.transform.scale(computer_img, (80, 80))
        print("[OK] Компьютер открытый загружен")
        return computer_img
    except Exception as e:
        print(f"[!] Не удалось загрузить компьютер: {e}")
        return None
def load_computer_closed():
    """
    Загружает изображение закрытого компьютера.
    """
    try:
        # Загружаем PNG с альфа-каналом
        computer_img = pygame.image.load("assets/comp-1.png")
        
        # Если изображение имеет альфа-канал, используем convert_alpha()
        if computer_img.get_flags() & pygame.SRCALPHA:
            computer_img = computer_img.convert_alpha()
        else:
            # Иначе конвертируем и устанавливаем прозрачность
            computer_img = computer_img.convert()
            computer_img.set_colorkey((255, 255, 255))  # белый прозрачный
            computer_img = computer_img.convert_alpha()
        
        # Масштабируем до нужного размера
        computer_img = pygame.transform.scale(computer_img, (80, 80))
        print("[OK] Компьютер закрытый загружен")
        return computer_img
    except Exception as e:
        print(f"[!] Не удалось загрузить компьютер: {e}")
        return None

def _create_placeholder(size, color):
    """Создаёт заглушку-иконку, если файл не найден."""
    try:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        surf.fill((*color, 255))
        return surf
    except Exception:
        surf = pygame.Surface((size, size))
        surf.fill(color)
        return surf


def load_inventory_images():
    """
    Загружает изображения инвентаря.
    Размер увеличен для соответствия увеличенным кругам инвентаря.
    При отсутствии файла используется цветная заглушка.
    """
    inventory_images = {}
    target_size = 70
    script_dir = os.path.dirname(os.path.abspath(__file__))
    search_paths = [
        os.path.join(script_dir, "assets"),
        os.path.join(script_dir, "..", "assets"),
        "assets",
    ]

    def find_and_load(filenames, target=None):
        """filenames: str или список вариантов (напр. с пробелами и подчёркиванием)"""
        for f in ([filenames] if isinstance(filenames, str) else filenames):
            for base in search_paths:
                path = os.path.join(base, f)
                if os.path.isfile(path):
                    try:
                        img = pygame.image.load(path).convert_alpha()
                        return pygame.transform.smoothscale(img, (target or target_size, target or target_size))
                    except Exception:
                        break
        return None

    def load_or_placeholder(filenames, fallback_color):
        img = find_and_load(filenames)
        return img if img else _create_placeholder(target_size, fallback_color)

    try:
        inventory_images["фонарик"] = load_or_placeholder("fonarik.png", (200, 180, 80))
        inventory_images["красная пыль"] = load_or_placeholder(["redsand to level.png", "redsand_to_level.png", "redsand-1.png"], (180, 50, 50))
        inventory_images["соль"] = load_or_placeholder("salt-1.png", (240, 240, 240))
        inventory_images["проектор"] = load_or_placeholder("proector.png", (100, 100, 120))
        inventory_images["аккумулятор"] = load_or_placeholder(["batareyka.png", "battery.png"], (80, 180, 60))
        inventory_images["крест"] = load_or_placeholder(["New Piskel.png", "New_Piskel.png", "cross.png"], (180, 160, 80))
        inventory_images["кровь"] = load_or_placeholder(["blood-1.png", "blood.png"], (150, 30, 30))
    except Exception as e:
        print(f"Не удалось загрузить изображения инвентаря: {e}")
        inventory_images = {}

    return inventory_images


def load_placement_sprites():
    """Спрайты для размещаемых на уровне предметов: пыль (до/после), соль (до/после). Размер 50x50."""
    size = 50
    script_dir = os.path.dirname(os.path.abspath(__file__))
    search_paths = [os.path.join(script_dir, "assets"), os.path.join(script_dir, "..", "assets"), "assets"]

    def load(filenames):
        for f in ([filenames] if isinstance(filenames, str) else filenames):
            for base in search_paths:
                path = os.path.join(base, f)
                if os.path.isfile(path):
                    try:
                        img = pygame.image.load(path).convert_alpha()
                        return pygame.transform.smoothscale(img, (size, size))
                    except Exception:
                        break
        return None

    dust_active = load(["redsand to level.png", "redsand_to_level.png", "redsand-1.png"]) or _create_placeholder(size, (180, 50, 50))
    dust_triggered = load(["redsand dif.png", "redsand_dif.png"]) or _create_placeholder(size, (100, 30, 30))
    salt_active = load("salt-1.png") or _create_placeholder(size, (240, 240, 240))
    salt_triggered = load("salt2.png") or _create_placeholder(size, (180, 180, 180))
    return dust_active, dust_triggered, salt_active, salt_triggered


def load_projector_sprite():
    """Спрайт проектора для размещения на карте. Размер 50x50."""
    size = 50
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for base in [os.path.join(script_dir, "assets"), os.path.join(script_dir, "..", "assets"), "assets"]:
        for fn in ["proector.png", "projector.png"]:
            path = os.path.join(base, fn)
            if os.path.isfile(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    return pygame.transform.smoothscale(img, (size, size))
                except Exception:
                    pass
    return _create_placeholder(size, (100, 100, 120))


def load_trash_icon():
    """
    Загружает иконку корзины.
    Оригинальный код из main.py без изменений.
    """
    try:
        icon_path = os.path.join(os.getcwd(), "assets/trach.png")
        img = pygame.image.load(icon_path).convert_alpha()
        # Подгоним под размер кнопок с небольшим отступом
        trash_icon = pygame.transform.smoothscale(img, (28, 28))
        return trash_icon
    except Exception as e:
        return None


def load_level_background(game):
    """
    Загружает фоновое изображение уровня.
    Сначала пытается загрузить из данных уровня, затем использует дефолтный.
    """
    if not hasattr(game, "bg_level1"):
        game.bg_level1 = None
    
    expected_size = (game.world_width, game.world_height)

    # Если кэш уже есть нужного размера — используем его
    if game.bg_level1 is not None and game.bg_level1.get_size() == expected_size:
        return game.bg_level1

    # Если есть данные уровня с фоном
    if game.level_data and game.level_data.get("background"):
        bg_path = game.level_data["background"]
        # Если относительный путь, ищем относительно файла уровня
        if game.level_file and not os.path.isabs(bg_path):
            bg_path = os.path.join(os.path.dirname(game.level_file), bg_path)
        
        try:
            if os.path.exists(bg_path):
                bg_img = pygame.image.load(bg_path).convert()
                game.bg_level1 = pygame.transform.scale(bg_img, expected_size)
                return game.bg_level1
        except Exception as e:
            print(f"Ошибка загрузки фона из уровня: {e}")
    
    # Загружаем дефолтный фон
    if not game.bg_level1:
        try:
            bg_img = pygame.image.load("backgroung_lvl1.jpg").convert()
            game.bg_level1 = pygame.transform.scale(bg_img, expected_size)
        except Exception:
            game.bg_level1 = None
    
    return game.bg_level1

def load_player_sprites():
    """
    Загружает спрайты персонажа (16 спрайтов по 4 на каждое направление).
    Оригинальный код из main.py без изменений.
    """
    player_sprites = {}
    directions = {
        "down": 2,   # 2 кадра
        "up": 4,
        "left": 4,
        "right": 4
    }

    for direction, frame_count in directions.items():
        player_sprites[direction] = []
        for i in range(frame_count):
            try:
                path = f"sprite_parts/player_{direction}_{i+1}.png"
                sprite = pygame.image.load(path).convert()  # сначала convert
                sprite.set_colorkey((255, 255, 255))        # делаем белый прозрачным
                sprite = sprite.convert_alpha()             # теперь можно снова включить альфу
                px = int(TILE_SIZE * MAP_SCALE)
                sprite = pygame.transform.scale(sprite, (px, px))
                player_sprites[direction].append(sprite)
            except Exception as e:
                print(f"[!] Не удалось загрузить спрайт {path}: {e}")
                # Продолжаем загрузку остальных спрайтов
    
    return player_sprites


def load_ghost_sprite():
    """
    Загружает спрайт приведения.
    """
    try:
        ghost_img = pygame.image.load("assets/ghost.png")
        
        # Если изображение имеет альфа-канал, используем convert_alpha()
        if ghost_img.get_flags() & pygame.SRCALPHA:
            ghost_img = ghost_img.convert_alpha()
        else:
            # Иначе конвертируем и устанавливаем прозрачность
            ghost_img = ghost_img.convert()
            ghost_img.set_colorkey((255, 255, 255))  # белый прозрачный
            ghost_img = ghost_img.convert_alpha()
        
        # Масштабируем до размера персонажа
        ghost_img = pygame.transform.scale(ghost_img, (TILE_SIZE, TILE_SIZE))
        print("[OK] Приведение загружено")
        return ghost_img
    except Exception as e:
        print(f"[!] Не удалось загрузить приведение: {e}")
        return None

def load_cork_board(screen_width=None, screen_height=None):
    """
    Загружает фон пробковой доски для меню.
    Растягивает изображение на ВЕСЬ экран, игнорируя пропорции.
    """
    # Определяем размер экрана
    if screen_width and screen_height:
        w, h = screen_width, screen_height
    else:
        try:
            screen = pygame.display.get_surface()
            w = screen.get_width() if screen else SCREEN_WIDTH
            h = screen.get_height() if screen else SCREEN_HEIGHT
        except:
            w, h = SCREEN_WIDTH, SCREEN_HEIGHT
    
    try:
        # Загружаем и сразу растягиваем на весь экран
        cork_img = pygame.image.load("menu_background.png").convert()
        # Принудительно растягиваем на весь экран (без сохранения пропорций)
        result = pygame.transform.scale(cork_img, (w, h))
        print(f"[OK] Фон меню: {w}x{h}")
        return result
    except Exception as e:
        print(f"[!] Ошибка загрузки menu_background.png: {e}")
        # Fallback — сплошной цвет
        fallback = pygame.Surface((w, h))
        fallback.fill((139, 90, 43))  # Коричневый
        return fallback

def load_pin_images():
    """
    Загружает изображения пинов для меню.
    """
    pin_images = {}
    pin_files = ["pin_1.png", "pin_2.png", "pin_3.png"]
    
    for i, pin_file in enumerate(pin_files, 1):
        try:
            pin_img = pygame.image.load(f"assets/{pin_file}")
            
            # Если изображение имеет альфа-канал, используем convert_alpha()
            if pin_img.get_flags() & pygame.SRCALPHA:
                pin_img = pin_img.convert_alpha()
            else:
                # Иначе конвертируем и устанавливаем прозрачность
                pin_img = pin_img.convert()
                pin_img.set_colorkey((255, 255, 255))  # белый прозрачный
                pin_img = pin_img.convert_alpha()
            
            # Масштабируем с сохранением пропорций
            original_width, original_height = pin_img.get_size()
            target_width = 150  # Целевая ширина
            scale_factor = target_width / original_width
            new_height = int(original_height * scale_factor)
            pin_img = pygame.transform.scale(pin_img, (target_width, new_height))
            pin_images[f"pin_{i}"] = pin_img
            print(f"✅ Пин {i} загружен")
        except Exception as e:
            print(f"[!] Не удалось загрузить пин {i}: {e}")
            pin_images[f"pin_{i}"] = None
    
    return pin_images

