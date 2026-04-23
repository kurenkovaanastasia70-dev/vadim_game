import pygame
import mechanics
from gamestate import GameState
from constants import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    FPS,
    TILE_SIZE,
    MAP_SCALE,
    WHITE,
    BLACK,
    GRAY,
    DARK_GRAY,
    LIGHT_GRAY,
    RED,
    GREEN,
    BLUE,
)
def handle_menu_events(game, event):
    for i, button in enumerate(game.menu_buttons):
        if button.handle_event(event):
            if i==0:  # Начать игру
            # Сначала выбор слота: если слот не выбран, переходим к сохранениям
                if not game.selected_save_slot:
                    game.push_state(GameState.SAVES)
                elif not game.difficulty_selected:
                    game.push_state(GameState.DIFF)
                else:
                    game.push_state(GameState.GAME)
            elif i==1:  # Настройки
                game.push_state(GameState.SETTINGS)
            elif i==2:  # Сохранить
                game.push_state(GameState.SAVES)
            elif i==3:  # Выход
                game.running=False


def handle_difficulty_events(game, event):
    for i, button in enumerate(game.difficulty_buttons):
        if button.handle_event(event):
            if i in (0, 1, 2, 3):
                game.difficulty_index = i
                game.difficulty_selected = True
                # Сброс для новой игры (HP, деньги, уровень)
                game.reset_for_new_game()
                game.set_state(GameState.GAME, reset_stack = True)
            elif i == 4:  # Назад
                game.go_back()

