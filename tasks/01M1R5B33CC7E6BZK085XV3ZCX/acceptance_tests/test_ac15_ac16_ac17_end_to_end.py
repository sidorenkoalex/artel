"""Приёмочный тест AC-15/AC-16/AC-17 (tasks/01M1R5B33CC7E6BZK085XV3ZCX/
SPEC.md, «Критерии приёмки») — сквозной прогон, требование 6.

AC-15: на песочнице с ДВУМЯ настоящими git-репозиториями (пульт +
целевой с локальным bare-origin) задача внешнего target проходит
`new -> in_dev -> review -> merge_gate -> done`: diff ревью-пакета на
входе в `review` не пуст и построен из клона целевого; merge-коммит
появляется в origin ЦЕЛЕВОГО; ни одного нового коммита не появляется в
`main` пульта.

AC-16: на той же песочнице гейт ёмкости diff реально вычисляет размер
diff клона целевого на переходе `in_dev -> review` — не пропускает
переход безусловно. Проверяется ЧЕРЕЗ ПУБЛИЧНЫЙ `fsm.cmd_advance`
(не прямым вызовом `_capacity_gate_refuses`, как в AC-10) — так тест
ловит не только саму функцию гейта, но и её реальную проводку в
диспетчер `in_dev`.

AC-17: существующие тесты `tests/` остаются зелёными (проверяет CI
полным прогоном — `# AC-17: manual` ниже, скилу test_author запрещено
гонять полный набор `tests/` в шаге, см. skills/test-authoring.md);
новые тесты двух-репозиторной песочницы не пишут ни байта в настоящий
репозиторий пульта или дерево разработчика — эта половина проверяется
автоматически: `config.ROOT`/`config.PROJECTS` этой песочницы обязаны
указывать во временный каталог, а не в реальный чекаут.

# AC-17: manual — «существующие tests/ остаются зелёными» проверяет
# полный прогон `tests/` на CI; test_author не гоняет здесь полный
# набор (skills/test-authoring.md, решение Оператора 05.09) — вторая
# половина критерия (песочница не пишет в реальное дерево) покрыта
# тестом test_ac17_sandbox_never_touches_the_real_repository_tree.

`new` (заведение задачи) в цепочке AC-15 — вне зоны этой SPEC (`new
--target` в CLI — ТЗ-2/ТЗ-3, см. «Не входит»): здесь задача заводится
напрямую через `store.insert_task`, тем же приёмом, что и остальные
файлы этой планки. `spec_writing -> spec_gate -> tests_writing`
(до `in_dev`) и `verifying -> acceptance` (между `review` и
`merge_gate`) не несут ни одной точки реестра §4.3 этой SPEC — сама
AC-15 называет только `in_dev`, `review`, `merge_gate`, `done`,
опуская их тем же образом; здесь они пройдены напрямую через
`store.set_state`, а не сквозным прогоном автогейта/lease/CI-поллинга
(предмет ДРУГИХ SPEC, не этой).

Красен до реализации: сегодня `in_dev -> review` пропускает гейт
ёмкости внешнего target безусловно (AC-16 упало бы: оверсайз-diff не
отказал бы переходу), а `merge_gate -> done` смержил бы ветку внешнего
target в main ПУЛЬТА (если бы вообще не упал на несуществующей там
ветке) — обе поломки делают сборку утверждений ниже красной.
"""
import sys
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import (artifact_branch, ci, config, fsm,  # noqa: E402
                          fsm_merge_gate, gitcmd, review, store)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import (ExternalTargetGitSandbox, write_plan_ready,  # noqa: E402
                      write_review_approved)

TASK = "01AC15ENDTOENDFLOWTASK1"


def _lock_tests(task_id: str) -> None:
    """PLAN.md ready + `tests_locked_sha` на текущей голове артефактной
    ветки — предпосылки гейта `in_dev`, не относящиеся к предмету этой
    SPEC (лок acceptance_tests/, задача 01M1NKTF173WV5CPDZ1C3WW69K)."""
    write_plan_ready(task_id)
    locked_sha = gitcmd.branch_head_sha(
        artifact_branch.branch_name(task_id))
    store.update_task(store.db(), task_id, tests_locked_sha=locked_sha)


