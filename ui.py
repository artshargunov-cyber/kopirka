import os
import math
import io
import zipfile
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QScrollArea, QCheckBox, QFileDialog, QMessageBox, QFrame, QSizePolicy,
    QDialog, QTextEdit, QApplication, QSpinBox, QButtonGroup, QRadioButton,
    QStackedWidget
)
from PyQt6.QtCore import Qt, QSize
from crop_widget import ImageCropDialog
from PyQt6.QtGui import QPixmap, QFont, QImage, QImageReader, QIcon, QPainter
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
from io import BytesIO

from roster_manager import RosterManager
from pdf_processor import PDFProcessor
from utils import get_resource_path


class RosterEditDialog(QDialog):
    def __init__(self, parent, current_students):
        super().__init__(parent)
        self.setWindowTitle("Редактирование списка класса")
        self.setMinimumSize(400, 500)
        self.setStyleSheet(parent.styleSheet())

        layout = QVBoxLayout(self)
        
        info_label = QLabel("Вставьте список учеников (каждое имя с новой строки):")
        layout.addWidget(info_label)

        self.text_edit = QTextEdit()
        names = [s["name"] for s in current_students if s["name"]]
        self.text_edit.setPlainText("\n".join(names))
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
        self.resize(1060, 700)
        self.setMinimumSize(860, 600)

        # Устанавливаем иконку
        icon_path = get_resource_path(os.path.join("assets", "icon.svg"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Иконка в формате .ico (для Windows taskbar)
        ico_path = get_resource_path(os.path.join("assets", "icon.ico"))
        if os.path.exists(ico_path):
            self.setWindowIcon(QIcon(ico_path))

        self.setAcceptDrops(True)

        self.roster_manager = RosterManager()
        self.pdf_processor = PDFProcessor()
        self.copies_per_page = 4
        # Режим: "roster" = по списку, "blank" = без шапки
        self.print_mode = "roster"

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

        # ── ЛЕВАЯ ПАНЕЛЬ ──────────────────────────────────────
        self.left_panel = QFrame()
        self.left_panel.setFixedWidth(360)
        self.left_panel.setObjectName("LeftPanel")
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(20, 20, 20, 20)
        self.left_layout.setSpacing(10)

        # Заголовок
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        self.title_label = QLabel("✂ Копирка")
        self.title_label.setObjectName("TitleLabel")
        title_layout.addWidget(self.title_label)
        
        info_label = QLabel("ℹ️")
        info_label.setCursor(Qt.CursorShape.PointingHandCursor)
        info_label.setToolTip(
            "<div style='white-space: pre-wrap; width: 400px; font-size: 13px;'>"
            "<b>О программе «Копирка»</b><br><br>"
            "Данное приложение является бесплатным и свободным программным обеспечением "
            "(Open Source). Разработано при помощи искусственного интеллекта.<br><br>"
            "<b>🔒 Конфиденциальность:</b> Программа работает локально на вашем компьютере. "
            "Она не собирает, не хранит и не передает ваши персональные данные, "
            "списки класса или загружаемые файлы на серверы третьих лиц.<br><br>"
            "<b>⚖️ Отказ от ответственности:</b> Пользователь самостоятельно несет ответственность "
            "за соблюдение авторских и смежных прав в отношении любых материалов "
            "(изображений, текстов, документов), загружаемых, тиражируемых и "
            "распространяемых с помощью данного программного обеспечения. "
            "Разработчик не несет ответственности за неправомерное использование "
            "чужой интеллектуальной собственности."
            "</div>"
        )
        # Добавим небольшой отступ сверху для значка, чтобы он был по центру текста
        info_label.setStyleSheet("padding-top: 5px; font-size: 16px;")
        
        title_layout.addWidget(info_label)
        title_layout.addStretch()
        
        # Кнопка обновления (скрыта по умолчанию)
        self.btn_update = QPushButton("⬆️")
        self.btn_update.setObjectName("UpdateBtn")
        self.btn_update.setStyleSheet("background-color: #22c55e; color: white; border-radius: 12px; padding: 4px 10px; font-weight: bold; border: none;")
        self.btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update.hide()
        self.btn_update.clicked.connect(self._on_update_clicked)
        title_layout.addWidget(self.btn_update)
        
        self.left_layout.addLayout(title_layout)


        # Загрузка файла
        self.btn_load_file = QPushButton("📂  Добавить файл (PDF / JPG / PNG / Word)")
        self.btn_load_file.clicked.connect(self.load_template_file)
        self.left_layout.addWidget(self.btn_load_file)

        self.file_status_label = QLabel("Файл не выбран  (или перетащите сюда)")
        self.file_status_label.setObjectName("StatusLabel")
        self.file_status_label.setWordWrap(True)
        self.left_layout.addWidget(self.file_status_label)

        # Разделитель
        self.left_layout.addWidget(self._make_separator())

        # ── ВЫБОР РЕЖИМА ──────────────────────────────────────
        mode_label = QLabel("Режим печати:")
        mode_label.setObjectName("SectionLabel")
        self.left_layout.addWidget(mode_label)

        mode_frame = QFrame()
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(6)

        self.rb_roster = QRadioButton("По списку класса")
        self.rb_roster.setChecked(True)
        self.rb_blank = QRadioButton("Без шапки / ФИО")

        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.rb_roster, 0)
        self.mode_group.addButton(self.rb_blank, 1)
        self.mode_group.idClicked.connect(self._on_mode_changed)

        mode_layout.addWidget(self.rb_roster)
        mode_layout.addWidget(self.rb_blank)
        self.left_layout.addWidget(mode_frame)

        # ── СТЕК: разные настройки для каждого режима ─────────
        self.mode_stack = QStackedWidget()

        # -- Страница 0: по списку --
        roster_page = QWidget()
        roster_layout = QVBoxLayout(roster_page)
        roster_layout.setContentsMargins(0, 0, 0, 0)
        roster_layout.setSpacing(6)

        self.btn_edit_roster = QPushButton("✏  Изменить список класса")
        self.btn_edit_roster.setObjectName("SecondaryButton")
        self.btn_edit_roster.clicked.connect(self.edit_roster)
        roster_layout.addWidget(self.btn_edit_roster)

        sel_frame = QFrame()
        sel_layout = QHBoxLayout(sel_frame)
        sel_layout.setContentsMargins(0, 0, 0, 0)
        sel_layout.setSpacing(6)

        self.btn_sel_all = QPushButton("Выбрать всех")
        self.btn_sel_all.clicked.connect(lambda: self.toggle_all(True))
        sel_layout.addWidget(self.btn_sel_all)

        self.btn_desel_all = QPushButton("Снять выбор")
        self.btn_desel_all.clicked.connect(lambda: self.toggle_all(False))
        sel_layout.addWidget(self.btn_desel_all)
        roster_layout.addWidget(sel_frame)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_widget.setObjectName("ScrollWidget")
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.scroll_widget)
        roster_layout.addWidget(self.scroll_area, stretch=1)
        self.student_checkboxes = []

        self.mode_stack.addWidget(roster_page)

        # -- Страница 1: без шапки --
        blank_page = QWidget()
        blank_layout = QVBoxLayout(blank_page)
        blank_layout.setContentsMargins(0, 0, 0, 0)
        blank_layout.setSpacing(6)

        blank_layout.addWidget(QLabel("Сколько раздаток напечатать:"))
        self.spin_total_copies = QSpinBox()
        self.spin_total_copies.setRange(1, 1000)
        self.spin_total_copies.setValue(1)
        self.spin_total_copies.valueChanged.connect(self.update_stats)
        blank_layout.addWidget(self.spin_total_copies)

        blank_layout.addStretch()
        self.mode_stack.addWidget(blank_page)

        self.left_layout.addWidget(self.mode_stack, stretch=1)

        # Разделитель
        self.left_layout.addWidget(self._make_separator())

        # ── НАСТРОЙКИ РАЗМЕЩЕНИЯ ──────────────────────────────
        settings_label = QLabel("Размещение на листе:")
        settings_label.setObjectName("SectionLabel")
        self.left_layout.addWidget(settings_label)

        self.copies_spinbox = QSpinBox()
        self.copies_spinbox.setRange(1, 100)
        self.copies_spinbox.setValue(self.copies_per_page)
        self.copies_spinbox.setPrefix("Копий на листе А4:  ")
        self.copies_spinbox.valueChanged.connect(self.on_copies_change)
        self.left_layout.addWidget(self.copies_spinbox)

        # ── СТАТИСТИКА ────────────────────────────────────────
        self.stats_frame = QFrame()
        self.stats_frame.setObjectName("StatsFrame")
        stats_layout = QVBoxLayout(self.stats_frame)
        stats_layout.setContentsMargins(10, 8, 10, 8)
        stats_layout.setSpacing(2)

        self.lbl_selected_count = QLabel("Выбрано: 0")
        self.lbl_pages_needed = QLabel("Потребуется листов А4: 0")
        stats_layout.addWidget(self.lbl_selected_count)
        stats_layout.addWidget(self.lbl_pages_needed)
        self.left_layout.addWidget(self.stats_frame)

        # Кнопки печати и сохранения
        self.btn_print_test = QPushButton("📄  Печать 1 тестового листа")
        self.btn_print_test.setObjectName("SecondaryButton")
        self.btn_print_test.setMinimumHeight(40)
        self.btn_print_test.clicked.connect(self.print_test_page)
        self.left_layout.addWidget(self.btn_print_test)

        self.btn_print_all = QPushButton("🖨  Распечатать всё")
        self.btn_print_all.setObjectName("PrimaryButton")
        self.btn_print_all.setMinimumHeight(48)
        self.btn_print_all.clicked.connect(self.print_all)
        self.left_layout.addWidget(self.btn_print_all)
        
        self.btn_save = QPushButton("💾  Сохранить в PDF")
        self.btn_save.setObjectName("SecondaryButton")
        self.btn_save.setMinimumHeight(40)
        self.btn_save.clicked.connect(self.save_pdf)
        self.left_layout.addWidget(self.btn_save)

        self.main_layout.addWidget(self.left_panel)

        # ── ПРАВАЯ ПАНЕЛЬ (превью) ────────────────────────────
        self.right_panel = QFrame()
        self.right_panel.setObjectName("RightPanel")
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.preview_label = QLabel("Загрузите файл для предпросмотра")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedSize(420, 594)
        self.preview_label.setObjectName("PreviewLabel")
        self.right_layout.addWidget(self.preview_label)

        self.main_layout.addWidget(self.right_panel, stretch=1)

    def _make_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("Separator")
        return line

    def _on_mode_changed(self, btn_id):
        self.print_mode = "roster" if btn_id == 0 else "blank"
        self.mode_stack.setCurrentIndex(btn_id)
        self.update_preview()

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow, QDialog {
                background-color: #F3F4F6;
            }
            #LeftPanel {
                background-color: #FFFFFF;
                border-right: 1px solid #E5E7EB;
            }
            #RightPanel {
                background-color: #F0F4FF;
            }
            #TitleLabel {
                font-size: 22px;
                font-weight: bold;
                color: #1E3A8A;
                margin-bottom: 4px;
            }
            #SectionLabel {
                font-size: 12px;
                font-weight: bold;
                color: #6B7280;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            QLabel {
                font-size: 13px;
                color: #374151;
            }
            #StatusLabel {
                color: #6B7280;
                font-style: italic;
                font-size: 12px;
            }
            QPushButton {
                background-color: #F3F4F6;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 8px 12px;
                color: #374151;
                font-weight: 500;
                font-size: 13px;
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
                border-radius: 8px;
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
                font-size: 13px;
                color: #111827;
            }
            QCheckBox {
                font-size: 13px;
                color: #374151;
                padding: 3px 0;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #D1D5DB;
            }
            QCheckBox::indicator:checked {
                background-color: #2563EB;
                border-color: #2563EB;
            }
            QRadioButton {
                font-size: 13px;
                color: #374151;
                padding: 6px 8px;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
            }
            QRadioButton:checked {
                background-color: #EFF6FF;
                border-color: #2563EB;
                color: #1D4ED8;
                font-weight: bold;
            }
            QSpinBox {
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 13px;
                background: white;
            }
            #StatsFrame {
                background-color: #F0F9FF;
                border: 1px solid #BAE6FD;
                border-radius: 6px;
            }
            #Separator {
                color: #E5E7EB;
                background: #E5E7EB;
                max-height: 1px;
            }
            #PreviewLabel {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                color: #9CA3AF;
            }
            QScrollBar:vertical {
                border: none;
                background: #F3F4F6;
                width: 8px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #D1D5DB;
                border-radius: 4px;
                min-height: 20px;
            }
        """)

    # ── ЗАГРУЗКА ФАЙЛОВ ────────────────────────────────────────────

    def load_template_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл раздатки",
            "",
            "Все поддерживаемые форматы (*.pdf *.png *.jpg *.jpeg *.docx);;PDF (*.pdf);;Изображения (*.png *.jpg *.jpeg);;Word документы (*.docx);;Все файлы (*.*)"
        )
        if filepath:
            self._process_file(filepath)

    def _process_file(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".docx":
            self._load_from_docx(filepath)
        else:
            self._load_standard_file(filepath)

    def _load_from_docx(self, filepath):
        """Извлекает первое изображение из Word-документа и предлагает его обрезать."""
        try:
            images = []
            with zipfile.ZipFile(filepath, 'r') as z:
                for name in z.namelist():
                    if name.startswith("word/media/") and any(
                        name.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff']
                    ):
                        images.append((name, z.read(name)))

            if not images:
                QMessageBox.warning(self, "Word", "В документе не найдено изображений.")
                return

            # Берём первое изображение
            img_name, img_data = images[0]

            if len(images) > 1:
                QMessageBox.information(
                    self, "Word",
                    f"В документе найдено {len(images)} изображений. Будет использовано первое."
                )

            # Загружаем как QPixmap
            qpixmap = QPixmap()
            QImageReader.setAllocationLimit(1024)
            qpixmap.loadFromData(img_data)

            if qpixmap.isNull():
                QMessageBox.critical(self, "Ошибка", "Не удалось прочитать изображение из Word-файла.")
                return

            # Конвертируем в fitz.Pixmap через PIL
            from PIL import Image as PILImage
            pil_img = PILImage.open(io.BytesIO(img_data)).convert("RGB")
            png_buf = io.BytesIO()
            pil_img.save(png_buf, format="PNG")

            import fitz
            pix = fitz.Pixmap(png_buf.getvalue())
            self.pdf_processor.template_pix = pix
            self.pdf_processor.template_width = pix.width
            self.pdf_processor.template_height = pix.height

            # Предлагаем обрезку
            dialog = ImageCropDialog(self, qpixmap)
            if dialog.exec():
                crop_rect = dialog.get_crop_rect()
                if crop_rect:
                    self.pdf_processor.crop_template(crop_rect)

            filename = os.path.basename(filepath)
            self.file_status_label.setText(f"📄 {filename}")
            self.file_status_label.setStyleSheet("color: #10B981;")
            self.update_preview()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть Word-файл:\n{e}")

    def _load_standard_file(self, filepath):
        success, msg = self.pdf_processor.load_template(filepath)
        if success:
            from PIL import Image
            pix = self.pdf_processor.template_pix
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')

            qpixmap = QPixmap()
            QImageReader.setAllocationLimit(1024)
            qpixmap.loadFromData(img_bytes.getvalue())

            if not qpixmap.isNull():
                dialog = ImageCropDialog(self, qpixmap)
                if dialog.exec():
                    crop_rect = dialog.get_crop_rect()
                    if crop_rect:
                        self.pdf_processor.crop_template(crop_rect)

            filename = os.path.basename(filepath)
            self.file_status_label.setText(f"📄 {filename}")
            self.file_status_label.setStyleSheet("color: #10B981;")
            self.update_preview()
        else:
            QMessageBox.critical(self, "Ошибка", msg)

    # ── DRAG-AND-DROP ──────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            filepath = urls[0].toLocalFile()
            if filepath:
                self._process_file(filepath)

    # ── СПИСОК КЛАССА ─────────────────────────────────────────────

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
        for i in reversed(range(self.scroll_layout.count())):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
        self.student_checkboxes.clear()

        students = self.roster_manager.get_all_students()
        for idx, student in enumerate(students):
            display_name = student["name"] if student["name"] else "(без имени)"
            cb = QCheckBox(display_name)
            cb.setChecked(student["selected"])
            cb.toggled.connect(lambda state, i=idx: self.on_student_toggled(i, state))
            self.scroll_layout.addWidget(cb)
            self.student_checkboxes.append(cb)

    def on_student_toggled(self, index, state):
        self.roster_manager.set_student_selection(index, state)
        self.update_stats()

    def toggle_all(self, state):
        self.roster_manager.select_all(state)
        for cb in self.student_checkboxes:
            cb.blockSignals(True)
            cb.setChecked(state)
            cb.blockSignals(False)
        self.update_stats()

    def on_copies_change(self, value):
        self.copies_per_page = value
        self.update_preview()

    # ── СТАТИСТИКА И ПРЕВЬЮ ───────────────────────────────────────

    def _get_hide_header(self):
        return self.print_mode == "blank"

    def _get_students_for_print(self):
        """Возвращает список учеников для печати в зависимости от режима."""
        if self.print_mode == "roster":
            selected = self.roster_manager.get_selected_students()
            if not selected:
                # Если ничего не выбрано, берём всех
                selected = self.roster_manager.get_all_students()
            # Если список вообще пуст — одна пустая копия
            return [s["name"] for s in selected] if selected else [""]
        else:
            # Режим без шапки — нужное количество пустых
            count = self.spin_total_copies.value()
            return [""] * count

    def update_stats(self):
        hide_header = self._get_hide_header()
        layout_res = self.pdf_processor.calculate_layout(self.copies_per_page, hide_header)
        copies_per_page_res = layout_res[2] if layout_res[0] > 0 else 0

        students = self._get_students_for_print()
        total_needed = len(students)

        pages = 0
        if copies_per_page_res > 0 and total_needed > 0:
            pages = math.ceil(total_needed / copies_per_page_res)

        if self.print_mode == "roster":
            selected = self.roster_manager.get_selected_students()
            self.lbl_selected_count.setText(f"Выбрано: {len(selected)} учеников")
        else:
            self.lbl_selected_count.setText(f"Раздаток: {self.spin_total_copies.value()} шт.")

        self.lbl_pages_needed.setText(f"Потребуется листов А4: {pages}")

    def update_preview(self):
        hide_header = self._get_hide_header()
        img, copies_per_page = self.pdf_processor.generate_preview(self.copies_per_page, hide_header)

        if img:
            img_bytes = BytesIO()
            img.save(img_bytes, format='PNG')
            pixmap = QPixmap()
            pixmap.loadFromData(img_bytes.getvalue())

            if pixmap.width() > pixmap.height():
                self.preview_label.setFixedSize(594, 420)
            else:
                self.preview_label.setFixedSize(420, 594)

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

    # ── СОХРАНЕНИЕ ────────────────────────────────────────────────

    def print_test_page(self):
        if not self.pdf_processor.template_pix:
            QMessageBox.warning(self, "Ошибка", "Сначала выберите файл для раздатки.")
            return

        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            self.btn_print_test.setText("Печать...")
            QApplication.processEvents()
            self._do_print(printer, is_test=True)
            self.btn_print_test.setText("📄  Печать 1 тестового листа")

    def print_all(self):
        if not self.pdf_processor.template_pix:
            QMessageBox.warning(self, "Ошибка", "Сначала выберите файл для раздатки.")
            return

        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            self.btn_print_all.setText("Печать...")
            QApplication.processEvents()
            self._do_print(printer, is_test=False)
            self.btn_print_all.setText("🖨  Распечатать всё")

    def _do_print(self, printer, is_test):
        import tempfile
        import fitz
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(tmp_fd)
        
        hide_header = False
        students = self.roster_manager.get_selected_students()
        
        if self.print_mode == "blank":
            try:
                total_needed = int(self.total_copies_input.text())
            except ValueError:
                total_needed = 1
            students = [""] * total_needed
            hide_header = True

        if is_test:
            # Для тестовой страницы берем только учеников на 1 страницу
            students = students[:self.copies_per_page]
            if not students:
                students = [""] * self.copies_per_page
            
        success, msg = self.pdf_processor.generate_pdf(
            self.copies_per_page, students, tmp_path, hide_header
        )
        
        if success:
            try:
                doc = fitz.open(tmp_path)
                painter = QPainter()
                if not painter.begin(printer):
                    raise RuntimeError("Не удалось инициализировать QPainter для выбранного принтера.")
                
                for i in range(len(doc)):
                    if i > 0:
                        printer.newPage()
                    page = doc[i]
                    # Рендерим с DPI 200 (достаточно для печати, предотвращает переполнение памяти GDI)
                    pix = page.get_pixmap(dpi=200)
                    img = QImage.fromData(pix.tobytes("png"))
                    
                    if img.isNull():
                        raise RuntimeError(f"Ошибка формирования картинки для страницы {i+1}.")
                    
                    rect = printer.pageRect(QPrinter.Unit.DevicePixel)
                    painter.drawImage(rect.toRect(), img)
                
                painter.end()
                doc.close()
                QMessageBox.information(self, "Успех", "Документ успешно отправлен на печать!")
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                try:
                    with open("print_error_log.txt", "w", encoding="utf-8") as f:
                        f.write(error_trace)
                except:
                    pass
                QMessageBox.critical(self, "Ошибка", f"Ошибка при печати:\n{e}\n\nЛог сохранен в print_error_log.txt")
        else:
            QMessageBox.critical(self, "Ошибка", msg)
            
        try:
            os.remove(tmp_path)
        except:
            pass

    def save_pdf(self):
        if not self.pdf_processor.template_pix:
            QMessageBox.warning(self, "Внимание", "Сначала загрузите файл раздатки.")
            return

        students = self._get_students_for_print()

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить PDF как",
            "",
            "PDF files (*.pdf)"
        )

        if filepath:
            self.btn_save.setEnabled(False)
            self.btn_save.setText("Сохранение...")
            QApplication.processEvents()

            hide_header = self._get_hide_header()
            success, msg = self.pdf_processor.generate_pdf(
                self.copies_per_page, students, filepath, hide_header
            )

            self.btn_save.setEnabled(True)
            self.btn_save.setText("🖨  Сохранить PDF для печати")

            if success:
                QMessageBox.information(self, "Успех", msg)
            else:
                QMessageBox.critical(self, "Ошибка", msg)

    def show_update_available(self, version, url):
        self.update_url = url
        self.btn_update.setText(f"⬆️ Обновить до v{version}")
        self.btn_update.show()

    def _on_update_clicked(self):
        import webbrowser
        webbrowser.open(self.update_url)
