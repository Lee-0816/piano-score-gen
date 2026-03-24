"""简单版改编引擎

特点：
- 只保留主旋律（右手单音）
- 左手简化为柱式和弦（全音符/二分音符）
- 去掉装饰音（过于短促的音符）
- 音域限制在一个八度内
- 每个音都标注指法
- 自动转调到简单调号（C/G/F/D 大调，升降号不超过2个）
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

    # 优先使用的简单调号（升号/降号 ≤ 2 个）
    # 按"调号简单程度"排序
    # KeySignature(sharps=N) — sharps: 0=C, 1=G, 2=D, 3=A, 4=E, 5=B, 6=F#, 7=C#
    #                        — sharps: -1=F, -2=Bb, -3=Eb, -4=Ab, -5=Db
    # C(0), G(1)/F(-1), D(2)/Bb(-2) 都很简单
    SIMPLE_KEYS = [
        KeySignature(sharps=0),   # C major (0 升降)
        KeySignature(sharps=1),   # G major (1 升)
        KeySignature(sharps=-1),  # F major (1 降)
        KeySignature(sharps=2),   # D major (2 升)
        KeySignature(sharps=-2),  # Bb major (2 降)
        KeySignature(sharps=3),   # A major (3 升)
        KeySignature(sharps=-3),  # Eb major (3 降)
    ]

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

        # 计算最佳转调：找到距离最近的简单调号
        transpose_semitones, target_key = self._find_best_transpose(score.key)

        # 提取并简化右手旋律（带转调）
        rh_measures = self._build_melody(score, ts, transpose_semitones)

        # 生成左手简单和弦（带转调）
        lh_measures = self._build_chords(score, ts, transpose_semitones)

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
            key_signature=target_key,
            time_signature=ts,
        )

    def _find_best_transpose(self, original_key: KeySignature) -> tuple[int, KeySignature]:
        """找到距离原始调性最近的简单调号，返回需要的半音数。
        
        简单调号：升号/降号 ≤ 2 个（C, G, F, D, Bb）。
        
        Args:
            original_key: 原始调号
            
        Returns:
            (transpose_semitones, target_key) - 需要升降的半音数和目标调号
        """
        from backend.models.score import key_to_semitone

        original_semitone = key_to_semitone(original_key)

        # 如果原始调号已经够简单（≤ 2 升降），直接用
        if abs(original_key.sharps) <= 2:
            return 0, original_key

        # 寻找最近的简单调号
        best_transpose = 0
        best_key = self.SIMPLE_KEYS[0]  # 默认 C major
        best_distance = 12

        for key in self.SIMPLE_KEYS:
            target_semitone = key_to_semitone(key)
            diff = (target_semitone - original_semitone) % 12
            if diff > 6:
                diff = 12 - diff
            if diff < best_distance:
                best_distance = diff
                best_key = key
                # 计算需要的转调半音数
                transpose = (target_semitone - original_semitone) % 12
                if transpose > 6:
                    transpose -= 12
                best_transpose = transpose

        return best_transpose, best_key

    def _build_melody(self, score: Score, ts: TimeSignature, 
                      transpose: int = 0) -> list[Measure]:
        """构建右手旋律声部。
        
        从主旋律声部提取音符，过滤装饰音，限制音域。
        
        Args:
            score: 原始乐谱
            ts: 拍号
            transpose: 转调半音数（正值=升，负值=降）
            
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

                # 转调
                pitch = note.pitch + transpose

                # 限制音域
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

    def _build_chords(self, score: Score, ts: TimeSignature,
                      transpose: int = 0) -> list[Measure]:
        """构建左手和弦伴奏。
        
        从伴奏声部提取和弦信息，简化为柱式和弦。
        每小节一个或两个全音符/二分音符和弦。
        
        Args:
            score: 原始乐谱
            ts: 拍号
            transpose: 转调半音数
            
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
                # 提取音高集合（带转调）
                pitches = sorted(set(n.pitch + transpose for n in notes))
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
