import pygame
import math
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
import level_config
from inventory_system import ItemType, MAX_CARRIED_ITEMS
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
        "freezing_temperature",
        "Низкая температура",
        "Градусник показывает холод в любимой комнате: отметь, если температура резко ниже обычной.",
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


def _draw_crt_atmosphere(game):
    """Легкая ретро-постобработка без новых ассетов: tint, scanlines, шум и тревожная вспышка."""
    now = pygame.time.get_ticks()
    threat = game.threat_level() if hasattr(game, "threat_level") else 0.0

    tint = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    tint.fill((18, 45, 38, 34))
    game.screen.blit(tint, (0, 0))

    # Красная вспышка только при реальной угрозе и заметно слабее прежней.
    if threat > 0.45:
        pulse = 0.5 + 0.5 * ((now // 180) % 2)
        danger_alpha = int(8 + 22 * (threat - 0.45) / 0.55 * pulse)
        danger = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        danger.fill((96, 28, 32, danger_alpha))
        game.screen.blit(danger, (0, 0))

    line_alpha = 34 + int(18 * threat)
    scanlines = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    for y in range(0, SCREEN_HEIGHT, 4):
        pygame.draw.line(scanlines, (0, 0, 0, line_alpha), (0, y), (SCREEN_WIDTH, y))
    game.screen.blit(scanlines, (0, 0))

    noise = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    step = 32
    offset = (now // 90) % step
    for y in range(-offset, SCREEN_HEIGHT, step):
        for x in range((y + offset) % 47, SCREEN_WIDTH, 96):
            alpha = 10 + int(28 * threat)
            noise.fill((220, 255, 230, alpha), (x, y, 2, 1))
    game.screen.blit(noise, (0, 0))

    vignette = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    edge = int(80 + 45 * threat)
    pygame.draw.rect(vignette, (0, 0, 0, edge), (0, 0, SCREEN_WIDTH, 28))
    pygame.draw.rect(vignette, (0, 0, 0, edge), (0, SCREEN_HEIGHT - 28, SCREEN_WIDTH, 28))
    pygame.draw.rect(vignette, (0, 0, 0, edge), (0, 0, 28, SCREEN_HEIGHT))
    pygame.draw.rect(vignette, (0, 0, 0, edge), (SCREEN_WIDTH - 28, 0, 28, SCREEN_HEIGHT))
    game.screen.blit(vignette, (0, 0))


def _draw_compact_status_hud(game):
    has_thermometer = game.inventory.get("градусник", False)
    hud_x, hud_y, hud_w, hud_h = 22, 16, 400, 132 if has_thermometer else 112
    hud_bg = pygame.Surface((hud_w, hud_h), pygame.SRCALPHA)
    hud_bg.fill((19, 25, 24, 218))
    game.screen.blit(hud_bg, (hud_x, hud_y))
    pygame.draw.rect(game.screen, (118, 156, 132), (hud_x, hud_y, hud_w, hud_h), 2, border_radius=6)

    font = pygame.font.Font(None, 24)
    small = pygame.font.Font(None, 20)
    hp = max(0, int(getattr(game, "player_hp", 0)))
    threat = game.threat_level() if hasattr(game, "threat_level") else 0.0
    sanity = max(0, min(100, int(round(getattr(game, "player_sanity", 100.0)))))
    if sanity >= 70:
        sanity_color = (146, 210, 178)
    elif sanity >= 50:
        sanity_color = (230, 206, 116)
    else:
        sanity_color = (225, 110, 90)

    game.screen.blit(small.render("HP", True, (145, 170, 160)), (hud_x + 12, hud_y + 10))
    for i in range(5):
        color = (225, 82, 82) if i < hp else (63, 74, 70)
        _draw_pixel_heart(game.screen, hud_x + 12 + i * 22, hud_y + 32, 2, color)

    rows = [
        ("$", str(getattr(game, "player_money", 0)), (230, 206, 116)),
        ("LV", str(getattr(game, "player_level", 1)), (146, 210, 178)),
        ("SAN", f"{sanity}%", sanity_color),
    ]
    x = hud_x + 132
    for label, value, color in rows:
        game.screen.blit(small.render(label, True, (145, 170, 160)), (x, hud_y + 10))
        val = font.render(value, True, color)
        game.screen.blit(val, (x, hud_y + 32))
        x += 78

    activity = max(0, min(100, int(getattr(game, "ghost_activity", 0))))
    activity_label = small.render(f"Активность призрака: {activity}%", True, (145, 170, 160))
    game.screen.blit(activity_label, (hud_x + 12, hud_y + 52))

    # Полоска рассудка (как sanity meter в Phasmophobia).
    sanity_bar = pygame.Rect(hud_x + 12, hud_y + 72, hud_w - 24, 8)
    pygame.draw.rect(game.screen, (42, 54, 49), sanity_bar, border_radius=4)
    sanity_fill = int(sanity_bar.w * (sanity / 100))
    if sanity_fill:
        pygame.draw.rect(game.screen, sanity_color, (sanity_bar.x, sanity_bar.y, sanity_fill, sanity_bar.h), border_radius=4)
    pygame.draw.rect(game.screen, (92, 118, 108), sanity_bar, 1, border_radius=4)

    bar = pygame.Rect(hud_x + 176, hud_y + 56, hud_w - 188, 8)
    pygame.draw.rect(game.screen, (42, 54, 49), bar, border_radius=4)
    fill_w = int(bar.w * max(threat, activity / 100))
    if fill_w:
        pygame.draw.rect(game.screen, (180, 46, 54), (bar.x, bar.y, fill_w, bar.h), border_radius=4)
    pygame.draw.rect(game.screen, (92, 118, 108), bar, 1, border_radius=4)

    if has_thermometer:
        temperature = game.get_current_temperature_c() if hasattr(game, "get_current_temperature_c") else None
        temp_value = "-- C" if temperature is None else f"{temperature:.1f} C"
        game.screen.blit(small.render("TEMP", True, (145, 170, 160)), (hud_x + 12, hud_y + 90))
        game.screen.blit(font.render(temp_value, True, (116, 207, 226)), (hud_x + 64, hud_y + 88))


def _draw_pixel_heart(screen, x, y, scale, color):
    pixels = (
        "01100110",
        "11111111",
        "11111111",
        "01111110",
        "00111100",
        "00011000",
    )
    shadow = (22, 15, 18)
    for row, line in enumerate(pixels):
        for col, bit in enumerate(line):
            if bit == "1":
                rect = pygame.Rect(x + col * scale, y + row * scale, scale, scale)
                pygame.draw.rect(screen, shadow, rect.move(scale, scale))
                pygame.draw.rect(screen, color, rect)


def _draw_retro_button(screen, button, active=False):
    mouse = pygame.mouse.get_pos()
    hovered = button.rect.collidepoint(mouse)
    bg = (31, 43, 39) if not hovered else (45, 66, 58)
    border = (214, 238, 207) if active else ((133, 196, 156) if hovered else (96, 132, 116))
    text_color = (235, 246, 238)
    pygame.draw.rect(screen, (5, 8, 7), button.rect.move(3, 3), border_radius=6)
    pygame.draw.rect(screen, bg, button.rect, border_radius=6)
    pygame.draw.rect(screen, border, button.rect, 2, border_radius=6)
    label = pygame.font.Font(None, 23).render(button.text, True, text_color)
    screen.blit(label, label.get_rect(center=button.rect.center))

EVIDENCE_LABELS = {key: label.split("[", 1)[0].strip() for key, label, _help in JOURNAL_EVIDENCE_HELP}


def _draw_radio_feedback(game):
    if pygame.time.get_ticks() >= getattr(game, "radio_feedback_until", 0):
        return
    announcement = getattr(game, "radio_announcement", None)
    panel_h = 72 if announcement else 54
    # Ниже журнала/меню и не пересекается с левым HUD (HUD ~ x0-420, y16-148).
    panel = pygame.Rect(SCREEN_WIDTH // 2 - 220, 170, 440, panel_h)
    surf = pygame.Surface(panel.size, pygame.SRCALPHA)
    surf.fill((14, 18, 24, 210))
    game.screen.blit(surf, panel.topleft)
    border = (120, 215, 190) if getattr(game, "radio_feedback_ok", False) else (205, 150, 90)
    pygame.draw.rect(game.screen, border, panel, 2, border_radius=7)

    font = pygame.font.Font(None, 22)
    small = pygame.font.Font(None, 20)
    if announcement:
        label = "Радио — база"
        game.screen.blit(font.render(label, True, (230, 236, 240)), (panel.x + 14, panel.y + 8))
        for i, line in enumerate(_wrap_lines(small, announcement, panel.w - 28)):
            if i >= 2:
                break
            game.screen.blit(small.render(line, True, (190, 210, 200)), (panel.x + 14, panel.y + 32 + i * 18))
        return

    label = "Радио: частота поймана" if getattr(game, "radio_feedback_ok", False) else "Радио: шум и помехи"
    game.screen.blit(font.render(label, True, (230, 236, 240)), (panel.x + 14, panel.y + 8))

    tick = pygame.time.get_ticks() // 70
    base_y = panel.y + 38
    for i in range(20):
        h = 4 + ((i * 7 + tick * 5) % 16)
        x = panel.x + 14 + i * 17
        pygame.draw.line(game.screen, border, (x, base_y - h // 2), (x, base_y + h // 2), 2)


def _format_setup_mmss(game):
    ticks = max(0, int(getattr(game, "setup_phase_ticks", 0)))
    seconds = ticks // max(1, 60)
    mm, ss = divmod(seconds, 60)
    return f"{mm:02d}:{ss:02d}", seconds


def _computer_setup_timer_active(game):
    ticks = max(0, int(getattr(game, "setup_phase_ticks", 0)))
    banner_until = int(getattr(game, "setup_complete_banner_until", 0) or 0)
    return ticks > 0 or pygame.time.get_ticks() < banner_until


def _draw_setup_shop_timer(game):
    """Единственный setup-таймер: только внутри экрана компьютера (магазин)."""
    if not _computer_setup_timer_active(game):
        return
    # Между «Назад» и деньгами, без пересечения с title/карточками.
    panel = pygame.Rect(620, 18, 160, 50)
    money = pygame.Rect(SCREEN_WIDTH - 230, 24, 188, 42)
    back = pygame.Rect(36, 28, 120, 36)
    if panel.colliderect(money):
        panel.right = money.left - 10
    if panel.colliderect(back):
        panel.left = back.right + 10

    ticks = max(0, int(getattr(game, "setup_phase_ticks", 0)))
    now = pygame.time.get_ticks()
    time_text, seconds = _format_setup_mmss(game)
    show_end = ticks <= 0

    bg = pygame.Surface(panel.size, pygame.SRCALPHA)
    bg.fill((12, 16, 18, 235))
    game.screen.blit(bg, panel.topleft)
    border = (120, 200, 160) if ticks > 0 else (220, 150, 90)
    pygame.draw.rect(game.screen, border, panel, 2, border_radius=6)

    tiny = pygame.font.Font(None, 18)
    big = pygame.font.Font(None, 36)
    game.screen.blit(tiny.render("SETUP", True, (145, 170, 160)), (panel.x + 8, panel.y + 3))
    pulse = (now // 250) % 2 == 0 if 0 < seconds <= 10 or show_end else True
    color = (255, 210, 120) if seconds <= 10 or show_end else (230, 240, 236)
    if pulse:
        value = big.render(time_text, True, color)
        game.screen.blit(value, value.get_rect(center=(panel.centerx, panel.y + panel.h * 0.62)))


def _draw_computer_interact_tip(game, computer_screen_rect):
    """Подсказка над компьютером на карте (без таймера)."""
    if not getattr(game, "near_computer", False):
        return
    tip_text = "Клик: открыть компьютер"
    font = pygame.font.Font(None, 24)
    text_surface = font.render(tip_text, True, WHITE)
    padding = 10
    tip_rect = pygame.Rect(
        0,
        0,
        text_surface.get_width() + padding * 2,
        text_surface.get_height() + padding * 2,
    )
    tip_rect.centerx = computer_screen_rect.centerx
    tip_rect.bottom = computer_screen_rect.top - 8
    tip_rect.x = max(8, min(tip_rect.x, SCREEN_WIDTH - tip_rect.w - 8))
    tip_rect.y = max(8, tip_rect.y)
    pygame.draw.rect(game.screen, DARK_GRAY, tip_rect)
    pygame.draw.rect(game.screen, WHITE, tip_rect, 2)
    game.screen.blit(text_surface, text_surface.get_rect(center=tip_rect.center))


def _draw_setup_complete_banner(game):
    """Баннер конца setup — ниже радио, без пересечения с HUD/кнопками."""
    banner_until = int(getattr(game, "setup_complete_banner_until", 0) or 0)
    if pygame.time.get_ticks() >= banner_until:
        return
    banner = pygame.Rect(SCREEN_WIDTH // 2 - 240, 256, 480, 44)
    banner_bg = pygame.Surface(banner.size, pygame.SRCALPHA)
    banner_bg.fill((28, 16, 14, 220))
    game.screen.blit(banner_bg, banner.topleft)
    pygame.draw.rect(game.screen, (220, 120, 80), banner, 2, border_radius=6)
    msg = pygame.font.Font(None, 26).render(
        "ФАЗА ПОДГОТОВКИ ОКОНЧЕНА",
        True,
        (255, 220, 190),
    )
    game.screen.blit(msg, msg.get_rect(center=banner.center))


def _draw_setup_find_computer_message(game):
    """Короткое оранжевое предупреждение без цифр таймера (~2 сек)."""
    until = int(getattr(game, "setup_timer_hint_until", 0) or 0)
    if pygame.time.get_ticks() >= until:
        return
    # Под HUD слева, не пересекается с меню/журналом справа.
    has_thermometer = bool(game.inventory.get("градусник", False))
    hud_bottom = 16 + (132 if has_thermometer else 112)
    panel = pygame.Rect(22, hud_bottom + 8, 440, 48)
    bg = pygame.Surface(panel.size, pygame.SRCALPHA)
    bg.fill((40, 22, 8, 230))
    game.screen.blit(bg, panel.topleft)
    pygame.draw.rect(game.screen, (255, 150, 40), panel, 2, border_radius=6)
    font = pygame.font.Font(None, 24)
    small = pygame.font.Font(None, 20)
    game.screen.blit(
        font.render("Таймер setup — внутри компьютера", True, (255, 180, 80)),
        (panel.x + 12, panel.y + 6),
    )
    game.screen.blit(
        small.render("Найди компьютер на карте и открой его.", True, (255, 200, 140)),
        (panel.x + 12, panel.y + 26),
    )


def _draw_lit_candles(game):
    candles = getattr(game, "lit_candles", None) or []
    if not candles:
        return
    now = pygame.time.get_ticks()
    for candle in candles:
        cx = int(candle["x"] - getattr(game, "camera_x", 0))
        cy = int(candle["y"] - getattr(game, "camera_y", 0))
        flicker = 0.7 + 0.3 * abs(math.sin(now / 140.0 + candle["x"] * 0.01))
        glow = pygame.Surface((120, 120), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 170, 60, int(45 * flicker)), (60, 60), 48)
        pygame.draw.circle(glow, (255, 220, 120, int(90 * flicker)), (60, 60), 18)
        game.screen.blit(glow, glow.get_rect(center=(cx, cy)))
        pygame.draw.rect(game.screen, (180, 140, 70), (cx - 4, cy - 2, 8, 14), border_radius=2)
        pygame.draw.circle(game.screen, (255, 220, 90), (cx, cy - 8), 4)


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


def _blit_centered_icon(screen, icon, rect, size):
    if not icon:
        return
    fitted = pygame.transform.scale(icon, (size, size))
    screen.blit(fitted, fitted.get_rect(center=rect.center))


def _journal_panel_rect():
    w = min(720, max(400, SCREEN_WIDTH - 32))
    h = min(600, max(420, SCREEN_HEIGHT - 20))
    return pygame.Rect((SCREEN_WIDTH - w) // 2, (SCREEN_HEIGHT - h) // 2, w, h)


def _journal_content_width(panel):
    return panel.w - 28 * 2


JOURNAL_ROW_H = 50
JOURNAL_CB_SIZE = 24
EVIDENCE_STATE_UNKNOWN = "unknown"
EVIDENCE_STATE_CONFIRMED = "confirmed"
EVIDENCE_STATE_EXCLUDED = "excluded"


def _journal_checkboxes_y0(inner):
    """Верхний край первого чекбокса (две фиксированные строки вступления под заголовком)."""
    return inner.y + 78


def _journal_close_rect(panel):
    """Одна и та же геометрия кнопки «Закрыть» для hit-test и отрисовки."""
    f = pygame.font.Font(None, 22)
    label = f.render("Закрыть  ·  J / Esc  ·  снаружи", True, (235, 238, 245))
    pad_x, pad_y = 12, 8
    w = min(label.get_width() + pad_x * 2, max(0, panel.w - 188))
    h = max(34, label.get_height() + pad_y * 2)
    r = pygame.Rect(panel.left + 10, panel.bottom - h - 6, w, h)
    # не вылезать за края панели и оставлять место под reset справа
    m = 6
    if r.left < panel.left + m:
        r.x = panel.left + m
    right_limit = panel.right - 178
    if r.right > right_limit:
        r.x = max(panel.left + m, right_limit - r.w)
    return r, label


def _journal_reset_rect(panel):
    f = pygame.font.Font(None, 21)
    label = f.render("Сбросить догадки", True, (245, 230, 230))
    pad_x, pad_y = 10, 8
    w = label.get_width() + pad_x * 2
    h = max(34, label.get_height() + pad_y * 2)
    x = panel.right - w - 14
    y = panel.bottom - h - 8
    return pygame.Rect(x, y, w, h), label


def _journal_confirm_reset_rect(panel):
    f = pygame.font.Font(None, 21)
    label = f.render("Подтвердить", True, (255, 242, 242))
    pad_x, pad_y = 10, 8
    w = label.get_width() + pad_x * 2
    h = max(34, label.get_height() + pad_y * 2)
    reset_rect, _ = _journal_reset_rect(panel)
    x = reset_rect.x - w - 8
    y = reset_rect.y
    return pygame.Rect(x, y, w, h), label


def journal_get_checkbox_rects(panel):
    """Прямоугольники чекбоксов в экранных координатах."""
    inner = panel.inflate(-28, -28)
    y0 = _journal_checkboxes_y0(inner)
    out = {}
    for i, (key, _h, _s) in enumerate(JOURNAL_EVIDENCE_HELP):
        out[key] = pygame.Rect(inner.x, y0 + i * JOURNAL_ROW_H, JOURNAL_CB_SIZE, JOURNAL_CB_SIZE)
    return out


def _journal_candidate_area(game, panel):
    inner = panel.inflate(-28, -28)
    cfg = game.ghost_manager.abilities_config
    marked = {k: game.journal_evidence.get(k, EVIDENCE_STATE_UNKNOWN) for k in EVIDENCE_PROFILE_KEYS}
    candidates = filter_journal_suspects(cfg, marked)
    row0 = _journal_checkboxes_y0(inner)
    list_top = row0 + len(JOURNAL_EVIDENCE_HELP) * JOURNAL_ROW_H + 10
    cnt_f = pygame.font.Font(None, 20)
    stat_text = f"Осталось вариантов: {len(candidates)} из {len(JOURNAL_LIST_PROFILE_IDS)}."
    sty = list_top
    for sline in _wrap_lines(cnt_f, stat_text, inner.w):
        sty += 22
    name_top = sty + 8
    close_rect, _ = _journal_close_rect(panel)
    list_bottom = max(name_top + 40, close_rect.top - 8)
    return inner, candidates, name_top, list_bottom


def journal_get_candidate_rects(game, panel):
    inner, candidates, name_top, list_bottom = _journal_candidate_area(game, panel)
    rects = {}
    row_h = 26
    y = name_top
    for name in candidates:
        if y + row_h > list_bottom:
            break
        rects[name] = pygame.Rect(inner.x, y, inner.w, row_h - 2)
        y += row_h
    return rects


def evidence_journal_hit_test(game, pos):
    panel = _journal_panel_rect()
    if not panel.collidepoint(pos):
        return "outside"
    close, _ = _journal_close_rect(panel)
    if close.collidepoint(pos):
        return "close"
    reset_rect, _ = _journal_reset_rect(panel)
    if reset_rect.collidepoint(pos):
        return "reset"
    if getattr(game, "journal_reset_confirm", False):
        confirm_rect, _ = _journal_confirm_reset_rect(panel)
        if confirm_rect.collidepoint(pos):
            return "confirm_reset"
    for key, r in journal_get_checkbox_rects(panel).items():
        if r.collidepoint(pos):
            return key
    for profile_id, r in journal_get_candidate_rects(game, panel).items():
        if r.collidepoint(pos):
            return ("guess", profile_id)
    return None


def _draw_journal_checkbox(screen, rect, state):
    fill = (34, 37, 49)
    border = (122, 132, 156)
    if state == EVIDENCE_STATE_CONFIRMED:
        fill = (32, 84, 58)
        border = (96, 215, 148)
    elif state == EVIDENCE_STATE_EXCLUDED:
        fill = (84, 42, 42)
        border = (236, 125, 125)
    pygame.draw.rect(screen, fill, rect, border_radius=5)
    pygame.draw.rect(screen, border, rect, 2, border_radius=5)
    if state == EVIDENCE_STATE_CONFIRMED:
        a = (rect.left + 6, rect.centery)
        b = (rect.left + 10, rect.bottom - 7)
        c = (rect.right - 5, rect.top + 7)
        pygame.draw.line(screen, (238, 255, 244), a, b, 3)
        pygame.draw.line(screen, (238, 255, 244), b, c, 3)
    elif state == EVIDENCE_STATE_EXCLUDED:
        pygame.draw.line(screen, (255, 226, 226), (rect.left + 6, rect.top + 6), (rect.right - 6, rect.bottom - 6), 3)
        pygame.draw.line(screen, (255, 226, 226), (rect.right - 6, rect.top + 6), (rect.left + 6, rect.bottom - 6), 3)


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
            "Касание призрака = минус жизнь. **Дело J** открывает журнал улик, **Меню** — выход с сохранением.",
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
    intro_lines = [
        "ЛКМ: неизвестно -> видел -> исключено.",
        "Список снизу считает и подтверждения, и исключения.",
    ]
    iy = inner.y + 28
    for intro in intro_lines:
        for line in _wrap_lines(sub_f, intro, cw):
            game.screen.blit(sub_f.render(line, True, (180, 190, 210)), (inner.x, iy))
            iy += 21

    cfg = game.ghost_manager.abilities_config
    marked = {k: game.journal_evidence.get(k, EVIDENCE_STATE_UNKNOWN) for k in EVIDENCE_PROFILE_KEYS}
    candidates = filter_journal_suspects(cfg, marked)

    box_f = pygame.font.Font(None, 20)
    small_f = pygame.font.Font(None, 17)
    names_f = pygame.font.Font(None, 19)
    row0 = _journal_checkboxes_y0(inner)
    tx = inner.x + 34

    for i, (key, h_text, s_text) in enumerate(JOURNAL_EVIDENCE_HELP):
        row_y = row0 + i * JOURNAL_ROW_H
        cb = pygame.Rect(inner.x, row_y, JOURNAL_CB_SIZE, JOURNAL_CB_SIZE)
        state = game.journal_evidence.get(key, EVIDENCE_STATE_UNKNOWN)
        row_bg = pygame.Rect(inner.x - 8, row_y - 6, inner.w + 16, JOURNAL_ROW_H - 4)
        if state == EVIDENCE_STATE_CONFIRMED:
            row_color = (28, 55, 45)
        elif state == EVIDENCE_STATE_EXCLUDED:
            row_color = (68, 38, 40)
        else:
            row_color = (34, 37, 50)
        pygame.draw.rect(game.screen, row_color, row_bg, border_radius=7)
        _draw_journal_checkbox(game.screen, cb, state)
        game.screen.blit(box_f.render(h_text, True, (240, 242, 248)), (tx, row_y))
        state_text = "не отмечено"
        state_color = (170, 175, 190)
        if state == EVIDENCE_STATE_CONFIRMED:
            state_text = "видел"
            state_color = (150, 235, 190)
        elif state == EVIDENCE_STATE_EXCLUDED:
            state_text = "исключено"
            state_color = (245, 170, 170)
        badge = small_f.render(state_text, True, state_color)
        game.screen.blit(badge, (inner.right - badge.get_width(), row_y + 2))
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
    stat_text = f"Осталось вариантов: {len(candidates)} из {n_all}."
    sty = list_top
    for sline in _wrap_lines(cnt_f, stat_text, cw):
        game.screen.blit(cnt_f.render(sline, True, (205, 215, 225)), (inner.x, sty))
        sty += 22

    _inner, _candidates, name_top, list_bottom = _journal_candidate_area(game, panel)
    row_h = 26
    y = name_top
    for idx, name in enumerate(candidates):
        if y + row_h > list_bottom:
            rest = max(0, len(candidates) - idx)
            if rest:
                game.screen.blit(
                    small_f.render(f"…ещё {rest}. Сузи галками.", True, (170, 175, 195)),
                    (inner.x, min(y, list_bottom - 18)),
                )
            break
        prof = cfg.get_profile(name)
        disp = (prof.get("display_name") or "").strip() or f"Тип {name}"
        row_rect = pygame.Rect(inner.x, y, inner.w, row_h - 2)
        mouse = pygame.mouse.get_pos()
        hovered = row_rect.collidepoint(mouse)
        pygame.draw.rect(game.screen, (42, 48, 64) if not hovered else (56, 68, 92), row_rect, border_radius=5)
        pygame.draw.rect(game.screen, (90, 104, 132), row_rect, 1, border_radius=5)
        label = f"Выбрать: {disp}  (тип {name})"
        game.screen.blit(names_f.render(label, True, (235, 238, 246)), (row_rect.x + 8, row_rect.y + 4))
        y += row_h

    confirm_mode = getattr(game, "journal_reset_confirm", False)
    reset_rect, reset_label = _journal_reset_rect(panel)
    pygame.draw.rect(game.screen, (96, 42, 46), reset_rect, border_radius=8)
    pygame.draw.rect(game.screen, (196, 110, 118), reset_rect, 1, border_radius=8)
    game.screen.blit(
        reset_label,
        (
            reset_rect.centerx - reset_label.get_width() // 2,
            reset_rect.centery - reset_label.get_height() // 2,
        ),
    )
    if confirm_mode:
        confirm_rect, confirm_label = _journal_confirm_reset_rect(panel)
        pygame.draw.rect(game.screen, (122, 54, 54), confirm_rect, border_radius=8)
        pygame.draw.rect(game.screen, (236, 168, 168), confirm_rect, 1, border_radius=8)
        game.screen.blit(
            confirm_label,
            (
                confirm_rect.centerx - confirm_label.get_width() // 2,
                confirm_rect.centery - confirm_label.get_height() // 2,
            ),
        )
        hint = small_f.render("Сброс удалит все отметки.", True, (235, 190, 190))
        game.screen.blit(hint, (inner.x, reset_rect.y + 10))

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
        game.screen.fill((84, 58, 36))

    shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    shade.fill((18, 10, 6, 82))
    game.screen.blit(shade, (0, 0))

    title_card = pygame.Rect(SCREEN_WIDTH // 2 - 270, 54, 540, 118)
    pygame.draw.rect(game.screen, (238, 224, 190), title_card, border_radius=5)
    pygame.draw.rect(game.screen, (94, 62, 38), title_card, 3, border_radius=5)
    pygame.draw.line(game.screen, (145, 38, 38), (title_card.left + 24, title_card.bottom - 22), (title_card.right - 24, title_card.bottom - 22), 3)

    font = pygame.font.Font(None, 64)
    title = font.render("ДЕЛО О ПРИЗРАКЕ", True, (42, 30, 22))
    game.screen.blit(title, title.get_rect(center=(title_card.centerx, title_card.y + 42)))

    font_small = pygame.font.Font(None, 26)
    subtitle = font_small.render("доска расследования • выбери следующую улику", True, (68, 48, 34))
    game.screen.blit(subtitle, subtitle.get_rect(center=(title_card.centerx, title_card.y + 82)))

    pin_centers = [button.rect.center for button in game.menu_buttons]
    thread_pairs = [(0, 2), (2, 1), (0, 3), (2, 4), (3, 4)]
    for a, b in thread_pairs:
        if a < len(pin_centers) and b < len(pin_centers):
            pygame.draw.line(game.screen, (128, 25, 28), pin_centers[a], pin_centers[b], 3)
            pygame.draw.line(game.screen, (210, 72, 65), pin_centers[a], pin_centers[b], 1)

    note_font = pygame.font.Font(None, 22)
    notes = [
        (pygame.Rect(84, 176, 176, 58), "ЭМП скачет"),
        (pygame.Rect(765, 150, 160, 60), "следы в УФ"),
        (pygame.Rect(735, 610, 176, 58), "радио шумит"),
    ]
    for rect, text in notes:
        pygame.draw.rect(game.screen, (226, 211, 164), rect, border_radius=4)
        pygame.draw.rect(game.screen, (93, 68, 41), rect, 2, border_radius=4)
        game.screen.blit(note_font.render(text, True, (52, 38, 28)), (rect.x + 12, rect.y + 18))

    ghost_x, ghost_y = SCREEN_WIDTH // 2, 228
    ghost_surf = pygame.Surface((150, 130), pygame.SRCALPHA)
    pygame.draw.ellipse(ghost_surf, (20, 26, 25, 150), (30, 8, 90, 104))
    pygame.draw.circle(ghost_surf, (225, 245, 230, 95), (58, 48), 6)
    pygame.draw.circle(ghost_surf, (225, 245, 230, 95), (92, 48), 6)
    pygame.draw.polygon(ghost_surf, (20, 26, 25, 150), [(32, 86), (48, 116), (64, 88), (82, 118), (98, 88), (118, 116), (120, 82)])
    game.screen.blit(ghost_surf, ghost_surf.get_rect(center=(ghost_x, ghost_y)))

    for y in range(0, SCREEN_HEIGHT, 5):
        pygame.draw.line(game.screen, (0, 0, 0, 26), (0, y), (SCREEN_WIDTH, y))

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

    _draw_setup_shop_timer(game)

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
        (8, "Радио", "радио", 65, "Ответы и подсказки по призраку.", ItemType.RADIO),
        (9, "ЭМП", "эмп", 70, "Скан активности рядом с игроком.", None),
        (10, "УФ фонарь", "уф фонарь", 60, "Подсвечивает следы на полу.", None),
        (11, "Градусник", "градусник", 55, "Показывает температуру текущей комнаты.", None),
        (12, "Свеча", "свеча", 25, "Firelight: рядом рассудок падает медленнее.", ItemType.CANDLE),
    ]

    card_w, card_h = 430, 68
    col_x = [62, 570]
    row_y = [88, 162, 236, 310, 384, 458, 532]
    mouse = pygame.mouse.get_pos()

    for pos, (btn_index, name, inv_key, price, desc, count_type) in enumerate(shop_items):
        col = 0 if pos < 7 else 1
        row = pos if pos < 7 else pos - 7
        card = pygame.Rect(col_x[col], row_y[row], card_w, card_h)
        bought = bool(game.inventory.get(inv_key, False))
        count = game.inventory_manager.item_counts.get(count_type, 0) if count_type else 0

        pygame.draw.rect(game.screen, (32, 36, 48), card, border_radius=8)
        pygame.draw.rect(game.screen, (84, 94, 116), card, 1, border_radius=8)

        icon_rect = pygame.Rect(card.x + 14, card.y + 16, 50, 50)
        pygame.draw.rect(game.screen, (45, 52, 68), icon_rect, border_radius=7)
        img = game.inventory_images.get(inv_key)
        if img:
            _blit_centered_icon(game.screen, img, icon_rect, 42)
        else:
            fallback = name_f.render(name[:1], True, (224, 228, 236))
            game.screen.blit(fallback, fallback.get_rect(center=icon_rect.center))

        x = icon_rect.right + 14
        game.screen.blit(name_f.render(name, True, (238, 242, 248)), (x, card.y + 12))
        for i, line in enumerate(_wrap_lines(body_f, desc, 210)):
            if i >= 1:
                break
            game.screen.blit(body_f.render(line, True, (160, 170, 188)), (x, card.y + 38 + i * 18))

        side_x = card.right - 118
        price_surf = small_f.render(f"{price} монет", True, (238, 214, 130))
        game.screen.blit(price_surf, (side_x, card.y + 10))

        if count_type:
            status = f"Есть: {count}"
            status_color = (175, 215, 190) if count else (148, 156, 172)
        else:
            status = "Куплено" if bought else "Не куплено"
            status_color = (175, 215, 190) if bought else (148, 156, 172)
        status_surf = small_f.render(status, True, status_color)
        game.screen.blit(status_surf, (side_x, card.y + 30))

        btn = game.shop_buttons[btn_index]
        btn.rect = pygame.Rect(card.right - 104, card.y + 51, 90, 24)
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

def draw_game_over(game):
    game.screen.fill((18, 12, 16))

    title_font = pygame.font.Font(None, 72)
    body_font = pygame.font.Font(None, 30)
    hint_font = pygame.font.Font(None, 24)

    reason = getattr(game, "game_over_reason", "hp")
    title_text = "Игра окончена"
    body_text = "HP закончились. Можно начать заново или вернуться в меню."
    if reason == "wrong_ghost":
        title_text = "Ошибка расследования"
        body_text = "Вы выбрали неверного призрака."

    title = title_font.render(title_text, True, (235, 72, 72))
    game.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 120)))

    body = body_font.render(body_text, True, (235, 230, 225))
    game.screen.blit(body, body.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 58)))

    hint = hint_font.render("Enter - заново, Esc - в меню", True, (170, 164, 158))
    game.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 22)))

    for button in game.game_over_buttons:
        button.draw(game.screen)


