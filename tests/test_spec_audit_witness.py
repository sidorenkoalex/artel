"""Граничные варианты свидетельства свежести, дополняющие продуктовую планку."""
import subprocess
import unittest
from unittest import mock

from orchestrator.advance_gates import spec_audit


class WitnessTest(unittest.TestCase):
    def refusal(self, *, timeout=False, actor="orchestrator", suffix=""):
        task = "T501"
        sha = "1234567890abcdef" * 2 + "12345678"
        subject = (f"{task}: артефакты шага spec_auditor "
                   "(автокоммит оркестратора"
                   + (", WIP после таймаута)" if timeout else ")"))
        history = subprocess.CompletedProcess(
            [], 0, stdout=f"{sha} {subject}\n", stderr="")
        rows = [
            {"id": 1, "actor": "fsm", "action": "state -> spec_audit",
             "detail": ""},
            {"id": 2, "actor": actor,
             "action": "автокоммит артефактов шага (артефактная ветка)",
             "detail": f"{subject} (артефактная ветка, sha {sha}){suffix}"},
        ]
        with mock.patch.object(spec_audit.artifact_branch, "git", return_value=history), \
                mock.patch.object(spec_audit.store, "task_steps", return_value=rows):
            return spec_audit.freshness_refusal(None, task, "refs/artifacts/T501")

    def test_deleted_files_suffix_preserves_current_witness(self):
        """Ловит мутацию: разбор запрещает суффикс удалённых файлов — новый
        обычный/WIP аудит с таким свидетельством ошибочно отклоняется.
        """
        for timeout in (False, True):
            with self.subTest(timeout=timeout):
                self.assertIsNone(self.refusal(
                    timeout=timeout,
                    suffix="; удалено: tasks/T501/NOTE-spec_auditor.md"))

    def test_other_actor_cannot_supply_exact_witness(self):
        """Ловит мутацию: снята проверка автора события — точный текст
        автокоммита от spec_auditor вместо orchestrator даёт свежесть.
        """
        refusal = self.refusal(actor="spec_auditor")
        self.assertIsNotNone(refusal)
        self.assertEqual(refusal[0], spec_audit.NOT_FRESH_REFUSAL_ACTION)
