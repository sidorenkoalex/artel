"""Приёмочные тесты регрессии №16 (SPEC 01M283NJV2PNDSS7J2HKS19YHJ):
`_acceptance_run_refuses` для собственного target обязан материализовать
планку `tasks/<id>/acceptance_tests/` из артефактной ветки в worktree
ДО прогона, независимо от исхода подтяжки (`Fresh`/`Pulled`) — на пути
`Fresh` до этой задачи ничего не материализовалось, и залоченная планка
молча не гонялась (`acceptance.run` отвечал вырожденным зелёным «не
заведены» на пустой каталог worktree).

Красен до реализации: `_acceptance_run_refuses` (orchestrator/fsm_advance.py,
self-target ветка) сегодня НЕ зовёт `acceptance.materialize_from_branch`
и не отличает «планки легитимно нет» от «планка не найдена в
источнике при локе/AC-разметке» — AC-1/AC-2/AC-5 красные на
неисправленном коде: `test_ac1_...`/`test_ac5_...` падают на пустом
`acceptance_tests/` worktree (материализации нет), `test_ac2_...`
падает, потому что вместо именованного отказа переход сегодня молча
проходит (нет отдельной ветки «не найдено в источнике»). `test_ac3_...`
(AC-3, `skip_tests`) и `test_ac4_...` (AC-4, повторный прогон на
`Pulled`) зелёные уже сегодня — см. маркеры на каждом тесте.

Провалидировано временным стабом (`_acceptance_run_refuses`,
дописанным по требованиям 1-3 SPEC прямо в `orchestrator/fsm_advance.py`
на время прогона, не закоммичен) — все пять тестов этого файла
позеленели; стаб отброшен `git checkout --`.
"""
import unittest
from unittest import mock

from orchestrator import acceptance, artifact_branch, fsm, gitcmd, store, workspace
from tests.sandbox import LightTransitionSandbox

_SPEC_WITH_AC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: регрессия №16 — планка

## Критерии приёмки

AC-1. ...
"""

_SPEC_SKIP_TESTS = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
skip_tests: стенд ещё не готов
---

# SPEC: регрессия №16 — планка (без тестов)

## Контекст

Тесты осознанно пропущены.
"""

_STUB_TEST = """import unittest


class StubTest(unittest.TestCase):

    def test_stub(self):
        pass
"""

_LOCKED_SHA = "f" * 40