class EndToEndExternalTargetFlowTest(ExternalTargetGitSandbox):

    def setUp(self):
        super().setUp()
        self.branch = f"task/{TASK.lower()}-x"
        self.checkout_task_branch(self.branch)
        (self.target_workspace / "feature.py").write_text(
            "def feature():\n    return 42\n", encoding="utf-8")
        self.wgit("add", "-A")
        self.wgit("commit", "-q", "-m", f"{TASK}: код фичи")

        self.insert_external_task(TASK, self.branch, state="in_dev")
        _lock_tests(TASK)

        self.pult_main_before = self.pult_main_state()

    def test_ac15_full_flow_merges_into_the_target_origin_only(self):
        """`new -> in_dev -> review -> merge_gate -> done` внешнего
        target: diff на входе в review непустой и из клона целевого,
        merge-коммит появляется в origin целевого, main пульта не
        сдвигается ни на один коммит.

        Ловит мутацию: `merge_gate -> done` мержит в `config.ROOT`
        вместо `target_workspace` (или падает на несуществующей там
        ветке) — `assertIn` на сообщении коммита в истории origin
        целевого и `assertEqual` на состоянии main пульта до/после это
        поймают.
        """
        conn = store.db()

        diff_text, diff_lines, reason = review.git_diff_part(
            config.MAIN_BRANCH, self.branch, repo=self.target_workspace)
        self.assertEqual(reason, "")
        self.assertGreater(
            diff_lines, 0,
            "diff ревью-пакета внешнего target пуст на входе в review "
            "(AC-15) — сборка снимка либо не видит клон целевого, либо "
            "коммит фичи потерян")

        fsm.cmd_advance(TASK)
        # amend-tests 11.09: после ADR-0015 порядок in_dev -> verifying ->
        # review (планка написана до ADR-0015); ревью переводится тем же
        # CAS-приёмом, что и остальные переходы вне реестра точек ниже.
        self.assertEqual(
            store.get_task(conn, TASK)["state"], "verifying",
            "переход in_dev -> verifying не состоялся — гейт ёмкости либо "
            "ошибочно отказал небольшому diff'у, либо PLAN.md/лок не "
            "прошли")
        store.set_state(conn, TASK, "review", "fsm",
                        expected_state="verifying",
                        detail="test bypass: CI зелёный")

        write_review_approved(TASK)
        ref = self.origin_git("show-ref", "--verify", "--quiet",
                              f"refs/heads/{self.branch}")
        self.assertEqual(
            ref.returncode, 0,
            f"{self.branch} не опубликована в origin целевого на "
            f"входе approved-ревью (AC-6)")

        # verifying/acceptance — вне реестра точек §4.3 этой SPEC (не
        # названы в AC-15 явно): переводятся напрямую, тем же
        # CAS-приёмом, что и остальные переходы `store.set_state`.
        store.set_state(conn, TASK, "acceptance", "fsm",
                        expected_state="review",
                        detail="test bypass: CI зелёный")
        store.set_state(conn, TASK, "merge_gate", "fsm",
                        expected_state="acceptance",
                        detail="test bypass: приёмка пройдена")

        with mock.patch.object(
                ci, "branch_status", lambda branch: (True, "зелёный (тест)")):
            t = store.get_task(conn, TASK)
            result = fsm_merge_gate._cmd_approve_merge_gate(
                conn, TASK, "merge_gate", t,
                confirmed_ci_note="зелёный (тест)")

        self.assertEqual(result, ("done",))
        self.assertEqual(store.get_task(conn, TASK)["state"], "done")

        target_origin_main = self.origin_git(
            "rev-parse", config.MAIN_BRANCH).stdout.strip()
        history = self.origin_git(
            "log", "--format=%s", target_origin_main).stdout
        self.assertIn(
            f"{TASK}: код фичи", history,
            f"merge-коммит задачи не найден в main origin целевого "
            f"после done: {history!r}")

        self.assertEqual(
            self.pult_main_state(), self.pult_main_before,
            "main пульта сдвинулся после done задачи внешнего target — "
            "ADR-0002/требование 4 SPEC нарушены")


class CapacityGateThroughAdvanceTest(ExternalTargetGitSandbox):
    """AC-16 через ПУБЛИЧНЫЙ диспетчер `fsm.cmd_advance`, не прямым
    вызовом `_capacity_gate_refuses` (тот прогон — AC-10)."""

    TASK2 = "01AC16CAPACITYVIAADVANC"

    def setUp(self):
        super().setUp()
        self.branch = f"task/{self.TASK2.lower()}-x"
        self.checkout_task_branch(self.branch)
        (self.target_workspace / "huge.txt").write_text(
            "x" * (config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES + 10_000),
            encoding="utf-8")
        self.wgit("add", "-A")
        self.wgit("commit", "-q", "-m", f"{self.TASK2}: правка")
        self.insert_external_task(self.TASK2, self.branch, state="in_dev")
        _lock_tests(self.TASK2)

    def test_ac16_oversized_external_target_diff_blocks_advance(self):
        """`fsm.cmd_advance` на оверсайз-diff внешнего target НЕ
        двигает задачу в `review` — гейт ёмкости реально сработал
        внутри диспетчера `in_dev`, а не был обойдён проводкой.

        Ловит мутацию: `_capacity_gate_refuses` для target ≠ self
        по-прежнему возвращает `False` безусловно (текущий код) —
        `cmd_advance` продвинул бы задачу в `review` независимо от
        размера diff'а, и `assertEqual` на состоянии это поймает.
        """
        conn = store.db()

        fsm.cmd_advance(self.TASK2)

        self.assertEqual(
            store.get_task(conn, self.TASK2)["state"], "in_dev",
            "оверсайз-diff внешнего target не остановил "
            "in_dev -> review — гейт ёмкости пропущен")


class SandboxIsolationTest(ExternalTargetGitSandbox):

    def test_ac17_sandbox_never_touches_the_real_repository_tree(self):
        """Инвариант 01M1KVGD18P9H5WR7VM8TGPV1T (тесты не пишут в
        настоящий репозиторий): `config.ROOT`/`config.PROJECTS` этой
        песочницы указывают ВО ВРЕМЕННЫЙ каталог, а не в дерево этого
        чекаута.

        Ловит мутацию: песочница (`tests.sandbox.RealGitSandbox`)
        перестаёт патчить `config.ROOT`/`config.PROJECTS` — оба указали
        бы на реальный `_REPO_ROOT`, и `assertNotEqual` это поймает.
        """
        self.assertNotEqual(config.ROOT, _REPO_ROOT)
        self.assertFalse(str(config.ROOT).startswith(str(_REPO_ROOT)))
        self.assertNotEqual(config.PROJECTS, _REPO_ROOT / ".artel" / "projects")


if __name__ == "__main__":
    import unittest
    unittest.main()
