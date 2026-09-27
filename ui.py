import os
import math
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, 
    QSlider, QScrollArea, QCheckBox, QFileDialog, QMessageBox, QFrame, QSizePolicy,
    QDialog, QTextEdit, QApplication, QComboBox
)
from PyQt6.QtCore import Qt, QSize, QMimeData
from crop_widget import ImageCropDialog
from PyQt6.QtGui import QPixmap, QFont, QImage
from io import BytesIO

from roster_manager import RosterManager
from pdf_processor import PDFProcessor

class RosterEditDialog(QDialog):
    def __init__(self, parent, current_students):
        super().__init__(parent)
        self.setWindowTitle("Редактирование списка класса")
        self.setMinimumSize(400, 500)
        self.setStyleSheet(parent.styleSheet()) # Наследуем стили

        layout = QVBoxLayout(self)
        
        info_label = QLabel("Вставьте список учеников (каждое имя с новой строки):")
        layout.addWidget(info_label)

        self.text_edit = QTextEdit()
        # Заполняем текущими учениками
        names = [s["name"] for s in current_students]
        self.text_edit.setPlainText("\\n".join(names))
        layout.addWidget(self.text_edit)

        self.btn_save = QPushButton("Сохранить")
        self.btn_save.setObjectName("PrimaryButton")
        self.btn_save.clicked.connect(self.accept)
        layout.addWidget(self.btn_save)

    def get_text(self):
        return self.text_edit.toPlainText()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Копирка")
        self.resize(1000, 700)
        self.setMinimumSize(800, 600)
        
        # Включаем drag-and-drop
        self.setAcceptDrops(True)
        
        self.roster_manager = RosterManager()
        self.pdf_processor = PDFProcessor()
        
        self.scale_value = 50
        self.orientation_mode = "auto"  # "auto", "portrait", "landscape"
        
        self.setup_ui()
        self.apply_stylesheet()
        
        self.refresh_student_list()
        self.update_stats()

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Левая панель
        self.left_panel = QFrame()
        self.left_panel.setFixedWidth(350)
        self.left_panel.setObjectName("LeftPanel")
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(20, 20, 20, 20)
        self.left_layout.setSpacing(10)

        self.title_label = QLabel("Копирка")
        self.title_label.setObjectName("TitleLabel")
        self.left_layout.addWidget(self.title_label)

        self.btn_load_file = QPushButton("Добавить файл")
        self.btn_load_file.clicked.connect(self.load_template_file)
        self.left_layout.addWidget(self.btn_load_file)

        self.file_status_label = QLabel("Файл не выбран (или перетащите сюда)")
        self.file_status_label.setObjectName("StatusLabel")
        self.file_status_label.setWordWrap(True)
        self.left_layout.addWidget(self.file_status_label)

        # Переключатель ориентации
        self.orientation_label = QLabel("Ориентация листа:")
        self.left_layout.addWidget(self.orientation_label)
        
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItems(["Автоматически", "Книжная (портрет)", "Альбомная (ландшафт)"])
        self.orientation_combo.currentIndexChanged.connect(self.on_orientation_change)
        self.left_layout.addWidget(self.orientation_combo)

        self.btn_edit_roster = QPushButton("Изменить список класса")
        self.btn_edit_roster.setObjectName("SecondaryButton")
        self.btn_edit_roster.clicked.connect(self.edit_roster)
        self.left_layout.addWidget(self.btn_edit_roster)

        # Контейнер для кнопок Выбрать всех / Снять выбор
        self.sel_frame = QFrame()
        self.sel_layout = QHBoxLayout(self.sel_frame)
        self.sel_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_sel_all = QPushButton("Выбрать всех")
        self.btn_sel_all.clicked.connect(lambda: self.toggle_all(True))
        self.sel_layout.addWidget(self.btn_sel_all)
        
        self.btn_desel_all = QPushButton("Снять выбор")
        self.btn_desel_all.clicked.connect(lambda: self.toggle_all(False))
        self.sel_layout.addWidget(self.btn_desel_all)
        
        self.left_layout.addWidget(self.sel_frame)

        # Кнопка добавления пустого ученика
        self.btn_add_empty = QPushButton("+ Добавить без имени")
        self.btn_add_empty.setObjectName("SecondaryButton")
        self.btn_add_empty.clicked.connect(self.add_empty_student)
        self.left_layout.addWidget(self.btn_add_empty)

        # Список учеников
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_widget.setObjectName("ScrollWidget")
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.scroll_widget)
        self.left_layout.addWidget(self.scroll_area, stretch=1)
        
        self.student_checkboxes = []

        # Ползунок масштаба
        self.scale_label = QLabel(f"Масштаб раздатки: {self.scale_value}%")
        self.left_layout.addWidget(self.scale_label)
        
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(10, 100)
        self.scale_slider.setValue(self.scale_value)
        self.scale_slider.valueChanged.connect(self.on_scale_change)
        self.left_layout.addWidget(self.scale_slider)

        # Инфо панели
        self.stats_frame = QFrame()
        self.stats_layout = QVBoxLayout(self.stats_frame)
        self.stats_layout.setContentsMargins(0, 10, 0, 10)
        
        self.lbl_selected_count = QLabel("Выбрано учеников: 0")
        self.stats_layout.addWidget(self.lbl_selected_count)
        
        self.lbl_pages_needed = QLabel("Всего потребуется листов А4: 0")
        self.stats_layout.addWidget(self.lbl_pages_needed)
        
        self.left_layout.addWidget(self.stats_frame)

        # Сохранить PDF
        self.btn_save = QPushButton("Сохранить для печати")
        self.btn_save.setObjectName("PrimaryButton")
        self.btn_save.setMinimumHeight(45)
        self.btn_save.clicked.connect(self.save_pdf)
        self.left_layout.addWidget(self.btn_save)

        self.main_layout.addWidget(self.left_panel)

        # Правая панель
        self.right_panel = QFrame()
        self.right_panel.setObjectName("RightPanel")
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.preview_label = QLabel("Загрузите файл для предпросмотра")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedSize(420, 594) # Пропорции A4
        self.preview_label.setObjectName("PreviewLabel")
        self.right_layout.addWidget(self.preview_label)

        self.main_layout.addWidget(self.right_panel, stretch=1)

    def apply_stylesheet(self):
        # Современный стиль в светлых/серых тонах
        self.setStyleSheet("""
            QMainWindow, QDialog {
                background-color: #F3F4F6;
            }
            #LeftPanel {
                background-color: #FFFFFF;
                border-right: 1px solid #E5E7EB;
            }
            #RightPanel {
                background-color: #F9FAFB;
            }
            #TitleLabel {
                font-size: 24px;
                font-weight: bold;
                color: #111827;
                margin-bottom: 10px;
            }
            QLabel {
                font-size: 14px;
                color: #374151;
            }
            #StatusLabel {
                color: #6B7280;
                font-style: italic;
            }
            QPushButton {
                background-color: #F3F4F6;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 8px 12px;
                color: #374151;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #E5E7EB;
            }
            #SecondaryButton {
                background-color: transparent;
                border: 1px dashed #9CA3AF;
            }
            #SecondaryButton:hover {
                background-color: #F3F4F6;
            }
            #PrimaryButton {
                background-color: #2563EB;
                color: white;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            #PrimaryButton:hover {
                background-color: #1D4ED8;
            }
            QScrollArea, QTextEdit {
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                background-color: #FFFFFF;
            }
            #ScrollWidget {
                background-color: #FFFFFF;
            }
            QTextEdit {
                padding: 8px;
                font-size: 14px;
                color: #111827;
            }
            QCheckBox {
                font-size: 14px;
                color: #111827;
                padding: 4px;
                background-color: transparent;
            }
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: #E5E7EB;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #2563EB;
                border: 1px solid #2563EB;
                width: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
            #PreviewLabel {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                color: #9CA3AF;
            }
        """)

    def load_template_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл раздатки",
            "",
            "Изображения и PDF (*.pdf *.png *.jpg *.jpeg);;Все файлы (*.*)"
        )
        if filepath:
            self._process_file(filepath)

    def _process_file(self, filepath):
        """Общий метод загрузки и обработки файла (вызывается и из диалога, и из drag-and-drop)."""
        success, msg = self.pdf_processor.load_template(filepath)
        if success:
            # Применяем выбранную ориентацию
            self._apply_orientation()
            
            # Предлагаем обрезку для любого загруженного файла (картинки и PDF)
            from PIL import Image
            import io
            pix = self.pdf_processor.template_pix
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            
            qpixmap = QPixmap()
            qpixmap.loadFromData(img_bytes.getvalue())
            
            dialog = ImageCropDialog(self, qpixmap)
            if dialog.exec():
                crop_rect = dialog.get_crop_rect()
                if crop_rect:
                    self.pdf_processor.crop_template(crop_rect)
                    # После обрезки снова применяем ориентацию
                    self._apply_orientation()

            filename = os.path.basename(filepath)
            self.file_status_label.setText(filename)
            self.file_status_label.setStyleSheet("color: #10B981;")  # Зеленый
            self.update_preview()
        else:
            QMessageBox.critical(self, "Ошибка", msg)

    # --- Drag-and-drop ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            filepath = urls[0].toLocalFile()
            if filepath:
                self._process_file(filepath)

    # --- Ориентация ---
    def on_orientation_change(self, index):
        modes = ["auto", "portrait", "landscape"]
        self.orientation_mode = modes[index]
        self._apply_orientation()
        self.update_preview()

    def _apply_orientation(self):
        """Устанавливает ориентацию страницы по выбору пользователя."""
        if self.orientation_mode == "auto":
            self.pdf_processor._update_page_orientation()
        elif self.orientation_mode == "portrait":
            self.pdf_processor.A4_WIDTH = self.pdf_processor.A4_PORTRAIT_W
            self.pdf_processor.A4_HEIGHT = self.pdf_processor.A4_PORTRAIT_H
            self.pdf_processor.USABLE_WIDTH = self.pdf_processor.A4_WIDTH - 2 * self.pdf_processor.MARGIN
            self.pdf_processor.USABLE_HEIGHT = self.pdf_processor.A4_HEIGHT - 2 * self.pdf_processor.MARGIN
        elif self.orientation_mode == "landscape":
            self.pdf_processor.A4_WIDTH = self.pdf_processor.A4_PORTRAIT_H
            self.pdf_processor.A4_HEIGHT = self.pdf_processor.A4_PORTRAIT_W
            self.pdf_processor.USABLE_WIDTH = self.pdf_processor.A4_WIDTH - 2 * self.pdf_processor.MARGIN
            self.pdf_processor.USABLE_HEIGHT = self.pdf_processor.A4_HEIGHT - 2 * self.pdf_processor.MARGIN

    # --- Пустой ученик ---
    def add_empty_student(self):
        """Добавляет ученика с пустым именем (пустое поле для подписи от руки)."""
        self.roster_manager.add_empty_student()
        self.refresh_student_list()
        self.update_stats()

    def edit_roster(self):
        dialog = RosterEditDialog(self, self.roster_manager.get_all_students())
        if dialog.exec():
            text = dialog.get_text()
            success, msg = self.roster_manager.update_from_text(text)
            if success:
                self.refresh_student_list()
                self.update_stats()
            else:
                QMessageBox.critical(self, "Ошибка", msg)

    def refresh_student_list(self):
        # Очистка лейаута
        for i in reversed(range(self.scroll_layout.count())): 
            widget = self.scroll_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
        
        self.student_checkboxes.clear()

        # Создание чекбоксов
        students = self.roster_manager.get_all_students()
        for idx, student in enumerate(students):
            display_name = student["name"] if student["name"] else "(без имени)"
            cb = QCheckBox(display_name)
            cb.setChecked(student["selected"])
            
            # Подключаем сигнал через лямбду, захватывая текущий индекс
            cb.toggled.connect(lambda state, i=idx: self.on_student_toggled(i, state))
            
            self.scroll_layout.addWidget(cb)
            self.student_checkboxes.append(cb)

    def on_student_toggled(self, index, state):
        self.roster_manager.set_student_selection(index, state)
        self.update_stats()

    def toggle_all(self, state):
        self.roster_manager.select_all(state)
        # Обновляем UI чекбоксов без вызова сигналов, чтобы избежать лишних пересчетов
        for cb in self.student_checkboxes:
            cb.blockSignals(True)
            cb.setChecked(state)
            cb.blockSignals(False)
        self.update_stats()

    def on_scale_change(self, value):
        self.scale_value = value
        self.scale_label.setText(f"Масштаб раздатки: {self.scale_value}%")
        self.update_preview()

    def update_stats(self):
        selected_students = self.roster_manager.get_selected_students()
        count = len(selected_students)
        
        if count == 0 and not self.roster_manager.get_all_students():
            total_needed = 1
        else:
            total_needed = count

        _, _, copies_per_page, _, _ = self.pdf_processor.calculate_layout(self.scale_value)
        
        pages = 0
        if copies_per_page > 0:
            pages = math.ceil(total_needed / copies_per_page) if total_needed > 0 else 0
            if not self.roster_manager.get_all_students() and pages == 0:
                 pages = 1

        self.lbl_selected_count.setText(f"Выбрано учеников: {count}")
        self.lbl_pages_needed.setText(f"Всего потребуется листов А4: {pages}")

    def update_preview(self):
        img, copies_per_page = self.pdf_processor.generate_preview(self.scale_value)
        
        if img:
            # Конвертация PIL Image в QPixmap
            img_bytes = BytesIO()
            img.save(img_bytes, format='PNG')
            pixmap = QPixmap()
            pixmap.loadFromData(img_bytes.getvalue())
            
            # Масштабируем до размеров превью контейнера
            pixmap_scaled = pixmap.scaled(
                self.preview_label.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.preview_label.setPixmap(pixmap_scaled)
            self.preview_label.setText("")
        else:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("Загрузите файл для предпросмотра")
            
        self.update_stats()

    def save_pdf(self):
        if not self.pdf_processor.template_pix:
            QMessageBox.warning(self, "Внимание", "Сначала загрузите файл раздатки.")
            return

        selected_students = self.roster_manager.get_selected_students()
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить PDF как",
            "",
            "PDF files (*.pdf)"
        )
        
        if filepath:
            self.btn_save.setEnabled(False)
            self.btn_save.setText("Сохранение...")
            QApplication.processEvents() # Обновляем UI
            
            success, msg = self.pdf_processor.generate_pdf(self.scale_value, selected_students, filepath)
            
            self.btn_save.setEnabled(True)
            self.btn_save.setText("Сохранить для печати")
            
            if success:
                QMessageBox.information(self, "Успех", msg)
            else:
                QMessageBox.critical(self, "Ошибка", msg)
