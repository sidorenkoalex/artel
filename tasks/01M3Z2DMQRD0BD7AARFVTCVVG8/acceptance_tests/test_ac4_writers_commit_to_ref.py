"""AC-4: каждое пишущее место оставляет новый коммит в `refs/artifacts/<id>`.

Группа: разовый
Красен до реализации: сегодня все пишущие места коммитят в ветку `artifact/<id>`, а `refs/artifacts/<id>` после `new` нет — голова ссылки пуста ещё до проверяемого действия.

Файл разовый: проверка идёт через настоящий git (`refs/artifacts/<id>`,
`artifact/<id>` локально и в bare `origin`), правила долгоживущих файлов
`tests/` такое запрещают.

Каждое место разыгрывается его публичным входом (команда CLI, `set_state`,
`checkpoint.commit_step_artifacts`, `fsm.cmd_advance`, `doctor --fix`), а
наблюдается снаружи: голова ссылки до и после, предок ли прежняя голова
новой, нет ли ветки `artifact/<id>` локально и в `origin`.
"""
import unittest

from _sandbox import (EXTERNAL_TARGET, RefSandbox, plank_text, ref_name)
from orchestrator import amend, checkpoint, doctor, runner, store


class Ac4CreationTest(RefSandbox):
    """AC-4: создание задачи."""

    def test_ac4_new_writes_ref_and_no_branch(self):
        """`new` пишет документы задачи коммитом в ссылку, ветку не заводит.

        Ловит мутацию: создание задачи оставлено на прежнем пути
        (`commit_files` в `refs/heads/artifact/<id>`) — ссылки нет, а
        ветка `artifact/<id>` есть локально и в `origin`.
        """
        task_id = self.new_task()

        head = self.local_head(task_id)
        self.assertTrue(head, f"new не создал {ref_name(task_id)}")
        self.assertIsNotNone(self.file_at(head, f"tasks/{task_id}/SPEC.md"),
                             "SPEC.md не в ссылке после new")
        self.assertFalse(self.legacy_branch_local(task_id),
                         "new завёл ветку artifact/<id>")
        self.assertFalse(self.legacy_branch_origin(task_id),
                         "new отправил ветку artifact/<id> в origin")


class Ac4RoleStepAutocommitTest(RefSandbox):
    """AC-4: автокоммит шага роли."""

    def test_ac4_role_step_autocommit_appends_commit(self):
        """Правка роли в выложенном `tasks/<id>/` — новый коммит ссылки.

        Каталог роли готовит `runner.role_cwd` (выкладка документов перед
        шагом), роль правит `SPEC.md`, автокоммит шага
        (`checkpoint.commit_step_artifacts`) переносит правку.

        Ловит мутацию: автокоммит шага пишет в прежнюю ветку
        `artifact/<id>` — голова ссылки не меняется, правки роли в ней нет.
        """
        task_id = self.new_task()
        before = self.local_head(task_id)
        self.assertTrue(before, f"предусловие: после new есть {ref_name(task_id)}")
        cwd = runner.role_cwd(self.conn, task_id, self.row(task_id)["target"])
        spec = cwd / "tasks" / task_id / "SPEC.md"
        self.assertTrue(spec.is_file(), "SPEC.md не выложен перед шагом роли")
        spec.write_text(spec.read_text(encoding="utf-8")
                        + "\nПравка роли АВТОКОММИТ-AC4.\n", encoding="utf-8")

        checkpoint.commit_step_artifacts(store.db(), task_id, "analyst")

        head = self.assert_ref_advanced(task_id, before, "автокоммит шага")
        self.assertIn("АВТОКОММИТ-AC4",
                      self.file_at(head, f"tasks/{task_id}/SPEC.md") or "")


class Ac4OperatorCommandsTest(RefSandbox):
    """AC-4: `answer` и `zones-extend`."""

    def test_ac4_answer_appends_commit(self):
        """`answer <id> <файл>` на эскалированной задаче — новый коммит ссылки.

        Ловит мутацию: `answer` коммитит `ANSWER-n.md` в прежнюю ветку —
        голова ссылки не меняется, `ANSWER-1.md` в ней нет.
        """
        task_id = self.new_task()
        before = self.local_head(task_id)
        self.assertTrue(before, f"предусловие: после new есть {ref_name(task_id)}")
        state = self.row(task_id)["state"]
        store.set_state(store.db(), task_id, "escalated", "fsm",
                        expected_state=state, detail="эскалация планки AC-4")
        before = self.local_head(task_id)
        answer_file = self.root / ".artel" / "answer-plank.md"
        answer_file.write_text("Ответ Оператора ОТВЕТ-AC4.\n", encoding="utf-8")

        out = self.run_cli("answer", task_id, str(answer_file))

        head = self.assert_ref_advanced(task_id, before, f"answer:\n{out}")
        self.assertIn("ОТВЕТ-AC4",
                      self.file_at(head, f"tasks/{task_id}/ANSWER-1.md") or "")

    def test_ac4_zones_extend_appends_commit(self):
        """`zones-extend <id> <путь>` — новый коммит ссылки с мандатом.

        Ловит мутацию: `zones-extend` коммитит `ANSWER-n.md` в прежнюю
        ветку — голова ссылки не меняется.
        """
        task_id = self.new_task()
        before = self.local_head(task_id)
        self.assertTrue(before, f"предусловие: после new есть {ref_name(task_id)}")

        out = self.run_cli("zones-extend", task_id, "docs/extra.md")

        head = self.assert_ref_advanced(task_id, before, f"zones-extend:\n{out}")
        self.assertIn("docs/extra.md",
                      self.file_at(head, f"tasks/{task_id}/ANSWER-1.md") or "")


