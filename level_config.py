import os
import json
from typing import Any, Dict, Optional


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(BASE_DIR, "levels_index.json")

_LEVEL_INDEX: Optional[Dict[str, Dict[str, Any]]] = None


def _load_index() -> Dict[str, Dict[str, Any]]:
    """
    Загружает реестр уровней из levels_index.json.
    Возвращает словарь {level_id: meta}.
    """
    if not os.path.isfile(INDEX_FILE):
        return {}

    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки реестра уровней: {e}")
        return {}

    levels = data.get("levels", [])
    index: Dict[str, Dict[str, Any]] = {}
    for level in levels:
        level_id = level.get("id")
        if level_id:
            index[level_id] = level
    return index


def get_level_index() -> Dict[str, Dict[str, Any]]:
    """
    Лениво загружает и кеширует реестр уровней.
    """
    global _LEVEL_INDEX
    if _LEVEL_INDEX is None:
        _LEVEL_INDEX = _load_index()
    return _LEVEL_INDEX


def get_level_file_path(level_id: str) -> Optional[str]:
    """
    Возвращает полный путь к JSON-файлу уровня по его id.
    """
    meta = get_level_index().get(level_id)
    if not meta:
        return None
    filename = meta.get("file")
    if not filename:
        return None
    return os.path.join(BASE_DIR, filename)


def get_level_by_number(number: int) -> Optional[Dict[str, Any]]:
    """
    Возвращает метаданные уровня по его порядковому номеру (number),
    если такое поле указано в levels_index.json.
    """
    for meta in get_level_index().values():
        if meta.get("number") == number:
            return meta
    return None


def get_level_file_path_by_number(number: int) -> Optional[str]:
    """
    Возвращает путь к файлу уровня по его порядковому номеру.
    """
    meta = get_level_by_number(number)
    if not meta:
        return None
    filename = meta.get("file")
    if not filename:
        return None
    return os.path.join(BASE_DIR, filename)

