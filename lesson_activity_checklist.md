# Чеклист занятия: задания, ачивки, бусты за счёт

**Локальный файл — вне git.** Не коммитить / не пушить.  
Формат: **смысл → идём по файлам сверху вниз → каждая важная строка: код / зачем / кто вызывает**.

Ветка: **`feature/level-tasks-achievements`** (после `4b96a38`).  
Фичи 1–3 (появление-drain, проклятая охота, магазин модов как на старом main) **на этой линии нет**.

```text
git checkout feature/level-tasks-achievements
git pull
python tools_test_sanity.py
```

Сложность для ручного прогона — **не Хардкор** (там setup = 0 сек).

---

# 0. Смысл фич (сказать до кода)

| Тема | Суть | Деньги |
|---|---|---|
| Задания выезда | Список **этого** уровня из `levels_index.json` | закрыл → **сессия** `player_money` |
| Достижения | Трофеи кампании из CSV/Google, как ачивки в играх | **не платят**. Только unlock + прогресс |
| Счёт | `global_money` | победа уровня **на счёт**; счёт тратится на **покупку бустов** |
| Буст | Один на выезд, **не бесплатный** | сначала купить за счёт, потом «Экипировать» или «Без буста» |

Одно событие (`buy_item`, `radio_answer`, `use_salt`) двигает **и** задание сессии, **и** ачивку — но награды разные.

| id буста | Эффект | Цена со счёта |
|---|---|---|
| `extra_slot` | носить 4 вместо 3 | 120 |
| `budget_boost` | +25$ сессии на этот выезд | 90 |
| `starter_candle` | 1 свеча в начале выезда | 70 |

Когда открывается `BOOST_PICK`:

1. **Новая игра** — после выбора сложности (`purpose="start"`).  
2. **Победа** — «Следующий уровень» (`purpose="next"`).  
3. **Загрузка слота** — этот экран **не** показывают.

Ачивки смотрят в **двух окнах** (одна и та же отрисовка):

- в деле: чип «Ачивки N/M» или клавиша **Y** → оверлей, игра на паузе;  
- в меню: пин «Достижения» → `GameState.ACHIEVEMENTS`.

---

# 1. Работаем по файлам

Порядок на занятии: данные → награды → бусты → экраны → клики → рисунок.

---

## Файл `gamestate.py`

**Зачем файл:** список экранов. Новые не путать с `SHOP`.

```python
WIN = "win"
BOOST_PICK = "boost_pick"      # купить / экипировать буст
ACHIEVEMENTS = "achievements"  # полный список из меню
```

| Строка | Зачем | Кто открывает |
|---|---|---|
| `BOOST_PICK` | отдельный экран, не магазин расходников | `open_boost_pick` |
| `ACHIEVEMENTS` | то же окно ачивок, но как страница меню | пин «Достижения» |

---

## Файл `levels_index.json`

**Зачем файл:** реестр уровней + задания **выезда** (не ачивки).

У каждого уровня блок:

```json
"tasks": [
  {
    "id": "l1_buy_1",
    "title": "Купить 1 предмет",
    "target": 1,
    "reward": 25,
    "event_key": "buy_item"
  }
]
```

| Поле | Зачем сказать ученику |
|---|---|
| `id` | внутреннее имя, чтобы сейв склеился с каталогом |
| `title` | текст в чипе «Задания» |
| `target` | сколько раз сделать действие |
| `reward` | сколько **session-$** |
| `event_key` | какое событие двигает прогресс |

**Кто читает:** `progression.resolve_task_catalog` → `new_tasks_for_level`.  
Нет `"tasks"` → `DEFAULT_TASK_CATALOG` в `progression.py`.

Уровень 1 сейчас: купить 1 предмет, 2 ответа по радио.  
Уровень 2: соль 2 раза, купить 2 предмета.

---

## Файл `local_lessons/achievements_catalog.csv`

**Зачем файл:** таблица трофеев, правится без Python.

```text
id,title,description,event_key,target,reward
first_buy,Первая покупка,Купить первый предмет,buy_item,1,20
radio_beginner,Связист,Получить 3 ответа по радио,radio_answer,3,30
salt_user,Соль готова,Использовать соль 3 раза,use_salt,3,25
candle_keeper,Хранитель огня,Купить свечу,buy_item,1,15
```

Построчно:

| Колонка | На экране |
|---|---|
| `title` | крупное имя («Связист») |
| `description` | **что сделать** («Получить 3 ответа по радио») |
| `event_key` + `target` | полоска `progress/target` |
| `reward` | в CSV можно оставить, **деньги из него не выдаются** |

**Кто читает:** `LocalAchievementTableProvider`, если нет Google URL.  
Порядок: `GOOGLE_SHEETS_ACHIEVEMENTS_CSV_URL` → этот CSV → `DEFAULT_ACHIEVEMENTS_TABLE`.

