import os
import math
import io
import zipfile
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QScrollArea, QCheckBox, QFileDialog, QMessageBox, QFrame, QSizePolicy,
    QDialog, QTextEdit, QApplication, QSpinBox, QButtonGroup, QRadioButton,
    QStackedWidget, QComboBox
)
from PyQt6.QtCore import Qt, QSize
from crop_widget import ImageCropDialog
from PyQt6.QtGui import QPixmap, QFont, QImage, QImageReader, QIcon, QPainter, QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
from io import BytesIO

from roster_manager import RosterManager
from pdf_processor import PDFProcessor
from utils import get_resource_path


class RosterEditDialog(QDialog):
    def __init__(self, parent, current_students):
        super().__init__(parent)
        self.setWindowTitle("Редактирование списка класса")
        self.setMinimumSize(420, 520)
        self.setStyleSheet(parent.styleSheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        info_label = QLabel("Вставьте список учеников (каждое имя с новой строки):")
        info_label.setObjectName("DialogHeader")
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

        ico_path = get_resource_path(os.path.join("assets", "icon.ico"))
        if os.path.exists(ico_path):
            self.setWindowIcon(QIcon(ico_path))

        self.setAcceptDrops(True)

        self.roster_manager = RosterManager()
        self.pdf_processor = PDFProcessor()
        self.copies_per_page = 4
        # Режим: "roster" = по списку, "blank" = без шапки
        self.print_mode = "roster"
        self.dark_mode = False

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
        self.left_panel.setFixedWidth(380)
        self.left_panel.setObjectName("LeftPanel")
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(20, 20, 20, 20)
        self.left_layout.setSpacing(10)

        # Заголовок
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(8)
        self.title_label = QLabel("✂ Копирка")
        self.title_label.setObjectName("TitleLabel")
        title_layout.addWidget(self.title_label)

        info_label = QLabel("ℹ️")
        info_label.setObjectName("InfoLabel")
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
        title_layout.addWidget(info_label)
        title_layout.addStretch()

        # Кнопка переключения темы (Светлая / Темная MD3)
        self.btn_theme = QPushButton("🌙")
        self.btn_theme.setObjectName("ThemeBtn")
        self.btn_theme.setFixedSize(34, 34)
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.setToolTip("Переключить тему (Светлая / Тёмная Material Design 3)")
        self.btn_theme.clicked.connect(self.toggle_theme)
        title_layout.addWidget(self.btn_theme)

        # Кнопка обновления (скрыта по умолчанию)
        self.btn_update = QPushButton("⬆️")
        self.btn_update.setObjectName("UpdateBtn")
        self.btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update.hide()
        self.btn_update.clicked.connect(self._on_update_clicked)
        title_layout.addWidget(self.btn_update)

        self.left_layout.addLayout(title_layout)

        # ── ВАРИАНТЫ ──────────────────────────────────────────
        variants_label = QLabel("Варианты заданий:")
        variants_label.setObjectName("SectionLabel")
        self.left_layout.addWidget(variants_label)

        # Контейнер со списком вариантов
        self.variants_container = QVBoxLayout()
        self.variants_container.setSpacing(6)
        self.variant_rows = []  # list of QHBoxLayout rows
        self.left_layout.addLayout(self.variants_container)

        self.btn_add_variant = QPushButton("＋  Добавить вариант")
        self.btn_add_variant.setObjectName("TonalButton")
        self.btn_add_variant.clicked.connect(self.add_variant)
        self.left_layout.addWidget(self.btn_add_variant)

        # Загрузка файла (основной вариант 1)
        self.btn_load_file = QPushButton("📂  Добавить файл (PDF / JPG / PNG / Word)")
        self.btn_load_file.setObjectName("TonalButton")
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
        mode_frame.setObjectName("SegmentedFrame")
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(4)

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
        roster_layout.setSpacing(8)

        self.btn_edit_roster = QPushButton("✏  Изменить список класса")
        self.btn_edit_roster.setObjectName("SecondaryButton")
        self.btn_edit_roster.clicked.connect(self.edit_roster)
        roster_layout.addWidget(self.btn_edit_roster)

        sel_frame = QFrame()
        sel_layout = QHBoxLayout(sel_frame)
        sel_layout.setContentsMargins(0, 0, 0, 0)
        sel_layout.setSpacing(6)

        self.btn_sel_all = QPushButton("Выбрать всех")
        self.btn_sel_all.setObjectName("SmallTonalButton")
        self.btn_sel_all.clicked.connect(lambda: self.toggle_all(True))
        sel_layout.addWidget(self.btn_sel_all)

        self.btn_desel_all = QPushButton("Снять выбор")
        self.btn_desel_all.setObjectName("SmallOutlinedButton")
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
        self.student_variant_combos = []

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

    # ─────────────────────────────────────────────────────────────────────────
    # Варианты
    # ─────────────────────────────────────────────────────────────────────────

    def _variant_labels(self):
        """Возвращает список строк для ComboBox вариантов."""
        count = self.pdf_processor.variant_count()
        return [f"Вариант {i + 1}" for i in range(count)]

    def _rebuild_variant_rows(self):
        """Перерисовывает строки вариантов в левой панели."""
        # Удаляем старые виджеты
        while self.variants_container.count():
            item = self.variants_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Удаляем дочерние виджеты вложенного layout
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

        self.variant_rows = []
        count = self.pdf_processor.variant_count()

        for i in range(count):
            row_widget = QFrame()
            row_widget.setObjectName("VariantRow")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(6, 4, 6, 4)
            row_layout.setSpacing(6)

            # Метка варианта
            lbl = QLabel(f"Вариант {i + 1}:")
            lbl.setFixedWidth(70)
            row_layout.addWidget(lbl)

            # Кнопка изменить файл
            btn_change = QPushButton("📂 Изменить файл")
            btn_change.setObjectName("SmallOutlinedButton")
            btn_change.clicked.connect(lambda checked, idx=i: self._change_variant_file(idx))
            row_layout.addWidget(btn_change, stretch=1)

            # Кнопка удалить (только если вариантов > 1)
            if count > 1:
                btn_del = QPushButton("✕")
                btn_del.setFixedSize(28, 28)
                btn_del.setToolTip(f"Удалить вариант {i + 1}")
                btn_del.setObjectName("DeleteBtn")
                btn_del.clicked.connect(lambda checked, idx=i: self._remove_variant(idx))
                row_layout.addWidget(btn_del)

            self.variants_container.addWidget(row_widget)
            self.variant_rows.append(row_widget)

        # Обновляем ComboBox-ы в списке учеников
        self._refresh_variant_combos()

    def add_variant(self):
        """Загружает новый файл и добавляет его как отдельный вариант."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл для нового варианта",
            "",
            "Все поддерживаемые форматы (*.pdf *.png *.jpg *.jpeg *.docx);;PDF (*.pdf);;"
            "Изображения (*.png *.jpg *.jpeg);;Word документы (*.docx);;Все файлы (*.*)"
        )
        if not filepath:
            return

        pix, width, height = self._load_file_to_pix(filepath)
        if pix is None:
            return

        # Предлагаем обрезку
        qpixmap = self._pix_to_qpixmap(pix)
        if qpixmap and not qpixmap.isNull():
            dialog = ImageCropDialog(self, qpixmap)
            if dialog.exec():
                crop_rect = dialog.get_crop_rect()
                if crop_rect:
                    # Добавляем временный вариант и сразу обрезаем
                    idx = self.pdf_processor.add_variant(pix, width, height)
                    self.pdf_processor.crop_template(crop_rect, variant_idx=idx)
                else:
                    self.pdf_processor.add_variant(pix, width, height)
            else:
                self.pdf_processor.add_variant(pix, width, height)
        else:
            self.pdf_processor.add_variant(pix, width, height)

        self._rebuild_variant_rows()
        self.update_preview()

    def _change_variant_file(self, variant_idx):
        """Заменяет файл существующего варианта."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            f"Выберите файл для варианта {variant_idx + 1}",
            "",
            "Все поддерживаемые форматы (*.pdf *.png *.jpg *.jpeg *.docx);;PDF (*.pdf);;"
            "Изображения (*.png *.jpg *.jpeg);;Word документы (*.docx);;Все файлы (*.*)"
        )
        if not filepath:
            return

        pix, width, height = self._load_file_to_pix(filepath)
        if pix is None:
            return

        qpixmap = self._pix_to_qpixmap(pix)
        crop_rect = None
        if qpixmap and not qpixmap.isNull():
            dialog = ImageCropDialog(self, qpixmap)
            if dialog.exec():
                crop_rect = dialog.get_crop_rect()

        self.pdf_processor.set_variant(variant_idx, pix, width, height)
        if crop_rect:
            self.pdf_processor.crop_template(crop_rect, variant_idx=variant_idx)

        self._rebuild_variant_rows()
        self.update_preview()

    def _remove_variant(self, variant_idx):
        """Удаляет вариант. Обновляет индексы вариантов у учеников."""
        self.pdf_processor.remove_variant(variant_idx)

        # Корректируем индексы вариантов у учеников
        count = self.pdf_processor.variant_count()
        students = self.roster_manager.get_all_students()
        for s in students:
            if s.get("variant", 0) >= count:
                s["variant"] = count - 1
        self.roster_manager.save_cache()

        self._rebuild_variant_rows()
        self.refresh_student_list()
        self.update_preview()

    def _refresh_variant_combos(self):
        """Обновляет варианты в уже отрисованных ComboBox-ах."""
        labels = self._variant_labels()
        for i, (cb, combo) in enumerate(zip(self.student_checkboxes, self.student_variant_combos)):
            combo.blockSignals(True)
            current = combo.currentIndex()
            combo.clear()
            combo.addItems(labels)
            # Восстанавливаем выбранный вариант из модели
            student_variant = self.roster_manager.get_all_students()[i].get("variant", 0)
            combo.setCurrentIndex(min(student_variant, len(labels) - 1))
            combo.setVisible(len(labels) > 1)
            combo.blockSignals(False)

    # ─────────────────────────────────────────────────────────────────────────
    # Загрузка файлов
    # ─────────────────────────────────────────────────────────────────────────

    def _pix_to_qpixmap(self, pix):
        """Конвертирует fitz.Pixmap в QPixmap."""
        from PIL import Image as PILImage
        img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qpixmap = QPixmap()
        QImageReader.setAllocationLimit(1024)
        qpixmap.loadFromData(buf.getvalue())
        return qpixmap

    def _load_file_to_pix(self, filepath):
        """
        Загружает файл и возвращает (fitz.Pixmap, width, height) или (None, 0, 0) при ошибке.
        Не изменяет состояние PDFProcessor.
        """
        import fitz
        ext = os.path.splitext(filepath)[1].lower()
        try:
            if ext == ".docx":
                return self._load_docx_to_pix(filepath)
            else:
                doc = fitz.open(filepath)
                page = doc[0]
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                width = page.rect.width
                height = page.rect.height
                doc.close()
                return pix, width, height
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить файл:\n{e}")
            return None, 0, 0

    def _load_docx_to_pix(self, filepath):
        """Извлекает первое изображение из DOCX и возвращает (fitz.Pixmap, w, h)."""
        import fitz
        from PIL import Image as PILImage
        try:
            images = []
            with zipfile.ZipFile(filepath, "r") as z:
                for name in z.namelist():
                    if name.startswith("word/media/") and any(
                        name.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"]
                    ):
                        images.append((name, z.read(name)))

            if not images:
                QMessageBox.warning(self, "Word", "В документе не найдено изображений.")
                return None, 0, 0

            img_name, img_data = images[0]
            if len(images) > 1:
                QMessageBox.information(
                    self, "Word",
                    f"В документе найдено {len(images)} изображений. Будет использовано первое."
                )

            pil_img = PILImage.open(io.BytesIO(img_data)).convert("RGB")
            png_buf = io.BytesIO()
            pil_img.save(png_buf, format="PNG")

            pix = fitz.Pixmap(png_buf.getvalue())
            return pix, pix.width, pix.height
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть Word-файл:\n{e}")
            return None, 0, 0

    def load_template_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл раздатки",
            "",
            "Все поддерживаемые форматы (*.pdf *.png *.jpg *.jpeg *.docx);;PDF (*.pdf);;"
            "Изображения (*.png *.jpg *.jpeg);;Word документы (*.docx);;Все файлы (*.*)"
        )
        if filepath:
            self._process_file(filepath)

    def _process_file(self, filepath):
        """Загружает файл как вариант 0 (основной шаблон). Если вариантов нет — создаёт первый."""
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".docx":
            self._load_from_docx_as_variant0(filepath)
        else:
            self._load_standard_file_as_variant0(filepath)

    def _load_standard_file_as_variant0(self, filepath):
        """Загружает обычный файл как вариант 0."""
        pix, width, height = self._load_file_to_pix(filepath)
        if pix is None:
            return

        # Обрезка
        qpixmap = self._pix_to_qpixmap(pix)
        crop_rect = None
        if not qpixmap.isNull():
            dialog = ImageCropDialog(self, qpixmap)
            if dialog.exec():
                crop_rect = dialog.get_crop_rect()

        # Инициализируем вариант 0 через load_template (для совместимости)
        success, msg = self.pdf_processor.load_template(filepath)
        if not success:
            QMessageBox.critical(self, "Ошибка", msg)
            return

        if crop_rect:
            self.pdf_processor.crop_template(crop_rect, variant_idx=0)

        filename = os.path.basename(filepath)
        self.file_status_label.setText(f"📄 {filename}")
        self.file_status_label.setProperty("loaded", True)
        self.file_status_label.style().unpolish(self.file_status_label)
        self.file_status_label.style().polish(self.file_status_label)
        self._rebuild_variant_rows()
        self.update_preview()

    def _load_from_docx_as_variant0(self, filepath):
        """Загружает DOCX как вариант 0."""
        import fitz
        pix, width, height = self._load_docx_to_pix(filepath)
        if pix is None:
            return

        qpixmap = self._pix_to_qpixmap(pix)
        crop_rect = None
        if not qpixmap.isNull():
            dialog = ImageCropDialog(self, qpixmap)
            if dialog.exec():
                crop_rect = dialog.get_crop_rect()

        # Обновляем вариант 0
        if not self.pdf_processor.variants:
            self.pdf_processor.add_variant(pix, width, height)
        else:
            self.pdf_processor.set_variant(0, pix, width, height)

        if crop_rect:
            self.pdf_processor.crop_template(crop_rect, variant_idx=0)

        filename = os.path.basename(filepath)
        self.file_status_label.setText(f"📄 {filename}")
        self.file_status_label.setProperty("loaded", True)
        self.file_status_label.style().unpolish(self.file_status_label)
        self.file_status_label.style().polish(self.file_status_label)
        self._rebuild_variant_rows()
        self.update_preview()

    # Drag-and-drop
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            filepath = urls[0].toLocalFile()
            if filepath:
                self._process_file(filepath)

    # ─────────────────────────────────────────────────────────────────────────
    # Список класса
    # ─────────────────────────────────────────────────────────────────────────

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
        self.student_variant_combos.clear()

        students = self.roster_manager.get_all_students()
        variant_labels = self._variant_labels()
        show_variants = len(variant_labels) > 1

        for idx, student in enumerate(students):
            display_name = student["name"] if student["name"] else "(без имени)"

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            cb = QCheckBox(display_name)
            cb.setChecked(student["selected"])
            cb.toggled.connect(lambda state, i=idx: self.on_student_toggled(i, state))
            row_layout.addWidget(cb, stretch=1)

            # ComboBox для выбора варианта
            combo = QComboBox()
            combo.addItems(variant_labels)
            combo.setCurrentIndex(min(student.get("variant", 0), len(variant_labels) - 1))
            combo.setFixedWidth(90)
            combo.setVisible(show_variants)
            combo.currentIndexChanged.connect(lambda vi, i=idx: self.on_student_variant_changed(i, vi))
            row_layout.addWidget(combo)

            self.scroll_layout.addWidget(row_widget)
            self.student_checkboxes.append(cb)
            self.student_variant_combos.append(combo)

    def on_student_toggled(self, index, state):
        self.roster_manager.set_student_selection(index, state)
        self.update_stats()

    def on_student_variant_changed(self, index, variant_idx):
        self.roster_manager.set_student_variant(index, variant_idx)

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

    # ─────────────────────────────────────────────────────────────────────────
    # Статистика и превью
    # ─────────────────────────────────────────────────────────────────────────

    def _get_hide_header(self):
        return self.print_mode == "blank"

    def _get_students_for_print(self):
        """Возвращает список (name, variant_idx) для печати."""
        if self.print_mode == "roster":
            selected = self.roster_manager.get_selected_students()  # [(name, variant), ...]
            if not selected:
                # Если ничего не выбрано — берём всех
                selected = [(s["name"], s.get("variant", 0))
                            for s in self.roster_manager.get_all_students()]
            return selected if selected else [("", 0)]
        else:
            count = self.spin_total_copies.value()
            return [("", 0)] * count

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

    # ─────────────────────────────────────────────────────────────────────────
    # Печать и сохранение
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_printer(self, printer):
        hide_header = self._get_hide_header()
        self.pdf_processor.calculate_layout(self.copies_per_page, hide_header)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        if self.pdf_processor.A4_WIDTH > self.pdf_processor.A4_HEIGHT:
            printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        else:
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)

    def print_test_page(self):
        if not self.pdf_processor.template_pix:
            QMessageBox.warning(self, "Ошибка", "Сначала выберите файл для раздатки.")
            return

        self.printer = QPrinter()
        self._setup_printer(self.printer)
        dialog = QPrintDialog(self.printer, self)
        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            self.btn_print_test.setText("Печать...")
            QApplication.processEvents()
            self._do_print(self.printer, is_test=True)
            self.btn_print_test.setText("📄  Печать 1 тестового листа")

    def print_all(self):
        if not self.pdf_processor.template_pix:
            QMessageBox.warning(self, "Ошибка", "Сначала выберите файл для раздатки.")
            return

        self.printer = QPrinter()
        self._setup_printer(self.printer)
        dialog = QPrintDialog(self.printer, self)
        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            self.btn_print_all.setText("Печать...")
            QApplication.processEvents()
            self._do_print(self.printer, is_test=False)
            self.btn_print_all.setText("🖨  Распечатать всё")

    def _do_print(self, printer, is_test):
        import tempfile
        import fitz
        from datetime import datetime

        log_path = os.path.join(os.path.expanduser("~"), "Desktop", "kopirka_print_log.txt")

        def write_log(msg):
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now()}] {msg}\n")
            except Exception:
                pass

        write_log("--- НАЧАЛО ПЕЧАТИ ---")
        self._setup_printer(printer)
        write_log(
            f"Ориентация принтера: {printer.pageLayout().orientation().name}, "
            f"формат: {printer.pageLayout().pageSize().name()}"
        )

        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(tmp_fd)

        hide_header = self._get_hide_header()
        students = self._get_students_for_print()

        if is_test:
            students = students[: self.copies_per_page]
            if not students:
                students = [("", 0)] * self.copies_per_page

        write_log("Генерация PDF...")
        success, msg = self.pdf_processor.generate_pdf(
            self.copies_per_page, students, tmp_path, hide_header
        )

        if success:
            try:
                write_log("Открытие PDF через fitz...")
                doc = fitz.open(tmp_path)

                write_log("Создание QPainter...")
                painter = QPainter()
                write_log(f"painter.begin()... (Printer name: {printer.printerName()})")

                if not painter.begin(printer):
                    write_log("Ошибка: painter.begin(printer) вернул False!")
                    raise RuntimeError("Не удалось инициализировать QPainter для выбранного принтера.")

                write_log("painter.begin() успешен!")

                for i in range(len(doc)):
                    write_log(f"Обработка страницы {i + 1}...")
                    if i > 0:
                        printer.newPage()

                    page = doc[i]
                    pix = page.get_pixmap(dpi=200)
                    img = QImage.fromData(pix.tobytes("png"))

                    if img.isNull():
                        raise RuntimeError(f"Ошибка формирования картинки для страницы {i + 1}.")

                    rect = printer.pageRect(QPrinter.Unit.DevicePixel)
                    from PyQt6.QtCore import QRectF

                    img_size = img.size()
                    w_ratio = rect.width() / img_size.width()
                    h_ratio = rect.height() / img_size.height()
                    scale = min(w_ratio, h_ratio)

                    new_w = img_size.width() * scale
                    new_h = img_size.height() * scale
                    x = rect.x() + (rect.width() - new_w) / 2.0
                    y = rect.y() + (rect.height() - new_h) / 2.0

                    target_rect = QRectF(x, y, new_w, new_h)
                    painter.drawImage(target_rect, img)
                    write_log(f"Страница {i + 1} отрисована!")

                painter.end()
                doc.close()
                QMessageBox.information(self, "Успех", "Документ успешно отправлен на печать!")
            except Exception as e:
                import traceback

                error_trace = traceback.format_exc()
                write_log(f"PYTHON EXCEPTION:\n{error_trace}")
                QMessageBox.critical(
                    self, "Ошибка", f"Ошибка при печати:\n{e}\n\nЛог сохранен на рабочем столе"
                )
        else:
            write_log(f"generate_pdf вернул ошибку: {msg}")
            QMessageBox.critical(self, "Ошибка", msg)

        try:
            os.remove(tmp_path)
        except Exception:
            pass
        write_log("--- КОНЕЦ ПЕЧАТИ ---")

    def save_pdf(self):
        if not self.pdf_processor.template_pix:
            QMessageBox.warning(self, "Внимание", "Сначала загрузите файл раздатки.")
            return

        students = self._get_students_for_print()

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Сохранить PDF как", "", "PDF files (*.pdf)"
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
            self.btn_save.setText("💾  Сохранить в PDF")

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

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.btn_theme.setText("☀️" if self.dark_mode else "🌙")
        self.apply_stylesheet()

    # ─────────────────────────────────────────────────────────────────────────
    # Стили Material Design 3 (Material You)
    # ─────────────────────────────────────────────────────────────────────────

    def apply_stylesheet(self):
        self.setStyleSheet(get_md3_stylesheet(self.dark_mode))


