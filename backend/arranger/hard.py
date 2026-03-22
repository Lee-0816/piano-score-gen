"""难版改编引擎

特点：
- 尽量还原原曲
- 左手使用琶音与和弦
- 保留节奏复杂度
- 只在难点位置标注指法
"""

from backend.arranger.base import Arranger
from backend.models.score import (
    Score, ArrangementResult, Part, Measure, NoteData,
    DifficultyLevel, TimeSignature
)
from backend.fingering.engine import FingeringEngine
from backend.config import PIANO_LOWEST_PITCH, PIANO_HIGHEST_PITCH


class HardArranger(Arranger):
    """难版改编器。
    
    尽可能保留原始乐谱的复杂度。
    """

    @property
    def difficulty(self) -> DifficultyLevel:
        """返回困难难度。"""
        return DifficultyLevel.HARD

    def arrange(self, score: Score) -> ArrangementResult:
        """将乐谱改编为难版。
        
        Args:
            score: 原始乐谱
            
        Returns:
            难版改编结果
        """
        ts = score.time_signature

        # 右手：尽量保留原始旋律
        rh_measures = self._build_melody(score, ts)

        # 左手：琶音 + 和弦伴奏
        lh_measures = self._build_arpeggio(score, ts)

        # 只在难点位置标注指法
        fingering_engine = FingeringEngine()
        rh_measures = fingering_engine.assign_to_measures(
            rh_measures, DifficultyLevel.HARD
        )

        rh_part = self._merge_measures_to_part("Piano - Right Hand", rh_measures)
        lh_part = self._merge_measures_to_part("Piano - Left Hand", lh_measures)

        return ArrangementResult(
            difficulty=DifficultyLevel.HARD,
            right_hand=rh_part,
            left_hand=lh_part,
            title=f"{score.title} (难版)",
            tempo=score.tempo,
            key_signature=score.key,
            time_signature=ts,
        )

    def _build_melody(self, score: Score, ts: TimeSignature) -> list[Measure]:
        """构建右手旋律声部。
        
        尽量保留原始音符，仅做必要调整。
        
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

                # 难版放宽音域限制
                pitch = note.pitch
                while pitch > PIANO_HIGHEST_PITCH + 5:
                    pitch -= 12
                while pitch < PIANO_LOWEST_PITCH - 5:
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

    def _build_arpeggio(
        self, score: Score, ts: TimeSignature
    ) -> list[Measure]:
        """构建左手琶音与和弦伴奏。
        
        结合琶音和柱式和弦，保留原始节奏。
        
        Args:
            score: 原始乐谱
            ts: 拍号
            
        Returns:
            伴奏小节列表
        """
        measures = []
        measure_len = ts.measure_length

        # 收集伴奏音符，按小节分组
        all_notes_by_measure: list[list[NoteData]] = []
        for part in score.accompaniment_parts:
            for i, measure in enumerate(part.measures):
                while len(all_notes_by_measure) <= i:
                    all_notes_by_measure.append([])
                all_notes_by_measure[i].extend(
                    n for n in measure.notes if not n.is_rest
                )

        max_measures = max(
            len(all_notes_by_measure),
            len(score.melody_part.measures) if score.melody_part else 0,
            1
        )

        for i in range(max_measures):
            if i < len(all_notes_by_measure) and all_notes_by_measure[i]:
                notes = all_notes_by_measure[i]
                pitches = sorted(set(n.pitch for n in notes))

                # 转到低音区
                bass_pitches = []
                for p in pitches:
                    while p > 52:
                        p -= 12
                    while p < 24:
                        p += 12
                    bass_pitches.append(p)
                bass_pitches = sorted(set(bass_pitches))

                if len(bass_pitches) >= 3:
                    # 琶音模式：上行分解和弦
                    beat_dur = ts.beat_unit
                    arp_notes = []

                    # 使用全部和弦音做琶音
                    for p in bass_pitches[:6]:
                        arp_notes.append(NoteData(
                            pitch=p,
                            duration=beat_dur * 0.5,
                            velocity=65,
                        ))

                    # 如果不够一整小节，补充柱式和弦
                    remaining = measure_len - sum(n.duration for n in arp_notes)
                    if remaining > 0 and bass_pitches:
                        arp_notes.append(NoteData(
                            pitch=bass_pitches[0],
                            duration=remaining,
                            velocity=70,
                        ))

                    measures.append(Measure(notes=arp_notes))
                elif bass_pitches:
                    # 音不足，用柱式和弦
                    notes_out = [
                        NoteData(pitch=p, duration=measure_len, velocity=65)
                        for p in bass_pitches[:4]
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