def handle_saves_events(game, event):
    for i, button in enumerate(game.saves_buttons):
        if button.handle_event(event):
            if i in (0, 1, 2):  # Слоты 1-3
                slot_num = i + 1
                # Проверяем, какая кнопка мыши была нажата
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Левая кнопка мыши - загрузить (только по кнопке слота)
                        if game.load_game(slot_num):
                            print(f"Игра загружена из слота {slot_num}")
                            game.set_state(GameState.GAME, reset_stack=True)
                        else:
                            print(f"Слот {slot_num} пуст - переходим к выбору сложности")
                            game.selected_save_slot = slot_num
                            game.push_state(GameState.DIFF)
                    elif event.button == 2:  # Средняя кнопка мыши - удалить
                        if game.saves.get(f"slot{slot_num}"):
                            game.delete_save(slot_num)
                            print(f"Сохранение в слоте {slot_num} удалено")
                        else:
                            print(f"Слот {slot_num} уже пуст")
            elif i == 3:  # Назад
                game.go_back()
    # Кнопка "Новая игра": выбираем первый свободный слот
    if game.saves_new_button.handle_event(event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            free_slot_found = False
            for slot_num in range(1, 4):
                if not game.saves.get(f"slot{slot_num}"):
                    # Регистрируем новый слот как выбранный, пока без сохранения
                    game.selected_save_slot = slot_num
                    # Переходим к выбору сложности
                    game.push_state(GameState.DIFF)
                    free_slot_found = True
                    break
            
            # Показываем сообщение только если НЕ нашли свободный слот
            if not free_slot_found:
                game.info_message = "Все слоты уже заняты, удалите один из слотов"
                game.info_until = pygame.time.get_ticks() + 1500
    # Обработка нажатий по кнопкам удаления рядом со слотами
    for i, del_btn in enumerate(game.saves_delete_buttons):
        if del_btn.handle_event(event):
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                slot_num = i + 1
                if game.saves.get(f"slot{slot_num}"):
                    game.delete_save(slot_num)
                    print(f"Сохранение в слоте {slot_num} удалено")
                else:
                    print(f"Слот {slot_num} уже пуст")
def handle_shop_events(game, event):
    """
    Обрабатывает события магазина (встроенного в игру).
    
    Параметры:
    event - событие pygame для обработки
    """
    # Проверяем все кнопки магазина
    for i, button in enumerate(game.shop_buttons):
        # Если кнопка была нажата
        if button.handle_event(event):
            if i == 0:  # Кнопка "Назад"
                game.go_back()
            elif i == 1:  # Кнопка "Купить фонарик"
                if game.buy_item("фонарик", 50):
                    print("Куплен фонарик!")
                else:
                    print("Недостаточно денег или предмет уже куплен!")
            elif i == 2:  # Кнопка "Купить красную пыль"
                if game.player_money >= 30:
                    game.player_money -= 30
                    game.inventory["красная пыль"] = True
                    from inventory_system import ItemType
                    game.inventory_manager.increase_count(ItemType.RED_DUST)
                    print("Куплена красная пыль!")
                else:
                    print("Недостаточно денег!")
            elif i == 3:  # Кнопка "Купить соль"
                if game.player_money >= 20:
                    game.player_money -= 20
                    game.inventory["соль"] = True
                    from inventory_system import ItemType
                    game.inventory_manager.increase_count(ItemType.SALT)
                    print("Куплена соль!")
                else:
                    print("Недостаточно денег!")
            elif i == 4:  # Кнопка "Купить проектор"
                if game.buy_item("проектор", 80):
                    print("Куплен проектор!")
                else:
                    print("Недостаточно денег или предмет уже куплен!")
            elif i == 5:  # Кнопка "Купить аккумулятор"
                if game.player_money >= 40:
                    game.player_money -= 40
                    game.inventory["аккумулятор"] = True
                    from inventory_system import ItemType
                    game.inventory_manager.increase_count(ItemType.BATTERY)
                    print("Куплен аккумулятор!")
                else:
                    print("Недостаточно денег!")
            elif i == 6:  # Кнопка "Купить крест"
                if game.player_money >= 60:
                    game.player_money -= 60
                    game.inventory["крест"] = True
                    from inventory_system import ItemType
                    game.inventory_manager.increase_count(ItemType.CROSS)
                    print("Куплен крест!")
                else:
                    print("Недостаточно денег!")
            elif i == 7:  # Кнопка "Купить кровь"
                if game.player_money >= 35:
                    game.player_money -= 35
                    game.inventory["кровь"] = True
                    from inventory_system import ItemType
                    game.inventory_manager.increase_count(ItemType.BLOOD)
                    print("Куплена кровь!")
                else:
                    print("Недостаточно денег!")
            elif i == 8:  # Кнопка "Купить радио"
                if game.buy_item("радио", 65):
                    print("Куплено радио!")
                else:
                    print("Недостаточно денег или предмет уже куплен!")
            elif i == 9:  # Кнопка "Купить ЭМП"
                if game.buy_item("эмп", 70):
                    print("Куплен ЭМП!")
                else:
                    print("Недостаточно денег или предмет уже куплен!")
            elif i == 10:  # Кнопка "Купить УФ фонарь"
                if game.buy_item("уф фонарь", 60):
                    print("Куплен УФ фонарь!")
                else:
                    print("Недостаточно денег или предмет уже куплен!")

def handle_settings_events(game, event):
    """
    Обрабатывает события экрана настроек.
    
    Параметры:
    event - событие pygame для обработки
    """
    # Проверяем все кнопки настроек
    for i, button in enumerate(game.settings_buttons):
        # Если кнопка была нажата
        if button.handle_event(event):
            if i == 0:  # Кнопка "Назад"
                game.go_back()
            elif i == 1:  # Кнопка "Громкость"
                game.volume = (game.volume + 10) % 110
                if pygame.mixer.get_init():
                    pygame.mixer.music.set_volume(game.volume)
                game.update_settings_button_texts()
            elif i == 2:  # Кнопка "Полноэкранный режим"
                game.toggle_fullscreen()
            elif i == 3:  # Кнопка "Сбросить настройки"
                game.fullscreen = True
                game.volume = 50
                if pygame.mixer.get_init():
                    pygame.mixer.music.set_volume(game.volume)
                game.update_settings_button_texts()

def handle_game_events(game, event):
    """
    Обрабатывает события игрового экрана.
    
    Параметры:
    event - событие pygame для обработки
    """
    # Если показываем диалог сохранения
    if game.show_save_prompt:
        for i, button in enumerate(game.save_prompt_buttons):
            if button.handle_event(event):
                if i == 0:  # Да - сохранить
                    if game.selected_save_slot:
                        game.save_game(game.selected_save_slot)
                        print(f"Игра сохранена в слот {game.selected_save_slot}")
                    else:
                        # Если нет выбранного слота, сохраняем в первый доступный
                        for slot_num in range(1, 4):
                            if not game.saves.get(f"slot{slot_num}"):
                                game.save_game(slot_num)
                                print(f"Игра сохранена в пустой слот {slot_num}")
                                break
                        else:
                            # Показываем окно об ошибке сохранения (все слоты заняты)
                            game.info_message = "Все слоты уже заняты, невозможно сохранить игру"
                            game.info_until = pygame.time.get_ticks() + 1500
                    game.show_save_prompt = False
                    game.set_state(GameState.MENU, reset_stack=True)
                    # НЕ сбрасываем выбранный слот при сохранении - он остается активным
                elif i == 1:  # Нет - не сохранять
                    game.show_save_prompt = False
                    game.set_state(GameState.MENU, reset_stack=True)
        return

    # Проверяем все кнопки игрового интерфейса
    for i, button in enumerate(game.game_buttons):
        # Если кнопка была нажата
        if button.handle_event(event):
            if i == 0:  # Кнопка "Меню"
                game.show_save_prompt = True
            elif i == 1:  # Кнопка "Магазин"
                game.push_state(GameState.SHOP)

    # Обработка нажатий и отпусканий клавиш для плавного движения
    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_F1:
            # Переключение отладочного режима для приведений
            game.ghost_manager.toggle_debug()
        # Клавиши 1-7 для использования предметов инвентаря
        elif event.key == pygame.K_1:
            game.inventory_manager.use_item_by_index(0)
        elif event.key == pygame.K_2:
            game.inventory_manager.use_item_by_index(1)
        elif event.key == pygame.K_3:
            game.inventory_manager.use_item_by_index(2)
        elif event.key == pygame.K_4:
            game.inventory_manager.use_item_by_index(3)
        elif event.key == pygame.K_5:
            game.inventory_manager.use_item_by_index(4)
        elif event.key == pygame.K_6:
            game.inventory_manager.use_item_by_index(5)
        elif event.key == pygame.K_7:
            game.inventory_manager.use_item_by_index(6)
        elif event.key == pygame.K_r:
            from inventory_system import ItemType
            game.inventory_manager.use_item(ItemType.RADIO)
        elif event.key == pygame.K_e:
            from inventory_system import ItemType
            game.inventory_manager.use_item(ItemType.EMF)
        elif event.key == pygame.K_t:
            from inventory_system import ItemType
            game.inventory_manager.use_item(ItemType.UV_FLASHLIGHT)
        # ESC для отмены размещения
        elif event.key == pygame.K_ESCAPE:
            game.inventory_manager.cancel_placement()
        elif event.key in game.keys_pressed:
            game.keys_pressed[event.key] = True
    elif event.type == pygame.KEYUP:
        if event.key in game.keys_pressed:
            game.keys_pressed[event.key] = False

        
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        mouse_pos = event.pos
        world_mouse_pos = (mouse_pos[0] + game.camera_x, mouse_pos[1] + game.camera_y)
        
        if game.inventory_manager.placement_mode:
            game.inventory_manager.place_item(world_mouse_pos[0], world_mouse_pos[1])
            return
        
        # Клик по проектору — зарядить аккумулятором (если не в режиме размещения)
        if game.inventory_manager.try_power_projector(world_mouse_pos[0], world_mouse_pos[1]):
            return
        
        if game.computer_rect and game.near_computer:
            pad = int(48 * MAP_SCALE)
            click_zone = game.computer_rect.inflate(pad * 2, pad * 2)
            if click_zone.collidepoint(world_mouse_pos):
                game.push_state(GameState.SHOP)
        
        # Обработка кликов по инвентарю (та же сетка, что в draws.draw_game)
        purchased_items = [item for item in game.inventory_items if game.inventory[item]]
        for i, item in enumerate(purchased_items):
            circle_x, inventory_y, circle_radius = mechanics.inventory_slot_screen(i)
            if ((mouse_pos[0] - circle_x) ** 2 + (mouse_pos[1] - inventory_y) ** 2) <= circle_radius ** 2:
                game.inventory_manager.use_item_by_index(i)
def handle_event(game):
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            game.running = False
        
        if game.state == GameState.MENU:
            handle_menu_events(game, event)
        elif game.state == GameState.SHOP:
            handle_shop_events(game, event)
        elif game.state == GameState.SETTINGS:
            handle_settings_events(game, event)
        elif game.state == GameState.GAME:
            handle_game_events(game, event)
        elif game.state == GameState.DIFF:
            handle_difficulty_events(game, event)
        elif game.state == GameState.SAVES:
            handle_saves_events(game, event)