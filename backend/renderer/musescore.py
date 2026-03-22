"""MuseScore 渲染器

将 ArrangementResult 渲染为 MusicXML 和 PDF 文件。
优先使用 MuseScore CLI (mscore) 渲染 PDF，
若不可用则仅输出 MusicXML。
"""

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from music21 import (
    stream, meter, key, tempo, clef, instrument,
    note as m21note, chord as m21chord, duration as m21duration,
    layout, metadata, expressions
)

from backend.models.score import ArrangementResult, NoteData, Measure
from backend.config import MUSESCORE_PATHS, OUTPUT_DIR


class MuseScoreRenderer:
    """乐谱渲染器。
    
    将改编结果渲染为 MusicXML 和 PDF 文件。
    """

    def __init__(self):
        """初始化渲染器，检测 MuseScore 可用性。"""
        self.musescore_path = self._find_musescore()

    def _find_musescore(self) -> Optional[str]:
        """查找 MuseScore 可执行文件路径。
        
        Returns:
            MuseScore 路径，未找到返回 None
        """
        for path in MUSESCORE_PATHS:
            if Path(path).exists():
                return path
            found = shutil.which(path)
            if found:
                return found
        return None

    @property
    def has_musescore(self) -> bool:
        """MuseScore 是否可用。"""
        return self.musescore_path is not None

    def render(
        self,
        arrangement: ArrangementResult,
        output_dir: Optional[Path] = None,
        output_format: str = "both",
    ) -> dict[str, Path]:
        """渲染改编结果为文件。
        
        Args:
            arrangement: 改编结果
            output_dir: 输出目录
            output_format: 输出格式 ("xml", "pdf", "both")
            
        Returns:
            输出文件路径字典 {"xml": Path, "pdf": Path}
        """
        if output_dir is None:
            output_dir = OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        # 构建 music21 乐谱流
        score_stream = self._build_score_stream(arrangement)

        # 生成安全文件名
        safe_name = self._safe_filename(arrangement.title)
        results = {}

        # 导出 MusicXML
        if output_format in ("xml", "both"):
            xml_path = output_dir / f"{safe_name}.musicxml"
            score_stream.write("musicxml", fp=str(xml_path))
            results["xml"] = xml_path

        # 渲染 PDF
        if output_format in ("pdf", "both"):
            if self.has_musescore:
                pdf_path = output_dir / f"{safe_name}.pdf"
                if output_format == "pdf":
                    # 需要先生成临时 XML
                    xml_tmp = output_dir / f"{safe_name}_tmp.musicxml"
                    score_stream.write("musicxml", fp=str(xml_tmp))
                    self._render_pdf(xml_tmp, pdf_path)
                    xml_tmp.unlink(missing_ok=True)
                elif "xml" in results:
                    self._render_pdf(results["xml"], pdf_path)
                results["pdf"] = pdf_path
            else:
                print(f"⚠️  MuseScore 未安装，跳过 PDF 渲染。请安装 MuseScore 后重试。")

        return results

    def render_to_pdf(
        self,
        arrangement: ArrangementResult,
        output_path: Path,
    ) -> Optional[Path]:
        """直接渲染为 PDF。
        
        Args:
            arrangement: 改编结果
            output_path: PDF 输出路径
            
        Returns:
            PDF 文件路径，失败返回 None
        """
        results = self.render(
            arrangement,
            output_dir=output_path.parent,
            output_format="pdf" if self.has_musescore else "xml",
        )
        return results.get("pdf") or results.get("xml")

    def _build_score_stream(self, arrangement: ArrangementResult) -> stream.Score:
        """将改编结果构建为 music21 乐谱流。
        
        Args:
            arrangement: 改编结果
            
        Returns:
            music21 Score 流
        """
        score = stream.Score()

        # 元数据
        score.metadata = metadata.Metadata()
        score.metadata.title = arrangement.title
        score.metadata.composer = ""

        # 设置拍号、调号、速度
        ts = arrangement.time_signature
        ks = arrangement.key_signature
        tempo_mark = tempo.MetronomeMark(number=arrangement.tempo)

        # 构建右手声部
        if arrangement.right_hand and arrangement.right_hand.measures:
            rh_part = self._build_part_stream(
                arrangement.right_hand,
                ts, ks, tempo_mark,
                instrument.Piano(),
                clef.TrebleClef(),
            )
            score.insert(0, rh_part)

        # 构建左手声部
        if arrangement.left_hand and arrangement.left_hand.measures:
            lh_part = self._build_part_stream(
                arrangement.left_hand,
                ts, ks, None,
                instrument.Piano(),
                clef.BassClef(),
            )
            score.insert(0, lh_part)

        return score

    def _build_part_stream(
        self,
        part_data,
        ts,
        ks,
        tempo_mark,
        instr,
        clef_obj,
    ) -> stream.Part:
        """构建单个声部流。
        
        Args:
            part_data: Part 数据对象
            ts: 拍号
            ks: 调号
            tempo_mark: 速度标记（仅右手需要）
            instr: 乐器
            clef_obj: 谱号
            
        Returns:
            music21 Part 流
        """
        part = stream.Part()
        part.insert(0, instr)

        for i, measure_data in enumerate(part_data.measures):
            m = stream.Measure(number=i + 1)

            # 第一小节添加谱号、拍号、调号、速度
            if i == 0:
                m.insert(0, clef_obj)
                m.insert(0, meter.TimeSignature(f"{ts.numerator}/{ts.denominator}"))

                if ks.sharps != 0:
                    m.insert(0, key.KeySignature(ks.sharps))

                if tempo_mark:
                    m.insert(0, tempo_mark)

            # 添加音符
            offset = 0.0
            for note_data in measure_data.notes:
                if note_data.is_rest:
                    rest = m21note.Rest(
                        duration=m21duration.Duration(note_data.duration)
                    )
                    m.insert(offset, rest)
                else:
                    n = m21note.Note(
                        midi=note_data.pitch,
                        duration=m21duration.Duration(note_data.duration),
                    )
                    n.volume.velocity = note_data.velocity

                    # 添加指法标注
                    if note_data.fingering is not None:
                        fingering_text = expressions.TextExpression(str(note_data.fingering))
                        fingering_text.style.fontSize = 10
                        fingering_text.style.fontStyle = "italic"
                        m.insert(offset, fingering_text)

                    m.insert(offset, n)

                offset += note_data.duration

            part.append(m)

        return part

    def _render_pdf(self, xml_path: Path, pdf_path: Path) -> bool:
        """使用 MuseScore CLI 将 MusicXML 渲染为 PDF。
        
        Args:
            xml_path: MusicXML 输入路径
            pdf_path: PDF 输出路径
            
        Returns:
            是否成功
        """
        if not self.musescore_path:
            return False

        try:
            cmd = [
                self.musescore_path,
                "-o", str(pdf_path),
                str(xml_path),
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode == 0 and pdf_path.exists()
        except (subprocess.TimeoutExpired, Exception) as e:
            print(f"⚠️  MuseScore 渲染失败: {e}")
            return False

    def _safe_filename(self, title: str) -> str:
        """生成安全的文件名。
        
        Args:
            title: 标题
            
        Returns:
            安全的文件名
        """
        import re
        # 保留中英文、数字、下划线
        safe = re.sub(r'[^\w\u4e00-\u9fff]', '_', title)
        safe = re.sub(r'_+', '_', safe).strip('_')
        return safe or "score"
