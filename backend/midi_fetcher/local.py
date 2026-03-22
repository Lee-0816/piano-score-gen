"""本地 MIDI 文件加载器"""

import glob
from pathlib import Path
from typing import Optional

from backend.midi_fetcher.base import MidiFetcher
from backend.config import SAMPLES_DIR


class LocalMidiFetcher(MidiFetcher):
    """从本地 samples 目录加载 MIDI 文件。
    
    支持按歌曲名称模糊匹配文件名。
    """

    def __init__(self, search_dir: Optional[Path] = None):
        """初始化本地加载器。
        
        Args:
            search_dir: 搜索目录，默认为 samples 目录
        """
        self.search_dir = search_dir or SAMPLES_DIR

    def _normalize(self, text: str) -> str:
        """标准化文本用于匹配（去空格、小写化）。
        
        Args:
            text: 输入文本
            
        Returns:
            标准化后的文本
        """
        return text.replace(" ", "").replace("_", "").lower()

    def fetch(self, song_name: str) -> Optional[Path]:
        """在本地目录中查找匹配的 MIDI 文件。
        
        首先尝试精确匹配，然后尝试模糊匹配。
        
        Args:
            song_name: 歌曲名称
            
        Returns:
            匹配的 MIDI 文件路径，未找到返回 None
        """
        if not self.search_dir.exists():
            return None

        # 收集所有 MIDI 文件
        midi_extensions = ["*.mid", "*.midi", "*.MID", "*.MIDI"]
        midi_files = []
        for ext in midi_extensions:
            midi_files.extend(glob.glob(str(self.search_dir / ext)))

        if not midi_files:
            return None

        normalized_name = self._normalize(song_name)

        # 精确匹配
        for midi_file in midi_files:
            file_stem = Path(midi_file).stem
            if self._normalize(file_stem) == normalized_name:
                return Path(midi_file)

        # 模糊匹配（包含关系）
        for midi_file in midi_files:
            file_stem = Path(midi_file).stem
            if normalized_name in self._normalize(file_stem):
                return Path(midi_file)
            if self._normalize(file_stem) in normalized_name:
                return Path(midi_file)

        return None

    def available(self, song_name: str) -> bool:
        """检查本地是否有匹配的 MIDI 文件。
        
        Args:
            song_name: 歌曲名称
            
        Returns:
            是否找到匹配文件
        """
        return self.fetch(song_name) is not None
