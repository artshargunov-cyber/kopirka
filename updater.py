"""
Модуль автоматического обновления.
Проверяет последний релиз на GitHub и предлагает пользователю обновиться.
"""
import json
import os
import sys
import subprocess
import tempfile
import threading
import urllib.request
import urllib.error

from utils import VERSION

GITHUB_REPO = "artshargunov-cyber/kopirka"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _version_tuple(v: str):
    """Конвертирует строку версии "1.5.0" -> (1, 5, 0)."""
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except Exception:
        return (0, 0, 0)


def check_for_update(callback):
    """
    Проверяет обновление в фоновом потоке.
    Вызывает callback(latest_version, download_url) если доступно обновление,
    или callback(None, None) если обновлений нет / ошибка.
    """
    def _check():
        try:
            req = urllib.request.Request(
                GITHUB_API_URL,
                headers={"User-Agent": "Kopirka-App"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())

            latest_tag = data.get("tag_name", "")
            latest_ver = latest_tag.lstrip("v")

            if _version_tuple(latest_ver) > _version_tuple(VERSION):
                # Ищем .exe установщик в ассетах
                assets = data.get("assets", [])
                installer_url = None
                for asset in assets:
                    name = asset.get("name", "").lower()
                    if name.endswith(".exe") and "setup" in name:
                        installer_url = asset.get("browser_download_url")
                        break
                # Если не нашли installer — берём страницу релиза
                if not installer_url:
                    installer_url = data.get("html_url", "")
                callback(latest_ver, installer_url)
            else:
                callback(None, None)
        except Exception:
            callback(None, None)

    t = threading.Thread(target=_check, daemon=True)
    t.start()


def download_and_run_installer(url, progress_callback=None):
    """
    Скачивает установщик во временную папку и запускает его.
    Возвращает True при успехе, False при ошибке.
    """
    try:
        tmp_dir = tempfile.mkdtemp()
        installer_path = os.path.join(tmp_dir, "KopirkaSetup.exe")

        req = urllib.request.Request(url, headers={"User-Agent": "Kopirka-App"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 8192
            with open(installer_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total:
                        progress_callback(int(downloaded / total * 100))

        # Запускаем установщик без shell=True для надежности
        # Добавляем флаг /SILENT если нужно, но лучше пусть будет обычный
        subprocess.Popen([installer_path])
        sys.exit(0)
        return True
    except Exception as e:
        print(f"Ошибка скачивания или запуска: {e}")
        import webbrowser
        webbrowser.open(url)
        return False
