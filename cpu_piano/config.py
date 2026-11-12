"""全局配置。"""

from dataclasses import dataclass

MIN_N, MAX_N = 12, 88          # 通道数硬性边界：一个八度 ~ 标准钢琴 88 键
KEY_MIN, KEY_MAX = 21, 108     # MIDI 键位：A0 ~ C8


@dataclass
class Config:
    # 采样
    tick: float = 0.1            # 采样间隔（秒）
    physical: bool = False       # 用物理核（SMT 折叠）
    fake_cores: int | None = None  # 模拟 N 核（测试）
    burn: int | None = None      # 让第 k 个核满载（压力测试）
    # 通道化
    min_cores: int = MIN_N
    max_cores: int = MAX_N
    agg: str = "max"             # >max_cores 折叠聚合：max / mean
    # 映射
    mode: str = "scale"          # center / spread / scale
    scale: str = "pentatonic"    # pentatonic / major / minor / chromatic
    reverse: bool = False        # core 0 最高音
    # 触发
    ema_alpha: float = 0.5
    on_th: float = 25.0          # Note On 阈值（%）
    off_th: float = 12.0         # Note Off 阈值（%）
    gamma: float = 0.7           # 力度曲线指数
    sustain: str = "decay"       # decay / repeat / hold
    repeat_min: float = 0.25     # repeat 模式：满载时的重弹间隔（秒）
    repeat_max: float = 2.0      # decay/repeat 模式：低负载时的重弹间隔（秒）
    max_voices: int = 12         # 复音上限
    # 音频
    backend: str = "synth"       # synth / midi / none
    volume: float = 0.3          # 主音量
