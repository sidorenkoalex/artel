"""Генератор справочника ядра: свойства вне долгоживущих файлов задачи.

Долгоживущие файлы `tests/test_01m4s24963r9h18an2xdp6r15b_*.py` держат
критерии SPEC; здесь — решения реализации, которых SPEC не фиксирует.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import core_reference

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "core_reference.py"
SHA = "0123456789abcdef0123456789abcdef01234567"


SETTINGS = ('"""Значения."""\n\n'
            "# Роли состояний. Подробности ниже.\n"
            "ROLES = {\n"
            "    'a': 1,  # первый элемент\n"
            "    'b': 2}  # пояснение хвоста\n")


def roles_row() -> str:
    text = core_reference.build(
        {"conf/values.py": SETTINGS},
        {"modules": ["conf/values.py"], "constants_module": "conf/values.py",
         "constants": ["ROLES"]},
        SHA, min_uses=3, generator_sha256="0" * 64)
    rows = [line for line in text.split("\n") if line.startswith("- `ROLES`")]
    assert len(rows) == 1, text
    return rows[0]


class MultilineConstantTest(unittest.TestCase):

    def test_comment_on_last_line_of_multiline_value_is_not_the_note(self):
        """Комментарий последней строки многострочного значения — пояснение
        её элемента, не константы: берётся блок над присваиванием.

        Ловит мутацию: строковый комментарий ищется и в строке `end_lineno`
        присваивания — пояснением `ROLES` станет «пояснение хвоста».
        """
        note = roles_row().rsplit(" — ", 1)[1]
        self.assertEqual("Роли состояний", note)

    def test_comments_inside_multiline_value_are_dropped(self):
        """Значение многострочной константы одной строкой — без комментариев
        элементов: иначе комментарий съедает хвост значения.

        Ловит мутацию: значение собирается схлопыванием пробелов фрагмента
        кода без вырезания комментариев — в строке «первый элемент».
        """
        value = roles_row().split(" = ", 1)[1].rsplit(" — ", 1)[0]
        self.assertEqual("{ 'a': 1, 'b': 2}", value)


class CliArgumentsTest(unittest.TestCase):

    def test_constants_module_without_constants_is_refused(self):
        """`--constants-module` без `--constants` — отказ кодом 2 и пустой stdout.

        Ловит мутацию: командная строка молча принимает модуль констант без
        перечня (код 0, справочник без раздела констант), хотя настройка
        `targets.yaml` такой пары не допускает.
        """
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "a.py").write_text('"""Модуль."""\n', encoding="utf-8")
            res = subprocess.run(
                [sys.executable, str(SCRIPT), root, "a.py",
                 "--constants-module", "a.py"],
                cwd=root, capture_output=True, text=True, timeout=120)
        self.assertEqual(2, res.returncode, res.stderr)
        self.assertEqual("", res.stdout)


if __name__ == "__main__":
    unittest.main()
