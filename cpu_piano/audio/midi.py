"""MIDI 后端：可接 FluidSynth / DAW / 系统 MIDI。需要 mido + python-rtmidi。"""

from __future__ import annotations


class MidiBackend:
    def __init__(self, port_name: str | None = None):
        import mido  # 延迟导入：仅 --backend midi 时需要

        self.mido = mido
        if port_name is None:
            names = mido.get_output_names()
            if not names:
                raise RuntimeError("没有可用的 MIDI 输出端口（安装 python-rtmidi 或启动 FluidSynth）")
            port_name = names[0]
        self.out = mido.open_output(port_name)

    def note_on(self, key: int, velocity: int) -> None:
        self.out.send(self.mido.Message("note_on", note=key, velocity=velocity))

    def note_off(self, key: int) -> None:
        self.out.send(self.mido.Message("note_off", note=key, velocity=0))

    def close(self) -> None:
        self.out.close()
