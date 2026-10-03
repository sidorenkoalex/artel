"""Записи пульта в ссылку документов при удалённой ролью ссылке и живой
фиксации отказывают, не создают корневой коммит и не перефиксируют его
(SPEC 01M41AB597B330P2RCXCMVRZPE, требование 5, AC-8; REVIEW итерации 1,
R1-F1).

Песочница — `DocsRefSandbox` долгоживущего файла задачи (настоящий git,
задача артели через `catalog.cmd_new`). «Роль удаляет ссылку» — `git
update-ref -d` мимо пульта.
"""
from orchestrator import amend, answer, fixation, store
from orchestrator.advance_gates import tests_writing
from tests.test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation import (
    DocsRefSandbox)


class DeletedRefTest(DocsRefSandbox):

    def delete_ref(self, task_id: str) -> None:
        self.rgit(task_id, "update-ref", "-d", self.ref(task_id))
        self.assertEqual(self.head(task_id), "",
                         self.note("предусловие: ссылка удалена"))

    def assert_refused_untouched(self, task_id: str, fixed: str, state: str,
                                 out: str, exited: bool, where: str) -> None:
        self.assertTrue(exited, self.note(f"{where}: отказа нет:\n{out}"))
        self.assertEqual(self.head(task_id), "", self.note(
            f"{where}: в удалённую ссылку записан коммит "
            f"{self.head(task_id)}:\n{out}"))
        self.assertEqual(self.fixed(task_id), fixed, self.note(
            f"{where}: tasks.fixed_sha изменён:\n{out}"))
        self.assertEqual(self.state(task_id), state, self.note(
            f"{where}: состояние задачи сменилось:\n{out}"))
        self.assertIsNotNone(fixation.check_integrity(store.db(), task_id),
                             self.note(f"{where}: сверка на старте шага "
                                       f"перестала отказывать"))
        self.assertIn(fixation.DOCS_REF_UNREAD_ACTION, out, self.note(
            f"{where}: отказ не называет причину:\n{out}"))

    def test_zones_extend_refuses_on_deleted_ref(self):
        """`zones-extend` при удалённой ссылке и живой фиксации — именованный отказ без коммита и перефиксации.

        Ловит мутацию: `fixation.stop_on_ref_drift` пропускает расхождение
        с непрочитанной головой (`not drift.moved` -> return, как в
        итерации 1) — `zones-extend` пишет корневой коммит с одним
        ANSWER и перефиксирует его.
        """
        task_id, fixed = self.ready_task()
        self.force_state(task_id, "in_dev")
        self.delete_ref(task_id)

        out, exited = self.run_cmd(answer.cmd_zones_extend, task_id,
                                   "docs/extra.md")

        self.assert_refused_untouched(task_id, fixed, "in_dev", out, exited,
                                      "zones-extend")

    def test_answer_refuses_on_deleted_ref(self):
        """`answer` при удалённой ссылке и живой фиксации — именованный отказ, задача остаётся в эскалации.

        Ловит мутацию: `answer` не зовёт `fixation.stop_on_ref_drift` или
        тот пропускает непрочитанную голову — ответ ложится корневым
        коммитом, `tasks.fixed_sha` равен ему.
        """
        task_id, fixed = self.ready_task()
        self.force_state(task_id, "escalated", escalated_from="in_dev")
        self.delete_ref(task_id)
        path = self.root / ".artel" / "answer.txt"
        path.write_text("Ответ Оператора.\n", encoding="utf-8")

        out, exited = self.run_cmd(answer.cmd_answer, task_id, str(path))

        self.assert_refused_untouched(task_id, fixed, "escalated", out, exited,
                                      "answer")

    def test_amend_tests_refuses_on_deleted_ref(self):
        """`amend-tests --from-branch` при удалённой ссылке и живой фиксации — именованный отказ без коммита лока.

        Ловит мутацию: `amend._cmd_amend_tests_from_branch` пропускает
        непрочитанную голову — правка планки пишет корневой коммит в
        ссылку и перефиксирует его.
        """
        task_id, fixed = self.ready_task(plank=True)
        self.force_state(task_id, "escalated", escalated_from="in_dev")
        self.delete_ref(task_id)

        out, exited = self.run_cmd(amend.cmd_amend_tests, task_id,
                                   "правка планки", from_branch=True)

        self.assert_refused_untouched(task_id, fixed, "escalated", out, exited,
                                      "amend-tests")

    def test_tests_writing_manifest_gate_refuses_on_deleted_ref(self):
        """Гейт перечня долгоживущих тестов при удалённой ссылке и живой фиксации отказывает и перечень не пишет.

        Ловит мутацию: `_tests_writing_manifest_gate` проверяет только
        `drift.moved` — перечень ложится корневым коммитом в удалённую
        ссылку и перефиксируется (`store.record_fixation`).
        """
        task_id, fixed = self.ready_task()
        self.force_state(task_id, "tests_writing")
        self.delete_ref(task_id)

        refusal = tests_writing._tests_writing_manifest_gate(
            store.db(), task_id, store.task_branch(store.db(), task_id), [])

        self.assertIsNotNone(refusal, self.note("гейт перечня не отказал"))
        self.assertIn(fixation.DOCS_REF_UNREAD_ACTION, refusal.action)
        self.assertEqual(self.head(task_id), "", self.note(
            f"перечень записан в удалённую ссылку: {self.head(task_id)}"))
        self.assertEqual(self.fixed(task_id), fixed,
                         self.note("tasks.fixed_sha изменён гейтом перечня"))
