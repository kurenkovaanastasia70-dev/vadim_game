import csv
import os
from dataclasses import dataclass
from typing import Dict, List
from urllib.error import URLError
from urllib.request import urlopen


DEFAULT_TASK_CATALOG = [
    {
        "id": "use_salt_3",
        "title": "Использовать соль 3 раза",
        "target": 3,
        "reward": 40,
        "event_key": "use_salt",
    },
    {
        "id": "radio_answer_3",
        "title": "Получить 3 ответа по радио",
        "target": 3,
        "reward": 45,
        "event_key": "radio_answer",
    },
    {
        "id": "buy_items_2",
        "title": "Купить 2 предмета",
        "target": 2,
        "reward": 35,
        "event_key": "buy_item",
    },
]

DEFAULT_ACHIEVEMENTS_TABLE = [
    {
        "id": "first_buy",
        "title": "Первая покупка",
        "description": "Купить первый предмет",
        "event_key": "buy_item",
        "target": 1,
        "reward": 20,
    },
    {
        "id": "radio_beginner",
        "title": "Связист",
        "description": "Получить 3 ответа по радио",
        "event_key": "radio_answer",
        "target": 3,
        "reward": 30,
    },
    {
        "id": "salt_user",
        "title": "Соль готова",
        "description": "Использовать соль 3 раза",
        "event_key": "use_salt",
        "target": 3,
        "reward": 25,
    },
]


class AchievementTableProvider:
    def load_rows(self) -> List[Dict]:
        raise NotImplementedError


