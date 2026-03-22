"""MIDI 文件获取器抽象基类"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class MidiFetcher(ABC):
    """MIDI 文件获取器抽象基类。
    
    所有 MIDI 获取器都应继承此类并实现 fetch 方法。
    """

    @abstractmethod
    def fetch(self, song_name: str) -> Optional[Path]:
        """获取指定歌曲的 MIDI 文件。
        
        Args:
            song_name: 歌曲名称
            
        Returns:
            MIDI 文件路径，未找到时返回 None
        """
        pass

    @abstractmethod
    def available(self, song_name: str) -> bool:
        """检查指定歌曲是否有可用的 MIDI 文件。
        
        Args:
            song_name: 歌曲名称
            
        Returns:
            是否可用
        """
        pass
