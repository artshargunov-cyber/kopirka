from PyQt6.QtWidgets import QWidget, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt, QRect, QPoint, QSize
from PyQt6.QtGui import QPainter, QColor, QPen

class InteractiveCropWidget(QWidget):
    def __init__(self, pixmap, original_size, parent=None):
        super().__init__(parent)
        self.pixmap = pixmap
        self.original_size = original_size
        self.setFixedSize(self.pixmap.size())
        
        self.scale_ratio_x = self.original_size.width() / self.pixmap.width()
        self.scale_ratio_y = self.original_size.height() / self.pixmap.height()

        # По умолчанию рамка на всю картинку с небольшим отступом (или без)
        margin = min(self.width(), self.height()) // 10
        self.crop_rect = QRect(margin, margin, self.width() - 2*margin, self.height() - 2*margin)
        
        self.handle_size = 10
        self.active_handle = None
        self.drag_start_pos = None
        self.drag_start_rect = None

        self.setMouseTracking(True) # Чтобы курсор менялся при наведении на ручки

    def get_crop_rect_original(self):
        x0 = int(self.crop_rect.left() * self.scale_ratio_x)
        y0 = int(self.crop_rect.top() * self.scale_ratio_y)
        x1 = int(self.crop_rect.right() * self.scale_ratio_x)
        y1 = int(self.crop_rect.bottom() * self.scale_ratio_y)
        return (x0, y0, x1, y1)

    def paintEvent(self, event):
        painter = QPainter(self)
        # Рисуем саму картинку
        painter.drawPixmap(0, 0, self.pixmap)
        
        # Рисуем затемнение (вне рамки)
        dark_color = QColor(0, 0, 0, 150)
        
        # 4 прямоугольника затемнения вокруг crop_rect
        r = self.rect()
        cr = self.crop_rect
        painter.fillRect(QRect(r.left(), r.top(), r.width(), cr.top() - r.top()), dark_color) # Top
        painter.fillRect(QRect(r.left(), cr.bottom() + 1, r.width(), r.bottom() - cr.bottom()), dark_color) # Bottom
        painter.fillRect(QRect(r.left(), cr.top(), cr.left() - r.left(), cr.height()), dark_color) # Left
        painter.fillRect(QRect(cr.right() + 1, cr.top(), r.right() - cr.right(), cr.height()), dark_color) # Right

        # Рисуем границу рамки
        pen = QPen(QColor(37, 99, 235)) # Синий цвет
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(cr)

        # Рисуем ручки (8 штук)
        painter.setBrush(QColor(255, 255, 255)) # Белые квадратики
        for handle_rect, _ in self._get_handles():
            painter.drawRect(handle_rect)

    def _get_handles(self):
        """Возвращает список кортежей (QRect, Имя_ручки)"""
        cr = self.crop_rect
        s = self.handle_size
        s_half = s // 2
        
        handles = [
            (QRect(cr.left() - s_half, cr.top() - s_half, s, s), 'top_left'),
            (QRect(cr.center().x() - s_half, cr.top() - s_half, s, s), 'top'),
            (QRect(cr.right() - s_half, cr.top() - s_half, s, s), 'top_right'),
            (QRect(cr.right() - s_half, cr.center().y() - s_half, s, s), 'right'),
            (QRect(cr.right() - s_half, cr.bottom() - s_half, s, s), 'bottom_right'),
            (QRect(cr.center().x() - s_half, cr.bottom() - s_half, s, s), 'bottom'),
            (QRect(cr.left() - s_half, cr.bottom() - s_half, s, s), 'bottom_left'),
            (QRect(cr.left() - s_half, cr.center().y() - s_half, s, s), 'left'),
        ]
        return handles

    def mousePressEvent(self, event):
        pos = event.pos()
        self.drag_start_pos = pos
        self.drag_start_rect = QRect(self.crop_rect)
        
        # Проверяем клик по ручкам
        for handle_rect, name in self._get_handles():
            if handle_rect.contains(pos):
                self.active_handle = name
                return

        # Проверяем клик внутри рамки для перетаскивания
        if self.crop_rect.contains(pos):
            self.active_handle = 'center'
            return

        # Клик снаружи рамки - создаем новую рамку
        self.active_handle = 'new'
        self.crop_rect = QRect(pos, pos)
        self.update()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        
        # Меняем курсор при наведении
        if not self.active_handle:
            cursor = Qt.CursorShape.ArrowCursor
            for handle_rect, name in self._get_handles():
                if handle_rect.contains(pos):
                    if name in ['top_left', 'bottom_right']: cursor = Qt.CursorShape.SizeFDiagCursor
                    elif name in ['top_right', 'bottom_left']: cursor = Qt.CursorShape.SizeBDiagCursor
                    elif name in ['left', 'right']: cursor = Qt.CursorShape.SizeHorCursor
                    elif name in ['top', 'bottom']: cursor = Qt.CursorShape.SizeVerCursor
                    break
            else:
                if self.crop_rect.contains(pos):
                    cursor = Qt.CursorShape.SizeAllCursor
            self.setCursor(cursor)
            return

        # Обработка перетаскивания/изменения размера
        diff = pos - self.drag_start_pos
        new_rect = QRect(self.drag_start_rect)

        if self.active_handle == 'center':
            new_rect.translate(diff)
        elif self.active_handle == 'new':
            new_rect = QRect(self.drag_start_pos, pos).normalized()
        else:
            if 'top' in self.active_handle:
                new_rect.setTop(pos.y())
            if 'bottom' in self.active_handle:
                new_rect.setBottom(pos.y())
            if 'left' in self.active_handle:
                new_rect.setLeft(pos.x())
            if 'right' in self.active_handle:
                new_rect.setRight(pos.x())

        # Нормализуем и ограничиваем пределами картинки
        new_rect = new_rect.normalized()
        new_rect = new_rect.intersected(self.rect())
        
        # Ограничиваем минимальный размер
        if new_rect.width() >= 10 and new_rect.height() >= 10:
            self.crop_rect = new_rect
            self.update()

    def mouseReleaseEvent(self, event):
        self.active_handle = None

class ImageCropDialog(QDialog):
    def __init__(self, parent, original_pixmap):
        super().__init__(parent)
        self.setWindowTitle("Интерактивная обрезка картинки")
        self.setStyleSheet(parent.styleSheet())
        
        layout = QVBoxLayout(self)
        
        self.info = QLabel("Изменяйте размер синей рамки, передвигайте её или нарисуйте новую.\\nНажмите 'Сохранить обрезку', чтобы применить.")
        layout.addWidget(self.info)

        # Scale pixmap to fit within 800x600 for UI purposes
        scaled_pixmap = original_pixmap.scaled(800, 600, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        self.crop_widget = InteractiveCropWidget(scaled_pixmap, original_pixmap.size(), self)
        
        # Центрируем кастомный виджет
        center_layout = QHBoxLayout()
        center_layout.addStretch()
        center_layout.addWidget(self.crop_widget)
        center_layout.addStretch()
        layout.addLayout(center_layout)
        
        btns = QHBoxLayout()
        self.btn_skip = QPushButton("Пропустить")
        self.btn_skip.clicked.connect(self.reject)
        btns.addWidget(self.btn_skip)
        
        self.btn_save = QPushButton("Сохранить обрезку")
        self.btn_save.setObjectName("PrimaryButton")
        self.btn_save.clicked.connect(self.accept)
        btns.addWidget(self.btn_save)
        
        layout.addLayout(btns)

    def get_crop_rect(self):
        return self.crop_widget.get_crop_rect_original()
