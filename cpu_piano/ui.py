"""终端可视化：rich Live 柱状图 + 音名标注 + 迷你钢琴条。

- 柱子用块字符 ▁▂▃▄▅▆▇█ 实现 8 级亚字符精度
- 颜色绿→黄→红渐变；发声中的通道加粗反色
- 峰值保持线缓慢下落
- 终端太窄时按 2:1 / 3:1 合并显示列（只影响显示，不影响发声）
"""

from __future__ import annotations

from rich.console import Console
from rich.live import Live
from rich.text import Text

from .mapper import note_name

BLOCKS = " ▁▂▃▄▅▆▇█"
COLW = 3        # 每个显示列占 3 个字符（含 1 列间隔）


def _load_style(v: float, active: bool) -> str:
    if v < 30:
        s = "green"
    elif v < 60:
        s = "yellow"
    elif v < 85:
        s = "red"
    else:
        s = "bright_red"
    return f"bold reverse {s}" if active else s


class TerminalUI:
    def __init__(self, n: int, keys: list[int], console: Console | None = None):
        self.n = n
        self.keys = list(keys)
        self.console = console or Console()
        self.peaks = [0.0] * n
        self.live: Live | None = None
        self.message = ""

    def start(self) -> None:
        self.live = Live(console=self.console, refresh_per_second=20)
        self.live.start()

    def stop(self) -> None:
        if self.live is not None:
            self.live.stop()
            self.live = None

    def set_message(self, msg: str) -> None:
        self.message = msg

    # ------------------------------------------------------------------ draw
    def render(self, vals: list[float], active: list[bool], header: str) -> None:
        n = self.n
        # 峰值保持：不低于当前值，每帧缓慢下落
        for i in range(n):
            self.peaks[i] = max(vals[i], self.peaks[i] - 2.0)

        w = self.console.size.width
        h = self.console.size.height

        # 窄屏合并：m 个通道合并为 1 列显示
        m = 1
        while -(-n // m) * COLW > max(COLW, w - 2):
            m += 1
        nd = -(-n // m)

        gvals, gactive, gpeak, gkeys, gcore = [], [], [], [], []
        for gi in range(nd):
            grp = list(range(gi * m, min((gi + 1) * m, n)))
            best = max(grp, key=lambda i: vals[i])
            gvals.append(vals[best])
            gactive.append(any(active[i] for i in grp))
            gpeak.append(max(self.peaks[i] for i in grp))
            gkeys.append(self.keys[best])
            gcore.append(grp[0])

        bar_rows = max(3, min(12, h - 8))
        text = Text()
        text.append(header, style="bold")
        text.append("\n")

        for r in range(bar_rows, 0, -1):
            for gi in range(nd):
                v = gvals[gi]
                rows_f = v / 100.0 * bar_rows
                full = int(rows_f)
                frac = rows_f - full
                ch, style = " ", None
                if full >= r:
                    ch, style = "█", _load_style(v, gactive[gi])
                elif full == r - 1 and frac > 0:
                    ch, style = BLOCKS[1 + int(frac * 8 - 1e-9)], _load_style(v, gactive[gi])
                else:
                    pr = gpeak[gi] / 100.0 * bar_rows
                    if abs(pr - r) < 0.5 and pr > rows_f:  # 峰值保持点
                        ch, style = "·", "bright_magenta"
                if style:
                    text.append(ch, style=style)
                else:
                    text.append(ch)
                text.append("  ")
            text.append("\n")

        text.append("└" + "─" * max(0, nd * COLW - 1))
        text.append("\n")

        # core 编号行
        for gi in range(nd):
            text.append(f"{gcore[gi]:>2} ")
        text.append("\n")

        # 音名行
        for gi in range(nd):
            text.append(f" {note_name(gkeys[gi]):<2}")
        text.append("\n")

        # 迷你钢琴条：□ 白键 ■ 黑键，发声中高亮反色
        for gi in range(nd):
            k = gkeys[gi]
            black = k % 12 in {1, 3, 6, 8, 10}
            if gactive[gi]:
                text.append(" █ ", style="bold reverse yellow")
            else:
                text.append(" ■ " if black else " □ ",
                            style="bright_black" if black else None)
        text.append("\n")

        if self.message:
            text.append(self.message, style="yellow")

        if self.live is not None:
            self.live.update(text)
        else:
            self.console.print(text)
