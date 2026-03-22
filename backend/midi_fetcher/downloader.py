"""从网上搜索下载 MIDI 文件

支持多个 MIDI 数据源：
- freemidi.org
- mididb.com
- 直接 URL 下载
"""

import re
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

from backend.midi_fetcher.base import MidiFetcher
from backend.config import OUTPUT_DIR, MIDI_DOWNLOAD_TIMEOUT, MAX_MIDI_FILE_SIZE


class WebMidiFetcher(MidiFetcher):
    """从公开 MIDI 网站搜索并下载 MIDI 文件。
    
    支持多个数据源，自动尝试各个来源。
    """

    def __init__(self):
        """初始化 Web 下载器。"""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })

    def _safe_filename(self, name: str) -> str:
        """生成安全的文件名。"""
        safe = re.sub(r'[^\w\u4e00-\u9fff]', '_', name)
        safe = re.sub(r'_+', '_', safe).strip('_')
        return safe or "midi_file"

    # ──────────────────────────────────────────────
    # Source 1: freemidi.org
    # ──────────────────────────────────────────────

    def _search_freemidi(self, song_name: str) -> Optional[str]:
        """从 freemidi.org 搜索 MIDI 下载链接。"""
        try:
            url = f"https://freemidi.org/search?q={quote_plus(song_name)}"
            r = self.session.get(url, timeout=MIDI_DOWNLOAD_TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if href.endswith((".mid", ".midi")):
                    return urljoin("https://freemidi.org", href)
        except Exception:
            pass
        return None

    # ──────────────────────────────────────────────
    # Source 2: mididb.com
    # ──────────────────────────────────────────────

    def _search_mididb(self, song_name: str) -> Optional[str]:
        """从 mididb.com 搜索 MIDI 下载链接。"""
        try:
            url = f"https://www.mididb.com/search/?q={quote_plus(song_name)}"
            r = self.session.get(url, timeout=MIDI_DOWNLOAD_TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            # mididb 搜索结果页的链接格式
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "/download/" in href and href.endswith((".mid", ".midi")):
                    return urljoin("https://www.mididb.com", href)
                if href.endswith((".mid", ".midi")):
                    return urljoin("https://www.mididb.com", href)
        except Exception:
            pass
        return None

    # ──────────────────────────────────────────────
    # Source 3: midiworld.com
    # ──────────────────────────────────────────────

    def _search_midiworld(self, song_name: str) -> Optional[str]:
        """从 midiworld.com 搜索 MIDI 下载链接。"""
        try:
            url = f"https://www.midiworld.com/search/?q={quote_plus(song_name)}"
            r = self.session.get(url, timeout=MIDI_DOWNLOAD_TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if href.endswith((".mid", ".midi")):
                    return urljoin("https://www.midiworld.com", href)
        except Exception:
            pass
        return None

    # ──────────────────────────────────────────────
    # 下载
    # ──────────────────────────────────────────────

    def _download_midi(self, url: str, song_name: str) -> Optional[Path]:
        """下载 MIDI 文件到本地。"""
        try:
            r = self.session.get(url, timeout=MIDI_DOWNLOAD_TIMEOUT, stream=True)
            r.raise_for_status()

            # 检查 content-type
            ct = r.headers.get("Content-Type", "")
            if "html" in ct and not url.endswith((".mid", ".midi")):
                # 可能是网页而不是文件，检查文件大小
                pass

            content_length = r.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_MIDI_FILE_SIZE:
                return None

            # 验证文件头部是否为 MIDI
            chunk = next(r.iter_content(chunk_size=16))
            if chunk[:4] != b'MThd':
                # 不是标准 MIDI 文件
                # 有些站点会返回重定向页面，尝试从中提取真实链接
                return None

            safe_name = self._safe_filename(song_name)
            file_path = OUTPUT_DIR / f"{safe_name}.mid"

            with open(file_path, "wb") as f:
                f.write(chunk)  # 写入已读取的头部
                downloaded = len(chunk)
                for chunk in r.iter_content(chunk_size=8192):
                    downloaded += len(chunk)
                    if downloaded > MAX_MIDI_FILE_SIZE:
                        file_path.unlink(missing_ok=True)
                        return None
                    f.write(chunk)

            return file_path
        except Exception:
            return None

    def download_from_url(self, url: str, song_name: str) -> Optional[Path]:
        """直接从 URL 下载 MIDI 文件。
        
        Args:
            url: MIDI 文件的直接下载链接
            song_name: 歌曲名称（用于命名文件）
            
        Returns:
            保存的文件路径，失败返回 None
        """
        return self._download_midi(url, song_name)

    # ──────────────────────────────────────────────
    # 主搜索逻辑
    # ──────────────────────────────────────────────

    def _generate_search_variants(self, song_name: str) -> list[str]:
        """生成搜索关键词变体。
        
        为中文歌曲生成可能的英文搜索词。
        
        Args:
            song_name: 原始歌曲名
            
        Returns:
            搜索关键词列表
        """
        variants = [song_name]

        # 添加 "piano" 后缀
        if "piano" not in song_name.lower():
            variants.append(f"{song_name} piano")

        # 添加 "MIDI" 后缀
        if "midi" not in song_name.lower():
            variants.append(f"{song_name} MIDI")

        # 纯英文搜索（去掉中文）
        chinese = re.findall(r'[\u4e00-\u9fff]+', song_name)
        english = re.findall(r'[a-zA-Z\s]+', song_name)
        if english:
            en_name = " ".join(english).strip()
            if en_name and en_name != song_name:
                variants.append(en_name)

        return variants

    def fetch(self, song_name: str) -> Optional[Path]:
        """从网上搜索并下载 MIDI 文件。
        
        依次尝试各个搜索源和关键词变体。
        
        Args:
            song_name: 歌曲名称
            
        Returns:
            下载的文件路径，未找到返回 None
        """
        variants = self._generate_search_variants(song_name)

        for variant in variants:
            # 1. freemidi.org
            url = self._search_freemidi(variant)
            if url:
                result = self._download_midi(url, song_name)
                if result:
                    return result

            # 2. mididb.com
            url = self._search_mididb(variant)
            if url:
                result = self._download_midi(url, song_name)
                if result:
                    return result

            # 3. midiworld.com
            url = self._search_midiworld(variant)
            if url:
                result = self._download_midi(url, song_name)
                if result:
                    return result

        return None

    def available(self, song_name: str) -> bool:
        """检查网上是否有可下载的 MIDI 文件。"""
        variants = self._generate_search_variants(song_name)
        for variant in variants:
            if self._search_freemidi(variant):
                return True
            if self._search_mididb(variant):
                return True
            if self._search_midiworld(variant):
                return True
        return False
