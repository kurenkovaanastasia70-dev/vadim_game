"""Photo-camera geometry and scoring for the top-down game world."""

from dataclasses import dataclass
import math

import pygame

from constants import MAP_SCALE, TILE_SIZE


PHOTO_ZONE_SIZE = int(TILE_SIZE * MAP_SCALE * 2.4)
PHOTO_COOLDOWN_MS = 1000
PHOTO_FEEDBACK_MS = 320
PHOTO_JOURNAL_LIMIT = 5
GHOST_UNIQUE_REWARD = 15
GHOST_DUPLICATE_REWARD = 3


@dataclass(frozen=True)
class PhotoCapture:
    zone: pygame.Rect
    captured: bool = False
    rarity: int = 0
    subject: str = ""
    score: float = 0.0


def photo_zone(player_rect, direction, size=PHOTO_ZONE_SIZE):
    """Return the square photographed immediately in front of the player."""
    size = max(1, int(size))
    zone = pygame.Rect(0, 0, size, size)
    px, py = player_rect.center
    if direction == "left":
        zone.midright = (player_rect.left, py)
    elif direction == "right":
        zone.midleft = (player_rect.right, py)
    elif direction == "up":
        zone.midbottom = (px, player_rect.top)
    else:
        zone.midtop = (px, player_rect.bottom)
    return zone


def _ghost_is_visible(ghost):
    state_name = getattr(getattr(ghost, "state", None), "name", "")
    if state_name == "INVISIBLE":
        return False
    sprite = getattr(ghost, "sprite", None)
    if sprite is not None and sprite.get_alpha() == 0:
        return False
    return bool(getattr(ghost, "rect", None))


def _subject_score(player_rect, zone, direction, subject_center):
    px, py = player_rect.center
    sx, sy = subject_center
    distance = math.hypot(sx - px, sy - py)
    player_edge = max(player_rect.w, player_rect.h) / 2
    distance_quality = 1.0 - min(1.0, max(0.0, distance - player_edge) / zone.w)

    lateral = abs(sy - py) if direction in ("left", "right") else abs(sx - px)
    center_quality = 1.0 - min(1.0, lateral / max(1.0, zone.w / 2))
    return 0.65 * distance_quality + 0.35 * center_quality


def _rarity_from_score(score):
    if score >= 0.67:
        return 3
    if score >= 0.38:
        return 2
    return 1


def capture_ghost_photo(player_rect, direction, ghosts, size=PHOTO_ZONE_SIZE):
    """Capture the best visible ghost inside the square and rate it 1..3."""
    zone = photo_zone(player_rect, direction, size=size)
    candidates = []
    for ghost in ghosts:
        if not _ghost_is_visible(ghost) or not zone.colliderect(ghost.rect):
            continue
        score = _subject_score(player_rect, zone, direction, ghost.rect.center)
        candidates.append((score, ghost))

    if not candidates:
        return PhotoCapture(zone=zone)

    score, _ghost = max(candidates, key=lambda row: row[0])
    return PhotoCapture(
        zone=zone,
        captured=True,
        rarity=_rarity_from_score(score),
        subject="ghost",
        score=score,
    )


def create_media_record(capture, previous_records):
    """Create a Phasmophobia-style Unique/Duplicate media record."""
    if not capture.captured:
        return None
    is_unique = not any(
        row.get("subject") == capture.subject
        for row in previous_records
        if isinstance(row, dict)
    )
    return {
        "subject": capture.subject,
        "rarity": capture.rarity,
        "unique": is_unique,
        "base_reward": GHOST_UNIQUE_REWARD if is_unique else GHOST_DUPLICATE_REWARD,
    }


def normalize_media_records(records):
    """Load safe photo records while remaining compatible with older saves."""
    normalized = []
    seen_subjects = set()
    for row in records or []:
        if not isinstance(row, dict) or row.get("subject") != "ghost":
            continue
        try:
            rarity = int(row.get("rarity", 1))
        except (TypeError, ValueError):
            rarity = 1
        subject = "ghost"
        is_unique = subject not in seen_subjects
        seen_subjects.add(subject)
        normalized.append({
            "subject": subject,
            "rarity": max(1, min(3, rarity)),
            "unique": is_unique,
            "base_reward": GHOST_UNIQUE_REWARD if is_unique else GHOST_DUPLICATE_REWARD,
        })
        if len(normalized) >= PHOTO_JOURNAL_LIMIT:
            break
    return normalized


def media_base_reward(records):
    return sum(
        max(0, int(row.get("base_reward", 0)))
        for row in records
        if isinstance(row, dict)
    )
