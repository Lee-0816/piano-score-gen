"""Midishow MIDI 文件获取器

Midishow (midishow.com) 是中文 MIDI 音乐分享网站。

注意：
- 该站需要注册账户并消耗积分（注册送5积分）才能下载
- 使用环境变量设置账户信息:
    MIDISHOW_USERNAME: Midishow 用户名
    MIDISHOW_PASSWORD: Midishow 密码
- 或通过 MidishowFetcher.set_credentials() 设置

依赖：
    pip install playwright  (Playwright 版本，支持动态加载)
    playwright install chromium
    或
    pip install requests beautifulsoup4  (简单版，大部分情况够用)
"""

import os
import re
from pathlib import Path
from typing import Optional

from backend.midi_fetcher.base import MidiFetcher
from backend.config import OUTPUT_DIR, MIDI_DOWNLOAD_TIMEOUT, MAX_MIDI_FILE_SIZE


class MidishowFetcher(MidiFetcher):
    """从 midishow.com 获取 MIDI 文件。
    
    Midishow 需要登录账户才能下载文件。
    使用 Playwright 浏览器自动化处理 JS 动态加载和登录。
    
    环境变量:
        MIDISHOW_USERNAME: Midishow 用户名
        MIDISHOW_PASSWORD: Midishow 密码
    """

    def __init__(self, username: str = None, password: str = None):
        """初始化 Midishow 下载器。
        
        Args:
            username: Midishow 用户名（可选，也可通过环境变量设置）
            password: Midishow 密码（可选，也可通过环境变量设置）
        """
        self.base_url = "https://www.midishow.com"
        self.username = username or os.getenv("MIDISHOW_USERNAME", "")
        self.password = password or os.getenv("MIDISHOW_PASSWORD", "")
        self._playwright = None
        self._browser = None
        self._page = None
        self._logged_in = False

    def set_credentials(self, username: str, password: str):
        """设置 Midishow 登录凭据。
        
        Args:
            username: 用户名
            password: 密码
        """
        self.username = username
        self.password = password
        self._logged_in = False

    def _get_browser(self):
        """获取或初始化浏览器实例。"""
        if self._playwright is None:
            try:
                from playwright.sync_api import sync_playwright
                self._playwright = sync_playwright().start()
                self._browser = self._playwright.chromium.launch(headless=True)
                self._page = self._browser.new_page()
            except ImportError:
                print("警告: Playwright 未安装，请运行: pip install playwright && playwright install chromium")
                return None
            except Exception as e:
                print(f"警告: 浏览器启动失败: {e}")
                return None
        return self._page

    def _login(self) -> bool:
        """登录 Midishow。
        
        Returns:
            是否登录成功
        """
        if self._logged_in:
            return True
        
        if not self.username or not self.password:
            print("未设置 Midishow 账户，跳过登录（下载可能受限）")
            return False
        
        page_obj = self._get_browser()
        if page_obj is None:
            return False
        
        try:
            page_obj.goto(f"{self.base_url}/user/account/login", timeout=30000)
            page_obj.wait_for_timeout(2000)
            
            # 填写登录表单
            page_obj.fill('input[name="login-form[username]"]', self.username)
            page_obj.fill('input[name="login-form[password]"]', self.password)
            
            # 提交
            page_obj.click('button[type="submit"], input[type="submit"]')
            page_obj.wait_for_timeout(3000)
            
            # 检查是否登录成功
            if "login" not in page_obj.url.lower():
                self._logged_in = True
                print("登录成功")
                return True
            else:
                print("登录失败，请检查用户名和密码")
                return False
                
        except Exception as e:
            print(f"登录出错: {e}")
            return False

    def _safe_filename(self, name: str) -> str:
        """生成安全的文件名。"""
        safe = re.sub(r'[^\w\u4e00-\u9fff]', '_', name)
        safe = re.sub(r'_+', '_', safe).strip('_')
        return safe or "midi_file"

    def _search_midishow(self, song_name: str) -> list[dict]:
        """搜索 midishow 并返回结果列表。
        
        Args:
            song_name: 歌曲名称
            
        Returns:
            搜索结果列表，每项包含 {id, title, url}
        """
        import requests
        from bs4 import BeautifulSoup
        import urllib.parse
        
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            })
            
            url = f"{self.base_url}/search/result?q={urllib.parse.quote(song_name)}"
            r = session.get(url, timeout=MIDI_DOWNLOAD_TIMEOUT, verify=False)
            soup = BeautifulSoup(r.text, "html.parser")
            
            # 找 MIDI 详情页链接
            links = soup.find_all("a", href=True)
            midi_links = []
            for a in links:
                href = a.get("href", "")
                m = re.search(r'/midi/(\d+)', href)
                if m and "browse" not in href:
                    midi_id = m.group(1)
                    title = a.get_text(strip=True)[:80]
                    midi_links.append({
                        "id": midi_id,
                        "title": title,
                        "url": href
                    })
            
            # 去重
            seen = set()
            unique_links = []
            for link in midi_links:
                if link["id"] not in seen:
                    seen.add(link["id"])
                    unique_links.append(link)
            
            return unique_links
            
        except Exception as e:
            print(f"搜索失败: {e}")
            return []

    def _download_midi(self, midi_id: str, song_name: str) -> Optional[Path]:
        """下载 MIDI 文件。
        
        Args:
            midi_id: MIDI 文件 ID
            song_name: 歌曲名称
            
        Returns:
            保存的文件路径
        """
        import requests
        
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            })
            
            # 先访问详情页获取 cookies
            session.get(f"{self.base_url}/midi/{midi_id}.html", timeout=15, verify=False)
            
            # 尝试下载
            url = f"{self.base_url}/midi/download?id={midi_id}"
            r = session.get(url, timeout=MIDI_DOWNLOAD_TIMEOUT, verify=False, stream=True, allow_redirects=True)
            r.raise_for_status()
            
            # 检查是否返回了 MIDI 文件
            ct = r.headers.get("Content-Type", "")
            chunk = next(r.iter_content(chunk_size=16))
            
            if chunk[:4] == b'MThd':
                # 直接返回 MIDI 文件
                safe_name = self._safe_filename(song_name)
                file_path = OUTPUT_DIR / f"{safe_name}.mid"
                with open(file_path, "wb") as f:
                    f.write(chunk)
                    for c in r.iter_content(chunk_size=8192):
                        if c:
                            f.write(c)
                print(f"下载成功: {file_path}")
                return file_path
            
            # 如果返回的是 HTML，可能需要登录
            if "html" in ct or chunk[:4] == b'<!DO':
                content = chunk.decode("utf-8", errors="ignore") + r.text
                
                # 检查是否需要登录
                if "登录" in content or "login" in content.lower():
                    print(f"需要登录才能下载 (MIDI ID: {midi_id})")
                    print("请设置 MIDISHOW_USERNAME 和 MIDISHOW_PASSWORD 环境变量")
                    return None
                
                # 检查是否需要积分
                if "积分" in content:
                    print(f"需要积分才能下载 (MIDI ID: {midi_id})")
                    print("请登录后确保账户有足够的积分")
                    return None
            
            print(f"下载失败: 未知响应格式")
            return None
            
        except Exception as e:
            print(f"下载失败: {e}")
            return None

    def fetch(self, song_name: str) -> Optional[Path]:
        """从 midishow 获取 MIDI 文件。
        
        Args:
            song_name: 歌曲名称
            
        Returns:
            MIDI 文件路径，未找到返回 None
        """
        # 搜索
        results = self._search_midishow(song_name)
        if not results:
            print(f"未找到: {song_name}")
            return None
        
        # 打印搜索结果
        print(f"找到 {len(results)} 个结果:")
        for i, link in enumerate(results[:5]):
            print(f"  [{i+1}] {link['title']} (ID: {link['id']})")
        
        # 取第一个结果
        result = results[0]
        print(f"选择: {result['title']}")
        
        # 如果有登录信息，先登录
        if self.username and self.password:
            self._login()
        
        # 下载
        return self._download_midi(result["id"], song_name)

    def fetch_with_playwright(self, song_name: str) -> Optional[Path]:
        """使用 Playwright 浏览器自动化获取 MIDI 文件。
        
        当简单 HTTP 请求无法下载时（如需要 JS 渲染），使用此方法。
        
        Args:
            song_name: 歌曲名称
            
        Returns:
            MIDI 文件路径，未找到返回 None
        """
        page_obj = self._get_browser()
        if page_obj is None:
            print("Playwright 不可用")
            return None
        
        try:
            # 登录
            if self.username and self.password:
                self._login()
            
            # 搜索
            results = self._search_midishow(song_name)
            if not results:
                print(f"未找到: {song_name}")
                return None
            
            result = results[0]
            print(f"选择: {result['title']}")
            
            # 访问下载页
            detail_url = f"{self.base_url}/midi/download?id={result['id']}"
            page_obj.goto(detail_url, timeout=30000, wait_until="networkidle")
            page_obj.wait_for_timeout(2000)
            
            # 点击下载按钮（如果存在）
            download_btn = page_obj.query_selector("a[href*='download'], .download-btn, button.download")
            if download_btn:
                with page_obj.expect_download(timeout=30000) as download_info:
                    download_btn.click()
                download = download_info.value
                
                safe_name = self._safe_filename(song_name)
                file_path = OUTPUT_DIR / f"{safe_name}.mid"
                download.save_as(str(file_path))
                print(f"下载成功: {file_path}")
                return file_path
            
            print("无法找到下载按钮")
            return None
            
        except Exception as e:
            print(f"Playwright 下载失败: {e}")
            return None

    def available(self, song_name: str) -> bool:
        """检查 midishow 是否有该歌曲的 MIDI。
        
        Args:
            song_name: 歌曲名称
            
        Returns:
            是否可用
        """
        results = self._search_midishow(song_name)
        return len(results) > 0

    def close(self):
        """关闭浏览器。"""
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def __del__(self):
        """析构时关闭浏览器。"""
        self.close()


class MidishowSimpleFetcher(MidishowFetcher):
    """简化版 Midishow 获取器（纯 HTTP，无需 Playwright）。
    
    使用 requests + BeautifulSoup 进行搜索和下载。
    需要设置账户信息才能下载文件。
    
    环境变量:
        MIDISHOW_USERNAME: Midishow 用户名
        MIDISHOW_PASSWORD: Midishow 密码
    """
    pass  # 继承 MidishowFetcher 的所有功能