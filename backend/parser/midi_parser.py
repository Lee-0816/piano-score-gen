"""MIDI 文件解析器

使用 music21 库解析 MIDI 文件，提取音符、调性、拍号、速度等信息。
自动识别主旋律轨道和伴奏轨道。
"""

from pathlib import Path
from typing import Optional

from music21 import converter, midi as m21midi, stream, note, chord, tempo, meter, key
from music21.pitch import Pitch

from backend.models.score import (
    Score, Part, Measure, NoteData,
    DifficultyLevel, TimeSignature, KeySignature
)
from backend.config import DEFAULT_TEMPO


class MidiParser:
    """MIDI 文件解析器。
    
    使用 music21 解析 MIDI 文件，提取结构化的乐谱数据。
    """

    def __init__(self):
        """初始化解析器。"""
        pass

    def parse(self, midi_path: Path, title: str = "", composer: str = "") -> Score:
        """解析 MIDI 文件并返回结构化 Score 对象。
        
        Args:
            midi_path: MIDI 文件路径
            title: 乐谱标题
            composer: 作曲者
            
        Returns:
            解析后的 Score 对象
            
        Raises:
            FileNotFoundError: MIDI 文件不存在
            ValueError: 无法解析 MIDI 文件
        """
        if not midi_path.exists():
            raise FileNotFoundError(f"MIDI 文件不存在: {midi_path}")

        try:
            score_stream = converter.parse(str(midi_path))
        except Exception as e:
            raise ValueError(f"无法解析 MIDI 文件: {e}")

        # 提取基本信息
        bpm = self._extract_tempo(score_stream)
        ts = self._extract_time_signature(score_stream)
        ks = self._extract_key_signature(score_stream)

        # 解析各轨道
        parts = self._extract_parts(score_stream)

        # 识别主旋律和伴奏
        melody_part, accompaniment_parts = self._identify_parts(parts)

        return Score(
            title=title or midi_path.stem,
            composer=composer or "Unknown",
            parts=parts,
            tempo=bpm,
            key=ks,
            time_signature=ts,
            melody_part=melody_part,
            accompaniment_parts=accompaniment_parts,
        )

    def _extract_tempo(self, score_stream: stream.Score) -> int:
        """从乐谱流中提取速度（BPM）。
        
        Args:
            score_stream: music21 乐谱流
            
        Returns:
            速度值（BPM）
        """
        tempi = score_stream.recurse().getElementsByClass(tempo.MetronomeMark)
        if tempi:
            return int(tempi[0].number)
        return DEFAULT_TEMPO

    def _extract_time_signature(self, score_stream: stream.Score) -> TimeSignature:
        """从乐谱流中提取拍号。
        
        Args:
            score_stream: music21 乐谱流
            
        Returns:
            TimeSignature 对象
        """
        time_sigs = score_stream.recurse().getElementsByClass(meter.TimeSignature)
        if time_sigs:
            ts = time_sigs[0]
            return TimeSignature(numerator=ts.numerator, denominator=ts.denominator)
        return TimeSignature(numerator=4, denominator=4)

    def _extract_key_signature(self, score_stream: stream.Score) -> KeySignature:
        """从乐谱流中提取调号。
        
        Args:
            score_stream: music21 乐谱流
            
        Returns:
            KeySignature 对象
        """
        key_sigs = score_stream.recurse().getElementsByClass(key.KeySignature)
        if key_sigs:
            ks = key_sigs[0]
            return KeySignature(sharps=ks.sharps, mode="major")
        return KeySignature(sharps=0, mode="major")

    def _extract_parts(self, score_stream: stream.Score) -> list[Part]:
        """从乐谱流中提取各声部。
        
        Args:
            score_stream: music21 乐谱流
            
        Returns:
            Part 对象列表
        """
        parts = []
        for i, part_stream in enumerate(score_stream.parts):
            part_name = part_stream.partName or f"Part {i + 1}"
            measures = self._extract_measures(part_stream)
            
            # 统计音符密度用于后续识别旋律
            note_count = sum(
                1 for m in measures for n in m.notes if not n.is_rest
            )
            
            parts.append(Part(
                name=part_name,
                measures=measures,
                note_count=note_count,
                avg_pitch=self._calc_avg_pitch(measures),
            ))
        
        return parts

    def _extract_measures(self, part_stream: stream.Part) -> list[Measure]:
        """从声部流中提取小节。
        
        Args:
            part_stream: music21 声部流
            
        Returns:
            Measure 对象列表
        """
        measures = []
        for measure_stream in part_stream.getElementsByClass(stream.Measure):
            notes = []
            
            for element in measure_stream.notesAndRests:
                if isinstance(element, note.Note):
                    notes.append(NoteData(
                        pitch=element.pitch.midi,
                        duration=element.duration.quarterLength,
                        velocity=element.volume.velocity or 80,
                        is_rest=False,
                    ))
                elif isinstance(element, chord.Chord):
                    # 和弦：取最高音作为主音
                    highest = max(element.pitches, key=lambda p: p.midi)
                    notes.append(NoteData(
                        pitch=highest.midi,
                        duration=element.duration.quarterLength,
                        velocity=element.volume.velocity or 80,
                        is_rest=False,
                    ))
                elif isinstance(element, note.Rest):
                    notes.append(NoteData(
                        pitch=0,
                        duration=element.duration.quarterLength,
                        velocity=0,
                        is_rest=True,
                    ))

            if notes:
                measures.append(Measure(notes=notes))

        return measures

    def _calc_avg_pitch(self, measures: list[Measure]) -> float:
        """计算声部的平均音高。
        
        Args:
            measures: 小节列表
            
        Returns:
            平均 MIDI 音高值
        """
        pitches = [
            n.pitch for m in measures for n in m.notes if not n.is_rest
        ]
        return sum(pitches) / len(pitches) if pitches else 60.0

    def _identify_parts(
        self, parts: list[Part]
    ) -> tuple[Optional[Part], list[Part]]:
        """识别主旋律声部和伴奏声部。
        
        规则：平均音高最高的声部通常为主旋律。
        
        Args:
            parts: 声部列表
            
        Returns:
            (主旋律声部, 伴奏声部列表)
        """
        if not parts:
            return None, []

        if len(parts) == 1:
            return parts[0], []

        # 按平均音高排序，最高的作为旋律
        sorted_parts = sorted(parts, key=lambda p: p.avg_pitch, reverse=True)
        melody = sorted_parts[0]
        accompaniment = sorted_parts[1:]

        return melody, accompaniment
