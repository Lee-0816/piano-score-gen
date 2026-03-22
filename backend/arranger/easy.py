"""简单版改编引擎

特点：
- 只保留主旋律（右手单音）
- 左手简化为柱式和弦（全音符/二分音符）
- 去掉装饰音（过于短促的音符）
- 音域限制在一个八度内
- 每个音都标注指法
"""

from backend.arranger.base import Arranger
from backend.models.score import (
    Score, ArrangementResult, Part, Measure, NoteData,
    DifficultyLevel, TimeSignature, KeySignature
)
from backend.fingering.engine import FingeringEngine
from backend.config import EASY_LOWEST_PITCH, EASY_HIGHEST_PITCH


class EasyArranger(Arranger):
    """简单版改编器。
    
    将乐谱改编为适合初学者的简单版本。
    """

    # 最小时值（六十四分音符及更短的视为装饰音，需过滤）
    MIN_DURATION = 0.25

    @property
    def difficulty(self) -> DifficultyLevel:
        """返回简单难度。"""
        return DifficultyLevel.EASY

    def arrange(self, score: Score) -> ArrangementResult:
        """将乐谱改编为简单版。
        
        Args:
            score: 原始乐谱
            
        Returns:
            简单版改编结果
        """
        ts = score.time_signature
        measure_len = ts.measure_length

        # 提取并简化右手旋律
        rh_measures = self._build_melody(score, ts)

        # 生成左手简单和弦
        lh_measures = self._build_chords(score, ts)

        # 为右手标注指法
        fingering_engine = FingeringEngine()
        rh_measures = fingering_engine.assign_to_measures(
            rh_measures, DifficultyLevel.EASY
        )

        rh_part = self._merge_measures_to_part("Piano - Right Hand", rh_measures)
        lh_part = self._merge_measures_to_part("Piano - Left Hand", lh_measures)

        return ArrangementResult(
            difficulty=DifficultyLevel.EASY,
            right_hand=rh_part,
            left_hand=lh_part,
            title=f"{score.title} (简单版)",
            tempo=max(60, score.tempo - 20),  # 简单版放慢速度
            key_signature=score.key,
            time_signature=ts,
        )

    def _build_melody(self, score: Score, ts: TimeSignature) -> list[Measure]:
        """构建右手旋律声部。
        
        从主旋律声部提取音符，过滤装饰音，限制音域。
        
        Args:
            score: 原始乐谱
            ts: 拍号
            
        Returns:
            简化后的小节列表
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
                        velocity=0,
                        is_rest=True,
                    ))
                    continue

                # 过滤装饰音
                if note.duration < self.MIN_DURATION:
                    continue

                # 限制音域
                pitch = note.pitch
                while pitch > EASY_HIGHEST_PITCH:
                    pitch -= 12
                while pitch < EASY_LOWEST_PITCH:
                    pitch += 12

                new_notes.append(NoteData(
                    pitch=pitch,
                    duration=note.duration,
                    velocity=note.velocity,
                    is_rest=False,
                ))

            # 合并连续相同音高的音符
            new_notes = self._merge_consecutive_same_pitch(new_notes)

            if new_notes:
                measures.append(Measure(notes=new_notes))

        # 补齐小节数（与原曲对齐）
        while len(measures) < len(score.melody_part.measures):
            measures.append(Measure(notes=[
                NoteData(pitch=0, duration=ts.measure_length, is_rest=True)
            ]))

        return measures

    def _build_chords(self, score: Score, ts: TimeSignature) -> list[Measure]:
        """构建左手和弦伴奏。
        
        从伴奏声部提取和弦信息，简化为柱式和弦。
        每小节一个或两个全音符/二分音符和弦。
        
        Args:
            score: 原始乐谱
            ts: 拍号
            
        Returns:
            和弦伴奏小节列表
        """
        measures = []
        measure_len = ts.measure_length

        # 收集所有伴奏音符，按小节分组
        all_notes_by_measure: list[list[NoteData]] = []

        for part in score.accompaniment_parts:
            for i, measure in enumerate(part.measures):
                while len(all_notes_by_measure) <= i:
                    all_notes_by_measure.append([])
                all_notes_by_measure[i].extend(
                    n for n in measure.notes if not n.is_rest
                )

        # 确定需要生成的小节数
        max_measures = max(
            len(all_notes_by_measure),
            len(score.melody_part.measures) if score.melody_part else 0,
            1
        )

        for i in range(max_measures):
            if i < len(all_notes_by_measure) and all_notes_by_measure[i]:
                notes = all_notes_by_measure[i]
                # 提取音高集合
                pitches = sorted(set(n.pitch for n in notes))
                # 转到低音区
                bass_pitches = []
                for p in pitches:
                    while p > 48:
                        p -= 12
                    while p < 28:
                        p += 12
                    bass_pitches.append(p)

                # 去重
                bass_pitches = sorted(set(bass_pitches))[:4]  # 最多四个音

                if bass_pitches:
                    if measure_len >= 4:
                        # 4/4 拍：两个二分音符和弦
                        chord_dur = measure_len / 2
                        notes_out = [
                            NoteData(pitch=p, duration=chord_dur, velocity=60)
                            for p in bass_pitches
                        ]
                    else:
                        # 其他拍号：一个全时值和弦
                        notes_out = [
                            NoteData(pitch=p, duration=measure_len, velocity=60)
                            for p in bass_pitches
                        ]
                    measures.append(Measure(notes=notes_out))
                else:
                    measures.append(Measure(notes=[
                        NoteData(pitch=0, duration=measure_len, is_rest=True)
                    ]))
            else:
                # 没有伴奏数据，生成静音小节
                measures.append(Measure(notes=[
                    NoteData(pitch=0, duration=measure_len, is_rest=True)
                ]))

        return measures

    def _merge_consecutive_same_pitch(
        self, notes: list[NoteData]
    ) -> list[NoteData]:
        """合并连续相同音高的音符。
        
        Args:
            notes: 音符列表
            
        Returns:
            合并后的音符列表
        """
        if not notes:
            return notes

        merged = [notes[0]]
        for note in notes[1:]:
            prev = merged[-1]
            if (not prev.is_rest and not note.is_rest
                    and prev.pitch == note.pitch):
                # 合并时值
                merged[-1] = NoteData(
                    pitch=prev.pitch,
                    duration=prev.duration + note.duration,
                    velocity=prev.velocity,
                    is_rest=False,
                )
            else:
                merged.append(note)

        return merged
