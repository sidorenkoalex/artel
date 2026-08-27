"""Приёмочные тесты T043 — провал генерации/коммита RETRO не блокирует
переход (SPEC.md, AC-3), на обоих путях: done (merge_gate) и kill.

Кill-путь здесь — только ПРОВАЛ (git-подкоманда `add`/`commit` отвечает
отказом): в этом сценарии ничего не долетает до main ни в каком смысле
(коммит не создан), поэтому тест не пересекается с эскалированным
вопросом AC-2 (`test_retro_escalation.py`) — там спорен только УСПЕШНЫЙ
коммит+push RETRO при kill с main, конфликтующий с существующим
`tests/test_invariants.KillKeepsMainIntactTest`
(docs/invariants.md, инвариант 15). Провал шага RETRO при kill main не
двигает ни при каком исходе AC-2.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import alerts, config, store  # noqa: E402
from retro_sandbox import RetroSandboxTest  # noqa: E402


def journal_text(task_id: str) -> str:
    return "\n".join(f"{s['action']} {s['detail']}"
                    for s in store.task_steps(store.db(), task_id)).lower()


def retro_incidents():
    incidents = alerts.open_alerts(store.db(), "incident")
    return [a for a in incidents if (a["source"] or "").startswith("fsm.retro")]


class Ac3DoneRetroFailureTest(RetroSandboxTest):
    """Провал коммита RETRO на merge_gate не отменяет merge/переход в done."""

    def setUp(self):
        super().setUp()
        self.write_context_spec()
        self.set_state("merge_gate")

    def test_ac3_done_path_retro_failure_still_completes_merge(self):
        self.approve(fail_git_subcommands=("add", "commit"))

        self.assertEqual(
            self.state(), "done",
            "провал шага RETRO не должен отменять merge и переход в done")
        self.assertIn(
            "push", self.git_subcommands(),
            "git push обязан выполниться независимо от исхода шага RETRO")

        text = journal_text(self.TASK)
        self.assertTrue(
            any(k in text for k in ("retro", "ретро"))
            and any(k in text for k in ("failed", "провал", "не удал", "ошиб")),
            "в журнале нет записи о провале шага генерации/коммита RETRO")

        self.assertTrue(
            retro_incidents(),
            "не заведён incident-алерт с source вида fsm.retro "
            "(SPEC, требование 9)")

# Ред. Оператора 27.08 (эскалация developer, PLAN T043): класс
# Ac3KillRetroFailureTest удалён — написан до решения (d) и требовал,
# чтобы kill пытался коммитить RETRO, что противоречит требованию 2
# SPEC и Ac2KillDoesNotTouchMainTest. AC-3 покрыт: done-путь —
# Ac3DoneRetroFailureTest ниже; kill-путь (провал подбора долга) —
# tests/test_fsm_retro.py::GenerateAndCommitRetroTest.
