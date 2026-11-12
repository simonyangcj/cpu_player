"""映射：N 个通道 → 88 个琴键中的 N 个（MIDI 编号 21~108）。"""

from __future__ import annotations

from .config import KEY_MAX, KEY_MIN

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

SCALES: dict[str, tuple[int, ...]] = {
    "pentatonic": (0, 2, 4, 7, 9),          # C 大调五声音阶 C D E G A
    "major": (0, 2, 4, 5, 7, 9, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "chromatic": tuple(range(12)),
}


def note_name(key: int) -> str:
    return f"{NOTE_NAMES[key % 12]}{key // 12 - 1}"


def map_keys(n: int, mode: str = "scale", scale: str = "pentatonic") -> list[int]:
    """返回 n 个严格递增、唯一、落在 21~108 内的 MIDI 键位。"""
    if n <= 0:
        return []
    if n == 1:
        return [(KEY_MIN + KEY_MAX) // 2]

    if mode == "spread":
        return [KEY_MIN + round(i * (KEY_MAX - KEY_MIN) / (n - 1))
                for i in range(n)]

    if mode == "scale" and scale != "chromatic":
        degrees = set(SCALES[scale])
        allowed = [k for k in range(KEY_MIN, KEY_MAX + 1) if k % 12 in degrees]
        if len(allowed) >= n:
            start = (len(allowed) - n) // 2
            return allowed[start:start + n]
        # 调内键不足（N 接近 88）→ 自动回退为半音窗口，保证边界不被破坏

    # center / 回退：以 E4 附近为中心的连续半音窗口
    low = max(KEY_MIN, min(64 - n // 2, KEY_MAX - n + 1))
    return list(range(low, low + n))
