"""改编引擎基类"""

from abc import ABC, abstractmethod

from backend.models.score import (
    Score, ArrangementResult, Part, Measure, NoteData, DifficultyLevel, TimeSignature
)


class Arranger(ABC):
    """改编引擎抽象基类。
    
    所有改编器都应继承此类并实现 arrange 方法。
    """

    @property
    @abstractmethod
    def difficulty(self) -> DifficultyLevel:
        """当前改编器的难度等级。"""
        pass

    @abstractmethod
    def arrange(self, score: Score) -> ArrangementResult:
        """将原始乐谱改编为指定难度。
        
        Args:
            score: 原始乐谱数据
            
        Returns:
            改编结果
        """
        pass

    def _merge_measures_to_part(
        self, name: str, measures: list[Measure]
    ) -> Part:
        """将小节列表合并为一个声部。
        
        Args:
            name: 声部名称
            measures: 小节列表
            
        Returns:
            Part 对象
        """
        note_count = sum(
            1 for m in measures for n in m.notes if not n.is_rest
        )
        pitches = [
            n.pitch for m in measures for n in m.notes if not n.is_rest
        ]
        avg_pitch = sum(pitches) / len(pitches) if pitches else 60.0

        return Part(
            name=name,
            measures=measures,
            note_count=note_count,
            avg_pitch=avg_pitch,
        )
