"""Красен до реализации: `orchestrator/fsm_advance.py::review`/`verifying`
для ВНЕШНЕГО target материализуют планку тем же `acceptance.
materialize_from_branch` (временный каталог) и прогоняют её тем же
`acceptance.run` (`cwd=config.ROOT`), что и узел регрессии — планка,
резолвящая `orchestrator/` от `__file__`, промахивается мимо кода
workspace'а внешнего target (SPEC «Требования» п.1: «worktree self-target
либо workspace внешнего target»). До правки — красный; после правки
(AC-5: `review`/`verifying` используют ту же материализацию/прогон, что
AC-1/AC-2) — зелёный.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (  # noqa: E402
    ExternalWorkspaceReviewSandbox, MARKER_NEW_MODULE, MARKER_TEST_VIA_FILE)


class Ac5ReviewUsesWorkspaceMaterializationTest(ExternalWorkspaceReviewSandbox):

    def test_ac5_review_acceptance_run_resolves_external_workspace_code(self):
        """`review()` (вердикт approved) обязана прогнать планку так, что
        `orchestrator/` резолвится в код WORKSPACE'а внешнего target
        (`config.PROJECTS/<target>/workspace/`), не во временный каталог/
        главную копию пульта — переход обязан пройти в `verifying`.

        Ловит мутацию: `review()` продолжает материализовывать планку во
        временный каталог и/или `acceptance.run` продолжает получать
        `cwd=config.ROOT` — `orchestrator/marker.py`, лежащий только в
        workspace внешнего target, не резолвится, планка красная, переход
        остаётся в `review`.
        """
        self.write_marker_in_workspace(MARKER_NEW_MODULE)
        self.commit_review_artifacts({"test_via_file.py": MARKER_TEST_VIA_FILE})

        self.run_review()

        self.assertEqual(
            self.state(), "verifying",
            f"журнал: {self.journal_details()}")


class Ac5VerifyingSharesTheSameFixTest(ExternalWorkspaceReviewSandbox):

    def test_ac5_verifying_reaches_acceptance_after_ci_green(self):
        """`verifying()` — второй узел, названный AC-5 (материализация
        планки, предшествующая `fsm_autogate._maybe_autogate_acceptance`):
        после зелёного CI переход обязан дойти до состояния `acceptance`,
        не споткнуться о материализацию планки внешнего target.

        Ловит мутацию: материализация внутри `verifying()` бросает
        исключение или иначе ломает переход при внешнем target (например,
        не создаёт каталог workspace заранее) — переход не доходит до
        `acceptance` даже при зелёном CI.
        """
        self.write_marker_in_workspace(MARKER_NEW_MODULE)
        self.commit_review_artifacts({"test_via_file.py": MARKER_TEST_VIA_FILE})
        self.run_review()
        self.assertEqual(self.state(), "verifying", "предпосылка теста не выполнена")

        self.run_verifying()

        self.assertEqual(
            self.state(), "acceptance",
            f"журнал: {self.journal_details()}")


if __name__ == "__main__":
    unittest.main()
