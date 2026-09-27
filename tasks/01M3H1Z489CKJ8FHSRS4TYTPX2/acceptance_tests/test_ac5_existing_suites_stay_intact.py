"""AC-5 (третья половина) — 01M3H1Z489CKJ8FHSRS4TYTPX2: три названных
критерием существующих набора остаются на месте, их тестовые методы не
удалены, не переименованы и не выключены пропуском.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. В `docs/stack.md` в разделе о заведении задач и прогнозе очереди
зон есть одно предложение о подзадачах деления; покрыты сценарии
AC-1--AC-3, а существующие `tests/test_catalog_spawn_subtask.py`,
`tests/test_catalog_zone_overlap.py` и `tests/test_zone_lock_forecast.py`
остаются зелёными без ослабления проверок.

«Без ослабления проверок» проверяется здесь структурно: состав тестовых
методов трёх названных файлов сверяется с их составом в ТОЧКЕ
РАСХОЖДЕНИЯ ветки с базой интеграции (не с сегодняшним диском: набор, из
которого файл убрали веткой, иначе сузился бы сам собой), а каждый
уцелевший метод — на отсутствие `unittest.skip*`/`expectedFailure`/
`self.skipTest(`. Дописанные этой задачей методы планка не запрещает —
сверяется ВКЛЮЧЕНИЕ, не равенство (требование 5 SPEC как раз велит
дописать проверки подзадач).

Сам прогон этих наборов — за CI кодовой ветки и автогейтом приёмки
(`acceptance.run_full_suite`), см. пометку ниже.

Зелёный с рождения: ни один метод трёх названных файлов пока не тронут —
это тест сохранения существующего поведения. Он краснеет тогда, когда
правка механики `spawn_subtask` удалит, переименует или заглушит чужой
тест вместо того, чтобы привести его к новому поведению.
"""

# AC-5: ci — полный прогон существующих tests/ гоняют CI кодовой ветки и
# автогейт приёмки (`acceptance.run_full_suite`): внутри планки его быть
# не может — раннер планки режет каждый тест таймаутом меньшим, чем
# длится полный набор, и skills/test-authoring.md запрещает автору планки
# такой прогон прямо. Остальные половины критерия закрыты тестами:
# структурная — этим файлом, документ и покрытие сценариев —
# test_ac5_docs_and_new_coverage.py.
import ast
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, gitcmd  # noqa: E402

#: Файлы, названные критерием AC-5 поимённо.
NAMED_SUITES = (
    "tests/test_catalog_spawn_subtask.py",
    "tests/test_catalog_zone_overlap.py",
    "tests/test_zone_lock_forecast.py",
)

_SKIP_DECORATORS = ("skip", "skipIf", "skipUnless", "expectedFailure")


def merge_base() -> str:
    """sha точки расхождения ветки задачи с базой интеграции:
    `origin/main`, а при его отсутствии — локальная `main`."""
    for ref in (f"origin/{config.MAIN_BRANCH}", config.MAIN_BRANCH):
        res = subprocess.run(["git", "merge-base", ref, "HEAD"],
                             cwd=config.ROOT, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    raise AssertionError("точка расхождения ветки с базой интеграции не "
                         "вычислена — сверять состав тестов не с чем")


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
    `unittest.skip*`/`expectedFailure` (на методе или на его классе) либо
    вызовом `self.skipTest(...)` в теле."""
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
                  f"существовать в точке расхождения ветки")
        return text

    def test_ac5_named_suites_keep_every_test_method(self):
        """Каждый из трёх файлов существует в ветке, и каждый его тестовый
        метод из точки расхождения существует под тем же именем.

        Ловит мутацию: юнит-тест, покрасневший от новой механики
        (например `tests/test_catalog_spawn_subtask.py::
        test_new_task_row_starts_in_spec_writing_like_cmd_new`, чей вывод
        теперь несёт ещё и предупреждение о пересечении), удалён или
        переименован вместо приведения к новому поведению — исчезнувшее
        имя будет названо.
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
            "тестовые методы точки расхождения исчезли из ветки — удаление "
            "или переименование теста это ослабление проверки (AC-5): "
            + ", ".join(gone))

    def test_ac5_no_named_suite_method_is_skipped(self):
        """Ни один тестовый метод трёх названных файлов не выключен
        `unittest.skip*`/`expectedFailure`/`self.skipTest(...)`.

        Ловит мутацию: тест, покрасневший от записи предварительных зон
        подзадачи, заглушен `@unittest.skip("чиним позже")` — набор
        формально остаётся зелёным, а проверка исчезает; имя заглушённого
        метода будет названо.
        """
        muted = []
        for rel in NAMED_SUITES:
            local = config.ROOT / rel
            if not local.is_file():
                muted.append(f"{rel}: файла нет в ветке")
                continue
            muted.extend(
                f"{rel}::{name}" for name in
                sorted(skipped_methods(local.read_text(encoding="utf-8"))))

        self.assertEqual(
            [], muted,
            "тестовые методы выключены пропуском вместо приведения к новому "
            "поведению (AC-5): " + ", ".join(muted))


if __name__ == "__main__":
    unittest.main()
