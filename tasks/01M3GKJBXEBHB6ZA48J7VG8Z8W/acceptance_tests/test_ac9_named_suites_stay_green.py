"""AC-9 — 01M3GKJBXEBHB6ZA48J7VG8Z8W: названные наборы `tests/` зелёные,
ни один тест не удалён, не переименован и не ослаблен.

Источник — SPEC.md, «Критерии приёмки»:

AC-9. Полный прогон `tests/` зелёный; `tests/test_answer.py`,
`tests/test_answer_gate.py`, `tests/test_answer_branch_reads.py`,
`tests/test_zones_gate.py`, `tests/test_test_integrity_gate.py` зелёные без
правки существующих ожиданий, ни один тест не удалён, не переименован и не
ослаблен.

Полный набор `tests/` здесь НЕ прогоняется (правило skills/test-authoring.md:
его гоняют CI и автогейт приёмки, а копия всего набора в планке — не
проверка, а второй CI) — прогоняются пять файлов, названных критерием
поимённо.

«Не удалён, не переименован, не ослаблен» проверяется тем, что проверяемо
механически: (а) каждый тестовый метод, существовавший в этих файлах ДО
правки задачи, существует в ветке под тем же именем; (б) число
выключателей теста (`@skip`/`@expectedFailure`/`self.skipTest(`) в них не
выросло. Переписанное ВНУТРИ метода ожидание планка не запрещает — это
предмет ревью по диффу, и именно его ревьювер сверяет с требованием «без
правки существующих ожиданий».

Базой сравнения взята голова ветки задачи на момент написания планки
(`BASE_SHA`), а не голова main: `tests/test_test_integrity_gate.py` в main
ещё не влит — он приехал мержем 01M3FQ2V, условием старта этой задачи
(«Контекст» SPEC), и в дереве main его нет вовсе. База читается `git show`
в репозитории рабочей копии — не с диска ветки: на диске лежит уже
правленая версия, сверять её с собой бессмысленно.

Зелёный с рождения: пять наборов проходят на сегодняшнем коде, ни один
метод ещё не удалён и ни один выключатель не добавлен — тест сохранения
существующего поведения. Он краснеет ровно тогда, когда правка задачи
ломает эти наборы (например новая проверка при записи отказывает мандату
существующих фикстур `answer`) или когда мешающий тест удалён,
переименован либо выключен вместо приведения кода к нему.
"""
import io
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

TESTS_DIR = _sandbox.REPO_ROOT / "tests"

#: Наборы, названные критерием поимённо.
NAMED_SUITES = ("test_answer.py", "test_answer_gate.py",
                "test_answer_branch_reads.py", "test_zones_gate.py",
                "test_test_integrity_gate.py")

#: Коммит, с которым сверяется состав тестов — голова ветки задачи до её
#: правки (main плюс мерж 01M3FQ2V, которым приехал
#: `tests/test_test_integrity_gate.py`).
BASE_SHA = "40d92262"

TEST_METHOD_RE = re.compile(r"^\s*def (test_\w+)", re.M)

#: Выключатели теста — те же формы, которые считает ослаблением сам гейт
#: неослабления тестов пульта.
DISABLERS = ("@unittest.skip", "@skip", "@unittest.expectedFailure",
             "@expectedFailure", "self.skipTest(")


def _git(*args) -> tuple:
    result = subprocess.run(["git", *args], cwd=_sandbox.REPO_ROOT,
                            capture_output=True, text=True)
    return result.returncode, result.stdout


def base_source(rel_path: str) -> str:
    code, text = _git("show", f"{BASE_SHA}:{rel_path}")
    if code != 0:
        raise AssertionError(f"{BASE_SHA}:{rel_path} не прочитан")
    return text


def method_names(source: str) -> set:
    return set(TEST_METHOD_RE.findall(source))


def disabler_count(source: str) -> int:
    return sum(source.count(token) for token in DISABLERS)


class NamedSuitesStayGreenTest(unittest.TestCase):

    def test_ac9_named_suites_pass_on_the_branch(self):
        """Пять названных критерием наборов `tests/` прогоняются целиком и
        проходят без единого провала.

        Ловит мутацию: разбор строки мандата перенесён в общий узел, но
        `orchestrator/answer.py` продолжает звать снятое имя
        (`fsm_advance._split_zone_paths`) — или новая проверка при записи
        отказывает мандату существующих фикстур `tests/test_answer.py`
        («Расширение зон разрешено: docs/a.md» для задачи, у которой кодовой
        ветки в песочнице нет вовсе): агрегированный результат перестанет
        быть успешным, и провалившийся метод будет назван в тексте.
        """
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        missing = []
        for name in NAMED_SUITES:
            if not (TESTS_DIR / name).is_file():
                missing.append(name)
                continue
            suite.addTests(loader.loadTestsFromName(f"tests.{Path(name).stem}"))

        self.assertEqual([], missing,
                         "файл(ы) названных наборов исчезли из ветки: "
                         + ", ".join(missing))

        result = unittest.TextTestRunner(stream=io.StringIO(),
                                         verbosity=0).run(suite)

        self.assertTrue(
            result.wasSuccessful(),
            "названные наборы не зелёные: провалы="
            + repr([str(case) for case, _ in result.failures])
            + "; ошибки=" + repr([str(case) for case, _ in result.errors]))

    def test_ac9_no_test_method_of_those_suites_disappeared(self):
        """Каждый тестовый метод, существовавший в этих файлах до правки
        задачи, существует в ветке под тем же именем.

        Ловит мутацию: тест, мешающий новому месту разбора или новой
        проверке при записи (например
        `ZonesMandateMarkerPathsTest.test_marker_line_paths_are_parsed`
        в `tests/test_answer.py`, зовущий функцию
        `answer._zones_mandate_marker_paths`), удалён или переименован
        вместо приведения кода к нему — `assertEqual` назовёт исчезнувшее
        имя.
        """
        gone = []
        for name in NAMED_SUITES:
            local = TESTS_DIR / name
            if not local.is_file():
                gone.append(f"{name}: файла нет")
                continue
            before = method_names(base_source(f"tests/{name}"))
            after = method_names(local.read_text(encoding="utf-8"))
            gone.extend(f"{name}::{method}" for method in sorted(before - after))

        self.assertEqual(
            [], gone,
            "тестовый метод(ы) базы сравнения исчезли из ветки — удаление или "
            "переименование теста это ослабление проверки (AC-9): "
            + ", ".join(gone))

    def test_ac9_no_disabler_was_added_to_those_suites(self):
        """Число выключателей теста (`@skip`, `@expectedFailure`,
        `self.skipTest(`) ни в одном из пяти наборов не выросло против базы
        сравнения.

        Ловит мутацию: мешающий тест формально оставлен на месте (имя не
        исчезло, предыдущий метод его не поймает), но выключен декоратором
        или `self.skipTest` — набор снова зелёный, а проверка не делается.
        """
        grown = []
        for name in NAMED_SUITES:
            local = TESTS_DIR / name
            if not local.is_file():
                continue
            before = disabler_count(base_source(f"tests/{name}"))
            after = disabler_count(local.read_text(encoding="utf-8"))
            if after > before:
                grown.append(f"{name}: было {before}, стало {after}")

        self.assertEqual([], grown,
                         "в названных наборах появились выключатели тестов: "
                         + ", ".join(grown))


if __name__ == "__main__":
    unittest.main()
