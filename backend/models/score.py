"""乐谱数据模型

使用 dataclass 定义乐谱相关的数据结构。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DifficultyLevel(str, Enum):
    """难度等级枚举。"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class NoteData:
    """单个音符数据。
    
    Attributes:
        pitch: MIDI 音高编号 (0-127)，0 表示休止符
        duration: 时值（四分音符为 1.0）
        velocity: 力度 (0-127)
        fingering: 指法 (1-5)，None 表示未标注
        is_rest: 是否为休止符
    """
    pitch: int
    duration: float
    velocity: int = 80
    fingering: Optional[int] = None
    is_rest: bool = False

    def __post_init__(self):
        """验证数据有效性。"""
        if self.is_rest:
            self.pitch = 0
            self.velocity = 0
        if self.fingering is not None:
            self.fingering = max(1, min(5, self.fingering))


@dataclass
class TimeSignature:
    """拍号。
    
    Attributes:
        numerator: 分子（每小节拍数）
        denominator: 分母（以几分音符为一拍）
    """
    numerator: int = 4
    denominator: int = 4

    @property
    def beats_per_measure(self) -> int:
        """每小节拍数。"""
        return self.numerator

    @property
    def beat_unit(self) -> float:
        """一拍的时值（四分音符为 1.0）。"""
        return 4.0 / self.denominator

    @property
    def measure_length(self) -> float:
        """一小节的总时值。"""
        return self.numerator * self.beat_unit

    def __str__(self) -> str:
        return f"{self.numerator}/{self.denominator}"


@dataclass
class KeySignature:
    """调号。
    
    Attributes:
        sharps: 升号数量（正数为升号，负数为降号）
        mode: 调式（major/minor）
    """
    sharps: int = 0
    mode: str = "major"

    def __str__(self) -> str:
        if self.sharps == 0:
            return f"C {self.mode}"
        elif self.sharps > 0:
            circle = ["C", "G", "D", "A", "E", "B", "F#", "C#"]
            idx = min(self.sharps, len(circle) - 1)
            return f"{circle[idx]} {self.mode}"
        else:
            circle = ["C", "F", "Bb", "Eb", "Ab", "Db", "Gb", "Cb"]
            idx = min(abs(self.sharps), len(circle) - 1)
            return f"{circle[idx]} {self.mode}"


@dataclass
class Measure:
    """一个小节。
    
    Attributes:
        notes: 音符列表
        time_signature: 拍号
        key_signature: 调号
    """
    notes: list[NoteData] = field(default_factory=list)
    time_signature: Optional[TimeSignature] = None
    key_signature: Optional[KeySignature] = None

    @property
    def total_duration(self) -> float:
        """小节总时值。"""
        return sum(n.duration for n in self.notes)


@dataclass
class Part:
    """一个声部（如右手、左手）。
    
    Attributes:
        name: 声部名称
        measures: 小节列表
        note_count: 音符数量（用于分析）
        avg_pitch: 平均音高（用于分析）
    """
    name: str = ""
    measures: list[Measure] = field(default_factory=list)
    note_count: int = 0
    avg_pitch: float = 60.0


@dataclass
class Score:
    """完整乐谱。
    
    Attributes:
        title: 曲名
        composer: 作曲者
        parts: 声部列表
        tempo: 速度（BPM）
        key: 调号
        time_signature: 拍号
        melody_part: 主旋律声部
        accompaniment_parts: 伴奏声部列表
    """
    title: str = ""
    composer: str = ""
    parts: list[Part] = field(default_factory=list)
    tempo: int = 100
    key: KeySignature = field(default_factory=KeySignature)
    time_signature: TimeSignature = field(default_factory=TimeSignature)
    melody_part: Optional[Part] = None
    accompaniment_parts: list[Part] = field(default_factory=list)


@dataclass
class ArrangementResult:
    """改编结果。
    
    Attributes:
        difficulty: 难度等级
        right_hand: 右手声部
        left_hand: 左手声部
        title: 标题
        tempo: 速度
        key_signature: 调号
        time_signature: 拍号
    """
    difficulty: DifficultyLevel = DifficultyLevel.EASY
    right_hand: Optional[Part] = None
    left_hand: Optional[Part] = None
    title: str = ""
    tempo: int = 100
    key_signature: KeySignature = field(default_factory=KeySignature)
    time_signature: TimeSignature = field(default_factory=TimeSignature)
