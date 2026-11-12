"""触发：EMA 平滑、迟滞开关、力度、sustain 策略、复音裁剪。"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Config


@dataclass
class NoteEvent:
    ch: int
    key: int
    vel: int
    on: bool


class Trigger:
    def __init__(self, keys: list[int], cfg: Config):
        self.keys = list(keys)
        n = len(keys)
        self.cfg = cfg
        self.s = [0.0] * n             # EMA 平滑后的值
        self.active = [False] * n      # 当前发声中
        self.last_strike = [0.0] * n

    def velocity(self, v: float) -> int:
        vel = 1 + 126 * (v / 100.0) ** self.cfg.gamma
        return max(1, min(127, round(vel)))

    def update(self, vals: list[float], now: float) -> tuple[list[NoteEvent], list[bool], list[float]]:
        """处理一帧。返回 (事件列表, 发声标记, 平滑值)。"""
        cfg = self.cfg
        n = len(self.keys)
        events: list[NoteEvent] = []

        # 1. EMA 平滑
        for i in range(n):
            x = max(0.0, min(100.0, vals[i] if i < len(vals) else 0.0))
            self.s[i] = cfg.ema_alpha * x + (1 - cfg.ema_alpha) * self.s[i]

        # 2. 迟滞 Note Off
        for i in range(n):
            if self.active[i] and self.s[i] < cfg.off_th:
                self.active[i] = False
                events.append(NoteEvent(i, self.keys[i], 0, on=False))

        # 3. 复音裁剪 + 迟滞 Note On
        #    每帧只保留使用率最高的 K 个通道发声；被挤掉的候选不触发，
        #    避免反复 on/off 抖动。
        cands = [i for i in range(n)
                 if not self.active[i] and self.s[i] > cfg.on_th]
        pool = [i for i in range(n) if self.active[i]] + cands
        pool.sort(key=lambda i: self.s[i], reverse=True)
        keep = set(pool[:cfg.max_voices])

        for i in range(n):  # 超出复音上限的先 off
            if self.active[i] and i not in keep:
                self.active[i] = False
                events.append(NoteEvent(i, self.keys[i], 0, on=False))
        for i in cands:    # 进入上限的候选 onset
            if i in keep:
                self.active[i] = True
                self.last_strike[i] = now
                events.append(NoteEvent(i, self.keys[i], self.velocity(self.s[i]), on=True))

        # 4. sustain 重弹
        if cfg.sustain in ("decay", "repeat"):
            for i in range(n):
                if self.active[i] and self.s[i] >= cfg.on_th:
                    if cfg.sustain == "decay":
                        interval = cfg.repeat_max
                    else:  # repeat：负载越大重弹越快
                        t = self.s[i] / 100.0
                        interval = cfg.repeat_max + (cfg.repeat_min - cfg.repeat_max) * t
                    if now - self.last_strike[i] >= interval:
                        self.last_strike[i] = now
                        events.append(NoteEvent(i, self.keys[i], self.velocity(self.s[i]), on=True))

        return events, list(self.active), list(self.s)
