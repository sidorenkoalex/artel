"""Юнит-тесты разбора `orchestrator.tz_check` (SPEC 01M598KY8V2P2GRD5Q67DRAZNA)
на свойства, которых не касается долгоживущий файл задачи: форма ссылки
у URL, пустая строка внутри тела функции, нетекстовый файл по ссылке,
согласование числа в заголовке вывода."""
import unittest

from orchestrator import tz_check


class _FakeTree:
    """Дерево из словаря {путь: байты} — без git."""

    def __init__(self, files: dict):
        self.sha = "a" * 40
        self.blobs = files
        self.files = list(files)
        self.file_set = set(files)
        self.by_name = {}
        for path in files:
            self.by_name.setdefault(path.rsplit("/", 1)[-1], []).append(path)
        self.extensions = {n.rsplit(".", 1)[1] for n in self.by_name if "." in n}

    def blob(self, path: str) -> bytes:
        return self.blobs[path]


class RefGrammarTest(unittest.TestCase):

    def test_url_with_port_is_not_a_ref(self):
        """Адрес с портом и схемой ссылкой `файл:строка` не считается.

        Ловит мутацию: левая граница ссылки допускает начало после `/` —
        `127.0.0.1:8443` из адреса со схемой становится ссылкой на файл
        `127.0.0.1` и уходит в отказ «файла нет»."""
        self.assertEqual(tz_check._refs("см. https://127.0.0.1:8443/a и "
                                        "http://127.0.0.1:80"), [])

    def test_ref_inside_sentence_keeps_range_bounds(self):
        """Диапазон в конце предложения разобран с обеими границами.

        Ловит мутацию: точка конца предложения или дефис диапазона рвут
        разбор — `b` теряется, и граница за концом файла не ловится."""
        [ref] = tz_check._refs("Смотри docs/x.md:12-40.")
        self.assertEqual((ref.path, ref.first, ref.last), ("docs/x.md", 12, 40))


class EnclosingTest(unittest.TestCase):

    def test_blank_line_in_function_body_gives_the_function(self):
        """Пустая строка внутри тела функции берёт отступ следующей строки.

        Ловит мутацию: пустая строка считается строкой уровня модуля
        (отступ 0) — ссылка на неё внутри функции кандидата не даёт."""
        lines = ["def outer():", "    a = 1", "", "    return a", ""]
        self.assertEqual(tz_check._enclosing(lines, 3), "outer")
        self.assertIsNone(tz_check._enclosing(lines, 5))


class NearNameTest(unittest.TestCase):

    def test_binary_file_window_not_checked(self):
        """Нетекстовый файл по ссылке окно «имени рядом» не сверяет.

        Ловит мутацию: окно сверяется и у бинарного файла — имя, которого
        в байтах нет, даёт ложное предупреждение."""
        tree = _FakeTree({"data/blob.bin": b"\x00\x01\n" * 10})
        report = tz_check.Report()
        tz = "См. data/blob.bin:5 `someName`."
        tz_check._check_refs(tree, tz, tz_check._refs(tz), report)
        self.assertEqual((report.refusals, report.warnings), ([], []))


class HeaderTest(unittest.TestCase):

    def test_header_counts_agree_in_number(self):
        """Заголовок согласует число с существительным и несёт sha.

        Ловит мутацию: окончание не зависит от числа («1 отказов»,
        «2 предупреждений»); sha дерева не попадает в заголовок."""
        report = tz_check.Report(sha="b" * 40, refusals=["x"],
                                 warnings=["y", "z"])
        header = report.lines()[0]
        self.assertTrue(header.startswith(
            "проверка ТЗ: 1 отказ, 2 предупреждения"), header)
        self.assertIn("b" * 40, header)
        self.assertTrue(tz_check.Report(warnings=["y"] * 11).lines()[0]
                        .startswith("проверка ТЗ: 0 отказов, 11 предупреждений"))


if __name__ == "__main__":
    unittest.main()