class LocalAchievementTableProvider(AchievementTableProvider):
    def __init__(self, csv_path: str):
        self.csv_path = csv_path

    def load_rows(self) -> List[Dict]:
        if not os.path.exists(self.csv_path):
            print(f"[progression] подтянулась таблица достижений: встроенный fallback (файл не найден: {self.csv_path})")
            return DEFAULT_ACHIEVEMENTS_TABLE.copy()

        rows = []
        with open(self.csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row.get("id"):
                    continue
                rows.append(
                    {
                        "id": row["id"].strip(),
                        "title": row.get("title", "").strip(),
                        "description": row.get("description", "").strip(),
                        "event_key": row.get("event_key", "").strip(),
                        "target": int(row.get("target", "1") or 1),
                        "reward": int(row.get("reward", "0") or 0),
                    }
                )
        if rows:
            print(f"[progression] подтянулась таблица достижений: local csv ({self.csv_path}), строк: {len(rows)}")
            return rows
        print(f"[progression] подтянулась таблица достижений: встроенный fallback (пустой local csv: {self.csv_path})")
        return DEFAULT_ACHIEVEMENTS_TABLE.copy()


class GoogleSheetsAchievementTableProvider(AchievementTableProvider):
    """Reads public Google Sheets data from CSV export URL."""

    def __init__(self, csv_export_url: str, fallback_provider: AchievementTableProvider):
        self.csv_export_url = csv_export_url
        self.fallback_provider = fallback_provider

    def load_rows(self) -> List[Dict]:
        if not self.csv_export_url:
            print("[progression] URL Google Sheets не задан, использую локальную таблицу")
            return self.fallback_provider.load_rows()

        try:
            with urlopen(self.csv_export_url, timeout=5) as response:
                body = response.read().decode("utf-8")
        except (URLError, TimeoutError, ValueError):
            print(f"[progression] не удалось загрузить Google Sheets ({self.csv_export_url}), использую локальную таблицу")
            return self.fallback_provider.load_rows()

        rows = []
        reader = csv.DictReader(body.splitlines())
        for row in reader:
            if not row.get("id"):
                continue
            try:
                target = int(row.get("target", "1") or 1)
                reward = int(row.get("reward", "0") or 0)
            except ValueError:
                continue
            rows.append(
                {
                    "id": row["id"].strip(),
                    "title": row.get("title", "").strip(),
                    "description": row.get("description", "").strip(),
                    "event_key": row.get("event_key", "").strip(),
                    "target": target,
                    "reward": reward,
                }
            )
        if rows:
            print(f"[progression] подтянулась таблица достижений: google sheets ({self.csv_export_url}), строк: {len(rows)}")
            return rows
        print(f"[progression] Google Sheets пустая ({self.csv_export_url}), использую локальную таблицу")
        return self.fallback_provider.load_rows()


@dataclass
class ProgressResult:
    messages: List[str]


class TaskAchievementManager:
    def __init__(self, game, achievement_provider: AchievementTableProvider):
        self.game = game
        self.achievement_provider = achievement_provider

    def new_state(self):
        tasks = []
        for task in DEFAULT_TASK_CATALOG:
            tasks.append(
                {
                    "id": task["id"],
                    "title": task["title"],
                    "event_key": task["event_key"],
                    "progress": 0,
                    "target": int(task["target"]),
                    "reward": int(task["reward"]),
                    "done": False,
                    "claimed": False,
                }
            )

        achievements_table = []
        for ach in self.achievement_provider.load_rows():
            achievements_table.append(
                {
                    "id": ach["id"],
                    "title": ach["title"],
                    "description": ach["description"],
                    "event_key": ach["event_key"],
                    "progress": 0,
                    "target": int(ach.get("target", 1)),
                    "reward": int(ach.get("reward", 0)),
                    "unlocked": False,
                    "claimed": False,
                }
            )
        return tasks, achievements_table

    def normalize_state(self, tasks, achievements_table):
        base_tasks, base_achievements = self.new_state()

        task_index = {t["id"]: t for t in base_tasks}
        if isinstance(tasks, list):
            for row in tasks:
                if not isinstance(row, dict):
                    continue
                task_id = row.get("id")
                if task_id in task_index:
                    task_index[task_id]["progress"] = max(0, min(int(row.get("progress", 0)), int(task_index[task_id]["target"])))
                    task_index[task_id]["done"] = bool(row.get("done", False))
                    task_index[task_id]["claimed"] = bool(row.get("claimed", False))

        ach_index = {a["id"]: a for a in base_achievements}
        if isinstance(achievements_table, list):
            for row in achievements_table:
                if not isinstance(row, dict):
                    continue
                ach_id = row.get("id")
                if ach_id in ach_index:
                    ach_index[ach_id]["progress"] = max(0, min(int(row.get("progress", 0)), int(ach_index[ach_id]["target"])))
                    ach_index[ach_id]["unlocked"] = bool(row.get("unlocked", False))
                    ach_index[ach_id]["claimed"] = bool(row.get("claimed", False))

        return list(task_index.values()), list(ach_index.values())

    def progress_event(self, event_key: str, value: int = 1) -> ProgressResult:
        messages = []
        if value <= 0:
            return ProgressResult(messages)

        for task in self.game.tasks:
            if task["event_key"] != event_key or task["done"]:
                continue
            task["progress"] = min(task["target"], task["progress"] + value)
            if task["progress"] >= task["target"]:
                task["done"] = True
                if not task["claimed"]:
                    task["claimed"] = True
                    self.game.player_money += task["reward"]
                    messages.append(f"Задание выполнено: {task['title']} (+{task['reward']}$)")

        for ach in self.game.achievements_table:
            if ach["event_key"] != event_key or ach["unlocked"]:
                continue
            ach["progress"] = min(ach["target"], ach["progress"] + value)
            if ach["progress"] >= ach["target"]:
                ach["unlocked"] = True
                if not ach["claimed"] and ach["reward"] > 0:
                    ach["claimed"] = True
                    self.game.player_money += ach["reward"]
                messages.append(f"Ачивка: {ach['title']}")

        return ProgressResult(messages)

    def unlock_achievement(self, achievement_id: str) -> ProgressResult:
        for ach in self.game.achievements_table:
            if ach["id"] != achievement_id or ach["unlocked"]:
                continue
            ach["unlocked"] = True
            ach["progress"] = ach["target"]
            if not ach["claimed"] and ach["reward"] > 0:
                ach["claimed"] = True
                self.game.player_money += ach["reward"]
            return ProgressResult([f"Ачивка: {ach['title']}"])
        return ProgressResult([])