def draw_win(game):
    game.screen.fill((9, 14, 18))
    for y in range(0, SCREEN_HEIGHT, 18):
        shade = 18 + y * 30 // max(1, SCREEN_HEIGHT)
        pygame.draw.line(game.screen, (8, shade, 20), (0, y), (SCREEN_WIDTH, y))

    panel = pygame.Rect(0, 0, 690, 620)
    panel.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
    shadow = panel.move(10, 12)
    pygame.draw.rect(game.screen, (2, 5, 7), shadow, border_radius=18)
    pygame.draw.rect(game.screen, (24, 34, 34), panel, border_radius=18)
    pygame.draw.rect(game.screen, (114, 219, 157), panel, 3, border_radius=18)

    glow = pygame.Surface((panel.w - 44, 76), pygame.SRCALPHA)
    glow.fill((88, 183, 128, 44))
    game.screen.blit(glow, (panel.x + 22, panel.y + 22))

    title_font = pygame.font.Font(None, 66)
    body_font = pygame.font.Font(None, 30)
    small_font = pygame.font.Font(None, 24)
    badge_font = pygame.font.Font(None, 22)

    ghost_name = getattr(game, "win_ghost_name", "призрак")
    has_next = game.has_next_level()
    next_level_id = getattr(game, "win_next_level_id", None)
    next_meta = level_config.get_level_index().get(next_level_id, {}) if next_level_id else {}
    next_name = next_meta.get("name", "следующий уровень")
    report = getattr(game, "win_report", {}) or {}
    evidence_keys = report.get("found_evidence", [])
    evidence_names = [EVIDENCE_LABELS.get(key, key) for key in evidence_keys]
    evidence_text = ", ".join(evidence_names) if evidence_names else "улики не отмечены в журнале"
    reward = int(report.get("reward", 0) or 0)
    reward_base = int(report.get("reward_base", reward) or 0)
    reward_diff = int(report.get("reward_difficulty_bonus", 0) or 0)
    reward_evidence = int(report.get("reward_evidence_bonus", 0) or 0)
    money_after = int(report.get("money_after", getattr(game, "player_money", 0)) or 0)
    report_next_name = report.get("next_level_name") or ("финал кампании" if not has_next else next_name)

    # Анимация начисления: сумма "набегает" за ~0.9 сек после победы.
    win_started = getattr(game, "win_entered_at", None)
    if win_started is None:
        anim_t = 1.0
    else:
        anim_t = min(1.0, (pygame.time.get_ticks() - win_started) / 900.0)
    ease = 1.0 - (1.0 - anim_t) ** 3
    shown_reward = int(round(reward * ease))
    shown_balance = money_after - reward + shown_reward

    title = title_font.render("Победа!", True, (172, 255, 194))
    game.screen.blit(title, title.get_rect(center=(panel.centerx, panel.y + 72)))

    badge = pygame.Rect(panel.centerx - 150, panel.y + 112, 300, 34)
    pygame.draw.rect(game.screen, (45, 75, 64), badge, border_radius=16)
    pygame.draw.rect(game.screen, (138, 229, 170), badge, 1, border_radius=16)
    badge_text = badge_font.render("Расследование завершено", True, (228, 247, 235))
    game.screen.blit(badge_text, badge_text.get_rect(center=badge.center))

    lines = [
        f"Вы верно определили тип: {ghost_name}.",
        "Улики совпали, журнал подтверждён, дело закрыто.",
    ]
    if has_next:
        lines.append(f"Открыт переход: {next_name}.")
        hint_text = "Enter - следующий уровень | R - заново | Esc - меню"
    else:
        lines.append("Это финал текущей цепочки уровней.")
        hint_text = "Enter - заново | Esc - меню"

    y = panel.y + 168
    for line in lines:
        for wrapped in _wrap_lines(body_font, line, panel.w - 104):
            text = body_font.render(wrapped, True, (230, 240, 232))
            game.screen.blit(text, text.get_rect(center=(panel.centerx, y)))
            y += 32
        y += 2

    report_box = pygame.Rect(panel.x + 58, panel.y + 268, panel.w - 116, 128)
    pygame.draw.rect(game.screen, (19, 28, 30), report_box, border_radius=12)
    pygame.draw.rect(game.screen, (72, 117, 94), report_box, 1, border_radius=12)

    # Подсветка строки с деньгами во время начисления.
    money_glow = pygame.Surface((report_box.w - 16, 28), pygame.SRCALPHA)
    money_glow.fill((255, 214, 120, int(40 + 50 * (1.0 - abs(ease - 0.55) * 1.6))))
    game.screen.blit(money_glow, (report_box.x + 8, report_box.y + 52))

    report_lines = [
        f"Найденные улики: {evidence_text}",
        f"Доход: +{shown_reward}$  (база {reward_base} + сложность {reward_diff} + улики {reward_evidence})",
    ]
    report_lines += [
        f"Баланс: {shown_balance}$",
        f"Дальше: {report_next_name}",
    ]
    ry = report_box.y + 10
    for idx, line in enumerate(report_lines):
        color = (255, 230, 150) if idx in (1, 2) else (205, 226, 212)
        for wrapped in _wrap_lines(small_font, line, report_box.w - 28):
            game.screen.blit(small_font.render(wrapped, True, color), (report_box.x + 14, ry))
            ry += 22

    pygame.draw.line(game.screen, (76, 116, 92), (panel.x + 70, panel.y + 410), (panel.right - 70, panel.y + 410), 2)

    hint = small_font.render(hint_text, True, (166, 194, 174))
    game.screen.blit(hint, hint.get_rect(center=(panel.centerx, panel.y + 430)))

    for button in game.win_buttons:
        button.draw(game.screen)


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
    game.inventory_manager.draw(game.screen, game.camera_x, game.camera_y)

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
            game.player_animation_frame %= len(frames)
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
    _draw_lit_candles(game)

    player_screen_rect = game.player_rect.move(-game.camera_x, -game.camera_y)
    player_visual_size = getattr(game, "player_visual_size", game.player_size)
    player_draw_rect = pygame.Rect(0, 0, player_visual_size, player_visual_size)
    player_draw_rect.center = player_screen_rect.center
    
    # отрисовка персонажа
    if sprite:
        game.screen.blit(sprite, player_draw_rect.topleft)
    else:  # fallback — если спрайты не загрузились
        pygame.draw.ellipse(game.screen, (235, 205, 170), player_draw_rect.inflate(-player_visual_size // 3, -player_visual_size // 2))
        pygame.draw.rect(game.screen, (58, 105, 165), player_draw_rect.inflate(-player_visual_size // 4, -player_visual_size // 5), border_radius=8)

    # Активный предмет в руке: если ничего не выбрано, но фонарик куплен — держим фонарик по умолчанию.
    if (
        getattr(game.inventory_manager, "active_hand_item", None) is None
        and game.inventory.get("фонарик", False)
    ):
        game.inventory_manager.active_hand_item = ItemType.FLASHLIGHT

    active_item = getattr(game.inventory_manager, "active_hand_item", None)
    if active_item == ItemType.FLASHLIGHT:
        ps = player_visual_size
        sz = max(28, int(ps * 0.38))
        pr = player_draw_rect
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
            hand_img = pygame.transform.scale(game.inventory_images["фонарик"], (sz, sz))
            game.screen.blit(hand_img, hand_rect.topleft)
        else:
            # Fallback, если иконка не загружена: жёлтый квадратик-фонарик.
            pygame.draw.rect(game.screen, (245, 220, 90), hand_rect)
            pygame.draw.rect(game.screen, (80, 65, 20), hand_rect, 1)


    # Отрисовка компьютера
    computer_screen_rect = None
    if game.computer and game.computer_rect:
        computer_screen_rect = game.computer_rect.move(-game.camera_x, -game.camera_y)
        comp_img = game.computer
        if comp_img.get_size() != computer_screen_rect.size:
            comp_img = pygame.transform.smoothscale(comp_img, computer_screen_rect.size)
        game.screen.blit(comp_img, computer_screen_rect.topleft)

    # Эффект затемнения: фонарик влияет только на видимость, не на sanity drain.
    flashlight_lit = bool(
        game.inventory.get("фонарик", False) and getattr(game, "flashlight_on", False)
    )
    if flashlight_lit:
        room_overlay = game._create_room_visibility_overlay()
        game.screen.blit(room_overlay, (0, 0))
    else:
        clipped_overlay = game._create_clipped_vignette_overlay()
        game.screen.blit(clipped_overlay, (0, 0))

    _draw_crt_atmosphere(game)
    game.inventory_manager.draw_dropped_items(game.screen, game.camera_x, game.camera_y)

    # Подпись у компьютера (без таймера — таймер только в магазине).
    if computer_screen_rect is not None:
        _draw_computer_interact_tip(game, computer_screen_rect)
    
    mouse_pos = pygame.mouse.get_pos()
    purchased_items = game.inventory_manager.visible_inventory_names()
    consumable_name_to_count = {
        "аккумулятор": game.inventory_manager.get_count(ItemType.BATTERY),
        "кровь": game.inventory_manager.get_count(ItemType.BLOOD),
        "свеча": game.inventory_manager.get_count(ItemType.CANDLE),
        "крест": game.inventory_manager.get_count(ItemType.CROSS),
        "красная пыль": game.inventory_manager.get_count(ItemType.RED_DUST),
        "соль": game.inventory_manager.get_count(ItemType.SALT),
        "радио": game.inventory_manager.get_count(ItemType.RADIO),
    }

    # Верхние игровые кнопки: магазин убран, журнал вынесен как явная кнопка "Дело".
    for button in game.game_buttons:
        _draw_retro_button(game.screen, button)
    if hasattr(game, "journal_button"):
        _draw_retro_button(game.screen, game.journal_button, active=getattr(game, "journal_open", False))

    _draw_compact_status_hud(game)
    _draw_setup_find_computer_message(game)
    _draw_radio_feedback(game)
    _draw_setup_complete_banner(game)

    # Инвентарь: прозрачные круги внизу экрана, та же геометрия используется в handlers.py.
    slot_font = pygame.font.Font(None, 18)
    qty_font = pygame.font.Font(None, 20)
    name_font = pygame.font.Font(None, 19)
    active_item = getattr(game.inventory_manager, "active_hand_item", None)
    hovered_name = None
    total_slots = max(MAX_CARRIED_ITEMS, len(purchased_items))
    for i in range(total_slots):
        item_name = purchased_items[i] if i < len(purchased_items) else None
        cx, cy, radius = mechanics.inventory_slot_screen(i)
        circle_rect = pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2)
        hovered = ((mouse_pos[0] - cx) ** 2 + (mouse_pos[1] - cy) ** 2) <= radius ** 2
        item_type = game.inventory_manager.item_type_from_name(item_name) if item_name else None
        is_active = item_type is not None and item_type == active_item
        fill = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        fill_alpha = 145 if hovered or is_active else (76 if item_name else 38)
        pygame.draw.circle(fill, (238, 244, 255, fill_alpha), (radius, radius), radius)
        game.screen.blit(fill, circle_rect.topleft)
        border = (255, 235, 150) if is_active else ((235, 245, 255) if hovered else ((160, 175, 190) if item_name else (92, 108, 120)))
        pygame.draw.circle(game.screen, border, (cx, cy), radius, 2)

        if item_name:
            icon = game.inventory_images.get(item_name)
            if icon:
                _blit_centered_icon(game.screen, icon, circle_rect, max(26, radius * 2 - 12))
            else:
                fallback = name_font.render(item_name[:1].upper(), True, (38, 43, 52))
                game.screen.blit(fallback, fallback.get_rect(center=circle_rect.center))
        else:
            pygame.draw.circle(game.screen, (120, 138, 150), (cx, cy), max(3, radius // 8), 1)

        key_surf = slot_font.render(str(i + 1), True, (235, 240, 248))
        key_bg = pygame.Rect(circle_rect.left + 1, circle_rect.top + 1, 16, 15)
        pygame.draw.rect(game.screen, (35, 40, 50), key_bg, border_radius=4)
        game.screen.blit(key_surf, key_surf.get_rect(center=key_bg.center))

        qty = consumable_name_to_count.get(item_name) if item_name else None
        if qty is not None:
            qty_surf = qty_font.render(f"x{qty}", True, (255, 245, 190))
            qty_bg = pygame.Rect(circle_rect.right - qty_surf.get_width() - 8, circle_rect.bottom - 18, qty_surf.get_width() + 6, 16)
            pygame.draw.rect(game.screen, (38, 34, 26), qty_bg, border_radius=5)
            game.screen.blit(qty_surf, qty_surf.get_rect(center=qty_bg.center))

        if hovered and item_name:
            hovered_name = item_name

    if hovered_name:
        label = name_font.render(f"{hovered_name}  |  ПКМ выбросить", True, (245, 248, 252))
        lx = max(8, min(SCREEN_WIDTH - label.get_width() - 18, mouse_pos[0] - label.get_width() // 2))
        ly = max(8, mouse_pos[1] - 34)
        tip_rect = pygame.Rect(lx - 7, ly - 5, label.get_width() + 14, label.get_height() + 8)
        tip_bg = pygame.Surface((tip_rect.w, tip_rect.h), pygame.SRCALPHA)
        tip_bg.fill((32, 36, 46, 220))
        game.screen.blit(tip_bg, tip_rect.topleft)
        pygame.draw.rect(game.screen, (170, 185, 205), tip_rect, 1, border_radius=5)
        game.screen.blit(label, (lx, ly))

    # Компактная панель прогресса + раскрытие ачивок по наведению
    panel_w, panel_h = 320, 92
    panel_x = SCREEN_WIDTH - panel_w - 20
    panel_y = 150
    panel_bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel_bg.fill((236, 228, 210, 205))
    game.screen.blit(panel_bg, (panel_x, panel_y))
    pygame.draw.rect(game.screen, (95, 77, 56), (panel_x, panel_y, panel_w, panel_h), 2)

    panel_font = pygame.font.Font(None, 22)
    y = panel_y + 8
    active_tasks = [t for t in getattr(game, "tasks", []) if not t.get("done")]
    for task in active_tasks[:2]:
        status = f"{task.get('progress', 0)}/{task.get('target', 0)}"
        short_title = str(task.get("title", task.get("id", "")))[:22]
        row = f"{short_title}: {status}"
        game.screen.blit(panel_font.render(row, True, (44, 37, 30)), (panel_x + 8, y))
        y += 22

    unlocked = sum(1 for a in getattr(game, "achievements_table", []) if a.get("unlocked"))
    total = len(getattr(game, "achievements_table", []))
    ach_row = f"Ачивки {unlocked}/{total} (наведи)"
    ach_text_surface = panel_font.render(ach_row, True, (44, 37, 30))
    ach_text_pos = (panel_x + 8, panel_y + panel_h - 24)
    game.screen.blit(ach_text_surface, ach_text_pos)
    ach_hover_rect = pygame.Rect(ach_text_pos[0], ach_text_pos[1], ach_text_surface.get_width(), ach_text_surface.get_height())

    achievement_rows = []
    for ach in getattr(game, "achievements_table", []):
        mark = "[x]" if ach.get("unlocked") else "[ ]"
        title = str(ach.get("title", ach.get("id", "")))
        desc = str(ach.get("description", "")).strip()
        progress = f"{ach.get('progress', 0)}/{ach.get('target', 0)}"
        row = f"{mark} {title}: {desc} ({progress})" if desc else f"{mark} {title} ({progress})"
        achievement_rows.append(row)
    popup_h = min(340, 12 + max(1, len(achievement_rows)) * 34)
    popup_rect = pygame.Rect(panel_x, panel_y + panel_h + 6, 430, popup_h)
    show_ach_popup = ach_hover_rect.collidepoint(mouse_pos) or popup_rect.collidepoint(mouse_pos)

    if show_ach_popup:
        popup_bg = pygame.Surface((popup_rect.w, popup_rect.h), pygame.SRCALPHA)
        popup_bg.fill((245, 239, 226, 225))
        game.screen.blit(popup_bg, popup_rect.topleft)
        pygame.draw.rect(game.screen, (95, 77, 56), popup_rect, 2)
        popup_font = pygame.font.Font(None, 21)
        max_text_w = popup_rect.w - 18
        if achievement_rows:
            for i, row in enumerate(achievement_rows[:10]):
                row_y = popup_rect.y + 7 + i * 34
                if i % 2 == 0:
                    pygame.draw.rect(game.screen, (234, 225, 209), (popup_rect.x + 4, row_y - 1, popup_rect.w - 8, 32))
                text = row
                while popup_font.size(text)[0] > max_text_w and len(text) > 4:
                    text = text[:-4] + "..."
                game.screen.blit(popup_font.render(text, True, (44, 37, 30)), (popup_rect.x + 8, row_y))
        else:
            game.screen.blit(popup_font.render("Нет ачивок", True, (60, 50, 40)), (popup_rect.x + 8, popup_rect.y + 8))
        
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
