# CPU Piano

让每一个 CPU 核心变成钢琴上的一个琴键：核心越忙，琴键被按得越重、越响。同时在终端里实时画出柱状起伏，让你**看到并听到**机器的负载。

- 通道数 N 硬性满足 **12 ≤ N ≤ 88**（一个八度 ~ 标准 88 键钢琴）
- 核心少于 12 → 派生子通道扩展；多于 88 → 相邻核心折叠
- 默认 **C 大调五声音阶量化**——无论哪些核同时响，听起来都是音乐而不是噪音
- 内置加法合成器，零外部文件，装完就响；也可接 MIDI 音源

```
CPU Piano  cores=12 → N=12  mode=scale:pentatonic  voices=3/12  tick=100ms  backend=synth

 100% │
  80% │            ▆
  60% │   █        █
  40% │   █  ▄     █     ▇
  20% │▂  █  █  ▄  █  ▁  █  ▄
   0% └────────────────────────
       0  1  2  3  4  5  6  7
      D3 E3 G3 A3 C4 D4 E4 G4 A4 C5 D5 E5
      □  █  □  █  █  █  □  █  □  □  █  █
```

## 安装

需要 Python 3.10+ 和 [uv](https://docs.astral.sh/uv/)。

```bash
uv sync
```

依赖已配置清华 PyPI 源（见 `pyproject.toml` 中的 `[[tool.uv.index]]`）。

Linux 上 `synth` 后端需要 PortAudio：`sudo apt install libportaudio2`。缺失时程序自动降级为无声模式并在画面提示。

## 使用

```bash
uv run cpu-piano                        # 直接跑：本机核数 → 琴键
uv run cpu-piano --burn 3               # 让第 3 个核满载，看/听对应的琴键
uv run cpu-piano --backend none         # 只看画面，不出声（调试/CI）
uv run cpu-piano --fake-cores 256       # 模拟 256 核，测试折叠路径
uv run cpu-piano --mode center          # 半音一一对应（物理直觉优先）
uv run cpu-piano --sustain repeat       # 重弹频率随负载增大，听出节奏感
uv run cpu-piano --backend midi         # 接 FluidSynth / DAW（需安装 midi 附加依赖）
```

MIDI 后端需要额外依赖：`uv sync --extra midi`（mido + python-rtmidi）。

按 `Ctrl+C` 退出。

## 配置项

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--tick` | 0.1 | 采样间隔（秒），建议 0.05~0.5 |
| `--mode` | scale | 映射模式：`center` 居中半音窗口 / `spread` 均匀铺开 / `scale` 调式量化 |
| `--scale` | pentatonic | 调式：`pentatonic` / `major` / `minor` / `chromatic` |
| `--sustain` | decay | 持续高负载策略：`decay` 定时重弹 / `repeat` 负载越大重弹越快 / `hold` 持续按住 |
| `--max-voices` | 12 | 同时发声上限（画面展示全部通道，声音只展示最忙的 K 个） |
| `--on` / `--off` | 25 / 12 | 触发阈值（%），迟滞防抖 |
| `--gamma` | 0.7 | 力度曲线指数，越小低负载越听得见 |
| `--agg` | max | 多于 88 核时的折叠聚合：`max` / `mean` |
| `--backend` | synth | 音频后端：`synth` / `midi` / `none` |
| `--volume` | 0.3 | 主音量 0~1 |
| `--reverse` | off | core 0 最高音（默认最低音） |
| `--physical` | off | 用物理核（SMT 兄弟线程折叠） |
| `--min-cores` / `--max-cores` | 12 / 88 | 通道数边界 |
| `--fake-cores N` | 无 | 模拟 N 核，测试边界 |
| `--burn K` | 无 | 让第 K 个核满载（压力测试） |

## 工作原理

```
┌──────────┐   ┌─────────────┐   ┌───────────┐   ┌──────────────┐
│ Sampler  │ → │ Channelizer │ → │ NoteMapper│ → │ Audio Engine │
│ psutil   │   │ 扩展/折叠    │   │ 通道→琴键  │   │ 合成/MIDI     │
└──────────┘   └─────────────┘   └───────────┘   └──────────────┘
                                      │
                                      ▼
                              ┌──────────────┐
                              │ Terminal UI  │
                              └──────────────┘
```

主循环每 100 ms 一帧：采样 → 通道化 → 平滑 → 触发判定 → 发声 + 刷新画面。

- **通道化**：核心数不足 12 时，每个核心派生多个子通道（快/慢 EMA、变化率 Δ、峰值保持）；超过 88 时按相邻核心分组折叠（默认取组内最大值，不漏尖峰）。
- **映射**：先在 88 键中筛出调内的键，再取居中的 N 个；调内键不足时自动回退为半音窗口。
- **触发**：钢琴是打击乐器，采用"起音 + 衰减"而非电平直通——EMA 平滑、迟滞开关（25% 开 / 12% 关）、力度随负载变化、持续高负载定时重弹。
- **合成**：前 6 个泛音按 1/k 衰减叠加，指数包络，起音 5 ms，低音衰减长、高音短。

详细设计见 [design.md](design.md)。

## 测试

```bash
uv run pytest
```

覆盖边界（1/4/12/89/256 核 → N 恒在 12~88、键位唯一且落在 21~108）、映射（居中/铺开/调式/回退）、触发（迟滞防抖、复音上限、sustain 重弹）与无声冒烟（终端宽度 40~200）。

## 已知注意事项

- 采样间隔 `--tick` 建议 ≥ 50 ms：太小的话采样本身耗 CPU，会"自己弹自己"。
- N = 88 时建议 100 列以上的终端宽度；窄屏只影响显示合并，不影响发声。
- 首帧 `psutil.cpu_percent` 返回 0，启动时已自动预热一次。
