import os
import sys

# Версия приложения (major.minor.patch)
VERSION = "1.5.4"
APP_NAME = "Kopirka"


def get_resource_path(relative_path):
    """Путь к файлам приложения (ассеты, шрифты). Работает в dev и PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


def get_user_data_path(filename=""):
    """
    Путь к пользовательским данным (список класса, настройки).
    На Windows: %APPDATA%\\Kopirka\\
    На Mac/Linux: ~/.kopirka/
    Эта папка НЕ удаляется при обновлении программы.
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        data_dir = os.path.join(base, APP_NAME)
    else:
        data_dir = os.path.join(os.path.expanduser("~"), f".{APP_NAME.lower()}")

    os.makedirs(data_dir, exist_ok=True)

    if filename:
        return os.path.join(data_dir, filename)
    return data_dir
