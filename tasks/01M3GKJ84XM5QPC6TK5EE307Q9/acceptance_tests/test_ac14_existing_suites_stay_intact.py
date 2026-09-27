"""AC-14 — 01M3GKJ84XM5QPC6TK5EE307Q9: перечисленные существующие
тестовые файлы на месте, их методы не удалены, не переименованы и не
пропущены; полный прогон `tests/` — за CI и автогейтом.

Источник — SPEC.md, «Критерии приёмки»:

AC-14. Полный прогон `tests/` зелёный; перечисленные в требовании 11
существующие тестовые файлы на месте, их тестовые методы не удалены, не
переименованы и не пропущены.

Критерий распадается на две половины с разной проверяемостью.

Вторая половина — структурная и проверяется здесь механически: состав
тестовых методов семи файлов, названных требованием 11, сверяется с их
составом в ТОЧКЕ РАСХОЖДЕНИЯ ветки с `main` (не с сегодняшним диском:
набор, из которого файл убрали веткой, иначе сузился бы сам собой), а
каждый уцелевший метод сверяется на отсутствие `unittest.skip*`/
`self.skipTest(`. Дописанные ветками методы планка не запрещает — она
сверяет ВКЛЮЧЕНИЕ, не равенство.

Первая половина — полный прогон `tests/` — помечена `ci` ниже:
skills/test-authoring.md прямо запрещает автору планки гонять полный
набор в своём шаге, а раннер планки режет каждый тест таймаутом
(`orchestrator/acceptance.py::_pytest_command`), заведомо меньшим
времени полного набора. Пометка `ci` автогейт приёмки НЕ выключает (в
отличие от manual/skip): доказательство — зелёный CI кодовой ветки и
`acceptance.run_full_suite` того же автогейта.

Зелёный с рождения: ни один метод перечисленных файлов пока не тронут —
тест сохранения существующего поведения. Он краснеет тогда, когда
правка требований 1-9 удалит, переименует или заглушит чужой тест
вместо того, чтобы привести его к новому поведению.
"""

# AC-14: ci — полный прогон существующих tests/ гоняют CI кодовой ветки
# и автогейт приёмки (`acceptance.run_full_suite`); внутри планки его
# прогона быть не может — раннер планки режет каждый тест таймаутом
# меньшим, чем длится полный набор, и skills/test-authoring.md запрещает
# автору планки такой прогон прямо. Структурная половина критерия
# (файлы на месте, методы не удалены/не переименованы/не пропущены)
# проверена тестами этого файла.
import ast
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, gitcmd  # noqa: E402

#: Файлы, названные требованием 11 SPEC поимённо.
NAMED_SUITES = (
    "tests/test_pull.py",
    "tests/test_fsm_map_conflict_autoresolve.py",
    "tests/test_fsm_merge_conflict_note.py",
    "tests/test_zone_lock.py",
    "tests/test_zones_gate.py",
    "tests/test_catalog_new_race.py",
    "tests/test_catalog_tz_path_check.py",
)

_SKIP_DECORATORS = ("skip", "skipIf", "skipUnless", "expectedFailure")


def merge_base() -> str:
    """sha точки расхождения ветки задачи с базой интеграции:
    `origin/main`, а при его отсутствии — локальная `main`."""
    for ref in ("origin/main", config.MAIN_BRANCH):
        res = subprocess.run(["git", "merge-base", ref, "HEAD"],
                             cwd=config.ROOT, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    raise AssertionError("точка расхождения ветки с main не вычислена — "
                         "сверять состав тестов не с чем")


def method_names(source: str) -> set:
    """{`Класс.метод`} тестовых методов модуля."""
    names = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and item.name.startswith("test"):
                names.add(f"{node.name}.{item.name}")
    return names


def _decorator_names(node) -> list:
    names = []
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        names.append(target.attr if isinstance(target, ast.Attribute)
                     else getattr(target, "id", ""))
    return names


def skipped_methods(source: str) -> set:
    """{`Класс.метод`} тестовых методов, выключенных декоратором
    `unittest.skip*`/`expectedFailure` (на методе или на его классе)
    либо вызовом `self.skipTest(...)` в теле."""
    skipped = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ClassDef):
            continue
        class_skipped = any(name in _SKIP_DECORATORS
                            for name in _decorator_names(node))
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not item.name.startswith("test"):
                continue
            body_skips = any(
                isinstance(call.func, ast.Attribute)
                and call.func.attr == "skipTest"
                for call in ast.walk(item) if isinstance(call, ast.Call))
            if class_skipped or body_skips or any(
                    name in _SKIP_DECORATORS for name in _decorator_names(item)):
                skipped.add(f"{node.name}.{item.name}")
    return skipped


class NamedSuitesStayIntactTest(unittest.TestCase):

    def setUp(self):
        self.base = merge_base()

    def baseline(self, rel: str) -> str:
        text, reason = gitcmd.show(self.base, rel)
        self.assertIsNotNone(
            text, f"{self.base}:{rel} не прочитан: {reason} — файл обязан "
                  f"существовать в точке расхождения")
        return text

    def test_ac14_named_suites_keep_every_test_method(self):
        """Каждый файл требования 11 существует в ветке, и каждый его
        тестовый метод из точки расхождения существует под тем же
        именем.

        Ловит мутацию: тест, мешающий новому авторазрешению подтяжки
        (например `tests/test_fsm_map_conflict_autoresolve.py::
        test_map_plus_other_file_conflict_still_escalates`, который
        сегодня ждёт эскалации на наборе «карта + другой файл»), удалён
        или переименован вместо того, чтобы быть приведённым к новому —
        ужесточённому — поведению; исчезнувшее имя будет названо.
        """
        gone = []
        for rel in NAMED_SUITES:
            local = config.ROOT / rel
            if not local.is_file():
                gone.append(f"{rel}: файла нет в ветке")
                continue
            before = method_names(self.baseline(rel))
            after = method_names(local.read_text(encoding="utf-8"))
            gone.extend(f"{rel}::{name}" for name in sorted(before - after))

        self.assertEqual(
            [], gone,
            "тестовые методы точки расхождения исчезли из ветки — "
            "удаление или переименование теста это ослабление проверки "
            "(AC-14): " + ", ".join(gone))

    def test_ac14_no_named_suite_method_is_skipped(self):
        """Ни один тестовый метод этих семи файлов не выключен
        `unittest.skip*`/`expectedFailure`/`self.skipTest(...)`.

        Ловит мутацию: тест, покрасневший от новой механики, заглушен
        `@unittest.skip("чиним позже")` — формально набор остаётся
        зелёным, а проверка исчезает; имя заглушённого метода будет
        названо.
        """
        muted = []
        for rel in NAMED_SUITES:
            local = config.ROOT / rel
            if not local.is_file():
                muted.append(f"{rel}: файла нет в ветке")
                continue
            muted.extend(f"{rel}::{name}" for name in
                         sorted(skipped_methods(local.read_text(encoding="utf-8"))))

        self.assertEqual(
            [], muted,
            "тестовые методы выключены пропуском вместо приведения к "
            "новому поведению (AC-14): " + ", ".join(muted))


if __name__ == "__main__":
    unittest.main()
