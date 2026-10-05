"""AC-7: выложенный `_pult.py` не утекает из рабочей копии.

После шага с выложенной планкой `_pult.py` нет ни в коммите ссылки
документов (автокоммит `orchestrator/checkpoint.py`, лок
`tests_locked_sha`), ни в кодовой ветке задачи, ни в каталоге документов
задачи.

Путь утечки, который сторожит файл: файл `tasks/<id>/…`, оставшийся в
рабочей копии кода к концу шага, автокоммит забирает в ссылку документов
(`checkpoint._take_code_copy_docs`), а `_pult.py` проходит фильтр
допустимых имён планки (`_*.py`). Сценарии оставляют выкладку в рабочей
копии (прерванный `plank-run`) и проверяют, что она никуда не доехала.

Группа: разовый
Красен до реализации: выкладка не кладёт `_pult.py` — предпосылка «помощник выложен» не выполняется.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _scenario import (HELPER_NAME, PLANK_TEST, TASK, PlankHelperSandbox,  # noqa: E402
                       git)

from orchestrator import (acceptance, checkpoint, config, fsm, runner,  # noqa: E402
                          store)


class NoLeakSandbox(PlankHelperSandbox):

    def setUp(self):
        super().setUp()
        self.commit_to_ref({"acceptance_tests/test_ac1_sandbox.py": PLANK_TEST},
                           "планка")

    def leave_materialized_plank(self) -> None:
        """Выкладка осталась в рабочей копии к концу шага."""
        acceptance.materialize_from_branch(TASK, self.ref, self.wt)
        self.assertTrue(self.helper_path.is_file(),
                        f"выкладка не положила {HELPER_NAME}")

    def assert_no_leak(self) -> None:
        in_ref = [p for p in self.ref_tree() if p.endswith(f"/{HELPER_NAME}")]
        self.assertEqual(in_ref, [], "помощник в ссылке документов")
        in_code = [p for p in self.code_branch_paths()
                   if p.endswith(HELPER_NAME)]
        self.assertEqual(in_code, [], "помощник в кодовой ветке задачи")
        docs = self.docs_dir()
        in_docs = sorted(p.relative_to(docs).as_posix()
                         for p in docs.rglob(HELPER_NAME)) if docs.is_dir() else []
        self.assertEqual(in_docs, [], "помощник в каталоге документов")


class StepCheckpointTest(NoLeakSandbox):

    def test_ac7_test_author_step_leftover_does_not_leak(self):
        """Шаг test_author с оставленной выкладкой — `_pult.py` никуда не доехал.

        Сценарий: `tests_writing`, шаг начат (`runner.role_cwd`), планка
        выложена в рабочую копию и не убрана; шаг закрывается чекпоинтами
        (`commit_success_checkpoint`, `commit_step_artifacts`), следующий
        шаг снова выкладывает каталог документов. `_pult.py` нет ни в
        ссылке, ни в кодовой ветке, ни в каталоге документов.

        Ловит мутацию: автокоммит забирает `tasks/<id>/` рабочей копии
        целиком без исключения помощника — `acceptance_tests/_pult.py`
        оказывается в ссылке и следующей выкладкой в каталоге документов."""
        runner.role_cwd(self.conn, TASK, config.DEFAULT_TARGET)
        self.leave_materialized_plank()

        checkpoint.commit_success_checkpoint(self.conn, TASK, "test_author")
        checkpoint.commit_step_artifacts(self.conn, TASK, "test_author")
        self.assert_no_leak()
        runner.role_cwd(self.conn, TASK, config.DEFAULT_TARGET)

        self.assert_no_leak()

    def test_ac7_developer_step_leftover_does_not_leak(self):
        """Шаг developer с оставленной выкладкой — `_pult.py` никуда не доехал.

        Сценарий: `in_dev`, шаг начат, планка выложена и не убрана, роль
        оставила незакоммиченный код; чекпоинт пульта коммитит код за
        роль, автокоммит шага переносит документы. В кодовой ветке есть
        код роли, но нет `_pult.py`; в ссылке и каталоге документов его
        тоже нет.

        Ловит мутацию: коммит кода за роль (`git add -A`) не исключает
        выложенный помощник — `tasks/<id>/acceptance_tests/_pult.py`
        попадает в кодовую ветку."""
        store.update_task(self.conn, TASK, state="in_dev")
        runner.role_cwd(self.conn, TASK, config.DEFAULT_TARGET)
        self.leave_materialized_plank()
        (self.wt / "feature.py").write_text("ROLE_CODE = 1\n", encoding="utf-8")

        checkpoint.commit_success_checkpoint(self.conn, TASK, "developer")
        checkpoint.commit_step_artifacts(self.conn, TASK, "developer")
        runner.role_cwd(self.conn, TASK, config.DEFAULT_TARGET)

        self.assertIn("feature.py", self.code_branch_paths(),
                      "чекпоинт не закоммитил код роли — сценарий не воспроизведён")
        self.assert_no_leak()


class LockTest(NoLeakSandbox):

    def test_ac7_locked_plank_commit_has_no_helper(self):
        """Лок `tests_locked_sha` фиксирует ссылку без `_pult.py`.

        Сценарий: выход из `tests_writing` в `in_dev`; сухой сбор (подменён
        наблюдателем) видит выложенный рядом с планкой `_pult.py`. После
        перехода дерево коммита `tests_locked_sha` не несёт `_pult.py`,
        кодовая ветка — тоже, выкладка из рабочей копии убрана.

        Ловит мутацию: выкладка помощника идёт через запись в ссылку
        документов (коммит `_pult.py` перед сбором) — лок фиксирует коммит
        с помощником."""
        seen = []

        def collect(tdir, *args, **kwargs):
            seen.append((Path(tdir) / "acceptance_tests" / HELPER_NAME).is_file())
            return True, "1 test collected"

        with mock.patch.object(acceptance, "collect", side_effect=collect):
            out = self.capture(fsm.cmd_advance, TASK)

        task = store.get_task(self.conn, TASK)
        self.assertEqual(task["state"], "in_dev", out)
        self.assertEqual(seen, [True], "сухой сбор шёл без выложенного помощника")
        locked = task["tests_locked_sha"]
        self.assertTrue(locked)
        tree = git(self.task_repo(), "ls-tree", "-r", "--name-only", locked)
        self.assertNotIn(HELPER_NAME, [Path(p).name for p in tree.splitlines()])
        self.assertIn(f"tasks/{TASK}/acceptance_tests/test_ac1_sandbox.py",
                      tree.splitlines())
        self.assert_no_leak()
        self.assertFalse((self.wt / "tasks" / TASK).exists())


if __name__ == "__main__":
    unittest.main()
