"""synth 回归测试：离线驱动 _callback（不打开真实音频流）。

回归背景：OutputStream 的回调签名是 (outdata, frames, time, status)——没有
indata。曾因误用全双工的 5 参数签名导致每个回调都抛 TypeError，全程静音。
"""

import threading

import numpy as np

import cpu_piano.audio.synth as mod
from cpu_piano.audio.synth import SynthBackend


def make_offline_synth() -> SynthBackend:
    mod._sd = object()  # 假装 sounddevice 可用，跳过构造检查
    sb = SynthBackend.__new__(SynthBackend)
    sb.volume = 0.3
    sb.sr = 44100
    sb.frames = 0
    sb.voices = {}
    sb.lock = threading.Lock()
    return sb


def test_callback_stream_signature_and_sound():
    sb = make_offline_synth()
    sb.note_on(60, 100)
    out = np.zeros((1024, 2), dtype=np.float32)
    sb._callback(out, 1024, None, None)  # 纯输出流：4 个位置参数
    assert sb.frames == 1024
    assert np.abs(out).max() > 0.01
    assert out.shape == (1024, 2)
    assert out.dtype == np.float32


def test_note_off_releases_and_culls():
    sb = make_offline_synth()
    sb.note_on(60, 100)
    sb._callback(np.zeros((1024, 2), dtype=np.float32), 1024, None, None)
    sb.note_off(60)
    rel = sb.frames
    for _ in range(20):  # 释放期 0.08s * 4 ≈ 20480 帧
        out = np.zeros((1024, 2), dtype=np.float32)
        sb._callback(out, 1024, None, None)
    assert sb.frames > rel + 0.08 * 4 * 44100
    assert 60 not in sb.voices


def test_voice_natural_decay_cull():
    sb = make_offline_synth()
    sb.note_on(108, 100)  # C8：tau ≈ 0.4s，6*tau ≈ 2.5s
    for _ in range(150):  # 3 秒
        out = np.zeros((1024, 2), dtype=np.float32)
        sb._callback(out, 1024, None, None)
        if 108 not in sb.voices:
            break
    assert 108 not in sb.voices
