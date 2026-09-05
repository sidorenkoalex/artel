"""Красен до реализации: `orchestrator/acceptance.py::materialize_from_branch`
кладёт планку во `tempfile.mkdtemp()`, а `acceptance.run` всегда запускает
прогон с `cwd=config.ROOT` (SPEC «Контекст») — планка, резолвящая
`orchestrator/` от `__file__` (`Path(__file__).resolve().parents[3]`),
промахивается мимо кодовой ветки задачи что через `__file__` (глубина
вложенности временного каталога не совпадает со штатным `tasks/<id>/
acceptance_tests/`), что через `cwd` (главная копия пульта, не worktree).
До правки задачи все тесты этого файла краснеют; после правки (AC-1:
материализация в рабочий каталог кода задачи вместо tempfile, AC-2: `cwd`
прогона равен тому же каталогу) — зеленеют.

Все четыре теста используют один и тот же узел `fsm._pull_main_or_
escalate` — единственную сегодня точку, где приёмочная планка
самостоятельно прогоняется на сверке свежести (SPEC «Требования» п.1,
AC-4: та же материализация и тот же прогон, что и остальные точки).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (MARKER_TEST_VIA_CWD, MARKER_TEST_VIA_FILE,  # noqa: E402
                      MarkerPullSandbox)
from orchestrator import store  # noqa: E402


class Ac1MaterializationLocationTest(MarkerPullSandbox):

    def test_ac1_materialization_lands_in_task_working_dir_not_tempdir(self):
        """Планка «через __file__» одна, без cwd-запасного пути: зелёная,
        только если материализация (AC-1) положила её по штатному пути
        `tasks/<id>/acceptance_tests/` РАБОЧЕГО КАТАЛОГА КОДА ЗАДАЧИ
        (worktree self-target), а не во временный каталог — и файл
        остаётся там же ПОСЛЕ вызова (не удалён вместе с tempdir).

        Ловит мутацию: материализация продолжает писать в `tempfile.
        mkdtemp()` либо кладёт файлы не по вложенности `tasks/<id>/
        acceptance_tests/` (например, плоско, без каталога `tasks/<id>/`
        между worktree и `acceptance_tests/`) — `Path(__file__).resolve().
        parents[3]` промахивается мимо каталога с `orchestrator/marker.py`
        кодовой ветки, `ModuleNotFoundError` красит тест, переход
        эскалирует вместо `"pulled"`.
        """
        self.commit_marker_plank({"test_via_file.py": MARKER_TEST_VIA_FILE})

        outcome = self.pull()

        self.assertEqual(
            outcome, "pulled",
            f"журнал: {self.journal_details()}")
        materialized = self.materialized_acceptance_dir() / "test_via_file.py"
        self.assertTrue(
            materialized.is_file(),
            f"планка обязана остаться материализованной по штатному пути "
            f"рабочего каталога кода задачи: {materialized}")


class Ac2RunCwdTest(MarkerPullSandbox):

    def test_ac2_run_cwd_equals_working_dir_not_pult_root(self):
        """Планка «только через cwd», БЕЗ `sys.path.insert` от `__file__`:
        зелёная, только если ПРОГОН (AC-2) идёт с `cwd`, равным рабочему
        каталогу кода задачи, а не `config.ROOT` (главная копия пульта,
        стоящая на main, где `orchestrator/marker.py` нет вовсе).

        Ловит мутацию: `acceptance.run` продолжает запускать `python3 -m
        unittest discover` с `cwd=config.ROOT`, даже если материализация
        (AC-1) уже кладёт планку в верный каталог — неявная вставка cwd в
        `sys.path`, которую делает `python3 -m unittest`, резолвит
        `orchestrator` от главной копии пульта (main), не от ветки задачи;
        `from orchestrator import marker` падает `ModuleNotFoundError` уже
        при импорте планки, переход эскалирует вместо `"pulled"`.
        """
        self.commit_marker_plank({"test_via_cwd.py": MARKER_TEST_VIA_CWD})

        outcome = self.pull()

        self.assertEqual(
            outcome, "pulled",
            f"журнал: {self.journal_details()}")


class Ac3FileAndCwdAgreeTest(MarkerPullSandbox):

    def test_ac3_file_based_and_cwd_based_resolution_agree_on_branch_code(self):
        """Обе планки — «через __file__» и «только через cwd» — в ОДНОМ
        прогоне: обязаны сойтись на ОДНОМ И ТОМ ЖЕ коде (AC-3 — «оба
        указывают на один и тот же код»), не на разных каталогах.

        Ловит мутацию: материализация (AC-1) и вычисление `cwd` для
        прогона (AC-2) расходятся на разные базовые каталоги (например,
        планка материализуется в worktree, а `cwd` вычисляется от другого
        пути) — один из двух файлов планки резолвит другой код и падает,
        даже если каждый способ резолвинга по отдельности мог бы
        сработать сам по себе.
        """
        self.commit_marker_plank({
            "test_via_file.py": MARKER_TEST_VIA_FILE,
            "test_via_cwd.py": MARKER_TEST_VIA_CWD,
        })

        outcome = self.pull()

        self.assertEqual(
            outcome, "pulled",
            f"журнал: {self.journal_details()}")


class Ac4MergeGateWindowSharesFixTest(MarkerPullSandbox):

    def test_ac4_merge_gate_window_pull_shares_the_same_fix(self):
        """Тот же узел `_pull_main_or_escalate`, вызванный с
        `state="merge_gate"` — именно так его зовёт `orchestrator/
        fsm_merge_gate.py::_cmd_approve_merge_gate` изнутри окна гейта
        (AC-4 — общий вход материализации и прогона, без дублей логики
        по точкам).

        Ловит мутацию: правка применена только к вызову из `approve
        acceptance` (например, отдельной веткой кода внутри одного из
        вызывающих мест, в обход общего узла), а сам `_pull_main_or_
        escalate` для `state="merge_gate"` продолжает читать планку
        по-старому — второй вызов с тем же кодом ветки красит переход
        вместо `"pulled"`.
        """
        self.commit_marker_plank({
            "test_via_file.py": MARKER_TEST_VIA_FILE,
            "test_via_cwd.py": MARKER_TEST_VIA_CWD,
        })
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?",
                     ("merge_gate", self.TASK))
        conn.commit()

        outcome = self.pull(state="merge_gate")

        self.assertEqual(
            outcome, "pulled",
            f"журнал: {self.journal_details()}")


if __name__ == "__main__":
    unittest.main()
