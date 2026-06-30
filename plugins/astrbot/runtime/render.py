"""HTML / 文本 转图片 (text_to_image / html_render 的真正实现)。

AstrBot 默认走远程 t2i 服务: 把 jinja2 模板 + 数据渲染成 HTML 再截图。
基座在本地复刻该流程:
  1. 用 jinja2 渲染模板字符串得到完整 HTML;
  2. 用无头浏览器 (chrome/chromium/edge, 或 Playwright) 对 HTML 截图;
  3. 返回本地 PNG 路径 (发送层会按本地图片处理)。

无可用浏览器时优雅降级 (返回空串), 调用方通常会退化为纯文本。
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import subprocess
import time

from core.base.logger import PLUGIN, get_logger

from . import state

log = get_logger(PLUGIN, "astrbot基座")

# 给纯文本兜底用的简单模板
_TEXT_TMPL = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
body{margin:0;padding:24px;background:#fff;font-size:26px;line-height:1.6;
font-family:"Noto Sans CJK SC","Microsoft YaHei",sans-serif;color:#1f2329;
white-space:pre-wrap;word-break:break-word;width:720px;}
</style></head><body>{{ text }}</body></html>"""

_CHROME_NAMES = (
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
    "chrome", "microsoft-edge",
)


def _render_dir() -> str:
    path = os.path.join(state.data_root(), "render")
    os.makedirs(path, exist_ok=True)
    return path


def _render_jinja(tmpl: str, data: dict) -> str:
    try:
        import jinja2
        return jinja2.Template(tmpl, autoescape=False).render(**(data or {}))
    except Exception as e:
        log.warning(f"[astrbot基座] jinja2 渲染失败, 用原始模板: {e}")
        return tmpl


def _find_chrome() -> str | None:
    for name in _CHROME_NAMES:
        path = shutil.which(name)
        if path:
            return path
    local = os.path.expanduser("~/.local/bin/google-chrome")
    return local if os.path.isfile(local) else None


def _shot_with_chrome_cli(html: str) -> str | None:
    """用 chrome --headless --screenshot 截图 (最通用)。"""
    chrome = _find_chrome()
    if not chrome:
        return None
    rdir = _render_dir()
    stamp = f"{int(time.time() * 1000)}_{hashlib.md5(html.encode()).hexdigest()[:8]}"
    html_path = os.path.join(rdir, f"{stamp}.html")
    png_path = os.path.join(rdir, f"{stamp}.png")
    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        cmd = [
            chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
            "--hide-scrollbars", "--force-device-scale-factor=2",
            "--default-background-color=FFFFFFFF",
            f"--screenshot={png_path}", "--window-size=760,1200",
            f"file://{html_path}",
        ]
        subprocess.run(cmd, capture_output=True, timeout=40, check=False)
        if os.path.isfile(png_path) and os.path.getsize(png_path) > 0:
            return png_path
    except (OSError, subprocess.SubprocessError) as e:
        log.warning(f"[astrbot基座] chrome 截图失败: {e}")
    finally:
        with contextlib.suppress(OSError):
            os.remove(html_path)
    return None


def _shot_with_playwright_cdp(html: str) -> str | None:
    """连到 ElainaBot 桌面已有的 Chrome (CDP) 截图, 作为后备。"""
    endpoint = os.environ.get("ASTRBOT_RENDER_CDP", "http://localhost:29229")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    rdir = _render_dir()
    png_path = os.path.join(rdir, f"{int(time.time() * 1000)}.png")
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(endpoint)
            ctx = browser.new_context(viewport={"width": 760, "height": 1200},
                                      device_scale_factor=2)
            page = ctx.new_page()
            page.set_content(html, wait_until="networkidle")
            page.screenshot(path=png_path, full_page=True)
            ctx.close()
        if os.path.isfile(png_path) and os.path.getsize(png_path) > 0:
            return png_path
    except Exception as e:
        log.warning(f"[astrbot基座] Playwright(CDP) 截图失败: {e}")
    return None


def render_html(tmpl: str, data: dict) -> str:
    """渲染 jinja2 模板并截图, 返回本地 PNG 路径; 失败返回空串。"""
    html = _render_jinja(tmpl, data)
    # chrome CLI 在沙箱/容器中最稳; 不行再用桌面 Chrome 的 CDP
    return _shot_with_chrome_cli(html) or _shot_with_playwright_cdp(html) or ""


def render_text(text: str) -> str:
    """把纯文本渲染成图片, 返回本地 PNG 路径; 失败返回空串。"""
    return render_html(_TEXT_TMPL, {"text": text})
