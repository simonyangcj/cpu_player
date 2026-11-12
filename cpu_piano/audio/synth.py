"""加法合成钢琴后端：numpy + sounddevice。

音色：前 6 个泛音按 1/k 衰减叠加，指数包络，
起音 5 ms，衰减常数与音高成反比（低音长、高音短），tanh 限幅防爆音。
"""

from __future__ import annotations

import threading

import numpy as np

try:
    import sounddevice as _sd
except Exception:  # PortAudio 缺失时 import 即失败
    _sd = None

_SAMPLE_RATE = 44100
_N_HARMONICS = 6
_HARM_NORM = sum(1.0 / k for k in range(1, _N_HARMONICS + 1))
_ATTACK = 0.005     # 起音（秒）
_RELEASE = 0.08      # note_off 后的释放（秒）


class SynthBackend:
    def __init__(self, volume: float = 0.3, sample_rate: int = _SAMPLE_RATE):
        if _sd is None:
            raise RuntimeError("sounddevice/PortAudio 不可用（Linux 需要 libportaudio2）")
        self.volume = max(0.0, min(1.0, volume))
        self.sr = sample_rate
        self.frames = 0                    # 已播放的采样帧计数
        self.voices: dict[int, list] = {}  # key -> [start, vel, release_start|None]
        self.lock = threading.Lock()
        self.stream = _sd.OutputStream(
            samplerate=self.sr, channels=2,
            callback=self._callback, blocksize=1024,
        )
        self.stream.start()
        self.device_name = self._query_device_name()

    def _query_device_name(self) -> str:
        """当前输出设备名（用于画面提示，让"听不见声音"的路由问题可见）。"""
        try:
            dev = _sd.default.device[1]
            return _sd.query_devices(dev)["name"] if dev is not None else "default"
        except Exception:
            return "default"

    # -------------------------------------------------------------- protocol
    def note_on(self, key: int, velocity: int) -> None:
        with self.lock:
            self.voices[key] = [self.frames, max(1, min(127, velocity)), None]

    def note_off(self, key: int) -> None:
        with self.lock:
            v = self.voices.get(key)
            if v is not None and v[2] is None:
                v[2] = self.frames

    def close(self) -> None:
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass

    # ---------------------------------------------------------------- audio
    def _callback(self, outdata, frames, time, status) -> None:
        # 纯输出流的回调签名是 (outdata, frames, time, status)，没有 indata
        idx = np.arange(self.frames, self.frames + frames, dtype=np.float64)
        self.frames += frames
        mix = np.zeros(frames)

        with self.lock:
            voices = list(self.voices.items())
        dead: list[int] = []

        for key, (start, vel, rel) in voices:
            t = (idx - start) / self.sr
            if t[-1] < 0:  # 下一窗口才开始的音
                continue
            tau = 5.0 * 2.0 ** (-(key - 21) / 24)   # 低音长、高音短
            env = np.exp(-np.maximum(t, 0.0) / tau)
            env *= np.clip(t / _ATTACK, 0.0, 1.0)   # 起音 5ms
            if rel is not None:
                tr = (idx - rel) / self.sr
                env *= np.exp(-np.maximum(tr, 0.0) / _RELEASE)
                if tr[-1] > _RELEASE * 4:
                    dead.append(key)
                    continue
            if t[-1] > tau * 6 or env[-1] < 1e-4:    # 包络自然衰减殆尽
                dead.append(key)
                continue
            f = 440.0 * 2.0 ** ((key - 69) / 12.0)
            wave = np.zeros(frames)
            for h in range(1, _N_HARMONICS + 1):
                wave += (1.0 / h) * np.sin(2 * np.pi * f * h * t)
            mix += (wave / _HARM_NORM) * env * (vel / 127.0)

        if dead:
            with self.lock:
                for k in dead:
                    if k in self.voices and self.voices[k][0] is not None:
                        self.voices.pop(k, None)

        out = np.tanh(mix * self.volume)  # 限幅防爆音
        outdata[:] = np.column_stack([out, out]).astype(np.float32)
