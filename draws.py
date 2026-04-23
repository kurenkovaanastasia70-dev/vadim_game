import pygame
from constants import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    SHOP_RIGHT_COLUMN_X,
    WHITE,
    BLACK,
    GRAY,
    DARK_GRAY,
    LIGHT_GRAY,
    RED,
    GREEN,
    BLUE,
)
import assets
import mechanics
from inventory_system import ItemType

def draw_menu(game):
    # Рисуем пробковую доску как фон (загружена один раз при инициализации)
    if hasattr(game, 'cork_board_bg') and game.cork_board_bg:
        game.screen.blit(game.cork_board_bg, (0, 0))
    else:
        game.screen.fill(DARK_GRAY)
    
    font = pygame.font.Font(None, 72)

    title = font.render("Приключенческая игра", True, BLACK)
    title_rect = title.get_rect(center=(SCREEN_WIDTH//2, 100))
    game.screen.blit(title, title_rect)

    font_small = pygame.font.Font(None, 36)
    subtitle = font_small.render("выбирете действие", True, BLACK)
    subtitle_rect = subtitle.get_rect(center=(SCREEN_WIDTH//2, 160))
    game.screen.blit(subtitle, subtitle_rect)
    
    # Рисуем пины вместо обычных кнопок
    for button in game.menu_buttons:
        button.draw(game.screen)
def _shop_desc_surface(text, max_width, color):
    """Одна строка описания; при нехватке места уменьшаем шрифт или обрезаем."""
    for size in (28, 26, 24, 22, 20):
        f = pygame.font.Font(None, size)
        surf = f.render(text, True, color)
        if surf.get_width() <= max_width:
            return surf
    f = pygame.font.Font(None, 20)
    ell = "…"
    t = text
    while len(t) > 8 and f.size(t + ell)[0] > max_width:
        t = t[:-1]
    return f.render(t + ell, True, color)


def draw_shop(game):
    """
    Отрисовывает экран магазина.
    
    Этот метод рисует:
    - Фон магазина
    - Заголовок "МАГАЗИН"
    - Информацию о деньгах игрока
    - Все кнопки магазина
    - Описания товаров
    """
    # Заполняем экран темно-серым цветом
    game.screen.fill(DARK_GRAY)
    
    # Создаем шрифт для заголовка магазина
    font = pygame.font.Font(None, 48)
    
    # Создаем и отображаем заголовок
    title = font.render("МАГАЗИН", True, WHITE)
    title_rect = title.get_rect(center=(SCREEN_WIDTH//2, 50))
    game.screen.blit(title, title_rect)
    
    font_money = pygame.font.Font(None, 32)
    money_text = font_money.render(f"Деньги: {game.player_money}", True, WHITE)
    game.screen.blit(money_text, (50, 20))
    
    # Отрисовываем все кнопки магазина
    for button in game.shop_buttons:
        button.draw(game.screen)
    
    # Описания строго справа от своей кнопки (индекс = shop_buttons), без налезания на кнопку
    shop_descriptions = {
        1: "Фонарик — освещает тёмные углы (50 монет)",
        2: "Красная пыль — магический компонент (30 монет)",
        3: "Соль — защита от духов (20 монет)",
        4: "Проектор — зона, куда призрак не заходит (80 монет)",
        5: "Аккумулятор — питание проектора (40 монет)",
        6: "Крест — временно прогоняет призрака (60 монет)",
        7: "Кровь — восстановление жизней (35 монет)",
        8: "Радио — подсказка о призраке (65 монет)",
        9: "ЭМП — уровень активности рядом (70 монет)",
        10: "УФ фонарь — следы на полу (60 монет)",
    }
    gap = 14
    # Левая колонка (кнопки 1–7): описание не заходит в зону правых кнопок (иначе текст рисуется поверх них).
    desc_split = SHOP_RIGHT_COLUMN_X - 8
    for btn_index, desc in shop_descriptions.items():
        if btn_index >= len(game.shop_buttons):
            continue
        btn = game.shop_buttons[btn_index]
        if btn_index <= 7:
            max_w = max(80, desc_split - btn.rect.right - gap)
        else:
            max_w = max(80, SCREEN_WIDTH - btn.rect.right - gap - 10)
        desc_surface = _shop_desc_surface(desc, max_w, WHITE)
        pos = desc_surface.get_rect(midleft=(btn.rect.right + gap, btn.rect.centery))
        if btn_index <= 7 and pos.right > desc_split:
            pos.right = desc_split
        elif pos.right > SCREEN_WIDTH - 8:
            pos.right = SCREEN_WIDTH - 8
        game.screen.blit(desc_surface, pos)

def draw_settings(game):
    """
    Отрисовывает экран настроек.
    
    Этот метод рисует:
    - Фон настроек
    - Заголовок "НАСТРОЙКИ"
    - Все кнопки настроек
    """
    # Заполняем экран темно-серым цветом
    game.screen.fill(DARK_GRAY)
    
    # Создаем шрифт для заголовка
    font = pygame.font.Font(None, 48)
    
    # Создаем и отображаем заголовок
    title = font.render("НАСТРОЙКИ", True, WHITE)
    title_rect = title.get_rect(center=(SCREEN_WIDTH//2, 50))
    game.screen.blit(title, title_rect)
    
    # Отрисовываем все кнопки настроек
    for button in game.settings_buttons:
        button.draw(game.screen)

def draw_difficulty(game):
    game.screen.fill(DARK_GRAY)
    font = pygame.font.Font(None, 48)
    title = font.render("ВЫБЕРИТЕ СЛОЖНОСТЬ", True, WHITE)
    title_rect = title.get_rect(center=(SCREEN_WIDTH//2, 120))
    game.screen.blit(title, title_rect)
    for button in game.difficulty_buttons:
        button.draw(game.screen)

def draw_saves(game):
    game.screen.fill(DARK_GRAY)
    font = pygame.font.Font(None, 48)
    title = font.render("СОХРАНЕНИЯ", True, WHITE)
    title_rect = title.get_rect(center=(SCREEN_WIDTH//2, 50))
    game.screen.blit(title, title_rect)
    for button in game.saves_buttons:
        button.draw(game.screen)
    for del_btn in game.saves_delete_buttons:
        # Рисуем подложку кнопки
        del_btn.draw(game.screen)
        # Если иконка загрузилась — рисуем её по центру кнопки
        if game.trash_icon is not None:
            icon_rect = game.trash_icon.get_rect(center=del_btn.rect.center)
            game.screen.blit(game.trash_icon, icon_rect)
    # Кнопка "Новая игра"
    game.saves_new_button.draw(game.screen)
    # Показываем информацию о слотах
    font_small = pygame.font.Font(None, 24)
    for i in range(3):
        slot_data = game.saves.get(f"slot{i+1}")
        if slot_data:
            level = slot_data.get('level', 1)
            hp = slot_data.get('hp', 5)
            money = slot_data.get('money', 100)
            info = f"Ур.{level} | HP:{hp} | ${money}"
            text = font_small.render(info, True, WHITE)
            game.screen.blit(text, (360, 110 + i * 50))
        else:
            text = font_small.render("Пусто", True, GRAY)
            game.screen.blit(text, (360, 110 + i * 50))
    # Вывод выбранного слота
    status_font = pygame.font.Font(None, 28)
    selected_text = "Выбранный слот: нет" if not game.selected_save_slot else f"Выбранный слот: {game.selected_save_slot}"
    sel_surface = status_font.render(selected_text, True, WHITE)
    game.screen.blit(sel_surface, (50, 340))

def draw_game(game):
    """
    Отрисовывает игровой экран.
    
    Этот метод рисует:
    - Черный фон (для темной атмосферы)
    - Заголовок с номером уровня
    - Сетку игрового поля (пока как заготовка)
    - Кнопки игрового интерфейса
    - Информацию о игроке (деньги, уровень)
    """
    # Задний фон уровня 1 из изображения (масштаб по размеру экрана)
    bg_level1 = assets.load_level_background(game)
    if bg_level1 is not None:
        game.screen.blit(bg_level1, (-game.camera_x, -game.camera_y))
    else:
        game.screen.fill(BLACK)
    
    for wall_rect, wall_color in game.walls:
        wall_screen = wall_rect.move(-game.camera_x, -game.camera_y)
        pygame.draw.rect(game.screen, wall_color, wall_screen)
        # Добавляем обводку для лучшей видимости
        pygame.draw.rect(game.screen, DARK_GRAY, wall_screen, 2)
    
    # Сетка временно отключена
    
    # КНОПКИ, ИНВЕНТАРЬ И ИНФОРМАЦИЯ БУДУТ НАРИСОВАНЫ ПОСЛЕ ЗАТЕМНЕНИЯ (в конце функции)


    # обновление кадра анимации только при движении
    current_time = pygame.time.get_ticks()


    if game.moving and current_time - game.animation_timer > game.animation_speed:
        game.animation_timer = current_time
        # Проверяем, что спрайты загружены и список не пустой
        if (game.player_direction in game.player_sprites and 
            len(game.player_sprites[game.player_direction]) > 0):
            game.player_animation_frame = (
                game.player_animation_frame + 1
            ) % len(game.player_sprites[game.player_direction])


    # получение текущего кадра
    sprite = None
    if game.player_direction in game.player_sprites:  # если есть спрайты для этого направления
        frames = game.player_sprites[game.player_direction]  # получаем спрайты для этого направления
        if frames and len(frames) > 0:  # если есть спрайты для этого направления
            # Проверяем, что индекс не выходит за границы
            if game.player_animation_frame < len(frames):
                sprite = frames[game.player_animation_frame]


    # Отрисовка приведений (перед игроком, чтобы игрок был поверх)
    game.ghost_manager.draw(game.screen, game.camera_x, game.camera_y)
    # Следы призрака (улика): в УФ-режиме контрастнее
    game.ghost_manager.draw_footprints(
        game.screen,
        uv_enabled=getattr(game, "uv_mode", False),
        camera_x=game.camera_x,
        camera_y=game.camera_y
    )

    player_screen_rect = game.player_rect.move(-game.camera_x, -game.camera_y)
    
    # отрисовка персонажа
    if sprite:
        game.screen.blit(sprite, player_screen_rect.topleft)
    else:  # fallback — если спрайты не загрузились
        pygame.draw.rect(game.screen, (255, 0, 0), player_screen_rect)

    # Активный предмет в руке: если ничего не выбрано, но фонарик куплен — держим фонарик по умолчанию.
    if (
        getattr(game.inventory_manager, "active_hand_item", None) is None
        and game.inventory.get("фонарик", False)
    ):
        game.inventory_manager.active_hand_item = ItemType.FLASHLIGHT

    active_item = getattr(game.inventory_manager, "active_hand_item", None)
    if active_item == ItemType.FLASHLIGHT:
        ps = game.player_size
        sz = max(28, int(ps * 0.38))
        pr = player_screen_rect
        cx, cy = pr.centerx, pr.centery
        off = int(ps * 0.40)
        hand_rect = pygame.Rect(0, 0, sz, sz)
        if game.player_direction == "left":
            hand_rect.center = (cx - off, cy)
        elif game.player_direction == "right":
            hand_rect.center = (cx + off, cy)
        elif game.player_direction == "up":
            hand_rect.center = (cx, cy - off)
        else:
            hand_rect.center = (cx, cy + off)

        if "фонарик" in game.inventory_images:
            hand_img = pygame.transform.smoothscale(game.inventory_images["фонарик"], (sz, sz))
            game.screen.blit(hand_img, hand_rect.topleft)
        else:
            # Fallback, если иконка не загружена: жёлтый квадратик-фонарик.
            pygame.draw.rect(game.screen, (245, 220, 90), hand_rect)
            pygame.draw.rect(game.screen, (80, 65, 20), hand_rect, 1)


    # Отрисовка компьютера
    if game.computer and game.computer_rect:
        computer_screen_rect = game.computer_rect.move(-game.camera_x, -game.camera_y)
        comp_img = game.computer
        if comp_img.get_size() != computer_screen_rect.size:
            comp_img = pygame.transform.smoothscale(comp_img, computer_screen_rect.size)
        game.screen.blit(comp_img, computer_screen_rect.topleft)
        
        # Показываем текстовое окно при приближении
        if game.near_computer:
            # Создаем текстовое окно над компьютером
            text = "Нажми на меня, тут магазин"
            font = pygame.font.Font(None, 24)
            text_surface = font.render(text, True, WHITE)
            
            # Размеры окна с отступами
            padding = 10
            box_width = text_surface.get_width() + padding * 2
            box_height = text_surface.get_height() + padding * 2
            
            # Позиция окна над компьютером
            box_x = computer_screen_rect.centerx - box_width // 2
            box_y = computer_screen_rect.y - box_height - 10
            
            # Рисуем фон окна
            box_rect = pygame.Rect(box_x, box_y, box_width, box_height)
            pygame.draw.rect(game.screen, DARK_GRAY, box_rect)
            pygame.draw.rect(game.screen, WHITE, box_rect, 2)
            
            # Рисуем текст
            text_rect = text_surface.get_rect(center=box_rect.center)
            game.screen.blit(text_surface, text_rect)

    # Отрисовка размещённых предметов (пыль, соль)
    game.inventory_manager.draw(game.screen, game.camera_x, game.camera_y)
    
    # Эффект затемнения: зависит от наличия фонарика
    if game.inventory.get("фонарик", False):
        # С фонариком: видна текущая комната целиком
        room_overlay = game._create_room_visibility_overlay()
        game.screen.blit(room_overlay, (0, 0))
    else:
        # Без фонарика: круг вокруг игрока, обрезанный по границам комнаты
        clipped_overlay = game._create_clipped_vignette_overlay()
        game.screen.blit(clipped_overlay, (0, 0))
    
    # Инвентарь поверх затемнения (геометрия — mechanics.inventory_slot_screen)
    purchased_items = [item for item in game.inventory_items if game.inventory[item]]

    label_map = {
        "фонарик": "фон.",
        "красная пыль": "пыль",
        "соль": "соль",
        "проектор": "проектор",
        "аккумулятор": "акк.",
        "крест": "крест",
        "кровь": "кровь",
        "радио": "радио",
        "эмп": "эмп",
        "уф фонарь": "уф",
    }

    for i, item in enumerate(purchased_items):
        circle_x, inventory_y, circle_radius = mechanics.inventory_slot_screen(i)

        pygame.draw.circle(game.screen, GRAY, (circle_x, inventory_y), circle_radius)
        pygame.draw.circle(game.screen, DARK_GRAY, (circle_x, inventory_y), circle_radius, 3)
        
        if item in game.inventory_images:
            img = game.inventory_images[item]
            img_rect = img.get_rect(center=(circle_x, inventory_y))
            game.screen.blit(img, img_rect)
        
        item_font = pygame.font.Font(None, 16)
        item_text = item_font.render(label_map.get(item, item), True, WHITE)
        item_rect = item_text.get_rect(midtop=(circle_x, inventory_y + circle_radius + 3))
        game.screen.blit(item_text, item_rect)
    
    # Отображение количества расходных предметов
    count_font = pygame.font.Font(None, 22)
    battery_count = game.inventory_manager.get_count(ItemType.BATTERY)
    blood_count = game.inventory_manager.get_count(ItemType.BLOOD)
    cross_count = game.inventory_manager.get_count(ItemType.CROSS)
    dust_count = game.inventory_manager.get_count(ItemType.RED_DUST)
    salt_count = game.inventory_manager.get_count(ItemType.SALT)
    
    count_text = count_font.render(f"Аккумуляторы: {battery_count}", True, WHITE)
    game.screen.blit(count_text, (50, 110))
    blood_text = count_font.render(f"Кровь: {blood_count}", True, WHITE)
    game.screen.blit(blood_text, (50, 132))
    cross_text = count_font.render(f"Кресты: {cross_count}", True, WHITE)
    game.screen.blit(cross_text, (50, 154))
    dust_text = count_font.render(f"Пыль: {dust_count}", True, WHITE)
    game.screen.blit(dust_text, (50, 176))
    salt_text = count_font.render(f"Соль: {salt_count}", True, WHITE)
    game.screen.blit(salt_text, (50, 198))
    
    # Кнопки меню и магазина
    for button in game.game_buttons:
        button.draw(game.screen)
    
    # Информация об игроке
    info_font = pygame.font.Font(None, 24)
    money_info = info_font.render(f"Деньги: {game.player_money}", True, WHITE)
    game.screen.blit(money_info, (50, 20))
    level_info = info_font.render(f"Уровень: {game.player_level}", True, WHITE)
    game.screen.blit(level_info, (50, 50))
    hp_info = info_font.render(f"Жизни: {game.player_hp}", True, WHITE)
    game.screen.blit(hp_info, (50, 80))
    controls_info = info_font.render("R: радио  E: ЭМП  T: УФ-следы", True, WHITE)
    game.screen.blit(controls_info, (50, 230))
    uv_state = info_font.render(f"УФ: {'вкл' if getattr(game, 'uv_mode', False) else 'выкл'}", True, WHITE)
    game.screen.blit(uv_state, (50, 254))
        
    if game.show_save_prompt:
        # Полупрозрачный фон
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(128)
        overlay.fill(BLACK)
        game.screen.blit(overlay, (0, 0))
        
        # Диалоговое окно
        dialog_rect = pygame.Rect(SCREEN_WIDTH//2 - 150, SCREEN_HEIGHT//2 - 50, 300, 120)
        pygame.draw.rect(game.screen, DARK_GRAY, dialog_rect)
        pygame.draw.rect(game.screen, WHITE, dialog_rect, 3)
        
        # Текст вопроса
        question_font = pygame.font.Font(None, 32)
        question_text = question_font.render("Сохранить игру?", True, WHITE)
        question_rect = question_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 10))
        game.screen.blit(question_text, question_rect)
        
        # Кнопки диалога
        for button in game.save_prompt_buttons:
            button.draw(game.screen)