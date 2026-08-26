# Чеклист занятия: `feature/phasmo-events-dual-money`

Локальный файл (можно не коммитить в «чистый» code PR — сейчас в ветке для урока).  
Формат: **смысл → карта файлов → уже есть / дописать → построчно → проверка**.

---

## 0. Подготовка

```text
git checkout feature/phasmo-events-dual-money
python tools_test_sanity.py
```

Сложность для ручного прогона — не Хардкор (setup = 0 сек).

---

## Уже на main (не повторять с нуля)

| Фича | Где |
|---|---|
| Конец фазы подготовки (hint / таймер в ПК / баннер / радио) | `main_work.py`, `draws.py`, `handlers.py` |
| Свеча (firelight) | `inventory_system.py`, `main_work.py`, магазин |
| Sanity MVP (drain, порог охоты, setup floor) | `main_work.py` |

---

# Фича 1. Появление призрака (простой вариант) (~20 мин)

## 1.1. Смысл

Событие активности → призрак **виден** рядом и идёт к игроку (как раньше).  
**−рассудок сразу при появлении на карте**, не от касания.  
Касание только «шипит» и завершает ивент. HP во время ивента не снимаем.

## 1.2. Карта файлов

| Файл | Роль |
|---|---|
| `main_work.py` | `SANITY_GHOST_EVENT_*`, `start/end/tick_ghost_appearance_event`, вызов из `trigger_activity_event` |
| `ghost.py` | `begin/end_appearance_event`, пауза FSM |

## 1.3. Порядок

1. Константы drain/длительность/скорость/дистанция  
2. `start_ghost_appearance_event` — спавн + **сразу** `drain_sanity`  
3. `tick_ghost_appearance_event` — движение; касание без второго drain  
4. В `ghost.py` — begin/end + early-return в update  
5. В игровом цикле — `tick_ghost_appearance_event()`; HP-gate с `ghost_event_active`

## 1.4. Проверка

```text
python tools_test_sanity.py
# sanity падает при start_*, не при касании
```

---

# Фича 2. Проклятая охота (~25 мин)

## 2.1. Смысл

Как выпиливали ранее / wiki Phasmo: старт **только** от cursed possession (у нас — радио ~22%).  
Игнор порога sanity и кулдауна; grace 1 с; +20 с ко всем охотам контракта.

## 2.2. Карта файлов

| Файл | Роль |
|---|---|
| `main_work.py` | `CURSED_HUNT_*`, grace, `start_activity_hunt(cursed=…)`, `try_start_cursed_hunt_from_possession` |
| `inventory_system.py` | Radio → шанс cursed hunt |

## 2.3. Порядок

1. Константы + поля `hunt_grace_ticks` / `hunt_is_cursed` / `contract_hunt_extension_seconds`  
2. `is_hunt_grace_period` / `is_hunt_chasing` / длительность с extension  
3. `start_activity_hunt(cursed=False/True)`  
4. `try_start_cursed_hunt_from_possession`  
5. serialize/restore hunt + radio text  
6. Radio.use — шанс вызова  

## 2.4. Проверка

```text
# при sanity 100 и большом кулдауне start_activity_hunt(cursed=True) == True
# grace == 1*FPS, extension == 20
```

---

# Фича 3. Два баланса денег (~30 мин)

## 3.1. Смысл (дизайн)

| Баланс | На что тратим | Как пополняем |
|---|---|---|
| **Сессия** (`player_money`) | Предметы магазина на текущем выезде | Бюджет в начале уровня (`SESSION_BUDGET_BY_DIFFICULTY` + мод); мелкий tip в конце setup (`SESSION_SETUP_TIP`) |
| **Счёт** (`global_money`) | Постоянные **модификации инвентаря** | Награда за победу; награды заданий/ачивок |

Сессионные деньги **не** копятся бесконечно: `grant_session_budget()` выставляет фиксированный бюджет на выезд.  
Победа **не** кормит session-магазин — только счёт (анти-накликивание расходников за реплеи).

## 3.2. Модификации (за счёт)

| id | Эффект | Цена |
|---|---|---|
| `extra_slot` | лимит ношения +1 | 120 |
| `budget_boost` | session-бюджет +25 | 90 |
| `starter_candle` | в начале уровня есть свеча | 70 |

## 3.3. Карта файлов

| Файл | Роль |
|---|---|
| `main_work.py` | `global_money`, `inventory_mods`, `grant_session_budget`, `buy_inventory_mod`, win→global, save/load |
| `progression.py` | награды задач/ачивок → `global_money` |
| `inventory_system.py` | `max_carried_items` учитывает мод |
| `draws.py` | HUD/магазин: сессия + счёт; карточки модов |
| `handlers.py` | кнопки модов 13–15 |

## 3.4. Порядок

1. Константы бюджетов + каталог модов  
2. Поля + save/load  
3. `grant_session_budget` / `_after_level_ready` / setup tip  
4. `enter_win` → `global_money`  
5. `buy_inventory_mod` + UI + handlers  
6. progression → global  

## 3.5. Проверка

```text
python tools_test_sanity.py
# buy_inventory_mod списывает global; grant_session_budget задаёт session; win увеличивает global
```

---

## Ручной прогон (10 мин)

1. Новый слот → в магазине видны **сессия** и **счёт**.  
2. Купить расходник за сессию; мод за счёт (сначала выиграть или выставить global в тесте).  
3. Дождаться appearance: sanity падает в момент появления.  
4. Радио вне setup: иногда проклятая охота.  
5. Победа: растёт **счёт**, session на следующем уровне снова бюджет.
