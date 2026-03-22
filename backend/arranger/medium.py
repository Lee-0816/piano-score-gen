"""中等版改编引擎

特点：
- 保留主旋律 + 简化的伴奏
- 左手加入分解和弦（Alberti bass）
- 保留基本节奏变化
- 关键位置标注指法
"""

from backend.arranger.base import Arranger
from backend.models.score import (
    Score, ArrangementResult, Part, Measure, NoteData,
    DifficultyLevel, TimeSignature
)
from backend.fingering.engine import FingeringEngine
from backend.config import PIANO_LOWEST_PITCH, PIANO_HIGHEST_PITCH


class MediumArranger(Arranger):
    """中等版改编器。
    
    保留较多原始信息，左手使用分解和弦。
    """

    @property
    def difficulty(self) -> DifficultyLevel:
        """返回中等难度。"""
        return DifficultyLevel.MEDIUM

    def arrange(self, score: Score) -> ArrangementResult:
        """将乐谱改编为中等版。
        
        Args:
            score: 原始乐谱
            
        Returns:
            中等版改编结果
        """
        ts = score.time_signature

        # 构建右手旋律（保留更多细节）
        rh_measures = self._build_melody(score, ts)

        # 构建左手分解和弦
        lh_measures = self._build_alberti_bass(score, ts)

        # 为右手关键位置标注指法
        fingering_engine = FingeringEngine()
        rh_measures = fingering_engine.assign_to_measures(
            rh_measures, DifficultyLevel.MEDIUM
        )

        rh_part = self._merge_measures_to_part("Piano - Right Hand", rh_measures)
        lh_part = self._merge_measures_to_part("Piano - Left Hand", lh_measures)

        return ArrangementResult(
            difficulty=DifficultyLevel.MEDIUM,
            right_hand=rh_part,
            left_hand=lh_part,
            title=f"{score.title} (中等版)",
            tempo=score.tempo,
            key_signature=score.key,
            time_signature=ts,
        )

    def _build_melody(self, score: Score, ts: TimeSignature) -> list[Measure]:
        """构建右手旋律声部。
        
        保留大部分原始音符，限制音域。
        
        Args:
            score: 原始乐谱
            ts: 拍号
            
        Returns:
            小节列表
        """
        if not score.melody_part:
            return []

        measures = []
        for measure in score.melody_part.measures:
            new_notes = []
            for note in measure.notes:
                if note.is_rest:
                    new_notes.append(NoteData(
                        pitch=0,
                        duration=note.duration,
                        velocity=note.velocity,
                        is_rest=True,
                    ))
                    continue

                # 限制音域（更宽松的范围）
                pitch = note.pitch
                while pitch > PIANO_HIGHEST_PITCH:
                    pitch -= 12
                while pitch < PIANO_LOWEST_PITCH:
                    pitch += 12

                new_notes.append(NoteData(
                    pitch=pitch,
                    duration=note.duration,
                    velocity=note.velocity,
                    is_rest=False,
                ))

            if new_notes:
                measures.append(Measure(notes=new_notes))

        return measures

    def _build_alberti_bass(
        self, score: Score, ts: TimeSignature
    ) -> list[Measure]:
        """构建左手 Alberti 分解和弦伴奏。
        
        Alberti bass 模式: 根音-五音-三音-五音
        
        Args:
            score: 原始乐谱
            ts: 拍号
            
        Returns:
            分解和弦小节列表
        """
        measures = []
        measure_len = ts.measure_length

        # 收集所有伴奏音高，按小节分组
        all_pitches_by_measure: list[list[int]] = []

        for part in score.accompaniment_parts:
            for i, measure in enumerate(part.measures):
                while len(all_pitches_by_measure) <= i:
                    all_pitches_by_measure.append([])
                for n in measure.notes:
                    if not n.is_rest:
                        all_pitches_by_measure[i].append(n.pitch)

        max_measures = max(
            len(all_pitches_by_measure),
            len(score.melody_part.measures) if score.melody_part else 0,
            1
        )

        for i in range(max_measures):
            if i < len(all_pitches_by_measure) and all_pitches_by_measure[i]:
                # 提取和弦音
                pitches = sorted(set(all_pitches_by_measure[i]))
                # 转到低音区
                chord_pitches = self._normalize_to_bass(pitches)

                if len(chord_pitches) >= 3:
                    # Alberti bass: 根音-五音-三音-五音
                    root = chord_pitches[0]
                    third = chord_pitches[1]
                    fifth = chord_pitches[2]

                    beat_dur = ts.beat_unit
                    alberti_pattern = [root, fifth, third, fifth]

                    notes_out = []
                    for p in alberti_pattern:
                        notes_out.append(NoteData(
                            pitch=p,
                            duration=beat_dur,
                            velocity=60,
                        ))
                    measures.append(Measure(notes=notes_out))
                elif chord_pitches:
                    # 和弦音不足，用柱式和弦
                    notes_out = [
                        NoteData(pitch=p, duration=measure_len, velocity=60)
                        for p in chord_pitches[:3]
                    ]
                    measures.append(Measure(notes=notes_out))
                else:
                    measures.append(Measure(notes=[
                        NoteData(pitch=0, duration=measure_len, is_rest=True)
                    ]))
            else:
                measures.append(Measure(notes=[
                    NoteData(pitch=0, duration=measure_len, is_rest=True)
                ]))

        return measures

    def _normalize_to_bass(self, pitches: list[int]) -> list[int]:
        """将音高转到低音区并排序去重。
        
        Args:
            pitches: 原始音高列表
            
        Returns:
            低音区音高列表（升序排列，去重）
        """
        bass = []
        for p in pitches:
            while p > 52:
                p -= 12
            while p < 28:
                p += 12
            bass.append(p)
        return sorted(set(bass))
