import fitz
import os
import math
from PIL import Image
from utils import get_resource_path


class PDFProcessor:
    def __init__(self):
        self.MARGIN = 5
        self.A4_PORTRAIT_W = 595.276
        self.A4_PORTRAIT_H = 841.890

        # Текущие размеры (меняются в зависимости от ориентации картинки)
        self.orientation = "portrait"
        self.A4_WIDTH = self.A4_PORTRAIT_W
        self.A4_HEIGHT = self.A4_PORTRAIT_H

        self.USABLE_WIDTH = self.A4_WIDTH - 2 * self.MARGIN
        self.USABLE_HEIGHT = self.A4_HEIGHT - 2 * self.MARGIN

        self.template_doc = None
        self.template_pix = None      # Вариант 1 (первичный шаблон, обратная совместимость)
        self.template_width = 0
        self.template_height = 0

        # Список вариантов: [{"pix": fitz.Pixmap, "width": float, "height": float}, ...]
        # Вариант 0 всегда совпадает с template_pix / template_width / template_height
        self.variants = []

    # ─────────────────────────────────────────────────────────────────────────
    # Вспомогательные методы для работы с вариантами
    # ─────────────────────────────────────────────────────────────────────────

    def _get_variant(self, idx):
        """Возвращает данные варианта по индексу (0-based). Если индекс вне диапазона — возвращает вариант 0."""
        if self.variants and 0 <= idx < len(self.variants):
            return self.variants[idx]
        # Fallback: используем основной шаблон
        if self.template_pix:
            return {"pix": self.template_pix, "width": self.template_width, "height": self.template_height}
        return None

    def _sync_primary(self):
        """Синхронизирует template_pix/width/height с вариантом 0."""
        if self.variants:
            v = self.variants[0]
            self.template_pix = v["pix"]
            self.template_width = v["width"]
            self.template_height = v["height"]

    def add_variant(self, pix, width, height):
        """Добавляет новый вариант и возвращает его индекс (0-based)."""
        self.variants.append({"pix": pix, "width": width, "height": height})
        self._sync_primary()
        self._update_page_orientation()
        return len(self.variants) - 1

    def set_variant(self, idx, pix, width, height):
        """Обновляет существующий вариант."""
        if 0 <= idx < len(self.variants):
            self.variants[idx] = {"pix": pix, "width": width, "height": height}
        self._sync_primary()
        self._update_page_orientation()

    def remove_variant(self, idx):
        """Удаляет вариант по индексу. Нельзя удалить последний."""
        if len(self.variants) > 1 and 0 <= idx < len(self.variants):
            self.variants.pop(idx)
        self._sync_primary()
        self._update_page_orientation()

    def variant_count(self):
        return len(self.variants)

    # ─────────────────────────────────────────────────────────────────────────
    # Ориентация страницы
    # ─────────────────────────────────────────────────────────────────────────

    def _update_page_orientation(self):
        """Определяет ориентацию листа А4 на основе размеров первого варианта."""
        if self.template_width > self.template_height:
            self.orientation = "landscape"
            self.A4_WIDTH = self.A4_PORTRAIT_H
            self.A4_HEIGHT = self.A4_PORTRAIT_W
        else:
            self.orientation = "portrait"
            self.A4_WIDTH = self.A4_PORTRAIT_W
            self.A4_HEIGHT = self.A4_PORTRAIT_H

        self.USABLE_WIDTH = self.A4_WIDTH - 2 * self.MARGIN
        self.USABLE_HEIGHT = self.A4_HEIGHT - 2 * self.MARGIN

    # ─────────────────────────────────────────────────────────────────────────
    # Загрузка файла
    # ─────────────────────────────────────────────────────────────────────────

    def load_template(self, filepath):
        """Загружает файл (PDF или изображение) как первый вариант."""
        try:
            doc = fitz.open(filepath)
            page = doc[0]

            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)
            self.template_doc = doc

            width = page.rect.width
            height = page.rect.height

            self._update_page_orientation_for(width, height)

            # Масштабируем если шаблон больше доступной области
            if width > self.USABLE_WIDTH or height > self.USABLE_HEIGHT:
                ratio = min(self.USABLE_WIDTH / width, self.USABLE_HEIGHT / height)
                width *= ratio
                height *= ratio

            # Инициализируем или заменяем вариант 0
            if not self.variants:
                self.variants.append({"pix": pix, "width": width, "height": height})
            else:
                self.variants[0] = {"pix": pix, "width": width, "height": height}

            self._sync_primary()
            self._update_page_orientation()

            return True, "Файл успешно загружен."
        except Exception as e:
            return False, f"Ошибка загрузки файла: {e}"

    def _update_page_orientation_for(self, width, height):
        """Вспомогательный — ставит ориентацию не обращаясь к self.template_*."""
        if width > height:
            self.orientation = "landscape"
            self.A4_WIDTH = self.A4_PORTRAIT_H
            self.A4_HEIGHT = self.A4_PORTRAIT_W
        else:
            self.orientation = "portrait"
            self.A4_WIDTH = self.A4_PORTRAIT_W
            self.A4_HEIGHT = self.A4_PORTRAIT_H
        self.USABLE_WIDTH = self.A4_WIDTH - 2 * self.MARGIN
        self.USABLE_HEIGHT = self.A4_HEIGHT - 2 * self.MARGIN

    # ─────────────────────────────────────────────────────────────────────────
    # Расчёт компоновки
    # ─────────────────────────────────────────────────────────────────────────

    def _get_max_scale(self, cell_w, cell_h, tw, th, hide_header=False):
        """Бинарный поиск максимального масштаба для заданных размеров шаблона."""
        low = 0.01
        high = 10.0
        best_s = 0
        for _ in range(50):
            mid = (low + high) / 2.0
            sw = tw * mid
            sh = th * mid
            hh = 0
            if not hide_header:
                fontsize = max(8.0, min(12.0, sw / 30.0))
                hh = 5 + fontsize * 1.2 + 2
            if sw <= cell_w and (sh + hh) <= cell_h:
                best_s = mid
                low = mid
            else:
                high = mid
        return best_s

    def calculate_layout(self, num_copies, hide_header=False):
        """
        Находит оптимальную сетку для размещения num_copies копий (на основе шаблона варианта 0).
        Возвращает: (cols, rows, num_copies, cell_w, cell_h, scale_factor)
        """
        if not self.template_pix:
            return 0, 0, 0, 0, 0, 0

        tw = self.template_width
        th = self.template_height

        best_area = 0
        best_config = None

        for orientation in ["portrait", "landscape"]:
            w = self.A4_PORTRAIT_W - 2 * self.MARGIN
            h = self.A4_PORTRAIT_H - 2 * self.MARGIN
            if orientation == "landscape":
                w, h = h, w

            for cols in range(1, num_copies + 1):
                rows = math.ceil(num_copies / cols)
                cell_w = w / cols
                cell_h = h / rows

                s = self._get_max_scale(cell_w, cell_h, tw, th, hide_header)
                if s > 0:
                    sw = tw * s
                    sh = th * s
                    area = sw * sh
                    if area > best_area:
                        best_area = area
                        best_config = (cols, rows, num_copies, cell_w, cell_h, s, orientation)

        if best_config:
            cols, rows, copies, cell_w, cell_h, s, orientation = best_config
            self.orientation = orientation
            if orientation == "portrait":
                self.A4_WIDTH = self.A4_PORTRAIT_W
                self.A4_HEIGHT = self.A4_PORTRAIT_H
            else:
                self.A4_WIDTH = self.A4_PORTRAIT_H
                self.A4_HEIGHT = self.A4_PORTRAIT_W
            self.USABLE_WIDTH = self.A4_WIDTH - 2 * self.MARGIN
            self.USABLE_HEIGHT = self.A4_HEIGHT - 2 * self.MARGIN
            return cols, rows, copies, cell_w, cell_h, s
        return 0, 0, 0, 0, 0, 0

    # ─────────────────────────────────────────────────────────────────────────
    # Отрисовка текста и линий
    # ─────────────────────────────────────────────────────────────────────────

    def _draw_text_without_bg(self, page, text, rect, fontsize):
        """Рисует текст с использованием шрифта Roboto, поддерживающего кириллицу."""
        font_path = get_resource_path(os.path.join("assets", "Roboto-Regular.ttf"))
        with open(font_path, "rb") as f:
            font_buf = f.read()
        page.insert_font(fontname="F0", fontbuffer=font_buf)
        page.insert_text(
            (rect.x0 + 2, rect.y0 + 5 + fontsize),
            text,
            fontsize=fontsize,
            fontname="F0",
            color=(0, 0, 0)
        )
        return rect.y0 + 5 + fontsize * 1.2

    def _draw_cut_lines(self, page, cols, rows, scaled_width, scaled_height):
        """Рисует линии отреза между рядами и колонками."""
        shape = page.new_shape()
        for c in range(1, cols):
            x = self.MARGIN + c * scaled_width
            shape.draw_line(fitz.Point(x, 0), fitz.Point(x, self.A4_HEIGHT))
        for r in range(1, rows):
            y = self.MARGIN + r * scaled_height
            shape.draw_line(fitz.Point(0, y), fitz.Point(self.A4_WIDTH, y))
        shape.finish(color=(0.7, 0.7, 0.7), dashes="[3 3] 0", width=0.5)
        shape.commit()

    # ─────────────────────────────────────────────────────────────────────────
    # Предпросмотр
    # ─────────────────────────────────────────────────────────────────────────

    def generate_preview(self, num_copies, hide_header=False):
        """
        Генерирует изображение (PIL Image) одной страницы A4 для предпросмотра.
        Для превью всегда используется вариант 0.
        """
        if not self.template_pix:
            return None, 0

        layout_res = self.calculate_layout(num_copies, hide_header)
        if layout_res[0] == 0:
            return None, 0
        cols, rows, copies_per_page, cell_w, cell_h, scale_factor = layout_res

        doc = fitz.open()
        page = doc.new_page(width=self.A4_WIDTH, height=self.A4_HEIGHT)

        v = self._get_variant(0)
        image_scaled_width = v["width"] * scale_factor
        image_scaled_height = v["height"] * scale_factor

        drawn_count = 0
        for r in range(rows):
            for c in range(cols):
                if drawn_count >= num_copies:
                    continue
                x0 = self.MARGIN + c * cell_w
                y0 = self.MARGIN + r * cell_h
                cell_rect = fitz.Rect(x0, y0, x0 + cell_w, y0 + cell_h)

                if not hide_header:
                    fontsize = max(8.0, min(12.0, image_scaled_width / 30.0))
                    header_text = "Ученик: Иванов Иван         Отметка: _______"
                    y_img = self._draw_text_without_bg(page, header_text, cell_rect, fontsize)
                    img_rect = fitz.Rect(x0, y_img + 2, x0 + image_scaled_width, y_img + 2 + image_scaled_height)
                else:
                    img_rect = fitz.Rect(x0, y0, x0 + image_scaled_width, y0 + image_scaled_height)

                page.insert_image(img_rect, pixmap=v["pix"], keep_proportion=True)
                drawn_count += 1

        self._draw_cut_lines(page, cols, rows, cell_w, cell_h)

        pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()
        return img, copies_per_page

    # ─────────────────────────────────────────────────────────────────────────
    # Генерация PDF
    # ─────────────────────────────────────────────────────────────────────────

    def generate_pdf(self, num_copies, students, output_path, hide_header=False):
        """
        Генерирует финальный многостраничный PDF.

        students — список кортежей (name: str, variant_idx: int)
                   ИЛИ просто список строк (обратная совместимость с режимом «Без шапки»).
        """
        if not self.template_pix:
            return False, "Не загружен файл раздатки."

        layout_res = self.calculate_layout(num_copies, hide_header)
        if layout_res[0] == 0:
            return False, "Невозможно разместить ни одной копии на листе."
        cols, rows, copies_per_page, cell_w, cell_h, scale_factor = layout_res

        if copies_per_page == 0:
            return False, "Слишком большое количество копий."

        if not students:
            students = [("", 0)]

        # Нормализация: принимаем как (name, variant) так и просто str
        def _norm(s):
            if isinstance(s, tuple):
                return s
            return (s, 0)

        students = [_norm(s) for s in students]

        doc = fitz.open()
        student_idx = 0
        total_students = len(students)

        while student_idx < total_students:
            page = doc.new_page(width=self.A4_WIDTH, height=self.A4_HEIGHT)
            drawn_on_page = 0

            for r in range(rows):
                for c in range(cols):
                    if drawn_on_page >= copies_per_page or student_idx >= total_students:
                        continue

                    student_name, variant_idx = students[student_idx]
                    v = self._get_variant(variant_idx)

                    image_scaled_width = v["width"] * scale_factor
                    image_scaled_height = v["height"] * scale_factor

                    x0 = self.MARGIN + c * cell_w
                    y0 = self.MARGIN + r * cell_h
                    cell_rect = fitz.Rect(x0, y0, x0 + cell_w, y0 + cell_h)

                    if not hide_header:
                        fontsize = max(8.0, min(12.0, image_scaled_width / 30.0))
                        name_part = f"Ученик: {student_name}" if student_name else "Фамилия, Имя: ____________"
                        # Добавляем номер варианта если вариантов больше одного
                        if len(self.variants) > 1:
                            var_label = f"  |  Вариант {variant_idx + 1}"
                        else:
                            var_label = ""
                        header_text = f"{name_part}{var_label}         Отметка: _______"
                        y_img = self._draw_text_without_bg(page, header_text, cell_rect, fontsize)
                        img_rect = fitz.Rect(x0, y_img + 2, x0 + image_scaled_width, y_img + 2 + image_scaled_height)
                    else:
                        img_rect = fitz.Rect(x0, y0, x0 + image_scaled_width, y0 + image_scaled_height)

                    page.insert_image(img_rect, pixmap=v["pix"], keep_proportion=True)
                    student_idx += 1
                    drawn_on_page += 1

            self._draw_cut_lines(page, cols, rows, cell_w, cell_h)

        try:
            doc.save(output_path)
            doc.close()
            return True, f"PDF успешно сохранен: {output_path}"
        except Exception as e:
            return False, f"Ошибка при сохранении PDF: {e}"

    # ─────────────────────────────────────────────────────────────────────────
    # Обрезка
    # ─────────────────────────────────────────────────────────────────────────

    def crop_template(self, rect_tuple, variant_idx=0):
        """
        Обрезает вариант по индексу variant_idx (по умолчанию — основной шаблон, вариант 0).
        rect_tuple: (x0, y0, x1, y1) в пикселях исходного Pixmap.
        """
        import io as _io

        v = self._get_variant(variant_idx)
        if not v:
            return

        pix = v["pix"]
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        cropped_img = img.crop(rect_tuple)

        img_bytes = _io.BytesIO()
        cropped_img.save(img_bytes, format="PNG")

        doc = fitz.open(stream=img_bytes.getvalue(), filetype="png")
        page = doc[0]

        new_pix = page.get_pixmap()
        new_w = page.rect.width
        new_h = page.rect.height

        # Масштабируем если шаблон больше доступной области
        if new_w > self.USABLE_WIDTH or new_h > self.USABLE_HEIGHT:
            ratio = min(self.USABLE_WIDTH / new_w, self.USABLE_HEIGHT / new_h)
            new_w *= ratio
            new_h *= ratio

        if variant_idx < len(self.variants):
            self.variants[variant_idx] = {"pix": new_pix, "width": new_w, "height": new_h}
        else:
            self.variants.append({"pix": new_pix, "width": new_w, "height": new_h})

        self._sync_primary()
        self._update_page_orientation()
