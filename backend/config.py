"""项目配置模块"""

import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 输出目录
OUTPUT_DIR = PROJECT_ROOT / "output"

# 示例 MIDI 文件目录
SAMPLES_DIR = PROJECT_ROOT / "samples"

# API 配置
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# MIDI 下载配置
MIDI_DOWNLOAD_TIMEOUT = int(os.getenv("MIDI_DOWNLOAD_TIMEOUT", "30"))
MAX_MIDI_FILE_SIZE = int(os.getenv("MAX_MIDI_FILE_SIZE", "5242880"))  # 5MB

# 音域限制（MIDI 音高编号）
# C3 (48) 到 C6 (84)，约三个八度，适合大多数演奏者
PIANO_LOWEST_PITCH = 48   # C3
PIANO_HIGHEST_PITCH = 84  # C6

# 简单版音域限制（一个八度）
EASY_LOWEST_PITCH = 60    # C4
EASY_HIGHEST_PITCH = 72   # C5

# 默认速度（BPM）
DEFAULT_TEMPO = 100

# 指法范围
MIN_FINGER = 1  # 大拇指
MAX_FINGER = 5  # 小指

# 手掌跨度（半音数，约一个八度）
HAND_SPAN_SEMITONES = 12

# MuseScore 可能的路径
MUSESCORE_PATHS = [
    "mscore",                  # PATH 中
    "musescore",               # 某些 Linux 发行版
    "/Applications/MuseScore 4.app/Contents/MacOS/mscore",  # macOS
    "/usr/bin/mscore",         # Linux
    "C:/Program Files/MuseScore 4/bin/mscore.exe",  # Windows
]

# 确保输出目录存在
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
