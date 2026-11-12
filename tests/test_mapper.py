"""设计文档 §13.2：映射单测。"""

import pytest

from cpu_piano.config import KEY_MAX, KEY_MIN
from cpu_piano.mapper import SCALES, map_keys, note_name

MODES = ["center", "spread", "scale"]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("n", [12, 13, 16, 32, 64, 88])
def test_keys_unique_and_in_range(mode, n):
    keys = map_keys(n, mode=mode, scale="pentatonic")
    assert len(keys) == n
    assert len(set(keys)) == n
    assert all(KEY_MIN <= k <= KEY_MAX for k in keys)
    assert keys == sorted(keys)


def test_center_12_continuous_centered():
    keys = map_keys(12, mode="center")
    assert keys == list(range(58, 70))  # 连续半音，中央区


def test_center_88_full_keyboard():
    assert map_keys(88, mode="center") == list(range(KEY_MIN, KEY_MAX + 1))


def test_spread_extremes():
    keys = map_keys(12, mode="spread")
    assert keys[0] == KEY_MIN
    assert keys[-1] == KEY_MAX


def test_scale_keys_in_scale():
    degrees = set(SCALES["pentatonic"])
    keys = map_keys(12, mode="scale", scale="pentatonic")
    assert len(keys) == 12
    assert all(k % 12 in degrees for k in keys)


@pytest.mark.parametrize("scale", ["pentatonic", "major", "minor"])
def test_scale_fallback_to_chromatic(scale):
    # 调内键数 < N 时自动回退为半音窗口
    assert map_keys(88, mode="scale", scale=scale) == list(range(KEY_MIN, KEY_MAX + 1))


def test_scale_is_centered_slice():
    degrees = set(SCALES["pentatonic"])
    allowed = [k for k in range(KEY_MIN, KEY_MAX + 1) if k % 12 in degrees]
    keys = map_keys(12, mode="scale", scale="pentatonic")
    start = (len(allowed) - 12) // 2
    assert keys == allowed[start:start + 12]


def test_note_name():
    assert note_name(21) == "A0"
    assert note_name(60) == "C4"
    assert note_name(108) == "C8"