---

## Файл `inventory_system.py`

**Зачем файл:** предметы + каталог бустов + лимит карманов.

### 1. `MAX_CARRIED_ITEMS = 3`

Базовый лимит. Сам по себе не смотрит на буст.

### 2. `SESSION_BOOST_CATALOG` — сверху вниз каждая запись

```python
{"id": "extra_slot", "title": "Карман +1", "desc": "...", "cost": 120}
{"id": "budget_boost", "title": "Бюджет +25$", "desc": "...", "cost": 90}
{"id": "starter_candle", "title": "Стартовая свеча", "desc": "...", "cost": 70}
```

| Поле | Зачем |
|---|---|
| `id` | ключ в `owned_boosts` / `equipped_boost` |
| `title` / `desc` | карточка на `BOOST_PICK` |
| `cost` | цена **со счёта**, не из сессии |

**Кто читает:** `buy_session_boost`, `draw_boost_pick`, сейв.

### 3. `get_max_carried_items(game)`

```python
extra = 1 if getattr(game, "equipped_boost", None) == "extra_slot" else 0
return MAX_CARRIED_ITEMS + extra
```

- строка 1: буст экипирован **и** это карман?  
- строка 2: 3 или 4.

**Кто вызывает:** `can_receive_item`, `receive_item`, `buy_item`, кружки инвентаря в `draws`.

### 4. `can_receive_item` / `receive_item`

```python
return self.carried_slots_count() < get_max_carried_items(self.game)
# ...
self.game._show_game_info(f"Инвентарь полон: максимум {limit} предмета.", 1200)
```

Лимит спрашивает игру, а не всегда тройку.

В этом файле **не** списывают `global_money`. Покупка буста — в `main_work.buy_session_boost`.

---

## Файл `progression.py`

**Зачем файл:** задания сессии + трофеи. Деньги только у заданий.

### Провайдеры (уже были)

`LocalAchievementTableProvider.load_rows` — нет файла / пустой CSV → fallback.  
`GoogleSheetsAchievementTableProvider` — нет URL / ошибка сети → local.

### `resolve_task_catalog(level_id)`

```python
# 1) level_id или game.current_level_id
# 2) level_config.get_level_index()[level_id]["tasks"]
# 3) собрать id/title/target/reward/event_key
# 4) иначе DEFAULT_TASK_CATALOG
```

**Зачем:** «какой список заданий у **этого** выезда». Ачивки сюда не кладём.

### `new_tasks_for_level(level_id)`

Из каталога живые записи: `progress=0`, `done=False`, `claimed=False`.

**Кто вызывает:** `_after_level_ready`, `new_state`.

### `new_state()`

```python
tasks = self.new_tasks_for_level(current_level_id)
# + таблица ачивок из провайдера: progress=0, unlocked=False
```

### `normalize_state(tasks, achievements_table)`

Сейв накладывает progress/done/unlocked на **актуальный** каталог. Новые id из CSV появятся, старые лишние отвалятся.

### `progress_event` — сердце, построчно

```python
if value <= 0:
    return ProgressResult([])          # мусор не двигаем
```

Задания:

```python
if task["event_key"] != event_key or task["done"]:
    continue
task["progress"] = min(task["target"], task["progress"] + value)
if task["progress"] >= task["target"]:
    task["done"] = True
    if not task["claimed"]:
        task["claimed"] = True
        self.game.player_money += task["reward"]   # ТОЛЬКО СЕССИЯ
```

Ачивки:

```python
if ach["event_key"] != event_key or ach["unlocked"]:
    continue
ach["progress"] = min(...)
if ach["progress"] >= ach["target"]:
    ach["unlocked"] = True
    ach["claimed"] = True
    # global_money НЕ трогаем
    messages.append(f"Достижение разблокировано: {ach['title']}")
```

**Кто вызывает:** `Game.progress_event` ← `buy_item`, радио, соль.

### `unlock_achievement(id)`

Прямой unlock без денег, то же сообщение.

---

## Файл `main_work.py`

**Зачем файл:** кошельки, покупка буста, победа на счёт, сейв, пауза при окне ачивок.

### Импорт

```python
from inventory_system import InventoryManager, SESSION_BOOST_CATALOG, ItemType, get_max_carried_items
from progression import GoogleSheets..., Local..., TaskAchievementManager
```

### `__init__` — поля (сверху вниз)

Пины меню, индекс 5:

```python
PinButton(430, 500, ..., "Достижения")
self.achievements_back_button = Button(...)
```

Бусты:

```python
self.boost_equip_button / boost_skip_button / boost_back_button
self.owned_boosts = {}       # что куплено (навсегда в слоте)
self.equipped_boost = None   # что надето на этот выезд
self.selected_boost_id = None
self.boost_pick_purpose = "next"  # "start" | "next"
```

