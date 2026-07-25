import fitz  # PyMuPDF
from PIL import Image
import math
import os

class PDFProcessor:
    def __init__(self):
        self.MARGIN = 20
        self.A4_PORTRAIT_W = 595.276
        self.A4_PORTRAIT_H = 841.890
        
        # Текущие размеры (меняются в зависимости от ориентации картинки)
        self.A4_WIDTH = self.A4_PORTRAIT_W
        self.A4_HEIGHT = self.A4_PORTRAIT_H
        
        self.USABLE_WIDTH = self.A4_WIDTH - 2 * self.MARGIN
        self.USABLE_HEIGHT = self.A4_HEIGHT - 2 * self.MARGIN

        self.template_doc = None
        self.template_pix = None
        self.template_width = 0
        self.template_height = 0

    def _update_page_orientation(self):
        """Определяет ориентацию листа А4 на основе размеров загруженной картинки."""
        if self.template_width > self.template_height:
            self.A4_WIDTH = self.A4_PORTRAIT_H  # Ландшафтная
            self.A4_HEIGHT = self.A4_PORTRAIT_W
        else:
            self.A4_WIDTH = self.A4_PORTRAIT_W  # Портретная
            self.A4_HEIGHT = self.A4_PORTRAIT_H
            
        self.USABLE_WIDTH = self.A4_WIDTH - 2 * self.MARGIN
        self.USABLE_HEIGHT = self.A4_HEIGHT - 2 * self.MARGIN

    def load_template(self, filepath):
        """Загружает файл (PDF или изображение) и сохраняет его как Pixmap для дальнейшего использования."""
        try:
            doc = fitz.open(filepath)
            page = doc[0] # Берем первую страницу
            
            # Для лучшего качества рендерим с матрицей (например, x2)
            mat = fitz.Matrix(2, 2)
            self.template_pix = page.get_pixmap(matrix=mat)
            self.template_doc = doc
            
            # Исходные размеры (до масштабирования пользователем)
            self.template_width = page.rect.width
            self.template_height = page.rect.height
            
            # Автоматически поворачиваем лист, если картинка горизонтальная
            self._update_page_orientation()
            
            # Если исходник больше доступной области, масштабируем его до 100%
            if self.template_width > self.USABLE_WIDTH or self.template_height > self.USABLE_HEIGHT:
                ratio = min(self.USABLE_WIDTH / self.template_width, self.USABLE_HEIGHT / self.template_height)
                self.template_width *= ratio
                self.template_height *= ratio

            return True, "Файл успешно загружен."
        except Exception as e:
            return False, f"Ошибка загрузки файла: {e}"

    def calculate_layout(self, scale_percent):
        """
        Рассчитывает количество копий на листе А4 и их размеры при заданном масштабе (от 10 до 100).
        """
        if not self.template_pix:
            return 0, 0, 0, 0, 0
            
        scale_factor = scale_percent / 100.0
        scaled_width = self.template_width * scale_factor
        scaled_height = self.template_height * scale_factor
        
        # Оцениваем место под текст (Имя + Оценка + отступы) - теперь в одну строку
        fontsize = max(8, min(14, scaled_width / 25))
        header_height = 10 + fontsize * 1.5 + 5 # Точная сумма всех вертикальных отступов текста
        
        total_width = scaled_width
        total_height = scaled_height + header_height

        # Защита от деления на ноль при очень маленьком масштабе
        if total_width < 1 or total_height < 1:
            return 0, 0, 0, total_width, total_height

        cols = int(self.USABLE_WIDTH // total_width)
        rows = int(self.USABLE_HEIGHT // total_height)
        
        return cols, rows, cols * rows, total_width, total_height

    def _draw_text_without_bg(self, page, text, rect, fontsize):
        """Рисует текст с использованием шрифта Roboto, поддерживающего кириллицу."""
        # Подключаем шрифт Roboto из папки assets
        font_path = os.path.join(os.path.dirname(__file__), "assets", "Roboto-Regular.ttf")
        with open(font_path, "rb") as f:
            font_buf = f.read()
        page.insert_font(fontname="F0", fontbuffer=font_buf)
        
        # Вставляем текст
        page.insert_text((rect.x0 + 5, rect.y0 + 5 + fontsize), text, fontsize=fontsize, fontname="F0", color=(0, 0, 0))
        return rect.y0 + 5 + fontsize * 1.5 # Возвращаем Y для следующего блока

    def _draw_cut_lines(self, page, cols, rows, scaled_width, scaled_height):
        """Рисует линии отреза (серые штрихпунктирные) между рядами и колонками."""
        shape = page.new_shape()
        
        # Вертикальные линии (между колонками)
        for c in range(1, cols):
            x = self.MARGIN + c * scaled_width
            shape.draw_line(fitz.Point(x, 0), fitz.Point(x, self.A4_HEIGHT))
            
        # Горизонтальные линии (между строками)
        for r in range(1, rows):
            y = self.MARGIN + r * scaled_height
            shape.draw_line(fitz.Point(0, y), fitz.Point(self.A4_WIDTH, y))
            
        shape.finish(color=(0.7, 0.7, 0.7), dashes="[3 3] 0", width=0.5)
        shape.commit()

    def generate_preview(self, scale_percent):
        """
        Генерирует изображение (PIL Image) одной страницы A4 для предпросмотра.
        """
        if not self.template_pix:
            return None, 0

        cols, rows, copies_per_page, sw, sh = self.calculate_layout(scale_percent)
        
        # Создаем временный пустой PDF документ для страницы
        doc = fitz.open()
        page = doc.new_page(width=self.A4_WIDTH, height=self.A4_HEIGHT)
        
        scale_factor = scale_percent / 100.0
        image_scaled_width = self.template_width * scale_factor
        image_scaled_height = self.template_height * scale_factor

        # Рендерим тестовые копии
        for r in range(rows):
            for c in range(cols):
                x0 = self.MARGIN + c * sw
                y0 = self.MARGIN + r * sh
                cell_rect = fitz.Rect(x0, y0, x0 + sw, y0 + sh)
                
                # Вставляем тестовый текст "Иванов Иван" и "Оценка: ____" в одну строку
                fontsize = max(8, min(14, image_scaled_width / 25))
                header_text = "Ученик: Иванов Иван         Оценка: _______"
                y_img = self._draw_text_without_bg(page, header_text, cell_rect, fontsize)
                
                # Вставляем изображение раздатки НИЖЕ текста, строго упираясь в нижнюю границу ячейки
                img_rect = fitz.Rect(x0, y_img + 5, x0 + image_scaled_width, y0 + sh)
                page.insert_image(img_rect, pixmap=self.template_pix)

        # Рисуем линии реза
        self._draw_cut_lines(page, cols, rows, sw, sh)

        # Конвертируем страницу в PIL Image
        # Для превью можно использовать меньшее разрешение (matrix)
        pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        doc.close()
        return img, copies_per_page

    def generate_pdf(self, scale_percent, students, output_path):
        """
        Генерирует финальный многостраничный PDF для всех учеников.
        Если список пуст, делает пустую строку вместо имени.
        """
        if not self.template_pix:
            return False, "Не загружен файл раздатки."

        cols, rows, copies_per_page, sw, sh = self.calculate_layout(scale_percent)
        
        if copies_per_page == 0:
            return False, "Масштаб слишком велик, ни одна копия не помещается на лист."

        if not students:
            # Fallback, если список не загружен/все сняты
            students = [""] # Сделаем 1 пустую копию

        doc = fitz.open()
        
        scale_factor = scale_percent / 100.0
        image_scaled_width = self.template_width * scale_factor
        image_scaled_height = self.template_height * scale_factor

        student_idx = 0
        total_students = len(students)
        
        while student_idx < total_students:
            page = doc.new_page(width=self.A4_WIDTH, height=self.A4_HEIGHT)
            
            for r in range(rows):
                for c in range(cols):
                    if student_idx >= total_students:
                        break # Все ученики размещены
                        
                    student_name = students[student_idx]
                    
                    x0 = self.MARGIN + c * sw
                    y0 = self.MARGIN + r * sh
                    cell_rect = fitz.Rect(x0, y0, x0 + sw, y0 + sh)
                    
                    fontsize = max(8, min(14, image_scaled_width / 25))
                    name_part = f"Ученик: {student_name}" if student_name else "Фамилия, Имя: ____________"
                    header_text = f"{name_part}         Оценка: _______"
                    
                    y_img = self._draw_text_without_bg(page, header_text, cell_rect, fontsize)
                    
                    # Жестко ограничиваем низ картинки границей ячейки
                    img_rect = fitz.Rect(x0, y_img + 5, x0 + image_scaled_width, y0 + sh)
                    page.insert_image(img_rect, pixmap=self.template_pix)
                    
                    student_idx += 1

            self._draw_cut_lines(page, cols, rows, sw, sh)

        try:
            doc.save(output_path)
            doc.close()
            return True, f"PDF успешно сохранен: {output_path}"
        except Exception as e:
            return False, f"Ошибка при сохранении PDF: {e}"

    def crop_template(self, rect_tuple):
        """
        Обрезает текущий загруженный шаблон (Pixmap) по переданным координатам (x0, y0, x1, y1).
        Для обрезки используется PIL Image.
        """
        if not self.template_pix:
            return

        import io
        img = Image.frombytes("RGB", [self.template_pix.width, self.template_pix.height], self.template_pix.samples)
        cropped_img = img.crop(rect_tuple)
        
        img_bytes = io.BytesIO()
        cropped_img.save(img_bytes, format='PNG')
        
        doc = fitz.open(stream=img_bytes.getvalue(), filetype="png")
        page = doc[0]
        
        self.template_pix = page.get_pixmap()
        self.template_width = page.rect.width
        self.template_height = page.rect.height
        
        self._update_page_orientation()
        
        # Если исходник больше доступной области, масштабируем его до 100%
        if self.template_width > self.USABLE_WIDTH or self.template_height > self.USABLE_HEIGHT:
            ratio = min(self.USABLE_WIDTH / self.template_width, self.USABLE_HEIGHT / self.template_height)
            self.template_width *= ratio
            self.template_height *= ratio
