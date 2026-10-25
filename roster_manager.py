import json
import os
import csv
from utils import get_user_data_path

CACHE_FILE = get_user_data_path("roster_cache.json")


class RosterManager:
    def __init__(self):
        # Each student: {"name": str, "selected": bool, "variant": int}
        # variant — 0-based index into the variants list (0 = Вариант 1, 1 = Вариант 2, …)
        self.students = []
        self.load_cache()

    def _ensure_variant(self, student):
        """Backward-compat: добавляет поле variant если его нет."""
        if "variant" not in student:
            student["variant"] = 0
        return student

    def load_cache(self):
        """Загружает список учеников из кэша (JSON)."""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                self.students = [self._ensure_variant(s) for s in raw]
            except Exception as e:
                print(f"Ошибка чтения кэша: {e}")
                self.students = []

    def save_cache(self):
        """Сохраняет список учеников в кэш (JSON)."""
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.students, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Ошибка сохранения кэша: {e}")

    def load_from_file(self, filepath):
        """Загружает список из TXT или CSV файла."""
        new_students = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                if filepath.lower().endswith(".csv"):
                    reader = csv.reader(f)
                    for row in reader:
                        if row:
                            name = row[0].strip()
                            if name:
                                new_students.append({"name": name, "selected": True, "variant": 0})
                else:  # TXT
                    for line in f:
                        name = line.strip()
                        if name:
                            new_students.append({"name": name, "selected": True, "variant": 0})

            if new_students:
                self.students = new_students
                self.save_cache()
                return True, "Список успешно загружен."
            else:
                return False, "Файл пуст или имеет неверный формат."
        except Exception as e:
            return False, f"Ошибка при чтении файла: {e}"

    def update_from_text(self, text):
        """Обновляет список из обычного текста (построчно). Сохраняет variant для существующих."""
        # Запоминаем старые варианты по имени
        old_variants = {s["name"]: s.get("variant", 0) for s in self.students}

        new_students = []
        lines = text.strip().split('\n')
        for line in lines:
            name = line.strip()
            if name:
                new_students.append({
                    "name": name,
                    "selected": True,
                    "variant": old_variants.get(name, 0)
                })

        self.students = new_students
        self.save_cache()
        return True, "Список успешно обновлен."

    def get_selected_students(self):
        """Возвращает список только выбранных учеников (name, variant)."""
        return [(s["name"], s.get("variant", 0)) for s in self.students if s["selected"]]

    def get_all_students(self):
        return self.students

    def set_student_selection(self, index, selected):
        """Обновляет состояние выбора конкретного ученика."""
        if 0 <= index < len(self.students):
            self.students[index]["selected"] = selected
            self.save_cache()

    def set_student_variant(self, index, variant):
        """Устанавливает вариант (0-based) для конкретного ученика."""
        if 0 <= index < len(self.students):
            self.students[index]["variant"] = variant
            self.save_cache()

    def select_all(self, selected=True):
        """Выбирает или снимает выбор со всех учеников."""
        for s in self.students:
            s["selected"] = selected
        self.save_cache()

    def add_empty_student(self):
        """Добавляет ученика с пустым именем (для подписи от руки)."""
        self.students.append({"name": "", "selected": True, "variant": 0})
        self.save_cache()
