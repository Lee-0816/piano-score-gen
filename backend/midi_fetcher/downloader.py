"""从网上搜索下载 MIDI 文件"""

import re
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from backend.midi_fetcher.base import MidiFetcher
from backend.config import OUTPUT_DIR, MIDI_DOWNLOAD_TIMEOUT, MAX_MIDI_FILE_SIZE


class WebMidiFetcher(MidiFetcher):
    """从公开 MIDI 网站搜索并下载 MIDI 文件。
    
    支持从 freemidi.org 等网站搜索。
    """

    SEARCH_SOURCES = [
        {
            "name": "freemidi",
            "search_url": "https://freemidi.org/search?q={query}",
            "base_url": "https://freemidi.org",
        },
    ]

    def __init__(self):
        """初始化 Web 下载器。"""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        })

    def _search_freemidi(self, song_name: str) -> Optional[str]:
        """从 freemidi.org 搜索 MIDI 下载链接。
        
        Args:
            song_name: 歌曲名称
            
        Returns:
            MIDI 文件下载 URL，未找到返回 None
        """
        try:
            search_url = f"https://freemidi.org/search?q={quote_plus(song_name)}"
            response = self.session.get(search_url, timeout=MIDI_DOWNLOAD_TIMEOUT)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # 查找 MIDI 下载链接
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                if href.endswith(".mid") or href.endswith(".midi"):
                    if not href.startswith("http"):
                        return f"https://freemidi.org{href}"
                    return href
        except Exception:
            pass
        return None

    def _download_midi(self, url: str, song_name: str) -> Optional[Path]:
        """下载 MIDI 文件到本地。
        
        Args:
            url: MIDI 文件 URL
            song_name: 歌曲名称（用于命名文件）
            
        Returns:
            保存的文件路径，下载失败返回 None
        """
        try:
            response = self.session.get(
                url, timeout=MIDI_DOWNLOAD_TIMEOUT, stream=True
            )
            response.raise_for_status()

            # 检查文件大小
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_MIDI_FILE_SIZE:
                return None

            # 清理文件名
            safe_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', song_name)
            file_path = OUTPUT_DIR / f"{safe_name}.mid"

            with open(file_path, "wb") as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    downloaded += len(chunk)
                    if downloaded > MAX_MIDI_FILE_SIZE:
                        file_path.unlink(missing_ok=True)
                        return None
                    f.write(chunk)

            return file_path
        except Exception:
            return None

    def fetch(self, song_name: str) -> Optional[Path]:
        """从网上搜索并下载 MIDI 文件。
        
        依次尝试各个搜索源。
        
        Args:
            song_name: 歌曲名称
            
        Returns:
            下载的文件路径，未找到返回 None
        """
        # 先尝试 freemidi
        midi_url = self._search_freemidi(song_name)
        if midi_url:
            return self._download_midi(midi_url, song_name)

        return None

    def available(self, song_name: str) -> bool:
        """检查网上是否有可下载的 MIDI 文件。
        
        Args:
            song_name: 歌曲名称
            
        Returns:
            是否找到
        """
        midi_url = self._search_freemidi(song_name)
        return midi_url is not None
