"""AC-2: выкладка кладёт `_pult.py` с подставленными значениями.

`materialize_from_branch` и `materialize_files` кладут `_pult.py` в
`tasks/<id>/acceptance_tests/` рабочей копии с id задачи, путём
репозитория ссылки документов, ревизией выкладки, базой диффа и источником
базы; повторная выкладка его не удаляет; `drop_from_code_copy` убирает
его вместе с планкой.

Имена констант базы, источника, репозитория и ревизии SPEC не называет —
тест ищет нужное значение среди открытых констант модуля, не навязывая
имя.

Группа: разовый
Красен до реализации: выкладка кладёт только файлы планки — `_pult.py` в каталоге выкладки нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _scenario import (PLANK_TEST, TASK, PlankHelperSandbox,  # noqa: E402
                       as_path_values, constant_values, load_helper)

from orchestrator import acceptance, artifact_branch  # noqa: E402


class MaterializationTest(PlankHelperSandbox):

    def setUp(self):
        super().setUp()
        self.commit_to_ref({"acceptance_tests/test_ac1_sandbox.py": PLANK_TEST},
                           "планка")

    def assert_substituted(self, helper, revision: str) -> None:
        values = constant_values(helper)
        self.assertEqual(getattr(helper, "TASK_ID", None), TASK)
        self.assertIn(self.task_repo().resolve(), as_path_values(values),
                      "путь репозитория ссылки документов не подставлен")
        self.assertIn(revision, values, "ревизия выкладки не подставлена")
        self.assertIn(self.expected_base(), values, "база диффа не подставлена")
        self.assertIn(self.expected_base_source(), values,
                      "источник базы не подставлен")

    def test_ac2_from_branch_lays_helper_with_values(self):
        """Выкладка из ссылки кладёт `_pult.py` с пятью значениями.

        Сценарий: `materialize_from_branch` по ссылке документов песочницы;
        рядом с тестом планки лежит `_pult.py`, его константы несут id
        задачи, путь репозитория ссылки (`workspace.task_repo`), sha
        головы ссылки на момент выкладки, `gitcmd.diff_base` и
        `gitcmd.diff_base_source` ветки задачи.

        Ловит мутацию: ревизия подставляется именем ссылки
        (`refs/artifacts/<id>`), а не её sha, или путь репозитория —
        корнем рабочей копии — значения среди констант нет."""
        revision = artifact_branch.ref_head(TASK)

        acceptance.materialize_from_branch(TASK, self.ref, self.wt)

        self.assertTrue((self.plank_dir / "test_ac1_sandbox.py").is_file())
        self.assertTrue(self.helper_path.is_file())
        self.assert_substituted(load_helper(self.helper_path), revision)

    def test_ac2_from_files_lays_helper_with_values(self):
        """Выкладка черновика кладёт `_pult.py` с теми же значениями.

        Сценарий: `materialize_files` с черновиком из одного теста; рядом
        лежит `_pult.py` с id задачи, путём репозитория ссылки, sha головы
        ссылки, базой и источником базы.

        Ловит мутацию: помощник кладёт только `materialize_from_branch`, а
        путь черновика (`plank-run` в `tests_writing`) его не получает —
        файла нет."""
        revision = artifact_branch.ref_head(TASK)

        acceptance.materialize_files(
            TASK, {"test_ac1_sandbox.py": PLANK_TEST.encode("utf-8")}, self.wt)

        self.assertTrue((self.plank_dir / "test_ac1_sandbox.py").is_file())
        self.assertTrue(self.helper_path.is_file())
        self.assert_substituted(load_helper(self.helper_path), revision)

    def test_ac2_repeated_materialization_keeps_helper(self):
        """Повторная выкладка не удаляет `_pult.py` как лишний файл.

        Сценарий: выкладка из ссылки, повторная выкладка из ссылки, затем
        выкладка черновика поверх — после каждой `_pult.py` на месте и
        несёт `TASK_ID` задачи.

        Ловит мутацию: помощник кладётся только когда его ещё нет на
        диске, а прунинг `_write_plank` убирает его как файл вне набора
        ссылки — после второй выкладки файла нет."""
        acceptance.materialize_from_branch(TASK, self.ref, self.wt)
        self.assertTrue(self.helper_path.is_file(), "после выкладки _pult.py нет")

        acceptance.materialize_from_branch(TASK, self.ref, self.wt)
        self.assertTrue(self.helper_path.is_file(),
                        "после повторной выкладки из ссылки _pult.py нет")
        self.assertEqual(load_helper(self.helper_path).TASK_ID, TASK)

        acceptance.materialize_files(
            TASK, {"test_ac1_sandbox.py": PLANK_TEST.encode("utf-8")}, self.wt)
        self.assertTrue(self.helper_path.is_file(),
                        "после выкладки черновика поверх _pult.py нет")
        self.assertEqual(load_helper(self.helper_path).TASK_ID, TASK)

    def test_ac2_drop_removes_helper_with_plank(self):
        """`drop_from_code_copy` убирает `_pult.py` вместе с планкой.

        Сценарий: выкладка из ссылки, `_pult.py` на месте; после
        `drop_from_code_copy` нет ни его, ни каталога `tasks/<id>/`
        рабочей копии.

        Ловит мутацию: выкладка дополнительно кладёт копию помощника вне
        `tasks/<id>/` (в корень рабочей копии, чтобы планка импортировала
        его без правки `sys.path`) — уборка каталога задачи её не видит,
        поиск находит оставшийся `_pult.py`."""
        acceptance.materialize_from_branch(TASK, self.ref, self.wt)
        self.assertTrue(self.helper_path.is_file())

        acceptance.drop_from_code_copy(TASK, self.wt)

        self.assertFalse(self.helper_path.exists())
        self.assertFalse((self.wt / "tasks" / TASK).exists())
        self.assertEqual(sorted(p.relative_to(self.wt).as_posix()
                                for p in self.wt.rglob("_pult.py")), [])


if __name__ == "__main__":
    unittest.main()
