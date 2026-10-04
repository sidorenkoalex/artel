"""AC-8: имя `_pult.py` зарезервировано за помощником пульта.

Файл `_pult.py` на первом уровне планки — в ссылке документов либо в
черновике `tests_writing` (каталог документов, который автокоммит шага
переносит в ссылку) — отклоняет выход из `tests_writing` именованным
действием с подсказкой «имя занято помощником пульта». При выкладке
планки, несущей свой `_pult.py`, на диске оказывается файл пульта.

Сценарий — настоящий git (`_scenario.PlankHelperSandbox`), сухой сбор
планки подменён ответом «собралось»: предмет — гейт имени, не pytest.
Контрольный тест той же песочницы без `_pult.py` доходит до `in_dev` —
отказ в остальных тестах вызван именно зарезервированным именем.

Группа: разовый
Красен до реализации: резервирования имени нет — планка со своим `_pult.py` проходит выход из `tests_writing` в `in_dev`, а выкладка кладёт на диск файл планки, не помощник пульта.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _scenario import (HELPER_NAME, PLANK_OWN_PULT, PLANK_TEST, TASK,  # noqa: E402
                       PlankHelperSandbox, load_helper)

from orchestrator import acceptance, checkpoint, config, fsm, runner, store  # noqa: E402

HINT = "имя занято помощником пульта"
REFUSAL_PREFIX = "переход отклонён"


class ReservedNameGateTest(PlankHelperSandbox):

    def setUp(self):
        super().setUp()
        self.commit_to_ref({"acceptance_tests/test_ac1_sandbox.py": PLANK_TEST},
                           "планка")

    def advance(self) -> str:
        before = len(store.task_steps(self.conn, TASK))
        with mock.patch.object(acceptance, "collect",
                               return_value=(True, "1 test collected")):
            out = self.capture(fsm.cmd_advance, TASK)
        self.new_rows = [dict(r) for r in store.task_steps(self.conn, TASK)][before:]
        return out

    def state(self) -> str:
        return store.get_task(self.conn, TASK)["state"]

    def assert_reserved_name_refusal(self, out: str) -> None:
        self.assertEqual(self.state(), "tests_writing", out)
        refusals = [r for r in self.new_rows
                    if (r["action"] or "").startswith(REFUSAL_PREFIX)]
        self.assertTrue(refusals, f"отказ перехода не записан в журнал:\n{out}")
        self.assertTrue(
            any(r["action"].strip() != REFUSAL_PREFIX for r in refusals),
            f"отказ без именованного действия: {refusals}")
        hint_lines = [line for line in out.splitlines()
                      if line.strip().startswith("дальше:") and HINT in line]
        self.assertTrue(hint_lines,
                        f"подсказка отказа не содержит «{HINT}»:\n{out}")

    def test_ac8_control_plank_without_reserved_name_reaches_in_dev(self):
        """Контроль песочницы: планка без `_pult.py` выходит из `tests_writing`.

        Сценарий: в ссылке только `test_ac1_sandbox.py`; `advance` переводит
        задачу в `in_dev`, ни одна строка вывода не называет «имя занято
        помощником пульта».

        Ловит мутацию: гейт имени срабатывает на собственный помощник,
        выложенный пультом для сухого сбора (сверяет каталог выкладки, а не
        планку ссылки/черновика) — любая задача застревает в
        `tests_writing` с этой подсказкой."""
        out = self.advance()

        self.assertEqual(self.state(), "in_dev", out)
        self.assertNotIn(HINT, out)

    def test_ac8_reserved_name_in_docs_ref_refuses_exit(self):
        """`_pult.py` в планке ссылки документов отклоняет выход из `tests_writing`.

        Сценарий: в ссылке рядом с тестом лежит свой `acceptance_tests/
        _pult.py`; `advance` оставляет задачу в `tests_writing`, журнал
        получает отказ с именованным действием, строка «дальше: …»
        содержит «имя занято помощником пульта».

        Ловит мутацию: проверка имени снята или сравнивает не то имя
        (`_plank.py`) — задача уходит в `in_dev`, отказа и подсказки нет."""
        self.commit_to_ref({f"acceptance_tests/{HELPER_NAME}": PLANK_OWN_PULT},
                           "планка со своим _pult.py")

        out = self.advance()

        self.assert_reserved_name_refusal(out)

    def test_ac8_reserved_name_in_draft_refuses_exit(self):
        """`_pult.py` в черновике `tests_writing` отклоняет выход.

        Сценарий: шаг test_author начат (`runner.role_cwd` выложил каталог
        документов), роль кладёт `acceptance_tests/_pult.py` в черновик —
        каталог документов, шаг завершается автокоммитом
        (`checkpoint.commit_step_artifacts`), затем `advance`: задача
        остаётся в `tests_writing`, отказ именован, подсказка содержит «имя
        занято помощником пульта».

        Ловит мутацию: резервирование проверяет только ссылку, а
        автокоммит шага молча отбрасывает `_pult.py` черновика без записи
        для гейта — выход проходит в `in_dev`, роль не узнаёт, что её файл
        потерян."""
        runner.role_cwd(self.conn, TASK, config.DEFAULT_TARGET)
        draft = self.docs_dir() / "acceptance_tests" / HELPER_NAME
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(PLANK_OWN_PULT, encoding="utf-8")
        checkpoint.commit_step_artifacts(self.conn, TASK, "test_author")

        out = self.advance()

        self.assert_reserved_name_refusal(out)


class PultFileWinsOnMaterializationTest(PlankHelperSandbox):

    def test_ac8_materialize_from_branch_lays_pult_file_over_plank_file(self):
        """Выкладка из ссылки: на диске `_pult.py` пульта, не файл планки.

        Сценарий: ссылка несёт тест и свой `acceptance_tests/_pult.py`;
        после `materialize_from_branch` файл на диске — не текст планки, а
        помощник: модуль с `TASK_ID` задачи и функцией `artifact_text`.

        Ловит мутацию: помощник кладётся до файлов ссылки (`_write_plank`
        перетирает его файлом планки) — на диске текст планки,
        `PLANK_OWN_PULT` вместо `TASK_ID`."""
        self.commit_to_ref({"acceptance_tests/test_ac1_sandbox.py": PLANK_TEST,
                            f"acceptance_tests/{HELPER_NAME}": PLANK_OWN_PULT},
                           "планка со своим _pult.py")

        acceptance.materialize_from_branch(TASK, self.ref, self.wt)

        self.assertNotEqual(self.helper_path.read_text(encoding="utf-8"),
                            PLANK_OWN_PULT)
        helper = load_helper(self.helper_path)
        self.assertEqual(getattr(helper, "TASK_ID", None), TASK)
        self.assertTrue(callable(getattr(helper, "artifact_text", None)))
        self.assertFalse(hasattr(helper, "PLANK_OWN_PULT"))

    def test_ac8_materialize_files_lays_pult_file_over_draft_file(self):
        """Выкладка черновика: на диске `_pult.py` пульта, не файл черновика.

        Сценарий: черновик `plank-run` несёт тест и свой `_pult.py`; после
        `materialize_files` на диске помощник пульта (`TASK_ID` задачи,
        `artifact_text`), а не текст черновика.

        Ловит мутацию: `materialize_files` кладёт помощник только при его
        отсутствии в наборе файлов (или до записи черновика) — на диске
        файл черновика."""
        acceptance.materialize_files(
            TASK, {"test_ac1_sandbox.py": PLANK_TEST.encode("utf-8"),
                   HELPER_NAME: PLANK_OWN_PULT.encode("utf-8")}, self.wt)

        self.assertNotEqual(self.helper_path.read_text(encoding="utf-8"),
                            PLANK_OWN_PULT)
        helper = load_helper(self.helper_path)
        self.assertEqual(getattr(helper, "TASK_ID", None), TASK)
        self.assertTrue(callable(getattr(helper, "artifact_text", None)))
        self.assertFalse(hasattr(helper, "PLANK_OWN_PULT"))


if __name__ == "__main__":
    unittest.main()