Кошельки и панели:

```python
self.player_money = 100          # сессия, магазин расходников
self.global_money = 0            # счёт: победы − покупка бустов
self.tasks_panel_open = False
# провайдер CSV/Google
self.progress_manager = TaskAchievementManager(...)
self.tasks, self.achievements_table = self.progress_manager.new_state()
self.achievements_panel_open = False
```

### `is_gameplay_paused` (оба места одинаковые)

```python
return bool(
    self.show_save_prompt
    or self.journal_open
    or getattr(self, "achievements_panel_open", False)  # окно ачивок = пауза
    or self.state in (GAME_OVER, WIN)
)
```

**Зачем:** пока читаешь трофеи, призрак не бьёт.

### Бусты, построчно

`owns_boost(id)` — флажок в `owned_boosts`.

`buy_session_boost(id)`:

```python
meta = ... из SESSION_BOOST_CATALOG
# уже куплено? → сообщение, False
# global_money < cost? → «Не хватает денег на счёте», False
self.global_money -= cost
self.owned_boosts[id] = True
self.selected_boost_id = id   # сразу можно экипировать
```

`open_boost_pick(purpose)`:

```python
if purpose == "next" and not self.has_next_level():
    return False
self.boost_pick_purpose = purpose
self.set_state(GameState.BOOST_PICK)
```

`apply_equipped_boost_inventory`:

```python
# только starter_candle И только если куплен
inventory["свеча"] = True
increase_count(CANDLE, 1)
```

`_commit_boost_and_enter_game(boost_id)`:

```python
self.equipped_boost = boost_id          # None = без буста
if budget_boost и куплен: player_money += 25
if purpose == "start":
    apply свечу → GAME
else:
    advance_to_next_level()
```

`equip_selected_boost_and_advance` — нельзя экипировать то, что не куплено.  
`skip_boost_and_advance` — `None`, выезд без буста.

### `_after_level_ready`

```python
self.tasks = self.progress_manager.new_tasks_for_level(self.current_level_id)
# achievements_table НЕ трогаем
```

Вызывать после каждого успешного load: `load_level_by_id`, ветки `load_level_for_current_level`.

### `reset_for_new_game`

```python
player_level = 1
current_level_id = первый из реестра
owned_boosts = {}
equipped_boost = None
global_money = 0
# задания+ачивки заново
```

### `buy_item`

```python
if not can_receive_item: лимит get_max_carried_items
player_money -= cost          # сессия
progress_event("buy_item", 1) # задание и/или ачивка
```

### `progress_event` (обёртка)

```python
result = self.progress_manager.progress_event(...)
if result.messages:
    self._show_game_info(result.messages[0], 1500)
self.autosave_current_slot()
```

### `enter_win`

```python
reward = breakdown["total"]
self.global_money += reward   # НА СЧЁТ, не в сессию
# report money_after = global_money
set_state(WIN)
```

### save / load

В сейв: `global_money`, `equipped_boost`, `owned_boosts` (список id), `CANDLE` в `item_counts`, `achievements_table`, `tasks`.

Из сейва: `owned_boosts` только известные id; `equipped_boost` только если буст **куплен**.

### `draw` loop

```python
elif ACHIEVEMENTS: draws.draw_achievements_window(self, standalone=True)
elif BOOST_PICK:   draws.draw_boost_pick(self)
```

---

## Файл `handlers.py`

**Зачем файл:** только клики. Деньги не считает.

### Меню

```python
i==0 ... i==4  # как было
i==5: game.push_state(GameState.ACHIEVEMENTS)
```

### `handle_achievements_menu_events`

```python
Назад / X / Esc → go_back()
```

### Сложность

```python
reset_for_new_game()
autosave_current_slot()
open_boost_pick(purpose="start")   # НЕ сразу GAME
```

Загрузка слота по-прежнему `set_state(GAME)`.

### Победа

«Следующий уровень» / Enter → `open_boost_pick()` (purpose по умолчанию `next`).

### `handle_boost_pick_events` построчно

```python
# 1) клик по «Купить» на карточке → buy_session_boost
# 2) клик по купленной карточке → selected_boost_id
# 3) Экипировать → equip_selected_boost_and_advance
# 4) Без буста → skip_boost_and_advance
# 5) Назад / Esc → DIFF если start, иначе WIN
# 1/2/3 — выбрать, если уже куплено; Space — без буста
```

### Игра: ачивки

```python
чип «Ачивки» → achievements_panel_open = not ...
Y → то же; закрывает журнал
Esc / X / клик мимо окна → закрыть
пока открыто — клики в мир не идут
```

Чип «Задания» по-прежнему маленький попап (не путать с окном ачивок).

`handle_event`: ветки `ACHIEVEMENTS` и `BOOST_PICK`.

