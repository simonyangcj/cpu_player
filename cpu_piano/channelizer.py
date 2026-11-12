"""通道化：把 n_cores 个原始采样值变成恰好落在 [min_cores, max_cores] 的 N 个通道。

- n > max_cores：折叠（Fold），相邻 g 个核心一组，max/mean 聚合
- n < min_cores：扩展（Fan-out），每个核心派生多个子通道（快/慢 EMA、变化率、峰值保持……）
- 其他：直通
"""

from __future__ import annotations

import math

from .config import Config


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


class Channelizer:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        # Fan-out 派生信号的状态（按 (core, slot) 惰性初始化）
        self._prev: dict[tuple[int, int], float] = {}
        self._ema: dict[tuple[int, int], float] = {}
        self._peak: dict[tuple[int, int], float] = {}

    def process(self, raw: list[float]) -> list[float]:
        n = len(raw)
        lo, hi = self.cfg.min_cores, self.cfg.max_cores
        if n > hi:
            return self._fold(raw)
        if n < lo:
            return self._fanout(raw)
        return [_clamp(v) for v in raw]

    # ------------------------------------------------------------------ fold
    def _fold(self, raw: list[float]) -> list[float]:
        hi = self.cfg.max_cores
        g = math.ceil(len(raw) / hi)
        out = []
        for i in range(0, len(raw), g):
            grp = raw[i:i + g]
            if self.cfg.agg == "mean":
                out.append(_clamp(sum(grp) / len(grp)))
            else:  # max（默认）
                out.append(_clamp(max(grp)))
        return out[:hi]

    # ---------------------------------------------------------------- fanout
    def _fanout(self, raw: list[float]) -> list[float]:
        n = len(raw)
        lo, hi = self.cfg.min_cores, self.cfg.max_cores
        k = math.ceil(lo / n)
        k = max(1, min(k, hi // n))  # 保证 n*k <= hi
        out: list[float] = []
        for c in range(n):
            x = _clamp(raw[c])
            delta = _clamp((x - self._prev.get((c, 0), x)) * 2.0)
            self._prev[(c, 0)] = x
            out.extend(self._derived(c, x, delta, k))
        return out

    def _derived(self, core: int, x: float, delta: float, k: int) -> list[float]:
        """从单核瞬时值派生 k 个子通道。

        slot 0..3：快 EMA / 慢 EMA / 变化率 Δ / 峰值保持（设计文档定义）
        slot >= 4：时间常数递增的额外 EMA（覆盖 1~2 核这类极端情况）
        """
        vals: list[float] = []
        for j in range(k):
            key = (core, j)
            if j == 0:      # 快 EMA：瞬时负载，主旋律
                v = self._upd_ema(key, x, 0.6)
            elif j == 1:    # 慢 EMA：持续负载趋势
                v = self._upd_ema(key, x, 0.15)
            elif j == 2:    # Δ：负载突然上升 → 短促重音
                v = delta
            elif j == 3:    # 峰值保持：余韵
                p = max(x, self._peak.get(key, 0.0) * 0.94)
                self._peak[key] = p
                v = p
            else:           # 兜底：α 递减的更长周期 EMA
                alpha = 0.9 * (0.55 ** (j - 4))
                v = self._upd_ema(key, x, alpha)
            vals.append(_clamp(v))
        return vals

    def _upd_ema(self, key: tuple[int, int], x: float, alpha: float) -> float:
        prev = self._ema.get(key, x)
        v = alpha * x + (1 - alpha) * prev
        self._ema[key] = v
        return v
