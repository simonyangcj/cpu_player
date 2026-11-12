"""设计文档 §13.5：无声模式冒烟——整条流水线不崩溃，终端宽度 40~200 都能渲染。"""

import rich.console
from cpu_piano.audio import make_backend
from cpu_piano.channelizer import Channelizer
from cpu_piano.config import Config
from cpu_piano.mapper import map_keys
from cpu_piano.sampler import FakeSampler
from cpu_piano.trigger import Trigger
from cpu_piano.ui import TerminalUI


def run_pipeline(n_cores, width, frames=30):
    cfg = Config(backend="none", fake_cores=n_cores)
    sampler = FakeSampler(n_cores, cfg.tick)
    channelizer = Channelizer(cfg)
    ch = channelizer.process(sampler.read())
    keys = map_keys(len(ch), cfg.mode, cfg.scale)
    trigger = Trigger(keys, cfg)
    audio, _ = make_backend(cfg)
    console = rich.console.Console(width=width, height=24, force_terminal=False, file=open("/dev/null", "w"))
    ui = TerminalUI(len(ch), keys, console=console)

    for i in range(frames):
        now = i * cfg.tick
        ch = channelizer.process(sampler.read())
        events, active, smoothed = trigger.update(ch, now)
        for e in events:
            if e.on:
                audio.note_on(e.key, e.vel)
            else:
                audio.note_off(e.key)
        header = f"smoke cores={n_cores} N={len(ch)}"
        ui.render(smoothed, active, header)  # 无 Live 时直接打印
    audio.close()


def test_smoke_various_cores_and_widths():
    for n in (1, 4, 12, 64, 128):
        for w in (40, 80, 120, 200):
            run_pipeline(n, w)