class Ac4PassportTest(RefSandbox):
    """AC-4: строка паспорта на смене состояния."""

    def test_ac4_state_change_appends_passport_commit(self):
        """Смена состояния задачи — новый коммит ссылки со строкой паспорта.

        Паспорт сегодня ведётся у задач внешнего target — сценарий берёт
        такую задачу.

        Ловит мутацию: строка паспорта дописывается в прежнюю ветку
        `artifact/<id>` — голова ссылки после `set_state` прежняя, строки
        нового состояния в `PASSPORT.md` ссылки нет.
        """
        self.declare_external_target()
        task_id = self.new_task(target=EXTERNAL_TARGET)
        before = self.local_head(task_id)
        self.assertTrue(before, f"предусловие: после new есть {ref_name(task_id)}")
        state = self.row(task_id)["state"]

        store.set_state(store.db(), task_id, "spec_gate", "fsm",
                        expected_state=state, detail="переход планки AC-4")

        head = self.assert_ref_advanced(task_id, before, "паспорт")
        self.assertIn("spec_gate",
                      self.file_at(head, f"tasks/{task_id}/PASSPORT.md") or "")


class Ac4TestsWritingExitTest(RefSandbox):
    """AC-4: перечень долгоживущих тестов и `tests_locked_sha`."""

    def test_ac4_tests_writing_exit_commits_manifest_and_lock_into_ref(self):
        """Выход из `tests_writing` пишет перечень и лок коммитами ссылки.

        У задачи есть долгоживущий файл в кодовой ветке. После выхода в
        `in_dev`: голова ссылки — потомок прежней; `tests_locked_sha` —
        новый коммит этой же ссылки (потомок прежней головы, предок или
        сама голова), в его дереве лежит перечень
        `acceptance_tests/long_lived.sha256.txt`.

        Ловит мутацию: перечень коммитится в прежнюю ветку, а лок берёт
        голову `refs/heads/artifact/<id>` — ссылка не продвигается, лок
        указывает на коммит вне её истории.
        """
        task_id = self.new_task()
        self.prepare_tests_writing(task_id)
        before = self.local_head(task_id)
        self.assertTrue(before, f"предусловие: есть {ref_name(task_id)}")

        self.lock_plank(task_id)

        head = self.assert_ref_advanced(task_id, before, "выход из tests_writing")
        locked = self.row(task_id)["tests_locked_sha"]
        self.assertTrue(locked, "tests_locked_sha не записан")
        self.assertNotEqual(locked, before, "лок не новый коммит ссылки")
        self.assertTrue(self.is_ancestor(before, locked),
                        "лок не потомок прежней головы ссылки")
        self.assertTrue(self.is_ancestor(locked, head),
                        "лок вне истории ссылки")
        self.assertIsNotNone(
            self.file_at(locked,
                         f"tasks/{task_id}/acceptance_tests/long_lived.sha256.txt"),
            "перечня долгоживущих тестов нет в дереве лока")

    def test_ac4_amend_tests_appends_commit(self):
        """`amend-tests <id>` после лока — новый коммит ссылки с правкой планки.

        Ловит мутацию: `amend-tests` коммитит правку планки в прежнюю
        ветку (`update-ref refs/heads/artifact/<id>`) — голова ссылки
        прежняя, правленой планки в ней нет.
        """
        task_id = self.new_task()
        wt = self.prepare_tests_writing(task_id)
        self.lock_plank(task_id)
        before = self.local_head(task_id)
        plank = wt / "tasks" / task_id / "acceptance_tests" / "test_ac1_plank.py"
        plank.parent.mkdir(parents=True, exist_ok=True)
        plank.write_text(plank_text("ПРАВКА-AC4"), encoding="utf-8")

        out = self.call(amend.cmd_amend_tests, task_id, "правка планки AC-4")

        head = self.assert_ref_advanced(task_id, before, f"amend-tests:\n{out}")
        self.assertIn(
            "ПРАВКА-AC4",
            self.file_at(head, f"tasks/{task_id}/acceptance_tests/"
                               f"test_ac1_plank.py") or "")


class Ac4DoctorFixTest(RefSandbox):
    """AC-4: уборка игнорируемых файлов в `doctor --fix`."""

    def test_ac4_doctor_fix_removes_ignored_file_by_new_commit(self):
        """`doctor --fix` убирает игнорируемый файл документов новым коммитом.

        `.gitignore` пульта игнорирует `*.pyc`; в документах живой задачи
        лежит `cache.pyc`. После `doctor --fix` голова ссылки — потомок
        прежней, файла в ней нет.

        Ловит мутацию: уборка ходит только по веткам `artifact/*` (как
        сегодня) — в ссылке `cache.pyc` остаётся, новой головы нет.
        """
        (self.root / ".gitignore").write_text(".artel/\n*.pyc\n",
                                              encoding="utf-8")
        self.git("add", ".gitignore")
        self.git("commit", "-q", "-m", "gitignore: *.pyc")
        task_id = self.new_task()
        self.seed_docs(task_id, {"cache.pyc": b"\x00\x01\xff"},
                       "игнорируемый файл")
        before = self.local_head(task_id)
        self.assertTrue(before, f"предусловие: есть {ref_name(task_id)}")
        self.assertIn(f"tasks/{task_id}/cache.pyc", self.tree_paths(before),
                      f"предусловие: cache.pyc в {ref_name(task_id)}")

        with self.only_git():
            out = self.call(doctor.cmd_doctor, fix=True)

        head = self.assert_ref_advanced(task_id, before, f"doctor --fix:\n{out[-800:]}")
        self.assertNotIn(f"tasks/{task_id}/cache.pyc", self.tree_paths(head),
                         "игнорируемый файл остался в ссылке")


if __name__ == "__main__":
    unittest.main()
