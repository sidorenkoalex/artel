"""AC-15: существующие тесты запретов и трассируемости планки — без правок и зелёные на ветке задачи.

Группа: разовый
Зелёный с рождения: тексты прежних находок запретов и разбор файлов без метки сегодня держат существующие тесты, задача их не правит; файл сторожит, что ветка задачи их не тронула и не покрасила.

Факт задачи: дифф ветки (помощник пульта `_pult.changed_paths`) не несёт
файлов существующих тестов запретов (`tests/test_guard_plank_bans.py`) и
разбора планки по правилу (`tests/test_guard_plank_rule_parsing.py`), а
классы запретов файла честного FAIL_TO_PASS не изменены от базы ветки;
прогон этих тестов pytest из корня рабочей копии — код выхода 0.
"""
import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE, changed_paths  # noqa: E402

UNTOUCHED = ("tests/test_guard_plank_bans.py",
             "tests/test_guard_plank_rule_parsing.py")
FAIL_TO_PASS = "tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py"
BAN_CLASSES = ("BansSandbox", "Ac16BansTest", "Ac17NotBannedTest",
               "Ac18BanPlacesTest", "Ac21EachCommentsTest")

REPO_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR",
            "GIT_NAMESPACE", "GIT_PREFIX")


def clean_env() -> dict:
    """Окружение без переменных, которыми git находит репозиторий в обход
    `-C` (тот же перечень, что у помощника пульта)."""
    return {k: v for k, v in os.environ.items() if k not in REPO_ENV}


def classes(source: str) -> dict:
    tree = ast.parse(source)
    return {node.name: ast.get_source_segment(source, node)
            for node in tree.body if isinstance(node, ast.ClassDef)}


def base_text(rel: str) -> str:
    res = subprocess.run(["git", "-C", CODE_ROOT, "show", f"{DIFF_BASE}:{rel}"],
                         capture_output=True, text=True, timeout=60,
                         env=clean_env())
    if res.returncode != 0:
        raise AssertionError(f"git show {DIFF_BASE}:{rel}: {res.stderr}")
    return res.stdout


class Ac15ExistingBansTestsTest(unittest.TestCase):

    def test_ac15_ban_and_traceability_tests_untouched(self):
        """Файлы существующих тестов запретов и разбора по правилу не входят в дифф задачи; классы запретов файла FAIL_TO_PASS равны базе.

        Ловит мутацию: разработчик правит текст ожидаемой находки в
        `tests/test_guard_plank_bans.py` под новый текст запрета — файл в
        `changed_paths`; правит класс `Ac16BansTest` — исходный текст
        класса отличается от базы.
        """
        changed = set(changed_paths())
        for rel in UNTOUCHED:
            with self.subTest(rel=rel):
                self.assertNotIn(rel, changed)
        head = classes((Path(CODE_ROOT) / FAIL_TO_PASS).read_text(encoding="utf-8"))
        base = classes(base_text(FAIL_TO_PASS))
        for name in BAN_CLASSES:
            with self.subTest(cls=name):
                self.assertIn(name, base)
                self.assertEqual(head.get(name), base[name])

    def test_ac15_ban_and_traceability_tests_green(self):
        """Существующие тесты запретов, разбора по правилу и классы запретов FAIL_TO_PASS проходят на ветке задачи.

        Ловит мутацию: новый разбор шаблонной таблицы `.each` меняет имя
        теста у `.each(t)(…)` или текст находки «числовой литерал …» —
        прежний тест красен, код выхода pytest не 0.
        """
        nodes = list(UNTOUCHED) + [f"{FAIL_TO_PASS}::{name}"
                                   for name in BAN_CLASSES[1:]]
        res = subprocess.run([sys.executable, "-m", "pytest", *nodes, "-q",
                              "-p", "no:cacheprovider"], cwd=CODE_ROOT,
                             capture_output=True, text=True, timeout=110,
                          env=clean_env())
        self.assertEqual(res.returncode, 0, res.stdout[-4000:] + res.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