class FreshPlankMaterializationTest(LightTransitionSandbox):
    """Общая подготовка: задача в `in_dev`, worktree "на своей ветке"
    (`workspace.on_task_branch` замокан `True` — тем же приёмом, что
    `tests/test_fsm_autogate.py::_AutogateConditionsUnitTest.call`), путь
    self-target (`config.DEFAULT_TARGET`, задача заведена без `target=`
    в `LightTransitionSandbox`)."""

    def write_source_plank(self) -> None:
        """Планка в АРТЕФАКТНОЙ ветке (симулируется диском `self.tdir` —
        `disk_backed_show`/`disk_backed_ls_tree_files` читают именно его,
        см. докстринг `tests/sandbox.py::LightTransitionSandbox`)."""
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            _SPEC_WITH_AC.format(task=self.TASK), encoding="utf-8")
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_stub.py").write_text(_STUB_TEST, encoding="utf-8")

    def write_source_spec_without_plank(self, skip_tests: bool) -> None:
        """Артефактная ветка несёт SPEC.md, но НЕ несёт
        `acceptance_tests/` — источник материализации пуст по плану
        теста (AC-2/AC-3: легитимность отсутствия зависит только от
        `skip_tests`/AC-разметки, не от произвольной пустоты)."""
        self.tdir.mkdir(parents=True, exist_ok=True)
        template = _SPEC_SKIP_TESTS if skip_tests else _SPEC_WITH_AC
        (self.tdir / "SPEC.md").write_text(
            template.format(task=self.TASK), encoding="utf-8")

    def worktree_plank_dir(self):
        return self.wt_path / "tasks" / self.TASK / "acceptance_tests"

    def advance_fresh_with_locked_plank(self):
        self.write_plan_ready()
        self.set_state("in_dev")
        conn = store.db()
        store.update_task(conn, self.TASK, tests_locked_sha=_LOCKED_SHA)
        for p in (mock.patch.object(workspace, "on_task_branch",
                                    return_value=True),
                 mock.patch.object(workspace, "path",
                                   return_value=self.wt_path),
                 mock.patch.object(gitcmd, "commits_behind", return_value=0)):
            p.start()
            self.addCleanup(p.stop)
        return self.capture(fsm.cmd_advance, self.TASK)

    def journal_details(self) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    # ------------------------------------------------------------- AC-1

    def test_ac1_self_target_materializes_before_run_on_fresh_branch(self):
        """Для собственного target и исхода `Fresh` `_acceptance_run_
        refuses` вызывает `acceptance.materialize_from_branch(task_id,
        branch, <worktree>)` РАНЬШЕ `acceptance.run` — оба узла
        отслеживаются общим списком порядка вызовов.

        Ловит мутацию: `_acceptance_run_refuses` продолжает брать
        `acc_tdir = <worktree>/tasks/<id>` напрямую, без вызова
        `acceptance.materialize_from_branch` — `calls` останется без
        записи `"materialize"`, и `assertIn`/`assertLess` ниже упадут.
        """
        self.write_source_plank()
        calls: list[str] = []
        real_materialize = acceptance.materialize_from_branch

        def spying_materialize(task_id, branch, code_dir):
            calls.append("materialize")
            self.assertEqual(task_id, self.TASK)
            self.assertEqual(branch, artifact_branch.branch_name(self.TASK),
                             "материализация обязана читать АРТЕФАКТНУЮ "
                             "ветку (artifact_source.resolve), не кодовую "
                             "ветку задачи")
            self.assertEqual(code_dir, self.wt_path,
                             "материализация обязана целиться в worktree "
                             "задачи (AC-1), не во временный/иной каталог")
            return real_materialize(task_id, branch, code_dir)

        def spying_run(tdir, cwd=None):
            calls.append("run")
            return True, "ok"

        with mock.patch.object(acceptance, "materialize_from_branch",
                               side_effect=spying_materialize), \
             mock.patch.object(acceptance, "run", side_effect=spying_run):
            self.advance_fresh_with_locked_plank()

        self.assertIn("materialize", calls,
                      "AC-1: acceptance.materialize_from_branch обязан "
                      "быть вызван для собственного target")
        self.assertIn("run", calls)
        self.assertLess(calls.index("materialize"), calls.index("run"),
                        "AC-1: материализация обязана идти ДО прогона")

    # ------------------------------------------------------------- AC-2

    def test_ac2_plank_missing_in_source_at_lock_refuses_named(self):
        """`tests_locked_sha` задан, но артефактная ветка НЕ несёт
        `tasks/<id>/acceptance_tests/` (SPEC.md с AC-разметкой без
        `skip_tests` — легитимной причины отсутствия нет) — переход
        `in_dev -> verifying` отклоняется именованным отказом «планка не
        найдена в источнике», не зелёным «acceptance_tests/ нет —
        приёмочные тесты не заведены».

        Ловит мутацию: отсутствие проверки легитимности пустого
        источника (планка молча трактуется как «не заведена») — переход
        пройдёт в `verifying`, и `assertEqual(self.state(), "in_dev")`
        ниже упадёт; либо отказ есть, но с текстом «не заведены» вместо
        «не найдена в источнике» — `assertIn` на точную фразу упадёт.
        """
        self.write_source_spec_without_plank(skip_tests=False)

        with mock.patch.object(
                acceptance, "run",
                return_value=(True, "acceptance_tests/ нет — приёмочные "
                             "тесты не заведены")) as acc_run:
            out = self.advance_fresh_with_locked_plank()

        self.assertEqual(self.state(), "in_dev",
                         "AC-2: переход обязан быть отклонён — планка "
                         "не найдена в источнике при локе")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("планка не найдена в источнике", combined,
                     "AC-2: отказ обязан быть именно этим именованным "
                     "текстом, не вырожденным «не заведены»")
        acc_run.assert_not_called()

    # ------------------------------------------------------------- AC-3

    def test_ac3_skip_tests_lets_missing_plank_pass(self):
        """SPEC артефактной ветки несёт `skip_tests` — отсутствие
        `acceptance_tests/` в источнике легитимно, переход `in_dev ->
        verifying` проходит несмотря на локальный `tests_locked_sha`
        (лок мог остаться от прежней версии SPEC до простановки
        `skip_tests`).

        Зелёный с рождения: до этой задачи `_acceptance_run_refuses`
        для собственного target берёт пустой `acc_tdir` без
        материализации и любого AC-разбора — `acceptance.run` уже
        сегодня отвечает вырожденным зелёным на пустой каталог, тем же
        исходом, что и правильная обработка `skip_tests` после
        исправления; тест защищает это НАМЕРЕННОЕ поведение от
        будущего сужения (например, отказа «не найдена в источнике»
        для ЛЮБОГО отсутствия планки без разбора `skip_tests`).

        Ловит мутацию: разбор легитимности отсутствия планки не
        учитывает `skip_tests` (например, требует отсутствия ЛЮБОЙ
        AC-разметки, игнорируя явный `skip_tests`) — переход отклонится
        отказом «не найдена в источнике», и `assertEqual(self.state(),
        "verifying")` ниже упадёт.
        """
        self.write_source_spec_without_plank(skip_tests=True)

        with mock.patch.object(acceptance, "run",
                               return_value=(True, "acceptance_tests/ нет")):
            self.advance_fresh_with_locked_plank()

        self.assertEqual(self.state(), "verifying",
                         "AC-3: skip_tests легитимизирует отсутствие "
                         "планки — переход обязан пройти")

    # ------------------------------------------------------------- AC-4

    def test_ac4_pulled_path_still_reruns_plank(self):
        """Путь `Pulled` (ветка отстаёт, подтяжка уже прогнала планку
        внутри `pull.evaluate`) — `_acceptance_run_refuses` всё равно
        гоняет её ещё раз своим отдельным рубежом; `acceptance.run`
        обязан быть позван ДВАЖДЫ за один `advance` (расклад уже
        закреплён `tests/test_branch_freshness_gate.py::
        test_advance_pulls_main_and_advances_when_acceptance_green` —
        этот тест дублирует свойство в зоне приёмочной планки этой
        задачи, не подменяет его).

        Зелёный с рождения: повторный прогон на `Pulled` уже реализован
        до этой задачи (`pull.evaluate` → `_materialize_and_run_plank`,
        затем `_acceptance_run_refuses` своим отдельным вызовом) —
        требование 3 SPEC прямо разрешает оставить это поведение как
        есть; тест защищает его от ослабления попутно с реализацией
        требований 1-2.

        Ловит мутацию: рубеж `_acceptance_run_refuses` начинает
        пропускать собственный прогон, когда исход подтяжки уже
        `Pulled` (например, ранний `return False` по флагу «уже
        прогнано подтяжкой») — `acc_run.call_count` упадёт до 1, и
        `assertEqual` ниже поймает это.
        """
        self.write_source_plank()
        self.write_plan_ready()
        self.set_state("in_dev")
        conn = store.db()
        store.update_task(conn, self.TASK, tests_locked_sha=_LOCKED_SHA)

        with mock.patch.object(workspace, "on_task_branch", return_value=True), \
             mock.patch.object(workspace, "path", return_value=self.wt_path), \
             mock.patch.object(gitcmd, "commits_behind", return_value=3), \
             mock.patch.object(acceptance, "run",
                               return_value=(True, "ok")) as acc_run:
            self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "verifying")
        self.assertEqual(acc_run.call_count, 2,
                         "AC-4: подтяжка (Pulled) не имеет права "
                         "отменить собственный повторный прогон "
                         "_acceptance_run_refuses")

    # ------------------------------------------------------------- AC-5

    def test_ac5_fresh_worktree_empty_plank_is_materialized_and_run(self):
        """Регрессия №16 воспроизведена дословно (SPEC, требование 4):
        задача с залоченной планкой (`tests_locked_sha`), worktree "на
        своей ветке" (`workspace.on_task_branch` -> `True`), `tasks/
        <id>/acceptance_tests/` В WORKTREE пуст (ничего не кладётся
        заранее — только источник, артефактная ветка, несёт планку),
        ветка не отстаёт от main (`commits_behind` -> 0, исход `Fresh`)
        — переход обязан материализовать планку в worktree и реально
        прогнать её (не вырожденное зелёное «не заведены»).

        Ловит мутацию: пропуск материализации в self-target ветке
        `_acceptance_run_refuses` (буквально требование 4 SPEC) —
        `acceptance_tests/` в worktree останется пустым/отсутствующим,
        `assertTrue(materialized_test.is_file())` ниже упадёт; если
        вдобавок прогон не звонится вовсе — переход тем не менее
        пройдёт вырожденным зелёным, и `assertEqual(self.state(),
        "verifying")` разойдётся с фактическим отказом только на
        честной материализации, маскируя дефект — поэтому именно
        существование файла на диске, не только состояние задачи,
        служит здесь решающей проверкой.
        """
        self.write_source_plank()
        self.assertFalse(
            self.worktree_plank_dir().exists(),
            "предпосылка сценария: worktree пуст ДО перехода — ничего "
            "не кладёт сама песочница")

        self.advance_fresh_with_locked_plank()

        materialized_test = self.worktree_plank_dir() / "test_stub.py"
        self.assertTrue(
            materialized_test.is_file(),
            "AC-5: планка обязана материализоваться в worktree из "
            "артефактной ветки — файл источника не появился на диске")
        self.assertEqual(
            materialized_test.read_text(encoding="utf-8"), _STUB_TEST,
            "материализованный файл обязан быть содержимым источника, "
            "не устаревшей/чужой копией")
        self.assertEqual(self.state(), "verifying",
                         "AC-5: реально прогнанная зелёная планка "
                         "обязана пропустить переход")


if __name__ == "__main__":
    unittest.main()
