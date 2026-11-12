"""设计文档 §13.1：边界单测。"""

import pytest

from cpu_piano.channelizer import Channelizer
from cpu_piano.config import Config


@pytest.mark.parametrize("n", [1, 2, 4, 8, 11, 12, 13, 16, 64, 88, 89, 128, 256])
def test_channel_count_bounds(n):
    cfg = Config()
    ch = Channelizer(cfg)
    out = ch.process([50.0] * n)
    assert 12 <= len(out) <= 88
    assert all(0.0 <= v <= 100.0 for v in out)


def test_passthrough():
    ch = Channelizer(Config())
    assert ch.process([10.0, 20.0, 30.0] + [0.0] * 9) == [10.0, 20.0, 30.0] + [0.0] * 9


def test_fanout_counts():
    ch = Channelizer(Config())
    assert len(ch.process([30.0] * 8)) == 16   # 8 核 → k=2 → 16 通道
    assert len(ch.process([30.0] * 4)) == 12   # 4 核 → k=3 → 12 通道
    assert len(ch.process([30.0] * 1)) == 12  # 1 核 → 12 派生通道


def test_fold_max_agg():
    cfg = Config(agg="max")
    ch = Channelizer(cfg)
    raw = [0.0] * 88 + [100.0]  # 89 核：最后一组含 100
    out = ch.process(raw)
    assert len(out) == 45
    assert out[-1] == 100.0
    assert max(out[:-1]) == 0.0


def test_fold_mean_agg():
    cfg = Config(agg="mean")
    ch = Channelizer(cfg)
    out = ch.process([100.0, 0.0] * 88)  # 176 核 → g=2 → 88 组
    assert len(out) == 88
    assert all(v == 50.0 for v in out)


def test_fanout_values_in_range():
    ch = Channelizer(Config())
    for _ in range(50):
        out = ch.process([100.0, 0.0, 50.0, 20.0])  # 4 核
        assert len(out) == 12
        assert all(0.0 <= v <= 100.0 for v in out)


def test_custom_bounds():
    cfg = Config(min_cores=20, max_cores=30)
    ch = Channelizer(cfg)
    assert len(ch.process([10.0] * 10)) >= 20   # 10 核 → k=2
    assert len(ch.process([10.0] * 100)) <= 30  # 100 核 → 折叠
