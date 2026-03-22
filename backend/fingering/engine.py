"""指法规则引擎

基于当前手位和音程关系，自动为音符分配合理的指法。
规则：
- 顺指法优先（相邻音用相邻手指）
- 跳音程用穿指/跨指
- 1指尽量在白键
- 难版只在难点标注指法
"""

from typing import Optional

from backend.models.score import (
    NoteData, Measure, DifficultyLevel
)
from backend.config import MIN_FINGER, MAX_FINGER, HAND_SPAN_SEMITONES


class FingeringEngine:
    """指法分配引擎。
    
    基于规则为音符序列分配合理的指法编号（1-5）。
    """

    # 白键的 MIDI 音名类（C D E F G A B）
    WHITE_KEY_CLASSES = {0, 2, 4, 5, 7, 9, 11}

    def __init__(self):
        """初始化指法引擎。"""
        pass

    def assign_to_measures(
        self, measures: list[Measure], difficulty: DifficultyLevel
    ) -> list[Measure]:
        """为小节列表中的音符分配指法。
        
        Args:
            measures: 小节列表
            difficulty: 难度等级（影响标注密度）
            
        Returns:
            带指法标注的小节列表
        """
        # 展平所有非休止音符进行连续指法分配
        all_notes: list[tuple[int, int, NoteData]] = []  # (measure_idx, note_idx, note)
        for mi, measure in enumerate(measures):
            for ni, note in enumerate(measure.notes):
                if not note.is_rest:
                    all_notes.append((mi, ni, note))

        if not all_notes:
            return measures

        # 分配指法
        fingerings = self._assign_sequential([n[2] for n in all_notes])

        # 根据难度筛选需要标注的指法
        if difficulty == DifficultyLevel.HARD:
            # 难版：只在跳音程处标注
            fingerings = self._filter_difficult_fingerings(
                fingerings, [n[2] for n in all_notes]
            )

        # 写回指法
        for idx, (mi, ni, _) in enumerate(all_notes):
            if fingerings[idx] is not None:
                old_note = measures[mi].notes[ni]
                measures[mi].notes[ni] = NoteData(
                    pitch=old_note.pitch,
                    duration=old_note.duration,
                    velocity=old_note.velocity,
                    fingering=fingerings[idx],
                    is_rest=old_note.is_rest,
                )

        return measures

    def _assign_sequential(self, notes: list[NoteData]) -> list[Optional[int]]:
        """为连续音符序列分配指法。
        
        使用顺指法优先策略，遇到跳音程时使用穿指/跨指。
        
        Args:
            notes: 非休止音符列表
            
        Returns:
            指法列表（与输入等长）
        """
        if not notes:
            return []

        fingerings: list[Optional[int]] = [None] * len(notes)

        # 确定起始指法
        first_pitch = notes[0].pitch
        fingerings[0] = self._get_start_finger(first_pitch)

        current_finger = fingerings[0]
        current_pitch = first_pitch

        for i in range(1, len(notes)):
            next_pitch = notes[i].pitch
            interval = next_pitch - current_pitch

            if abs(interval) <= 2:
                # 顺指法：相邻音用相邻手指
                next_finger = current_finger + (1 if interval > 0 else -1)
            elif interval > 2:
                # 上行跳音：穿指
                next_finger = self._cross_over(current_finger, interval)
            else:
                # 下行跳音：跨指
                next_finger = self._cross_under(current_finger, interval)

            # 约束到 1-5
            next_finger = max(MIN_FINGER, min(MAX_FINGER, next_finger))

            fingerings[i] = next_finger
            current_finger = next_finger
            current_pitch = next_pitch

        return fingerings

    def _get_start_finger(self, pitch: int) -> int:
        """根据音高确定起始指法。
        
        - 低音区：5指（小指在左边）
        - 中音区：3指（中指）
        - 高音区：1指（大拇指在右边）
        
        Args:
            pitch: MIDI 音高
            
        Returns:
            起始指法编号
        """
        pitch_class = pitch % 12
        octave_pos = pitch // 12

        if octave_pos < 5:
            return 5  # 低音区用小指开始
        elif octave_pos < 6:
            return 3  # 中音区用中指
        else:
            return 1  # 高音区用大拇指

    def _cross_over(self, current_finger: int, interval: int) -> int:
        """穿指：大拇指穿过其他手指。
        
        上行跳音时，大拇指从其他手指下方穿过。
        
        Args:
            current_finger: 当前指法
            interval: 音程（半音数，正数为上行）
            
        Returns:
            下一个指法
        """
        if current_finger <= 2:
            # 已经用 1-2 指，继续上行
            return min(current_finger + 2, MAX_FINGER)
        else:
            # 用 3-5 指，穿大拇指
            return 1

    def _cross_under(self, current_finger: int, interval: int) -> int:
        """跨指：其他手指跨过大拇指。
        
        下行跳音时，其他手指从大拇指上方跨过。
        
        Args:
            current_finger: 当前指法
            interval: 音程（半音数，负数为下行）
            
        Returns:
            下一个指法
        """
        if current_finger >= 4:
            # 已经用 4-5 指，继续下行
            return max(current_finger - 2, MIN_FINGER)
        else:
            # 用 1-3 指，跨小指
            return MAX_FINGER

    def _filter_difficult_fingerings(
        self, fingerings: list[Optional[int]], notes: list[NoteData]
    ) -> list[Optional[int]]:
        """难版：只保留难点位置的指法。
        
        难点定义：跳音程（超过 2 个半音）的位置。
        
        Args:
            fingerings: 完整指法列表
            notes: 音符列表
            
        Returns:
            筛选后的指法列表
        """
        if len(fingerings) <= 1:
            return fingerings

        filtered = [fingerings[0]]  # 第一个总是标注

        for i in range(1, len(notes)):
            interval = notes[i].pitch - notes[i - 1].pitch
            if abs(interval) > 2:
                # 跳音程，保留指法
                filtered.append(fingerings[i])
            else:
                # 顺指法，不标注
                filtered.append(None)

        return filtered

    def _is_white_key(self, pitch: int) -> bool:
        """判断音高是否为白键。
        
        Args:
            pitch: MIDI 音高
            
        Returns:
            是否为白键
        """
        return (pitch % 12) in self.WHITE_KEY_CLASSES
