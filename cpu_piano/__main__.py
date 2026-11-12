"""CLI 入口与主循环。

主循环节拍固定：采样 → 通道化 → 触发判定 → 发声 → 刷新画面。
"""

from __future__ import annotations

import argparse
import multiprocessing
import os
import time

from . import __version__
from .audio import make_backend
from .channelizer import Channelizer
from .config import Config
from .mapper import map_keys
from .sampler import FakeSampler, RealSampler
from .trigger import Trigger
from .ui import TerminalUI


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cpu-piano",
        description="用 CPU 使用率弹钢琴：每个核心是一个琴键（12 ≤ N ≤ 88）",
    )
    p.add_argument("--version", action="version", version=f"cpu-piano {__version__}")
    p.add_argument("--tick", type=float, default=0.1, help="采样间隔（秒），建议 0.05~0.5")
    p.add_argument("--mode", choices=("center", "spread", "scale"), default="scale",
                   help="映射模式（默认 scale：调式量化，更好听）")
    p.add_argument("--scale", choices=("pentatonic", "major", "minor", "chromatic"),
                   default="pentatonic", help="调式")
    p.add_argument("--agg", choices=("max", "mean"), default="max",
                   help="大于 88 核时的折叠聚合方式")
    p.add_argument("--sustain", choices=("decay", "repeat", "hold"), default="decay",
                   help="持续高负载策略")
    p.add_argument("--max-voices", type=int, default=12, help="同时发声上限")
    p.add_argument("--on", type=float, default=25.0, help="Note On 阈值（%%）")
    p.add_argument("--off", type=float, default=12.0, help="Note Off 阈值（%%）")
    p.add_argument("--gamma", type=float, default=0.7, help="力度曲线指数")
    p.add_argument("--backend", choices=("synth", "midi", "none"), default="synth",
                   help="音频后端")
    p.add_argument("--volume", type=float, default=0.3, help="主音量 0~1")
    p.add_argument("--min-cores", type=int, default=12, help="通道数下界")
    p.add_argument("--max-cores", type=int, default=88, help="通道数上界")
    p.add_argument("--reverse", action="store_true", help="core 0 最高音（默认最低音）")
    p.add_argument("--physical", action="store_true", help="用物理核（SMT 折叠）")
    p.add_argument("--fake-cores", type=int, default=None, metavar="N",
                   help="模拟 N 核，用于测试 12/88 边界")
    p.add_argument("--burn", type=int, default=None, metavar="K",
                   help="让第 K 个核满载（压力测试）")
    return p


def _burn_worker(core: int) -> None:
    try:
        os.sched_setaffinity(0, {core})
    except OSError:
        pass
    while True:  # noqa: SIM300 - 就是要满载
        pass


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.on <= args.off:
        raise SystemExit("--on 必须大于 --off（迟滞）")
    cfg = Config(
        tick=args.tick, mode=args.mode, scale=args.scale, agg=args.agg,
        sustain=args.sustain, max_voices=args.max_voices,
        on_th=args.on, off_th=args.off, gamma=args.gamma,
        backend=args.backend, volume=args.volume,
        min_cores=args.min_cores, max_cores=args.max_cores,
        reverse=args.reverse, physical=args.physical,
        fake_cores=args.fake_cores, burn=args.burn,
    )
    if not 1 <= cfg.max_voices:
        raise SystemExit("--max-voices 至少为 1")

    burn_proc = None
    if cfg.burn is not None:
        burn_proc = multiprocessing.Process(
            target=_burn_worker, args=(cfg.burn,), daemon=True)
        burn_proc.start()

    sampler = (FakeSampler(cfg.fake_cores, cfg.tick) if cfg.fake_cores
               else RealSampler(cfg.physical))
    n_cores = cfg.fake_cores or len(sampler.read())

    channelizer = Channelizer(cfg)
    raw = sampler.read()
    ch = channelizer.process(raw)
    n_channels = len(ch)

    keys = map_keys(n_channels, cfg.mode, cfg.scale)
    if cfg.reverse:
        keys = list(reversed(keys))

    trigger = Trigger(keys, cfg)
    audio, warn = make_backend(cfg)

    ui = TerminalUI(n_channels, keys)
    if warn:
        ui.set_message(warn)

    ui.start()
    t0 = time.monotonic()
    frame = 0
    try:
        while True:
            now = time.monotonic()
            raw = sampler.read()
            ch = channelizer.process(raw)
            events, active, smoothed = trigger.update(ch, now)
            for e in events:
                if e.on:
                    audio.note_on(e.key, e.vel)
                else:
                    audio.note_off(e.key)
            header = (
                f"CPU Piano  cores={n_cores} → N={n_channels}  "
                f"mode={cfg.mode}:{cfg.scale}  voices={sum(active)}/{cfg.max_voices}  "
                f"tick={cfg.tick * 1000:.0f}ms  backend={cfg.backend}"
            )
            ui.render(smoothed, active, header)
            frame += 1
            delay = t0 + frame * cfg.tick - time.monotonic()
            if delay > 0:
                time.sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        ui.stop()
        audio.close()
        if burn_proc is not None:
            burn_proc.terminate()


if __name__ == "__main__":
    main()
