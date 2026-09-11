"""Приёмочный тест AC-9/AC-10 (tasks/01M1R5B33CC7E6BZK085XV3ZCX/SPEC.md,
«Критерии приёмки»).

AC-9: diff ревью-пакета (`review.git_diff_part`) для target ≠ self
строится в клоне контекста target'а; для self diff по-прежнему из
`config.ROOT`.

AC-10: гейт ёмкости diff (`fsm_advance._capacity_gate_refuses`)
применяется к ЛЮБОМУ target: для target ≠ self он больше не
пропускается безусловно, а считает diff в клоне контекста target'а тем
же способом, что и AC-9.

Красен до реализации: `git_diff_part` сегодня безусловно строит diff в
`config.ROOT` (ветки внешнего target там нет); `_capacity_gate_refuses`
сегодня для target ≠ self возвращает `False` СРАЗУ, до какого-либо
diff'а вообще — тест с ЗАВЕДОМО избыточным diff'ом (больше
`config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES`) обязан получить отказ
(`True`), а сегодняшний код тихо пропускает переход всегда.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config, fsm_advance, review, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ExternalTargetGitSandbox  # noqa: E402


class GitDiffPartRepoContextTest(ExternalTargetGitSandbox):
    """AC-9: `review.git_diff_part(..., repo=...)`."""

    def setUp(self):
        super().setUp()
        self.branch = "task/ac9-diff-x"
        self.checkout_task_branch(self.branch)
        (self.target_workspace / "feature.txt").write_text(
            "код фичи\n" * 5, encoding="utf-8")
        self.wgit("add", "-A")
        self.wgit("commit", "-q", "-m", "код фичи")

    def test_ac9_diff_against_the_target_clone_is_not_empty(self):
        """diff `main...branch` В `target_workspace` — непустой (файл
        реально добавлен там).

        Ловит мутацию: `repo=` принимается, но игнорируется (по-прежнему
        `config.ROOT`) — там нет ни ветки, ни файла, `diff_lines`
        осталось бы 0, а текст — `(не собран: ...)`.
        """
        text, lines, reason = review.git_diff_part(
            config.MAIN_BRANCH, self.branch, repo=self.target_workspace)

        self.assertEqual(reason, "")
        self.assertGreater(lines, 0)
        self.assertIn("feature.txt", text)

    def test_ac9_without_repo_still_reads_root(self):
        """Байт-в-байт прежнее поведение self (без `repo=`): читает
        `config.ROOT`, где такой ветки нет — сбор не удался."""
        text, lines, reason = review.git_diff_part(
            config.MAIN_BRANCH, self.branch)

        self.assertNotEqual(reason, "")
        self.assertEqual(lines, 0)


class CapacityGateExternalTargetTest(ExternalTargetGitSandbox):
    """AC-10: `fsm_advance._capacity_gate_refuses` — считает diff
    целевого, больше не пропускает external target безусловно."""

    def _make_task(self, task_id: str, payload_bytes: int) -> None:
        branch = f"task/{task_id.lower()}-x"
        self.checkout_task_branch(branch)
        (self.target_workspace / "huge.txt").write_text(
            "x" * payload_bytes, encoding="utf-8")
        self.wgit("add", "-A")
        self.wgit("commit", "-q", "-m", f"{task_id}: правка")
        self.insert_external_task(task_id, branch, state="in_dev")
        self.branch = branch

    def test_ac10_oversized_diff_of_the_external_target_is_refused(self):
        """diff заведомо больше `config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES`
        — гейт ОТКАЗЫВАЕТ (`True`), а не пропускает безусловно.

        Ловит мутацию: `if store.task_target(...) != config.
        DEFAULT_TARGET: return False` остался на месте (старое
        поведение) — гейт ответит `False` независимо от размера diff'а,
        и `assertTrue` здесь провалится.
        """
        task_id = "01AC10OVERSIZEDDIFFTASK"
        self._make_task(task_id,
                        config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES + 10_000)
        conn = store.db()
        t = store.get_task(conn, task_id)

        refused = fsm_advance._capacity_gate_refuses(conn, task_id, t, "in_dev")

        self.assertTrue(
            refused,
            f"гейт ёмкости пропустил diff внешнего target размером "
            f">{config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES} байт")

    def test_ac10_small_diff_of_the_external_target_is_not_refused(self):
        """Diff заведомо МЕНЬШЕ потолка — гейт пропускает (`False`),
        не любой diff внешнего target подозрителен."""
        task_id = "01AC10SMALLDIFFTASK0001"
        self._make_task(task_id, 100)
        conn = store.db()
        t = store.get_task(conn, task_id)

        refused = fsm_advance._capacity_gate_refuses(conn, task_id, t, "in_dev")

        self.assertFalse(refused)


if __name__ == "__main__":
    import unittest
    unittest.main()
