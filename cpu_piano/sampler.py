"""CPU 采样：真实（psutil）或模拟（--fake-cores）。"""

from __future__ import annotations

import math
import random

import psutil


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


class Sampler:
    def read(self) -> list[float]:
        raise NotImplementedError


class RealSampler(Sampler):
    """psutil 每核采样。physical=True 时把 SMT 兄弟线程折叠为物理核。"""

    def __init__(self, physical: bool = False):
        self.physical = physical
        self.n_phys: int | None = None
        if physical:
            phys = psutil.cpu_count(logical=False)
            logical = psutil.cpu_count(logical=True)
            if phys and logical and phys < logical:
                self.n_phys = phys
        # psutil.cpu_percent 首次调用返回 0，先预热一次
        psutil.cpu_percent(interval=None, percpu=True)

    def read(self) -> list[float]:
        vals = psutil.cpu_percent(interval=None, percpu=True)
        if self.n_phys:
            n = self.n_phys
            return [_clamp(sum(vals[p::n]) / n) for p in range(n)]
        return [_clamp(v) for v in vals]


class FakeSampler(Sampler):
    """模拟 N 核：随机游走 + 正弦波 + 偶发尖峰，用于测试 12/88 边界。"""

    def __init__(self, n: int, tick: float = 0.1):
        self.n = n
        self.tick = tick
        self.t = 0.0
        self.phase = [random.uniform(0, 2 * math.pi) for _ in range(n)]
        self.speed = [random.uniform(0.2, 1.2) for _ in range(n)]
        self.level = [random.uniform(5, 45) for _ in range(n)]
        self.spike = [0.0] * n

    def read(self) -> list[float]:
        self.t += self.tick
        out = []
        for i in range(self.n):
            self.level[i] = _clamp(self.level[i] + random.uniform(-8, 8), 2, 55)
            v = self.level[i] + 25 * math.sin(self.t * self.speed[i] + self.phase[i])
            if self.spike[i] > 0:
                v += 70
                self.spike[i] -= self.tick
            elif random.random() < 0.003:
                self.spike[i] = random.uniform(0.3, 2.0)
            out.append(_clamp(v))
        return out
