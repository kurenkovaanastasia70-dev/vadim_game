import pygame
from constants import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
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
from ghost import EVIDENCE_PROFILE_KEYS, filter_journal_suspects, JOURNAL_LIST_PROFILE_IDS

# Только признаки из ghost_abilities.ini: приборы плюс уже существующие can_walk/can_fly.
JOURNAL_EVIDENCE_HELP = [
    (
        "amp",
        "ЭМП-метр  [E]",
        "Пики шкалы 2–4 — отметь, если поймал. Снизу останутся типы, у которых в данных предусмотрен сильный ЭМП.",
    ),
    (
        "ultraviolet",
        "УФ-фонарь  [T]",
        "Следы в УФ: галка, если увидел. Сужает список по типам с такой же уликой.",
    ),
    (
        "radio",
        "Радиоприёмник  [R]",
        "Ответ или голос с радио: галка, если слышал. Снимай галку, если радио «молчит» в таком раунде.",
    ),
    (
        "can_walk",
        "Ходит по полу",
        "Отмечай, если призрак явно перемещается пешком: следы, обход стен, движение по комнатам без полёта.",
    ),
    (
        "can_fly",
        "Летает",
        "Отмечай, если призрак держится над полом или проходит путь как летающий тип. Это уже есть в конфиге.",
    ),
]


def _wrap_lines(font, text, max_width):
    """Разбивает строку на подстроки, чтобы ширина не превышала max_width (по словам)."""
    words = text.split()
    if not words:
        return [""]
    lines = []
    line = words[0]
    for w in words[1:]:
        t = f"{line} {w}"
        if font.size(t)[0] <= max_width:
            line = t
        else:
            lines.append(line)
            line = w
    lines.append(line)
    return lines


