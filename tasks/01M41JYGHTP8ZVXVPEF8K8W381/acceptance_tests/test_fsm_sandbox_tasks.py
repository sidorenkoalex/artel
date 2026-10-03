"""AC-6, AC-7 — 01M41JYGHTP8ZVXVPEF8K8W381: песочница `FsmTest` подменяет
`config.TASKS` временным каталогом; сторож в `tests/` это держит.

Группа: разовый

`tests/test_invariants.py` защищён: правка приезжает приложением PLAN.md и
в рабочем дереве ветки не видна. Поэтому исполняемые проверки идут во
временной копии дерева кода ветки (`_appendix.scratch_tree`) с наложенными
приложениями; «каталог задач корня запуска» там — `tasks/` КОПИИ, и
песочница, пишущая туда, видна, не трогая рабочую копию.

Сторож AC-7 — тестовый файл `tests/*.py`, добавленный или изменённый веткой
задачи (кроме самого защищённого `tests/test_invariants.py`, который ветка
не правит), с упоминанием `FsmTest`. «Возврат `self.tdir` в настоящий
`config.TASKS`» разыгрывается копией, где приложение к
`tests/test_invariants.py` НЕ наложено: это ровно сегодняшняя песочница,
кладущая `self.tdir` в каталог задач корня запуска.

Красен до реализации: PLAN.md с приложением к tests/test_invariants.py ещё не написан и сторожа в tests/ нет (их пишет developer) — проба setUp видит настоящий config.TASKS, сторож не находится.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _appendix as ap  # noqa: E402

PROBE_NAME = "test_zz_probe_01m41jyghtp8zvxvpef8k8w381.py"
PROBE = '''\
"""Проба планки 01M41JYGHTP8ZVXVPEF8K8W381 — существует только в копии."""
import unittest
from pathlib import Path

from orchestrator import config
from tests import test_invariants as ti

REAL_TASKS = Path(config.TASKS).resolve()
REAL_ROOT = Path(config.ROOT).resolve()


class SetUpPatchesTasksProbe(ti.FsmTest):

    def test_probe(self):
        tasks = Path(config.TASKS).resolve()
        tdir = Path(self.tdir).resolve()
        self.assertNotEqual(REAL_TASKS, tasks,
                            "FsmTest.setUp не подменил config.TASKS")
        self.assertFalse(tasks.is_relative_to(REAL_ROOT),
                         f"config.TASKS={tasks} внутри корня {REAL_ROOT}")
        self.assertTrue(tdir.is_relative_to(tasks),
                        f"self.tdir={tdir} не под config.TASKS={tasks}")
        self.assertTrue(tdir.is_dir(), f"{tdir} не заведён")
'''


def _tasks_entries(root: Path) -> set:
    tasks = root / "tasks"
    return {p.name for p in tasks.iterdir()} if tasks.is_dir() else set()


class FsmSandboxTasksTest(unittest.TestCase):

    def setUp(self):
        self.state = ap.state()
        self.diag = self.state.diagnosis()

    def _require_invariants_appendix(self):
        self.assertTrue(ap.appendices_for(ap.INVARIANTS),
                        f"в PLAN.md нет приложения к {ap.INVARIANTS}; "
                        f"{self.diag}")
        self.assertEqual((), self.state.apply_failures, self.diag)

    def test_ac6_fsm_setup_patches_tasks_with_tdir_under_it(self):
        """В `FsmTest.setUp` после приложения `config.TASKS` — временный каталог, `self.tdir` под ним.

        Сценарий: в копию дерева с приложениями кладётся проба —
        наследник `FsmTest`, чей тест после `setUp` сверяет: `config.TASKS`
        отличается от значения до `setUp`, лежит вне корня запуска,
        `self.tdir` — заведённый каталог под ним. Проба проходит pytest.

        Ловит мутацию: `TASKS` добавлен в цикл подмены, но `self.tdir`
        по-прежнему строится от сохранённого заранее настоящего пути
        (`REPO_ROOT / "tasks"`) — проба видит `self.tdir` вне подменённого
        `config.TASKS` и краснеет; либо подмена `TASKS` забыта вовсе —
        `config.TASKS` равен настоящему.
        """
        self._require_invariants_appendix()
        with ap.scratch_tree() as (tmp, failures):
            self.assertEqual([], failures, self.diag)
            (tmp / "tests" / PROBE_NAME).write_text(PROBE, encoding="utf-8")
            res = ap.run_pytest(tmp, [f"tests/{PROBE_NAME}"])
        self.assertEqual(0, res.returncode,
                         (res.stdout + res.stderr)[-3000:])

    def test_ac6_test_assertions_unchanged(self):
        """Утверждения тестов `tests/test_invariants.py` после приложения те же, что в базе.

        Сценарий: в тексте файла базы и после приложения для каждой функции
        собираются утверждения (`assert`, `self.assert*`, `self.fail`) без
        номеров строк; наборы по функциям совпадают.

        Ловит мутацию: вместе с подменой `TASKS` поправлено ожидание
        теста, читавшего каталог задачи (например `assertIn(f"tasks/
        {self.TASK}/SPEC.md", ...)` переписан под новый путь) — набор
        утверждений функции разошёлся, тест краснеет.
        """
        self._require_invariants_appendix()
        base = ap.base_text(ap.INVARIANTS)
        self.assertTrue(base, self.diag)

        def nonempty(source):
            return {k: v for k, v in ap.assertion_map(source).items() if v}

        before = nonempty(base)
        after = nonempty(ap.applied_text(ap.INVARIANTS))
        changed = sorted(k for k in before.keys() | after.keys()
                         if before.get(k) != after.get(k))
        self.assertEqual([], changed,
                         "утверждения этих функций изменились приложением")

    def test_ac6_invariants_pass_with_appendix(self):
        """`tests/test_invariants.py` с приложением проходит в копии дерева кода ветки.

        Сценарий: копия дерева с наложенными приложениями, pytest
        `tests/test_invariants.py -n auto` — код возврата 0.

        Ловит мутацию: подменён только `config.TASKS`, а бриф developer
        по-прежнему читает SPEC.md через `config.ROOT / "tasks/<id>"`
        (комментарий в `FsmTest.setUp` о том, почему `TASKS` не
        подменялся) — тесты брифа не находят SPEC и краснеют.
        """
        self._require_invariants_appendix()
        code, out, fails = ap.invariants_run_applied()
        self.assertEqual((), fails, self.diag)
        self.assertEqual(0, code, out)

    def test_ac7_guard_green_with_fix_and_red_with_real_tasks(self):
        """Сторож в `tests/` зелёный с приложением и красный при `self.tdir` в настоящем каталоге задач.

        Сценарий: сторож — файлы `tests/*.py` ветки с упоминанием
        `FsmTest`, хотя бы один тестовый метод которых несёт в докстринге
        «Ловит мутацию». В копии с приложениями сторож проходит, и каталог
        задач копии после прогона не получил новых записей; в копии без
        приложения к `tests/test_invariants.py` (песочница кладёт
        `self.tdir` в `config.TASKS` корня запуска) сторож падает
        проваленным тестом (код pytest 1).

        Ловит мутацию: сторож проверяет лишь отсутствие каталога ПОСЛЕ
        `doCleanups` — сегодняшний `addCleanup` убирает каталог, и в копии
        без приложения сторож остаётся зелёным; тест краснеет на
        утверждении «без приложения — красный».
        """
        guards = [p for p in ap.branch_changed_tests()
                  if "FsmTest" in (ap.REPO_ROOT / p).read_text(
                      encoding="utf-8")]
        self.assertTrue(guards, "в tests/ ветки нет сторожа, упоминающего "
                                "FsmTest")
        claims = []
        for rel in guards:
            tree = ap.ast.parse((ap.REPO_ROOT / rel).read_text(
                encoding="utf-8"))
            for node in ap.ast.walk(tree):
                if (isinstance(node, (ap.ast.FunctionDef,
                                      ap.ast.AsyncFunctionDef))
                        and node.name.startswith("test")
                        and "Ловит мутацию" in (ap.ast.get_docstring(node)
                                                or "")):
                    claims.append(f"{rel}::{node.name}")
        self.assertTrue(claims, f"у тестов сторожа {guards} нет заявки "
                                f"«Ловит мутацию»")

        self._require_invariants_appendix()
        with ap.scratch_tree() as (tmp, failures):
            self.assertEqual([], failures, self.diag)
            before = _tasks_entries(tmp)
            green = ap.run_pytest(tmp, guards)
            left = _tasks_entries(tmp) - before
        self.assertEqual(0, green.returncode,
                         (green.stdout + green.stderr)[-3000:])
        self.assertEqual(set(), left, "сторож с приложением оставил каталог "
                                      "в каталоге задач корня запуска")

        with ap.scratch_tree(skip=(ap.INVARIANTS,)) as (tmp, failures):
            self.assertEqual([], failures, self.diag)
            red = ap.run_pytest(tmp, guards)
        self.assertEqual(1, red.returncode,
                         "сторож не краснеет, когда self.tdir лежит в "
                         "настоящем config.TASKS:\n"
                         + (red.stdout + red.stderr)[-3000:])


if __name__ == "__main__":
    unittest.main()
