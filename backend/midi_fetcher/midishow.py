"""Midishow MIDI 文件获取器

Midishow (midishow.com) 是中文 MIDI 音乐分享网站。

使用方式:
    from backend.midi_fetcher.midishow import MidishowFetcher
    
    # 方式一：环境变量（推荐）
    # export MIDISHOW_USERNAME="xxx"
    # export MIDISHOW_PASSWORD="xxx"
    fetcher = MidishowFetcher()
    
    # 方式二：代码中传入
    fetcher = MidishowFetcher(username="xxx", password="xxx")
    
    midi_path = fetcher.fetch("这世界那么多人")

依赖:
    pip install requests beautifulsoup4
"""

import os
import re
from pathlib import Path
from typing import Optional

from backend.midi_fetcher.base import MidiFetcher
from backend.config import OUTPUT_DIR, MIDI_DOWNLOAD_TIMEOUT, MAX_MIDI_FILE_SIZE


class MidishowFetcher(MidiFetcher):
    """从 midishow.com 获取 MIDI 文件。
    
    支持登录后下载（需要账户积分）。
    """
    
    BASE_URL = "https://www.midishow.com"
    LOGIN_URL = f"{BASE_URL}/user/account/login"
    SEARCH_URL = f"{BASE_URL}/search/result"
    
    def __init__(self, username: str = None, password: str = None):
        """初始化 Midishow 下载器。
        
        Args:
            username: Midishow 用户名（可选，也可通过环境变量设置）
            password: Midishow 密码（可选，也可通过环境变量设置）
        """
        self.username = username or os.getenv("MIDISHOW_USERNAME", "")
        self.password = password or os.getenv("MIDISHOW_PASSWORD", "")
        self._session = None
        self._logged_in = False
    
    def _get_session(self):
        """获取或初始化 HTTP 会话。"""
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            })
        return self._session
    
    def _safe_filename(self, name: str) -> str:
        """生成安全的文件名。"""
        safe = re.sub(r'[^\w\u4e00-\u9fff]', '_', name)
        safe = re.sub(r'_+', '_', safe).strip('_')
        return safe or "midi_file"
    
    def _get_csrf_token(self, html: str) -> str:
        """从 HTML 中提取 CSRF token。"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        csrf_input = soup.find("input", {"name": "_csrf"})
        return csrf_input.get("value", "") if csrf_input else ""
    
    def login(self) -> bool:
        """登录 Midishow。
        
        Returns:
            是否登录成功
        """
        if self._logged_in:
            return True
        
        if not self.username or not self.password:
            print("未设置 Midishow 账户，无法登录")
            return False
        
        session = self._get_session()
        
        try:
            # 获取登录页面的 CSRF token
            r = session.get(self.LOGIN_URL, timeout=15, verify=False)
            csrf_token = self._get_csrf_token(r.text)
            
            # 提交登录表单
            login_data = {
                "_csrf": csrf_token,
                "LoginForm[identity]": self.username,
                "LoginForm[password]": self.password,
                "LoginForm[rememberMe]": "0",
            }
            r2 = session.post(
                self.LOGIN_URL, data=login_data,
                timeout=15, verify=False, allow_redirects=True
            )
            
            # 检查登录是否成功
            if "account" not in r2.url.lower() or "login" not in r2.url.lower():
                self._logged_in = True
                print("登录成功")
                return True
            else:
                print("登录失败，请检查用户名和密码")
                return False
                
        except Exception as e:
            print(f"登录出错: {e}")
            return False
    
    def search(self, song_name: str) -> list[dict]:
        """搜索 MIDI 文件。
        
        Args:
            song_name: 歌曲名称
            
        Returns:
            搜索结果列表，每项包含 {id, title, url}
        """
        import urllib.parse
        from bs4 import BeautifulSoup
        
        session = self._get_session()
        
        try:
            url = f"{self.SEARCH_URL}?q={urllib.parse.quote(song_name)}"
            r = session.get(url, timeout=MIDI_DOWNLOAD_TIMEOUT, verify=False)
            soup = BeautifulSoup(r.text, "html.parser")
            
            # 找 MIDI 详情页链接
            links = soup.find_all("a", href=True)
            midi_links = []
            seen_ids = set()
            
            for a in links:
                href = a.get("href", "")
                m = re.search(r'/midi/(\d+)', href)
                if m and "browse" not in href:
                    midi_id = m.group(1)
                    if midi_id not in seen_ids:
                        seen_ids.add(midi_id)
                        title = a.get_text(strip=True)[:80]
                        midi_links.append({
                            "id": midi_id,
                            "title": title,
                            "url": href
                        })
            
            return midi_links
            
        except Exception as e:
            print(f"搜索失败: {e}")
            return []
    
    def download(self, midi_id: str, song_name: str = "midi_file") -> Optional[Path]:
        """下载 MIDI 文件。
        
        下载流程:
        1. 访问详情页获取 data-mid token
        2. POST 下载表单提交（带 CSRF）
        3. 解析 meta refresh 跳转链接
        4. GET 下载文件
        
        Args:
            midi_id: MIDI 文件 ID
            song_name: 歌曲名称（用于命名文件）
            
        Returns:
            保存的文件路径，失败返回 None
        """
        from bs4 import BeautifulSoup
        
        session = self._get_session()
        
        try:
            # 确保已登录
            if not self.login():
                return None
            
            # 1. 访问详情页
            detail_url = f"{self.BASE_URL}/midi/{midi_id}.html"
            session.get(detail_url, timeout=15, verify=False)
            
            # 2. 获取下载页面的 CSRF token
            dl_page_url = f"{self.BASE_URL}/midi/download?id={midi_id}"
            r_dl = session.get(dl_page_url, timeout=15, verify=False)
            soup_dl = BeautifulSoup(r_dl.text, "html.parser")
            
            # 找下载表单
            dl_form = soup_dl.find("form", {"action": lambda x: x and "download" in x})
            if not dl_form:
                print("未找到下载表单")
                return None
            
            csrf_elem = dl_form.find("input", {"name": "_csrf"})
            if not csrf_elem:
                print("未找到 CSRF token")
                return None
            
            csrf_token = csrf_elem.get("value", "")
            
            # 3. POST 提交下载表单
            r_post = session.post(
                dl_page_url,
                data={"_csrf": csrf_token},
                timeout=30, verify=False,
                headers={"Referer": dl_page_url}
            )
            
            # 4. 解析 meta refresh 跳转链接
            meta_match = re.search(r'url=([^"\'>\s;]+)', r_post.text)
            if not meta_match:
                # 检查是否需要积分
                if "积分" in r_post.text:
                    print("积分不足，无法下载")
                else:
                    print("无法解析下载链接")
                return None
            
            download_token_url = meta_match.group(1)
            full_url = f"{self.BASE_URL}{download_token_url}"
            
            # 5. 下载文件
            r_final = session.get(
                full_url, timeout=MIDI_DOWNLOAD_TIMEOUT, verify=False, stream=True,
                headers={"Referer": dl_page_url}
            )
            
            # 验证 MIDI 文件头
            chunk = next(r_final.iter_content(chunk_size=16))
            if chunk[:4] != b'MThd':
                print(f"下载的不是 MIDI 文件 (头部: {chunk[:4]})")
                return None
            
            # 保存文件
            safe_name = self._safe_filename(song_name)
            file_path = OUTPUT_DIR / f"{safe_name}.mid"
            
            with open(file_path, "wb") as f:
                f.write(chunk)
                for c in r_final.iter_content(chunk_size=8192):
                    if c:
                        f.write(c)
            
            print(f"下载成功: {file_path}")
            return file_path
            
        except Exception as e:
            print(f"下载失败: {e}")
            return None
    
    def fetch(self, song_name: str) -> Optional[Path]:
        """搜索并下载 MIDI 文件。
        
        Args:
            song_name: 歌曲名称
            
        Returns:
            MIDI 文件路径，未找到返回 None
        """
        # 搜索
        results = self.search(song_name)
        if not results:
            print(f"未找到: {song_name}")
            return None
        
        # 打印搜索结果
        print(f"找到 {len(results)} 个结果:")
        for i, r in enumerate(results[:5]):
            print(f"  [{i+1}] {r['title'][:60]} (ID: {r['id']})")
        
        # 取第一个结果
        result = results[0]
        print(f"选择: {result['title'][:60]}")
        
        # 下载
        return self.download(result["id"], song_name)
    
    def available(self, song_name: str) -> bool:
        """检查 midishow 是否有该歌曲的 MIDI。
        
        Args:
            song_name: 歌曲名称
            
        Returns:
            是否可用
        """
        results = self.search(song_name)
        return len(results) > 0