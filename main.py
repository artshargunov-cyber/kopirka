import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox, QProgressDialog
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QMetaObject, Q_ARG
from ui import MainWindow
from utils import get_resource_path, VERSION
from updater import check_for_update, download_and_run_installer


def _show_update_dialog(window, latest_ver, download_url):
    """Показывает диалог обновления в главном потоке Qt."""
    msg = QMessageBox(window)
    msg.setWindowTitle("Доступно обновление")
    msg.setIcon(QMessageBox.Icon.Information)
    msg.setText(
        f"<b>Доступна новая версия Копирки!</b><br><br>"
        f"Ваша версия: <b>{VERSION}</b><br>"
        f"Новая версия: <b>{latest_ver}</b><br><br>"
        f"Хотите обновить программу сейчас?"
    )
    msg.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    msg.setDefaultButton(QMessageBox.StandardButton.Yes)
    msg.button(QMessageBox.StandardButton.Yes).setText("Обновить")
    msg.button(QMessageBox.StandardButton.No).setText("Позже")

    if msg.exec() == QMessageBox.StandardButton.Yes:
        if download_url.endswith(".exe"):
            progress = QProgressDialog("Скачивание обновления...", None, 0, 100, window)
            progress.setWindowTitle("Обновление")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)

            def on_progress(pct):
                progress.setValue(pct)
                QApplication.processEvents()

            ok = download_and_run_installer(download_url, on_progress)
            if not ok:
                QMessageBox.critical(window, "Ошибка", "Не удалось скачать обновление.\nПопробуйте позже.")
        else:
            # Нет готового установщика — открываем страницу релиза в браузере
            import webbrowser
            webbrowser.open(download_url)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Иконка приложения
    ico_path = get_resource_path(os.path.join("assets", "icon.ico"))
    svg_path = get_resource_path(os.path.join("assets", "icon.svg"))
    if os.path.exists(ico_path):
        app.setWindowIcon(QIcon(ico_path))
    elif os.path.exists(svg_path):
        app.setWindowIcon(QIcon(svg_path))

    window = MainWindow()
    window.show()

    # Проверка обновлений в фоне (не блокирует запуск)
    def on_update_check(latest_ver, download_url):
        if latest_ver:
            # Нужно вызвать GUI из главного потока
            app.postEvent(window, _UpdateEvent(latest_ver, download_url))

    check_for_update(on_update_check)

    sys.exit(app.exec())


# Кастомный Qt Event для передачи данных обновления в главный поток
from PyQt6.QtCore import QEvent

class _UpdateEvent(QEvent):
    TYPE = QEvent.Type(QEvent.registerEventType())

    def __init__(self, version, url):
        super().__init__(self.TYPE)
        self.version = version
        self.url = url


# Переопределим event() в MainWindow динамически
_original_event = MainWindow.event if hasattr(MainWindow, 'event') else None

def _patched_event(self, event):
    if isinstance(event, _UpdateEvent):
        _show_update_dialog(self, event.version, event.url)
        return True
    if _original_event:
        return _original_event(self, event)
    return super(MainWindow, self).event(event)

MainWindow.event = _patched_event


if __name__ == "__main__":
    main()
