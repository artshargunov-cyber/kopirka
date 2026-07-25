import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # Устанавливаем иконку приложения
    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.svg")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Современный стиль, напоминающий Windows 10/11
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
