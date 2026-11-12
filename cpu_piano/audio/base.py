"""音频后端协议。"""

from __future__ import annotations

from typing import Protocol


class AudioBackend(Protocol):
    def note_on(self, key: int, velocity: int) -> None: ...
    def note_off(self, key: int) -> None: ...
    def close(self) -> None: ...


class NullBackend:
    """无声后端：只看画面，便于调试和测试。"""

    def note_on(self, key: int, velocity: int) -> None:
        pass

    def note_off(self, key: int) -> None:
        pass

    def close(self) -> None:
        pass
