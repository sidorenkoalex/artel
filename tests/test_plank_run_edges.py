"""Углы `plank-run` и восстановления удалённых файлов, не покрытые
долгоживущими файлами задачи 01M41R4YAM4NGEQXW1FWH7T22M: формы аргумента
`[файл]`, отказ при документах в рабочей копии кода, таймаут прогона,
свой долгоживущий файл test_author.

Песочницы — те же, что у долгоживущих файлов задачи (настоящий git,
`tests/sandbox.py::RealGitSandbox`).
"""
import subprocess
import unittest
from unittest import mock

from orchestrator import acceptance, checkpoint, config, store
from tests.test_01m41r4yam4ngeqxw1fwh7t22m_plank_run import (FAILING, PASSING,
                                                            PlankRunSandbox)
from tests.test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted import \
    RestoreDeletedSandbox


class PlankRunFileArgTest(PlankRunSandbox):

    def setUp(self):
        super().setUp()
        self.commit_fixed_plank({
            "test_a_plank.py": PASSING.format(name="a_one")
            + FAILING.format(name="a_two"),
            "test_b_plank.py": FAILING.format(name="b_must_not_run")})

    def test_file_arg_accepts_task_prefix_and_node(self):
        """`[файл]` с префиксом `tasks/<id>/acceptance_tests/` и с узлом
        pytest `::тест` прогоняет только названное.

        Ловит мутацию: префикс пути не снимается — отказ «файла нет в
        планке», pytest не запускается; узел `::тест` отбрасывается —
        исполняется и красный `test_a_two`, «1 failed» в выводе.
        """
        arg = (f"tasks/{self.own_dir.name}/acceptance_tests/"
               f"test_a_plank.py::test_a_one")
        status, output = self.plank_run(arg)
        self.assertEqual(status, 0, self.explain(output))
        self.assertEqual(len(self.pytest_calls), 1, self.explain(output))
        self.assertIn("1 passed", output, self.explain(output))
        self.assertNotIn("failed", output, self.explain(output))
        self.assertNotIn("b_must_not_run", output, self.explain(output))

    def test_unknown_file_refuses_without_layout(self):
        """Файл, которого нет в планке, — отказ без выкладки и прогона.

        Ловит мутацию: аргумент не сверяется с составом планки — pytest
        запускается на несуществующем пути (код 4) вместо именованного
        отказа «файла нет в планке», и выкладка случается.
        """
        status, output = self.plank_run("test_missing_plank.py")
        self.assertNotEqual(status, 0, self.explain(output))
        self.assertIn("нет в планке", output, self.explain(output))
        self.assertEqual(self.pytest_calls, [], self.explain(output))
        self.assertFalse(self.own_dir.exists(), self.explain(output))


class PlankRunStrayDocsTest(PlankRunSandbox):

    def test_documents_in_code_copy_refuse_and_stay(self):
        """Документ задачи в `tasks/<id>/` рабочей копии кода — отказ, файл
        на месте.

        Ловит мутацию: проверки документов нет — выкладка и уборка
        `tasks/<id>/` сносят PLAN.md, записанный туда по ошибке, до того
        как пульт после шага перенесёт его в ссылку документов.
        """
        self.commit_fixed_plank({"test_a_plank.py": PASSING.format(name="a")})
        plan = self.own_dir / "PLAN.md"
        plan.parent.mkdir(parents=True)
        plan.write_text(f"план {self.seed}\n", encoding="utf-8")
        status, output = self.plank_run()
        self.assertNotEqual(status, 0, self.explain(output))
        self.assertIn("PLAN.md", output, self.explain(output))
        self.assertEqual(self.pytest_calls, [], self.explain(output))
        self.assertEqual(plan.read_text(encoding="utf-8"),
                         f"план {self.seed}\n", self.explain(output))


class PlankRunTimeoutTest(PlankRunSandbox):

    def test_timeout_exits_nonzero_and_drops_layout(self):
        """Прогон, превысивший таймаут, — ненулевой код и текст о таймауте,
        выкладка убрана.

        Ловит мутацию: `TimeoutExpired` не перехвачен в `run_plank` либо
        оборванный прогон выходит кодом 0 — статус 0 или нет текста
        «превысил»; уборка не в `finally` — каталог задачи остаётся.
        """
        self.commit_fixed_plank({"test_a_plank.py": PASSING.format(name="a")})
        self.raise_in_pytest = subprocess.TimeoutExpired(
            ["pytest"], config.ACCEPTANCE_TIMEOUT_SEC, output=b"half")
        status, output = self.plank_run()
        self.assertNotEqual(status, 0, self.explain(output))
        self.assertIn("превысил", output, self.explain(output))
        self.assertFalse(self.own_dir.exists(), self.explain(output))


class RunPlankUnitTest(unittest.TestCase):

    def test_run_plank_returns_exit_code_and_full_output(self):
        """`run_plank` отдаёт код выхода pytest и весь вывод, не хвост.

        Ловит мутацию: код выхода сворачивается в «зелёно/красно»
        (`returncode == 0`) — возвращается `False` вместо 3; вывод
        обрезается до 2000 символов, как у `run()` гейта, — начало вывода
        пропадает.
        """
        long_head = "н" * 5000
        done = subprocess.CompletedProcess([], 3, long_head + "хвост", "")
        with mock.patch.object(subprocess, "run", return_value=done) as run:
            code, output = acceptance.run_plank(["x"], config.ROOT)
        self.assertEqual(code, 3)
        self.assertTrue(output.startswith(long_head))
        self.assertEqual(run.call_args.kwargs["timeout"],
                         config.ACCEPTANCE_TIMEOUT_SEC)


class TestAuthorOwnFileTest(RestoreDeletedSandbox):

    def test_test_author_own_long_lived_deletion_left_to_its_mandate(self):
        """Удаление test_author своего долгоживущего файла восстановлением
        не трогается, чужой файл `tests/` — восстанавливается.

        Сценарий: в HEAD ветки задачи — свой долгоживущий файл задачи; шаг
        test_author в `tests_writing` удаляет его и файл общей зоны.
        `restore_out_of_bounds_deletions` возвращает только файл общей зоны.

        Ловит мутацию: свои долгоживущие файлы не исключены из
        восстановления — test_author не может убрать свой же файл в
        `tests_writing`, он возвращается из HEAD.
        """
        task_id, wt = self.new_task("test_author")
        own = f"tests/test_{task_id.lower()}_own.py"
        (wt / own).write_text("def test_own():\n    pass\n", encoding="utf-8")
        self.wt_git(wt, "add", own)
        self.wt_git(wt, "commit", "-q", "-m", "свой файл")
        (wt / own).unlink()
        common = "tests/test_common_zone_fixture.py"
        (wt / common).unlink()
        restored = checkpoint.restore_out_of_bounds_deletions(
            self.conn, task_id, "test_author", wt)
        self.assertEqual(restored, [common], self.explain())
        self.assertFalse((wt / own).exists(), self.explain())
        rows = [r for r in store.task_steps(self.conn, task_id)
                if r["action"] == checkpoint.RESTORED_DELETIONS_ACTION]
        self.assertEqual(len(rows), 1, self.explain())
        self.assertIn(common, rows[0]["detail"], self.explain())


if __name__ == "__main__":
    unittest.main()
