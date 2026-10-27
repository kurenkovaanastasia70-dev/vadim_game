"""Absolute project paths shared by runtime modules and tests."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "assets"
SPRITE_PARTS_DIR = PROJECT_ROOT / "sprite_parts"
DATA_DIR = PROJECT_ROOT / "data"
MENU_BACKGROUND_FILE = PROJECT_ROOT / "menu_background.png"
DEFAULT_LEVEL_BACKGROUND_FILE = ASSETS_DIR / "backgroung_lvl1.jpg"
ACHIEVEMENTS_FILE = DATA_DIR / "achievements_catalog.csv"
SAVE_FILE = PROJECT_ROOT / "save.json"