def get_md3_tokens(dark_mode: bool = False):
    """
    Тональные палитры Material Design 3 (MD3).
    Базовый цвет (Seed Color): #0B57D0 (Google Material You Vibrant Blue)
    """
    if dark_mode:
        return {
            "primary": "#A8C7FA",
            "on_primary": "#062E6F",
            "primary_container": "#0842A0",
            "on_primary_container": "#D3E3FD",
            "primary_hover": "#BDD5FB",
            "primary_pressed": "#8EB5F8",
            "secondary": "#AFC6E3",
            "on_secondary": "#193148",
            "secondary_container": "#2A415A",
            "on_secondary_container": "#D7E3F8",
            "tertiary": "#D7BDE3",
            "on_tertiary": "#3C2947",
            "tertiary_container": "#543F5F",
            "on_tertiary_container": "#F3DAFF",
            "surface": "#111318",
            "surface_dim": "#111318",
            "surface_container_lowest": "#0C0E13",
            "surface_container_low": "#191C20",
            "surface_container": "#1D2024",
            "surface_container_high": "#282A2F",
            "surface_container_highest": "#33353A",
            "on_surface": "#E2E2E9",
            "on_surface_variant": "#C4C7D0",
            "outline": "#8E9199",
            "outline_variant": "#44474E",
            "error": "#FFB4AB",
            "error_container": "#93000A",
            "on_error": "#690005",
            "on_error_container": "#FFDAD6",
            "success": "#6DD58C",
            "state_hover_surface": "rgba(255, 255, 255, 0.06)",
            "state_pressed_surface": "rgba(255, 255, 255, 0.12)",
            "state_hover_primary": "#364F6D",
            "state_pressed_primary": "#456182",
        }
    else:
        return {
            "primary": "#0B57D0",
            "on_primary": "#FFFFFF",
            "primary_container": "#D3E3FD",
            "on_primary_container": "#041E49",
            "primary_hover": "#0842A0",
            "primary_pressed": "#042B6A",
            "secondary": "#475D78",
            "on_secondary": "#FFFFFF",
            "secondary_container": "#D7E3F8",
            "on_secondary_container": "#041C35",
            "tertiary": "#6C5778",
            "on_tertiary": "#FFFFFF",
            "tertiary_container": "#F3DAFF",
            "on_tertiary_container": "#261432",
            "surface": "#F8F9FA",
            "surface_dim": "#D9DFE8",
            "surface_container_lowest": "#FFFFFF",
            "surface_container_low": "#F0F4F9",
            "surface_container": "#E9EEF6",
            "surface_container_high": "#E1E6EC",
            "surface_container_highest": "#D9DFE8",
            "on_surface": "#1A1C1E",
            "on_surface_variant": "#44474E",
            "outline": "#74777F",
            "outline_variant": "#C4C7D0",
            "error": "#BA1A1A",
            "error_container": "#FFDAD6",
            "on_error": "#FFFFFF",
            "on_error_container": "#410002",
            "success": "#146C2E",
            "state_hover_surface": "rgba(0, 0, 0, 0.04)",
            "state_pressed_surface": "rgba(0, 0, 0, 0.08)",
            "state_hover_primary": "#C5D8F6",
            "state_pressed_primary": "#B3CBF2",
        }