def _journal_panel_rect():
    w = min(640, max(400, SCREEN_WIDTH - 32))
    h = min(520, max(380, SCREEN_HEIGHT - 20))
    return pygame.Rect((SCREEN_WIDTH - w) // 2, (SCREEN_HEIGHT - h) // 2, w, h)


def _journal_content_width(panel):
    return panel.w - 28 * 2


JOURNAL_ROW_H = 54
JOURNAL_CB_SIZE = 24


def _journal_checkboxes_y0(inner):
    """Верхний край первого чекбокса (две фиксированные строки вступления под заголовком)."""
    return inner.y + 78


def _journal_close_rect(panel):
    """Одна и та же геометрия кнопки «Закрыть» для hit-test и отрисовки."""
    f = pygame.font.Font(None, 22)
    label = f.render("Закрыть  ·  J / Esc  ·  снаружи", True, (235, 238, 245))
    pad_x, pad_y = 12, 8
    w = min(label.get_width() + pad_x * 2, max(0, panel.w - 12))
    h = max(34, label.get_height() + pad_y * 2)
    r = pygame.Rect(panel.centerx - w // 2, panel.bottom - h - 6, w, h)
    # не вылезать за края панели
    m = 6
    if r.left < panel.left + m:
        r.x = panel.left + m
    if r.right > panel.right - m:
        r.x = panel.right - m - r.w
    return r, label


def journal_get_checkbox_rects(panel):
    """Прямоугольники чекбоксов в экранных координатах."""
    inner = panel.inflate(-28, -28)
    y0 = _journal_checkboxes_y0(inner)
    out = {}
    for i, (key, _h, _s) in enumerate(JOURNAL_EVIDENCE_HELP):
        out[key] = pygame.Rect(inner.x, y0 + i * JOURNAL_ROW_H, JOURNAL_CB_SIZE, JOURNAL_CB_SIZE)
    return out


def evidence_journal_hit_test(game, pos):
    panel = _journal_panel_rect()
    if not panel.collidepoint(pos):
        return "outside"
    close, _ = _journal_close_rect(panel)
    if close.collidepoint(pos):
        return "close"
    for key, r in journal_get_checkbox_rects(panel).items():
        if r.collidepoint(pos):
            return key
    return None


def _draw_journal_checkbox(screen, rect, checked):
    fill = (34, 37, 49)
    border = (122, 132, 156)
    if checked:
        fill = (32, 84, 58)
        border = (96, 215, 148)
    pygame.draw.rect(screen, fill, rect, border_radius=5)
    pygame.draw.rect(screen, border, rect, 2, border_radius=5)
    if checked:
        a = (rect.left + 6, rect.centery)
        b = (rect.left + 10, rect.bottom - 7)
        c = (rect.right - 5, rect.top + 7)
        pygame.draw.line(screen, (238, 255, 244), a, b, 3)
        pygame.draw.line(screen, (238, 255, 244), b, c, 3)


def draw_howto(game):
    game.screen.fill((18, 20, 28))
    pad_x = 24
    margin = 20
    body_rect = pygame.Rect(
        margin,
        50,
        SCREEN_WIDTH - margin * 2,
        SCREEN_HEIGHT - 58,
    )
    glass = pygame.Surface((body_rect.w, body_rect.h), pygame.SRCALPHA)
    glass.fill((32, 36, 48, 232))
    game.screen.blit(glass, body_rect.topleft)
    pygame.draw.rect(game.screen, (100, 115, 150), body_rect, 1, border_radius=8)

    game.howto_back_button.draw(game.screen)

    title_f = pygame.font.Font(None, 38)
    h_f = pygame.font.Font(None, 25)
    b_f = pygame.font.Font(None, 21)
    sm = pygame.font.Font(None, 19)
    title = title_f.render("Как играть", True, (230, 235, 255))
    game.screen.blit(title, (body_rect.centerx - title.get_width() // 2, body_rect.y + 10))

    content_w = body_rect.w - 36
    x0 = body_rect.x + 18
    y = body_rect.y + 50
    dim = (200, 205, 215)

    # Таблица: клавиша — действие
    table_title = h_f.render("Клавиши (в игре, после покупок)", True, (160, 200, 255))
    game.screen.blit(table_title, (x0, y))
    y += 30
    rows = [
        ("R", "Радио — вопрос духу (нужен предмет в магазине)"),
        ("E", "ЭМП — шкала активности рядом: пики — признак, отмечаешь в журнале"),
        ("T", "Ультрафиолет — подсветка следов, отмечаешь, если поймал"),
        ("J", "Журнал — что уже видел; игра сравнивает с известными типами призраков"),
        ("1 — 7", "Слоты инвентаря внизу: выбрать купленный предмет"),
    ]
    for k, desc in rows:
        game.screen.blit(sm.render(k, True, (120, 220, 200)), (x0, y))
        for line in _wrap_lines(b_f, desc, content_w - 100):
            game.screen.blit(b_f.render(line, True, dim), (x0 + 100, y))
            y += 22
        y += 6

    y += 8
    sections = [
        (
            "С чего начать",
            "В главном меню выбери слот и «Новая игра» или пустой слот → сложность. В миссии: "
            "сначала найди **компьютер** (иконка, часто у края карты) и купи **фонарик** — иначе комнаты в тумане. "
            "Потом **ЭМП, УФ, радио** — иначе не проверить улику для журнала. Деньги — слева вверху.",
        ),
        (
            "Как сужается расследование",
            "Каждому из семи **известных** типов духов сопоставлен свой набор: ЭМП, УФ, радио (то, что ловит приборами). "
            "Журнал (J) оставляет в списке только тех, у кого **все твои галки** согласуются с «их» признаками.",
        ),
        (
            "Список кандидатов",
            "В сценарии раунда участвуют **семь** полно настроенных существ. Остальные варианты в базе (если появятся) "
            "в твоём расследовании не мешают — их не увидишь в этом списке.",
        ),
        (
            "Опасность и сейв",
            "Касание призрака = минус жизнь. **Меню** (справа вверху) — выход с сохранением в слот.",
        ),
    ]

    for head, body in sections:
        if y > body_rect.bottom - 30:
            break
        s = h_f.render(head, True, (170, 200, 255))
        game.screen.blit(s, (x0, y))
        y += 28
        for line in _wrap_lines(b_f, body.replace("**", ""), content_w):
            if y > body_rect.bottom - 24:
                break
            game.screen.blit(b_f.render(line, True, dim), (x0, y))
            y += 24
        y += 10

    if y < body_rect.bottom - 20:
        game.screen.blit(
            sm.render("Имена внизу журнала — «Молчаливый», «Берсерк» и т.д. — смысл смотри по поведению в катке.", True, (130, 135, 150)),
            (x0, min(y, body_rect.bottom - 22)),
        )


def draw_evidence_journal_overlay(game):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 175))
    game.screen.blit(overlay, (0, 0))

    panel = _journal_panel_rect()
    pygame.draw.rect(game.screen, (28, 30, 42), panel, border_radius=10)
    pygame.draw.rect(game.screen, (130, 140, 170), panel, 2, border_radius=10)

    inner = panel.inflate(-28, -28)
    cw = inner.w

    title_f = pygame.font.Font(None, 30)
    sub_f = pygame.font.Font(None, 20)
    game.screen.blit(title_f.render("Журнал улик", True, WHITE), (inner.x, inner.y))
    game.screen.blit(
        sub_f.render("1) Галка = я уже увидел эту улику в катке.", True, (180, 190, 210)), (inner.x, inner.y + 28)
    )
    game.screen.blit(
        sub_f.render("2) Снизу — кто ещё подходит из семи вариантов в этом сценарии (лишние роли в игре не мешают).", True, (180, 190, 210)),
        (inner.x, inner.y + 50),
    )

    cfg = game.ghost_manager.abilities_config
    marked = {k: game.journal_evidence.get(k, False) for k in EVIDENCE_PROFILE_KEYS}
    candidates = filter_journal_suspects(cfg, marked)

    box_f = pygame.font.Font(None, 20)
    small_f = pygame.font.Font(None, 17)
    names_f = pygame.font.Font(None, 19)
    row0 = _journal_checkboxes_y0(inner)
    tx = inner.x + 34

    for i, (key, h_text, s_text) in enumerate(JOURNAL_EVIDENCE_HELP):
        row_y = row0 + i * JOURNAL_ROW_H
        cb = pygame.Rect(inner.x, row_y, JOURNAL_CB_SIZE, JOURNAL_CB_SIZE)
        on = game.journal_evidence.get(key, False)
        row_bg = pygame.Rect(inner.x - 8, row_y - 6, inner.w + 16, JOURNAL_ROW_H - 4)
        pygame.draw.rect(game.screen, (34, 37, 50) if not on else (28, 55, 45), row_bg, border_radius=7)
        _draw_journal_checkbox(game.screen, cb, on)
        game.screen.blit(box_f.render(h_text, True, (240, 242, 248)), (tx, row_y))
        help_w = max(0, cw - 40)
        hy = row_y + 22
        for li, wline in enumerate(_wrap_lines(small_f, s_text, help_w)):
            if li >= 2 or hy + 18 > panel.bottom - 100:
                break
            game.screen.blit(small_f.render(wline, True, (150, 160, 178)), (tx, hy))
            hy += 19

    list_top = row0 + len(JOURNAL_EVIDENCE_HELP) * JOURNAL_ROW_H + 10
    sep = pygame.Rect(inner.x, list_top - 2, inner.w, 1)
    pygame.draw.rect(game.screen, (90, 95, 115), sep)

    n_all = len(JOURNAL_LIST_PROFILE_IDS)
    cnt_f = pygame.font.Font(None, 20)
    stat_text = (
        f"Осталось вариантов: {len(candidates)} из {n_all} "
        "(по отмеченным уликам и признакам из ghost_abilities.ini — тип остаётся, если сходятся твои галки и его профиль)."
    )
    sty = list_top
    for sline in _wrap_lines(cnt_f, stat_text, cw):
        game.screen.blit(cnt_f.render(sline, True, (205, 215, 225)), (inner.x, sty))
        sty += 22

    name_top = sty + 6
    line_h = 20
    _pre_close, _ = _journal_close_rect(panel)
    list_bottom = _pre_close.top - 8
    if list_bottom < name_top + 40:
        list_bottom = name_top + 40
    list_w = inner.w

    y = name_top
    overflowed = False
    for idx, name in enumerate(candidates):
        if overflowed or y + line_h > list_bottom:
            break
        prof = cfg.get_profile(name)
        disp = (prof.get("display_name") or "").strip() or f"Тип {name}"
        wlines = _wrap_lines(names_f, f"·  {disp}  (класс {name}; выбрано по уликам)", list_w)
        for wl in wlines:
            if y + line_h > list_bottom:
                rest = max(0, len(candidates) - idx)
                game.screen.blit(
                    small_f.render(
                        f"…дальше не влезло (ещё ~{rest}). Сузи галками.",
                        True,
                        (170, 175, 195),
                    ),
                    (inner.x, min(y, list_bottom - line_h)),
                )
                overflowed = True
                break
            game.screen.blit(names_f.render(wl, True, (230, 232, 240)), (inner.x, y))
            y += line_h
        if overflowed:
            break
        y += 2

    if not candidates and any(marked.values()):
        game.screen.blit(
            small_f.render("Ни один из семи вариантов не подходит под отмеченное — сними лишние галки.", True, (255, 170, 170)),
            (inner.x, name_top),
        )

    close_rect, close_surf = _journal_close_rect(panel)
    pygame.draw.rect(game.screen, (42, 44, 58), close_rect, border_radius=5)
    pygame.draw.rect(game.screen, (200, 210, 230), close_rect, 1, border_radius=5)
    game.screen.blit(close_surf, close_surf.get_rect(center=close_rect.center))


def draw_menu(game):
    # Рисуем пробковую доску как фон (загружена один раз при инициализации)
    if hasattr(game, "cork_board_bg") and game.cork_board_bg:
        game.screen.blit(game.cork_board_bg, (0, 0))
    else:
        game.screen.fill(DARK_GRAY)

    font = pygame.font.Font(None, 72)

    title = font.render("Приключенческая игра", True, BLACK)
    title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 100))
    game.screen.blit(title, title_rect)

    font_small = pygame.font.Font(None, 36)
    subtitle = font_small.render("выбирете действие", True, BLACK)
    subtitle_rect = subtitle.get_rect(center=(SCREEN_WIDTH // 2, 160))
    game.screen.blit(subtitle, subtitle_rect)

    # Рисуем пины вместо обычных кнопок
    for button in game.menu_buttons:
        button.draw(game.screen)

def draw_shop(game):
    game.screen.fill((24, 26, 34))

    title_f = pygame.font.Font(None, 46)
    money_f = pygame.font.Font(None, 30)
    name_f = pygame.font.Font(None, 25)
    body_f = pygame.font.Font(None, 19)
    small_f = pygame.font.Font(None, 18)
    btn_f = pygame.font.Font(None, 22)

    title = title_f.render("МАГАЗИН", True, (238, 242, 248))
    game.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 48)))

    money_box = pygame.Rect(SCREEN_WIDTH - 230, 24, 188, 42)
    pygame.draw.rect(game.screen, (36, 42, 54), money_box, border_radius=8)
    pygame.draw.rect(game.screen, (88, 104, 130), money_box, 1, border_radius=8)
    money = money_f.render(f"$ {game.player_money}", True, (240, 226, 150))
    game.screen.blit(money, money.get_rect(center=money_box.center))

    back = game.shop_buttons[0]
    back_hover = back.rect.collidepoint(pygame.mouse.get_pos())
    pygame.draw.rect(game.screen, (126, 48, 52) if not back_hover else (166, 66, 70), back.rect, border_radius=7)
    pygame.draw.rect(game.screen, (235, 190, 190), back.rect, 1, border_radius=7)
    back_text = btn_f.render(back.text, True, (248, 248, 248))
    game.screen.blit(back_text, back_text.get_rect(center=back.rect.center))

    shop_items = [
        (1, "Фонарик", "фонарик", 50, "Базовый свет для тёмных комнат.", None),
        (2, "Красная пыль", "красная пыль", 30, "Расходник для защиты и ловушек.", ItemType.RED_DUST),
        (3, "Соль", "соль", 20, "Оставляет защитную зону на полу.", ItemType.SALT),
        (4, "Проектор", "проектор", 80, "Ставит область, куда призрак не заходит.", None),
        (5, "Аккумулятор", "аккумулятор", 40, "Питание для проектора.", ItemType.BATTERY),
        (6, "Крест", "крест", 60, "Короткая защита от призрака.", ItemType.CROSS),
        (7, "Кровь", "кровь", 35, "Восстанавливает запас жизней.", ItemType.BLOOD),
        (8, "Радио", "радио", 65, "Ответы и подсказки по призраку.", None),
        (9, "ЭМП", "эмп", 70, "Скан активности рядом с игроком.", None),
        (10, "УФ фонарь", "уф фонарь", 60, "Подсвечивает следы на полу.", None),
    ]

    card_w, card_h = 430, 82
    col_x = [62, 570]
    row_y = [112, 214, 316, 418, 520]
    mouse = pygame.mouse.get_pos()

    for pos, (btn_index, name, inv_key, price, desc, count_type) in enumerate(shop_items):
        col = 0 if pos < 5 else 1
        row = pos if pos < 5 else pos - 5
        card = pygame.Rect(col_x[col], row_y[row], card_w, card_h)
        bought = bool(game.inventory.get(inv_key, False))
        count = game.inventory_manager.item_counts.get(count_type, 0) if count_type else 0

        pygame.draw.rect(game.screen, (32, 36, 48), card, border_radius=8)
        pygame.draw.rect(game.screen, (84, 94, 116), card, 1, border_radius=8)

        icon_rect = pygame.Rect(card.x + 14, card.y + 16, 50, 50)
        pygame.draw.rect(game.screen, (45, 52, 68), icon_rect, border_radius=7)
        img = game.inventory_images.get(inv_key)
        if img:
            game.screen.blit(pygame.transform.smoothscale(img, (42, 42)), (icon_rect.x + 4, icon_rect.y + 4))
        else:
            fallback = name_f.render(name[:1], True, (224, 228, 236))
            game.screen.blit(fallback, fallback.get_rect(center=icon_rect.center))

        x = icon_rect.right + 14
        game.screen.blit(name_f.render(name, True, (238, 242, 248)), (x, card.y + 12))
        for i, line in enumerate(_wrap_lines(body_f, desc, 210)):
            if i >= 2:
                break
            game.screen.blit(body_f.render(line, True, (160, 170, 188)), (x, card.y + 38 + i * 18))

        price_surf = small_f.render(f"{price} монет", True, (238, 214, 130))
        game.screen.blit(price_surf, (card.right - 128, card.y + 12))

        if count_type:
            status = f"Есть: {count}"
            status_color = (175, 215, 190) if count else (148, 156, 172)
        else:
            status = "Куплено" if bought else "Не куплено"
            status_color = (175, 215, 190) if bought else (148, 156, 172)
        status_surf = small_f.render(status, True, status_color)
        game.screen.blit(status_surf, (card.right - 128, card.y + 34))

        btn = game.shop_buttons[btn_index]
        hover = btn.rect.collidepoint(mouse)
        can_buy = game.player_money >= price
        if not count_type and bought:
            btn_color = (64, 72, 86)
            label = "Есть"
        elif can_buy:
            btn_color = (52, 126, 82) if not hover else (66, 160, 104)
            label = "Купить"
        else:
            btn_color = (78, 78, 88)
            label = "Мало $"
        pygame.draw.rect(game.screen, btn_color, btn.rect, border_radius=7)
        pygame.draw.rect(game.screen, (178, 190, 206), btn.rect, 1, border_radius=7)
        label_surf = btn_f.render(label, True, (246, 248, 250))
        game.screen.blit(label_surf, label_surf.get_rect(center=btn.rect.center))

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
    controls_info = info_font.render("J: журнал  R: радио  E: ЭМП  T: УФ", True, WHITE)
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

    if getattr(game, "journal_open", False) and not game.show_save_prompt:
        draw_evidence_journal_overlay(game)
