"""У артели (`runner: pult-pytest`) места запуска не изменились: фиксация
части 1 и тест `acceptance_suite` при пустой БД зелёные и не правлены;
ключ итога полного набора артели — прежний байт в байт.

Группа: разовый

Факт этой задачи: «файл не правлен задачей» и «ключ равен ключу кода до
задачи» после мержа проверять не на чем — свойство мест запуска артели
дальше держит сама фиксация части 1
(`tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py`).

Дифф задачи и база — помощником пульта `_pult.py` (`changed_paths`,
`DIFF_BASE`, `CODE_ROOT`); прогон фиксаций — тем же интерпретатором, что
гоняет планку, в рабочей копии кода (`CODE_ROOT`).

Зелёный с рождения: код до задачи и есть прежнее поведение артели — фиксация части 1 и тест acceptance_suite зелёные, ключ итога равен своей формуле; файл краснеет, если задача сломает или поправит их.
"""
import ast
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE, changed_paths  # noqa: E402

FIXATION = "tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py"
SUITE_TEST_FILE = "tests/test_acceptance.py"
SUITE_TEST_CLASS = "AcceptanceSuiteTreeFailureTest"
SUITE_TEST_NODE = f"{SUITE_TEST_FILE}::{SUITE_TEST_CLASS}"


def _class_source(text: str, name: str) -> str | None:
    """Исходный текст класса `name` модуля `text`; `None` — класса нет."""
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return ast.get_source_segment(text, node)
    return None


class ArtelPlacesUnchangedTest(unittest.TestCase):
    """Фиксации поведения артели целы и зелёные."""

    def test_ac1_fixations_not_edited(self):
        """Фиксация части 1 и тест `acceptance_suite` при пустой БД не правлены задачей.

        Файл фиксации части 1 не входит в пути задачи (`changed_paths`);
        класс `AcceptanceSuiteTreeFailureTest` в `tests/test_acceptance.py`
        в голове ветки байт в байт тот же, что в базе диффа.

        Ловит мутацию: разработчик подогнал ожидание
        `local.assert_called_once_with(Path("/tmp"), "T001")` под новую форму
        вызова `full_suite` с профилем либо поправил литералы argv/окружения
        фиксации части 1 — путь фиксации появится в `changed_paths`, текст
        класса разойдётся с базой.
        """
        changed = changed_paths()
        self.assertNotIn(FIXATION, changed,
                         f"фиксация части 1 правлена задачей: {changed}")
        self.assertIsNotNone(DIFF_BASE, "база диффа задачи не вычислена")
        base = subprocess.run(
            ["git", "-C", CODE_ROOT, "show", f"{DIFF_BASE}:{SUITE_TEST_FILE}"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(base.returncode, 0, base.stderr)
        head = (Path(CODE_ROOT) / SUITE_TEST_FILE).read_text(encoding="utf-8")
        expected = _class_source(base.stdout, SUITE_TEST_CLASS)
        self.assertIsNotNone(expected, f"{SUITE_TEST_CLASS} нет в базе")
        self.assertEqual(_class_source(head, SUITE_TEST_CLASS), expected,
                         f"{SUITE_TEST_NODE} правлен задачей")

    def test_ac1_fixations_green(self):
        """Фиксация части 1 (оба пути команды) и тест `acceptance_suite` зелёные на коде ветки.

        Один прогон pytest в рабочей копии кода: весь файл фиксации части
        1 (argv, `cwd`, окружение восьми мест запуска на `command=None` и
        на `[python3, -m, pytest]`) и класс `AcceptanceSuiteTreeFailureTest`
        (при пустой БД `acceptance_suite` зовёт `full_suite(Path("/tmp"),
        "T001")`). Код возврата 0, в выводе нет `failed`/`error`.

        Ловит мутацию: ветка `pytest-own` протекла в путь артели (свой
        сеанс, чистое окружение, `cwd` = `workdir`) или `acceptance_suite`
        передаёт `full_suite` профиль и у артели — фиксация или тест
        `acceptance_suite` краснеют, код возврата ненулевой.
        """
        res = subprocess.run(
            [sys.executable, "-m", "pytest", FIXATION, SUITE_TEST_NODE,
             "-p", "no:cacheprovider", "-q"],
            cwd=CODE_ROOT, capture_output=True, text=True, timeout=110)
        output = res.stdout + res.stderr
        self.assertEqual(res.returncode, 0, output[-4000:])
        self.assertIn("passed", output, output[-4000:])


class ArtelSuiteKeyUnchangedTest(unittest.TestCase):
    """Ключ итога полного набора артели — прежняя формула байт в байт."""

    def test_ac8_pult_pytest_key_byte_identical(self):
        """Ключ gate- и base-итога артели совпадает с формулой кода до задачи.

        Формула до задачи: sha256 от JSON (ключи по алфавиту) с деревом,
        `sys.version`, установленными пакетами и argv команды пульта —
        для gate `<python> -m pytest tests <флаги пульта> -n <рабочие> -p
        xdist`, для base — без `tests` и без флагов параллели. Сверяется
        `suite_result_key(tree)` и `suite_result_key(tree, [python3, -m,
        pytest])` на нескольких деревьях, gate и base.

        Ловит мутацию: в ключ артели добавлены поля `runner`/`workdir`/`env`
        (пусть и пустые) — sha256 разойдётся с формулой, сохранённые итоги
        артели перестанут засчитываться.
        """
        sys.path.insert(0, CODE_ROOT)
        from orchestrator import acceptance, config, stack
        py = stack.pytest_python_executable()
        flags = ["-p", "no:cacheprovider", "-p", "timeout",
                 "-o", f"timeout={stack.PER_TEST_TIMEOUT_SEC}"]
        packages = sorted((d.metadata["Name"].lower(), d.version)
                          for d in importlib.metadata.distributions())
        for n in range(3):
            tree = hashlib.sha1(f"дерево {n}".encode()).hexdigest()
            for base in (False, True):
                argv = ([py, "-m", "pytest", *flags] if base else
                        [py, "-m", "pytest", "tests", *flags,
                         "-n", str(config.FULL_SUITE_WORKERS), "-p", "xdist"])
                data = {"tree": tree, "python": sys.version,
                        "packages": packages, "command": argv}
                expected = hashlib.sha256(json.dumps(
                    data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                for command in (None, ["python3", "-m", "pytest"]):
                    with self.subTest(tree=tree, base=base, command=command):
                        self.assertEqual(acceptance.suite_result_key(
                            tree, command, base=base), expected)


if __name__ == "__main__":
    unittest.main()