def get_md3_stylesheet(dark_mode: bool = False) -> str:
    p = get_md3_tokens(dark_mode)
    return f"""
        /* ── Base Window & Dialogs ── */
        QMainWindow, QDialog {{
            background-color: {p['surface_container_low']};
            color: {p['on_surface']};
            font-family: "Roboto", "Segoe UI", -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
        }}

        /* ── Left Panel (Tonal Elevation Surface) ── */
        #LeftPanel {{
            background-color: {p['surface_container_low']};
            border-right: 1px solid {p['outline_variant']};
        }}

        /* ── Right Panel (Canvas Area) ── */
        #RightPanel {{
            background-color: {p['surface_container_lowest']};
        }}

        /* ── Typography Scale ── */
        #TitleLabel {{
            font-size: 22px;
            font-weight: 700;
            color: {p['on_surface']};
            letter-spacing: -0.4px;
            margin-bottom: 2px;
        }}

        #SectionLabel {{
            font-size: 11px;
            font-weight: 700;
            color: {p['primary']};
            text-transform: uppercase;
            letter-spacing: 0.8px;
            margin-top: 4px;
            margin-bottom: 2px;
        }}

        QLabel {{
            font-size: 13px;
            color: {p['on_surface']};
        }}

        #InfoLabel {{
            font-size: 16px;
            color: {p['on_surface_variant']};
            padding: 2px 4px;
        }}

        #StatusLabel {{
            color: {p['on_surface_variant']};
            font-style: italic;
            font-size: 12px;
            padding: 2px 0px;
        }}

        #StatusLabel[loaded="true"] {{
            color: {p['success']};
            font-style: normal;
            font-weight: 600;
        }}

        #DialogHeader {{
            font-size: 14px;
            font-weight: 600;
            color: {p['on_surface']};
            margin-bottom: 4px;
        }}

        /* ── MD3 Buttons ── */

        /* Standard Default Button (Tonal / Outlined Pill) */
        QPushButton {{
            background-color: {p['surface_container_high']};
            border: 1px solid {p['outline_variant']};
            border-radius: 18px;
            padding: 7px 16px;
            color: {p['on_surface']};
            font-weight: 500;
            font-size: 13px;
            min-height: 22px;
        }}
        QPushButton:hover {{
            background-color: {p['surface_container_highest']};
            border-color: {p['outline']};
        }}
        QPushButton:pressed {{
            background-color: {p['outline_variant']};
        }}
        QPushButton:disabled {{
            background-color: {p['surface_container']};
            color: {p['outline']};
            border-color: {p['surface_container_high']};
        }}

        /* Primary Filled Button (Pill, High Emphasis) */
        #PrimaryButton {{
            background-color: {p['primary']};
            color: {p['on_primary']};
            border: none;
            font-size: 14px;
            font-weight: 600;
            letter-spacing: 0.2px;
            border-radius: 22px;
            min-height: 44px;
            padding: 8px 24px;
        }}
        #PrimaryButton:hover {{
            background-color: {p['primary_hover']};
        }}
        #PrimaryButton:pressed {{
            background-color: {p['primary_pressed']};
        }}
        #PrimaryButton:disabled {{
            background-color: {p['outline_variant']};
            color: {p['surface_container_lowest']};
        }}

        /* Secondary Outlined Button (Pill, Medium Emphasis) */
        #SecondaryButton {{
            background-color: transparent;
            border: 1px solid {p['outline']};
            color: {p['primary']};
            border-radius: 20px;
            font-size: 13px;
            font-weight: 500;
            min-height: 38px;
            padding: 6px 18px;
        }}
        #SecondaryButton:hover {{
            background-color: {p['primary_container']};
            border-color: {p['primary']};
            color: {p['on_primary_container']};
        }}
        #SecondaryButton:pressed {{
            background-color: {p['secondary_container']};
        }}
        #SecondaryButton:disabled {{
            border-color: {p['outline_variant']};
            color: {p['outline']};
        }}

        /* Tonal Button (Filled Secondary Container, Pill) */
        #TonalButton {{
            background-color: {p['secondary_container']};
            color: {p['on_secondary_container']};
            border: none;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            min-height: 38px;
            padding: 6px 18px;
        }}
        #TonalButton:hover {{
            background-color: {p['state_hover_primary']};
        }}
        #TonalButton:pressed {{
            background-color: {p['state_pressed_primary']};
        }}

        /* Small Action Buttons (Select All / Deselect All) */
        #SmallTonalButton {{
            background-color: {p['surface_container_high']};
            color: {p['on_surface']};
            border: 1px solid {p['outline_variant']};
            border-radius: 16px;
            padding: 5px 12px;
            font-size: 12px;
            font-weight: 500;
            min-height: 28px;
        }}
        #SmallTonalButton:hover {{
            background-color: {p['surface_container_highest']};
            border-color: {p['outline']};
        }}

        #SmallOutlinedButton {{
            background-color: transparent;
            color: {p['primary']};
            border: 1px solid {p['outline_variant']};
            border-radius: 16px;
            padding: 5px 12px;
            font-size: 12px;
            font-weight: 500;
            min-height: 28px;
        }}
        #SmallOutlinedButton:hover {{
            background-color: {p['primary_container']};
            border-color: {p['primary']};
            color: {p['on_primary_container']};
        }}

        /* Delete Icon Button (MD3 Error Tonal Squircle) */
        #DeleteBtn {{
            background-color: {p['error_container']};
            color: {p['on_error_container']};
            border: none;
            border-radius: 14px;
            padding: 0px;
            font-weight: bold;
            font-size: 12px;
        }}
        #DeleteBtn:hover {{
            background-color: {p['error']};
            color: {p['on_error']};
        }}

        /* Update Badge Button */
        #UpdateBtn {{
            background-color: {p['success']};
            color: #FFFFFF;
            border: none;
            border-radius: 14px;
            padding: 4px 10px;
            font-weight: 600;
            font-size: 12px;
        }}
        #UpdateBtn:hover {{
            opacity: 0.9;
        }}

        /* Theme Toggle Icon Button */
        #ThemeBtn {{
            background-color: {p['surface_container_high']};
            color: {p['on_surface']};
            border: 1px solid {p['outline_variant']};
            border-radius: 17px;
            padding: 2px;
            font-size: 15px;
        }}
        #ThemeBtn:hover {{
            background-color: {p['surface_container_highest']};
            border-color: {p['primary']};
        }}

        /* ── MD3 Cards & Containers ── */

        /* Variant Row Card */
        #VariantRow {{
            background-color: {p['surface_container_lowest']};
            border: 1px solid {p['outline_variant']};
            border-radius: 14px;
            padding: 4px 8px;
        }}

        /* Stats Container Card */
        #StatsFrame {{
            background-color: {p['secondary_container']};
            border: 1px solid {p['outline_variant']};
            border-radius: 16px;
            padding: 8px 12px;
        }}
        #StatsFrame QLabel {{
            color: {p['on_secondary_container']};
            font-weight: 500;
            font-size: 13px;
        }}

        /* Segmented Frame Container */
        #SegmentedFrame {{
            background-color: {p['surface_container_high']};
            border-radius: 22px;
            padding: 3px;
        }}

        /* Segmented Radio Buttons */
        QRadioButton {{
            font-size: 13px;
            font-weight: 500;
            color: {p['on_surface_variant']};
            padding: 7px 16px;
            border: none;
            border-radius: 18px;
            background: transparent;
        }}
        QRadioButton::indicator {{
            width: 0px;
            height: 0px;
        }}
        QRadioButton:hover {{
            background-color: {p['state_hover_surface']};
            color: {p['on_surface']};
        }}
        QRadioButton:checked {{
            background-color: {p['surface_container_lowest']};
            color: {p['primary']};
            font-weight: 600;
        }}

        /* Scroll Area & Student List */
        QScrollArea {{
            border: 1px solid {p['outline_variant']};
            border-radius: 14px;
            background-color: {p['surface_container_lowest']};
        }}
        #ScrollWidget {{
            background-color: {p['surface_container_lowest']};
            border-radius: 14px;
        }}

        /* Text Editor (Dialog) */
        QTextEdit {{
            border: 1px solid {p['outline_variant']};
            border-radius: 14px;
            background-color: {p['surface_container_lowest']};
            color: {p['on_surface']};
            padding: 10px;
            font-size: 13px;
        }}
        QTextEdit:focus {{
            border: 2px solid {p['primary']};
        }}

        /* Checkboxes (MD3 Indicator) */
        QCheckBox {{
            font-size: 13px;
            color: {p['on_surface']};
            padding: 4px 0;
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 5px;
            border: 2px solid {p['outline']};
            background-color: transparent;
        }}
        QCheckBox::indicator:hover {{
            border-color: {p['primary']};
            background-color: {p['state_hover_surface']};
        }}
        QCheckBox::indicator:checked {{
            background-color: {p['primary']};
            border-color: {p['primary']};
        }}

        /* Inputs (SpinBox & ComboBox) */
        QSpinBox, QComboBox {{
            border: 1px solid {p['outline_variant']};
            border-radius: 12px;
            padding: 6px 12px;
            font-size: 13px;
            background-color: {p['surface_container_lowest']};
            color: {p['on_surface']};
            min-height: 24px;
        }}
        QSpinBox:hover, QComboBox:hover {{
            border-color: {p['outline']};
        }}
        QSpinBox:focus, QComboBox:focus {{
            border: 2px solid {p['primary']};
        }}
        QComboBox::drop-down {{
            border: none;
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {p['surface_container_lowest']};
            border: 1px solid {p['outline_variant']};
            border-radius: 12px;
            padding: 4px;
            selection-background-color: {p['primary_container']};
            selection-color: {p['on_primary_container']};
            color: {p['on_surface']};
        }}

        /* Separator Line */
        #Separator {{
            background-color: {p['outline_variant']};
            border: none;
            min-height: 1px;
            max-height: 1px;
            margin: 4px 0;
        }}

        /* Preview Canvas (Right Panel) */
        #PreviewLabel {{
            background-color: {p['surface_container_lowest']};
            border: 1px solid {p['outline_variant']};
            border-radius: 16px;
            color: {p['on_surface_variant']};
        }}

        /* MD3 Subtle Scrollbars */
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 8px;
            margin: 4px 2px 4px 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {p['outline_variant']};
            border-radius: 4px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {p['outline']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}

        /* Tooltips */
        QToolTip {{
            background-color: {p['surface_container_highest']};
            color: {p['on_surface']};
            border: 1px solid {p['outline_variant']};
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 12px;
        }}
    """