---

## Файл `draws.py`

**Зачем файл:** картинка. Деньги не меняет.

Вспомогательные:

| Функция | Зачем |
|---|---|
| `_fit_text` | обрезка с «…», текст не вылезает из прямоугольника |
| `_screen_wh` | реальный размер окна (полноэкран 819×614 ≠ 1024×768) |

### HUD

Только `сессия` / `счёт` / `LV` / `SAN`. Без огромных панелей.

Подсказка setup — **под** HUD. Пока она висит, чип «Ачивки» уезжает вправо (`x=470`), чтобы квадраты не пересекались.

Баннер «фаза окончена» ниже (y≈318). Радио — около y=248.

### Магазин `draw_shop`

Шапка: «Назад» слева, деньги справа (`сессия $ / счёт $`), таймер **слева от денег**, не поверх.  
Карточки 2×6 от `sw/sh`. Кнопка «Купить» **внутри** правой колонки карточки (hitbox = то, что нарисовано).

### `draw_boost_pick`

Заголовок, `счёт $`, три карточки с **ценой**.  
Не куплено → «Купить» / «Мало $». Куплено → клик выбрать.  
Снизу: Назад / Без буста / Экипировать (серое, пока не куплен выбранный).

### `draw_achievements_window(game, standalone=False)` — построчно

```python
if standalone:   # страница меню: фон + кнопка Назад
else:            # оверлей в деле: затемнение
panel по центру
заголовок «Достижения» + «Открыто N из M»
кнопка X → achievements_close_rect
для каждой ачивки:
    СДЕЛАНО / ЕЩЁ НЕТ
    title
    description   # что нужно сделать — читаемый текст
    полоска progress/target
```

**Кто вызывает:**  
`draw()` если `ACHIEVEMENTS` (`standalone=True`);  
конец `draw_game` если `achievements_panel_open` (`standalone=False`).

### Чипы в `draw_game`

- «Ачивки N/M» — только ярлык, **не** список. Список в большом окне.  
- «Задания N/M» — по клику попап: полное имя + `прогресс +$`.

Меню/журнал привязаны к `sw` (`topright`), чтобы на узком экране не уезжали за край.

---

## Файл `tools_test_sanity.py`

Прогон без окна:

- задание → session-$;  
- ачивка → `global_money` не растёт;  
- рисуется окно ачивок, `push_state(ACHIEVEMENTS)`;  
- буст без покупки экипировать нельзя;  
- покупка списывает счёт; `skip` → `equipped_boost is None`.

```text
python tools_test_sanity.py
```

---

# 2. Сквозная шпаргалка

| Событие | Файл | Куда |
|---|---|---|
| Закрыл задание выезда | `progression.progress_event` | сессия +$ |
| Открыл ачивку | тот же `progress_event` | трофей, без денег |
| Победа | `enter_win` | счёт +$ |
| Купить расходник | `buy_item` | сессия − |
| Купить буст | `buy_session_boost` | счёт − |
| Экипировать / без буста | `_commit_boost_and_enter_game` | эффект на выезд |
| Старт уровня | `_after_level_ready` | новые `tasks`, ачивки живы |
| Чип / Y | `handlers` + `draw_achievements_window` | окно в деле |
| Пин «Достижения» | меню → `ACHIEVEMENTS` | то же окно |

---

# 3. Порядок на занятии

1. `gamestate.py` — `BOOST_PICK`, `ACHIEVEMENTS`  
2. `levels_index.json` + CSV — данные  
3. `progression.py` — session-$ vs unlock без денег  
4. `inventory_system.py` — каталог + `cost` + лимит слотов  
5. `main_work.py` — кошельки, `buy_session_boost`, win на счёт, `_after_level_ready`  
6. `handlers.py` — сложность → бусты; чип/Y; пин меню  
7. `draws.py` — HUD без наложений, магазин, окно ачивок, карточки бустов  
8. `tools_test_sanity.py` + ручной прогон  

---

# 4. Ручной прогон

1. Меню → пин **Достижения**: видны названия, «что сделать», `0/N`, «ЕЩЁ НЕТ». Назад.  
2. Новая игра → сложность → экран бустов. Без покупки «Экипировать» серое. **Без буста** → уровень 1.  
3. В деле чип «Ачивки» / **Y**: то же окно, пауза. X или Esc.  
4. Чип «Задания»: текст цели и `+$` сессии.  
5. Компьютер: таймер **не** на деньгах; «Купить» внутри карточки.  
6. Купить предмет → сессия +$ (задание); ачивка «Первая покупка» без денег на счёт.  
7. Победа → «На счёт: +…$». Следующий уровень → купить буст со счёта → Экипировать.  
8. `extra_slot`: 4 кружка. `starter_candle`: свеча сразу. Нет денег → «Мало $» / «Без буста».
