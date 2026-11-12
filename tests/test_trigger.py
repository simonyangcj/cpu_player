"""触发逻辑单测：迟滞、复音上限、力度、sustain。"""

from cpu_piano.config import Config
from cpu_piano.mapper import map_keys
from cpu_piano.trigger import Trigger

KEYS12 = map_keys(12, mode="center")


def make_trigger(**kw) -> Trigger:
    cfg = Config(ema_alpha=1.0, sustain="hold", **kw)  # alpha=1 → 不平滑，便于断言
    return Trigger(KEYS12, cfg)


def onoffs(events):
    return (sum(1 for e in events if e.on), sum(1 for e in events if not e.on))


def test_onset_and_hysteresis():
    tr = make_trigger()
    ev, active, _ = tr.update([50.0] * 12, now=0.1)
    n_on, n_off = onoffs(ev)
    assert n_on == 12 and n_off == 0 and all(active)

    # 掉到 on/off 阈值之间：保持，无事件（迟滞防抖）
    ev, active, _ = tr.update([18.0] * 12, now=0.2)
    assert ev == [] and all(active)

    # 跌破 off 阈值：全部 Note Off
    ev, active, _ = tr.update([5.0] * 12, now=0.3)
    n_on, n_off = onoffs(ev)
    assert n_on == 0 and n_off == 12 and not any(active)


def test_no_churn_near_threshold():
    tr = make_trigger()
    tr.update([50.0] * 12, now=0.1)
    # 在阈值附近抖动（15~20，处于迟滞区间）
    for t, v in [(0.2, 15.0), (0.3, 20.0), (0.4, 14.0), (0.5, 19.0)]:
        ev, _, _ = tr.update([v] * 12, now=t)
        assert ev == []


def test_polyphony_cap():
    tr = make_trigger(max_voices=4)
    ev, active, _ = tr.update([80.0] * 12, now=0.1)
    n_on, _ = onoffs(ev)
    assert n_on == 4 and sum(active) == 4


def test_polyphony_prefers_loudest():
    tr = make_trigger(max_voices=2)
    vals = [90.0] + [30.0] * 11
    ev, active, _ = tr.update(vals, now=0.1)
    struck = {e.ch for e in ev if e.on}
    assert 0 in struck and len(struck) == 2
    assert active[0]


def test_velocity_bounds():
    tr = make_trigger()
    ev, _, _ = tr.update([100.0] * 12, now=0.1)
    assert all(1 <= e.vel <= 127 for e in ev)
    tr2 = make_trigger()
    ev2, _, _ = tr2.update([26.0] * 12, now=0.1)  # 刚过阈值
    assert all(1 <= e.vel <= 127 for e in ev2)
    # 低负载力度应明显低于满载力度
    assert max(e.vel for e in ev2) < min(e.vel for e in ev)


def test_restrike_decay():
    tr = Trigger(KEYS12, Config(ema_alpha=1.0, sustain="decay", repeat_max=2.0))
    tr.update([90.0] * 12, now=0.1)
    # 1.9s：未到重弹间隔
    ev, _, _ = tr.update([90.0] * 12, now=2.0)
    assert onoffs(ev) == (0, 0)
    # 2.1s：全部重弹
    ev, _, _ = tr.update([90.0] * 12, now=2.2)
    n_on, _ = onoffs(ev)
    assert n_on == 12


def test_restrike_repeat_faster_with_load():
    tr = Trigger(KEYS12, Config(ema_alpha=1.0, sustain="repeat",
                                repeat_min=0.25, repeat_max=2.0))
    tr.update([100.0] * 12, now=0.1)
    # 满载 0.35s > 0.25s 间隔 → 已重弹
    ev, _, _ = tr.update([100.0] * 12, now=0.45)
    assert onoffs(ev)[0] == 12


def test_hold_no_restrike():
    tr = Trigger(KEYS12, Config(ema_alpha=1.0, sustain="hold"))
    tr.update([90.0] * 12, now=0.1)
    ev, active, _ = tr.update([90.0] * 12, now=5.0)
    assert ev == [] and all(active)
