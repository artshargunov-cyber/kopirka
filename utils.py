import os
import sys

def get_resource_path(relative_path):
    """ Получить абсолютный путь к ресурсу, работает и для dev, и для PyInstaller """
    try:
        # PyInstaller создает временную папку и хранит путь в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))

    return os.path.join(base_path, relative_path)
