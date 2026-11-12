"""音频后端工厂。"""

from __future__ import annotations

from ..config import Config
from .base import AudioBackend, NullBackend


def make_backend(cfg: Config) -> tuple[AudioBackend, str]:
    """按配置创建后端；失败时自动降级到 none 并返回警告信息。"""
    if cfg.backend == "none":
        return NullBackend(), ""
    try:
        if cfg.backend == "midi":
            from .midi import MidiBackend
            return MidiBackend(), ""
        from .synth import SynthBackend
        synth = SynthBackend(volume=cfg.volume)
        return synth, f"audio device: {synth.device_name}  (听不到声音？检查系统输出路由)"
    except Exception as e:  # noqa: BLE001 - 任何音频故障都降级，不中断程序
        return NullBackend(), f"[audio fallback] backend '{cfg.backend}' unavailable: {e} -> using 'none'"
