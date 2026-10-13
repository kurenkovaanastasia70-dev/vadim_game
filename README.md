# Vadim Game

Собранная версия проекта для публикации в репозиторий.

## Запуск

1. Установите Python 3.11+.
2. Установите зависимости:
   - `pip install -r requirements.txt`
3. Запустите игру:
   - `python main_work.py`
4. (Опционально) Запустите редактор уровней:
   - `python level_editor.py`

## Проверка baseline

Запустите автоматические проверки без открытия окна игры:

```bash
python -m unittest discover -s tests -v
python tools_test_sanity.py
# GUI smoke test: opens a real Pygame window and saves screenshots to %TEMP%
python tools_test_gui.py
```

Тесты проверяют загрузку уровней, headless-игровой цикл, работу предметов и проектора, сохранение/загрузку, состояние призрака и переход между уровнями. GUI smoke test дополнительно проверяет реальные экраны меню, сохранений, сложности, бустов, игры, журнала и диалога выхода в меню.

## Основные файлы

- `main_work.py` — точка входа игры.
- `draws.py` — отрисовка экранов.
- `handlers.py` — обработка событий.
- `mechanics.py` — игровая механика и движение.
- `inventory_system.py` — система инвентаря.
- `ghost.py` — логика призраков.

## Данные и ресурсы

- `assets/` — графические ресурсы.
- `sprite_parts/` — кадры игрока.
- `level1.json`, `level2.json`, `levels_index.json` — уровни.
- `ghost_abilities.ini` — конфиг поведения призраков.

## Примечания

- `save.json` используется для локальных сохранений.
- Файл не нужно коммитить в репозиторий (см. `.gitignore`).
