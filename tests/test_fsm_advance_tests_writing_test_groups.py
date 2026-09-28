"""Юнит-тесты гейта групп приёмочных тестов на выходе `tests_writing`
(`orchestrator/advance_gates/tests_writing.py::_tests_writing_test_groups_gate`)
и проверки строки группы в `amend-tests` (`orchestrator/amend.py`) — SPEC
01M3N0BWYQ9KHVN41Z4G72706R, требования 1-2, 4-7; ADR-0020.

Правила самих признаков — `tests/test_guard_test_groups.py`; здесь —
подключение к переходу: отказ, журнал с подсказкой, повтор, область
(target, канарейка), один узел заявки мутации, сбор долгоживущего файла из
`tests/`.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import acceptance, amend, config, fsm, store  # noqa: E402
from scripts import guard  # noqa: E402
from tests.sandbox import LightTransitionSandbox  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

SPEC_ONE_AC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: гейт групп приёмочных тестов (юнит)

## Критерии приёмки

AC-1. Единственный критерий, покрытый тестом.
"""

CLAIM = "Ловит мутацию: фикстура гейта групп, исполнением не запускается."


def plank(group: str | None = guard.GROUP_LONG_LIVED, head: str = "",
          claim: str = CLAIM) -> str:
    group_line = "" if group is None else f"\nГруппа: {group}"
    return f'''"""Зелёный с рождения: фикстура гейта групп.{group_line}
"""
import unittest

from tests.sandbox import capture  # noqa: F401
{head}


class PlankTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        """Фикстурный критерий.

        {claim}
        """
        self.assertTrue(True)
'''


class _GroupsSandbox(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            SPEC_ONE_AC.format(task=self.TASK), encoding="utf-8")

    def write_plank(self, content: str, name: str = "test_ac.py") -> None:
        tests_dir = self.tdir / "acceptance_tests"
        if tests_dir.is_dir():
            shutil.rmtree(tests_dir)
        tests_dir.mkdir(parents=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def advance(self) -> list:
        """Записи журнала «переход отклонён: группы…» за этот `advance`."""
        self.set_state("tests_writing")
        before = len(store.task_steps(store.db(), self.TASK))
        with mock.patch.object(acceptance, "collect",
                               return_value=(True, "1 test collected")):
            self.capture(fsm.cmd_advance, self.TASK)
        return [r for r in store.task_steps(store.db(), self.TASK)[before:]
                if r["action"] == "переход отклонён: группы приёмочных тестов"]

    def set_row(self, **fields) -> None:
        conn = store.db()
        for key, value in fields.items():
            conn.execute(f"UPDATE tasks SET {key}=? WHERE id=?", (value, self.TASK))
        conn.commit()


class TestGroupsGateTest(_GroupsSandbox):

    def test_refusal_is_journalled_with_errors_and_hint(self):
        """Файл без строки группы и долгоживущий файл с признаком — задача
        в `tests_writing`, одна запись отказа несёт обе ошибки и подсказку
        «исправь файл … повтори».

        Ловит мутацию: гейт не подключён к `fsm_advance.tests_writing`
        (или подсказка только печатается, не попадает в `detail`) —
        задача уходит в `in_dev` / в журнале нет подсказки.
        """
        for content in (plank(None), plank(head="import _sandbox  # noqa: F401")):
            with self.subTest(content=content[:60]):
                self.write_plank(content)
                refusals = self.advance()
                self.assertEqual(self.state(), "tests_writing")
                self.assertEqual(len(refusals), 1)
                detail = refusals[0]["detail"]
                self.assertIn("acceptance_tests/test_ac.py", detail)
                self.assertRegex(detail, r"исправь файл.*повтори")

    def test_fixed_file_passes_on_retry(self):
        """Отказ по методу без заявки, затем исправленный файл — повторный
        `advance` уводит в `in_dev` без `amend-tests`.

        Ловит мутацию: гейт запоминает отказ (например, по записи журнала)
        и держит переход после исправления — задача остаётся в
        `tests_writing`.
        """
        self.write_plank(plank(claim="Без заявки."))
        self.assertTrue(self.advance())
        self.write_plank(plank())
        self.assertEqual(self.advance(), [])
        self.assertEqual(self.state(), "in_dev")

    def test_external_target_is_not_checked(self):
        """Задача внешнего target с файлом без строки группы — отказа
        гейта групп нет.

        Ловит мутацию: условие области снято (или написано по признаку
        «не канарейка») — внешняя задача получает отказ.
        """
        self.set_row(target="sled")
        self.write_plank(plank(None))
        self.assertEqual(self.advance(), [])

    def test_canary_task_of_default_target_is_checked(self):
        """Канареечная задача target `artel` с файлом без строки группы —
        отказ, как у обычной.

        Ловит мутацию: канарейка исключена из гейта (`if t["is_canary"]:
        return None`) — отказа нет.
        """
        self.set_row(is_canary=1)
        self.write_plank(plank(None))
        self.assertTrue(self.advance())

    def test_mutation_claim_goes_through_review_gate_node(self):
        """Заявка мутации долгоживущего файла проверяется узлом
        `guard.test_functions_without_mutation_claim` с текстом файла как
        HEAD.

        Ловит мутацию: гейт разбирает докстринги своей копией
        `MUTATION_CLAIM` — шпион узла не видит вызова с текстом файла.
        """
        content = plank(claim="Без заявки.")
        self.write_plank(content)
        spy = mock.Mock(wraps=guard.test_functions_without_mutation_claim)
        with mock.patch.object(guard, "test_functions_without_mutation_claim", spy):
            self.assertTrue(self.advance())
        spy.assert_any_call(None, content)


class CollectFromTestsDirTest(unittest.TestCase):

    def test_clean_long_lived_file_collects_from_tests_dir(self):
        """Долгоживущий файл без ошибок гейта групп, скопированный в
        `tests/` зеркала репозитория, собирается `pytest --collect-only`.

        Ловит мутацию: признак «импорт вне перечня» отвергает пакет
        `tests` — фикстура с `from tests.sandbox import capture` получает
        ошибку гейта (первое утверждение).
        """
        content = plank()
        self.assertEqual(guard.long_lived_errors_from_files(
            [("test_ac.py", content)], "01ABC") + guard.group_line_errors_from_files(
            [("test_ac.py", content)]), [])
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        for name in ("orchestrator", "scripts", "conftest.py", "pyproject.toml"):
            os.symlink(REPO_ROOT / name, tmp / name)
        (tmp / "tests").mkdir()
        for entry in ("__init__.py", "sandbox.py"):
            os.symlink(REPO_ROOT / "tests" / entry, tmp / "tests" / entry)
        (tmp / "tests" / "test_long_lived.py").write_text(content, encoding="utf-8")
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q",
             "-p", "no:cacheprovider", "tests/test_long_lived.py"],
            cwd=tmp, capture_output=True, text=True, timeout=110)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("test_ac1_first_criterion", res.stdout)


class AmendGroupLineTest(unittest.TestCase):

    TDIR = "tasks/01ABC/acceptance_tests"

    def errors(self, target: str, locked: dict | None, files: list) -> list:
        row = {"target": target, "tests_locked_sha": "abc"}
        with mock.patch.object(amend, "_branch_tests_snapshot",
                               return_value=locked):
            return amend._group_line_errors(row, self.TDIR, files)

    def test_post_rule_plank_is_checked(self):
        """Лок несёт строку группы — правка без неё даёт ошибку с именем
        файла. Подключение к обоим путям `amend-tests` сторожит
        `tests/test_amend.py::AmendGroupLineRefusalTest`.

        Ловит мутацию: `_group_line_errors` считает планкой «до правила»
        и лок, несущий строку группы (`plank_has_group_lines` не
        различает), — правка без строки группы проходит без ошибок.
        """
        locked = {f"{self.TDIR}/test_ac.py": plank(guard.GROUP_ONE_OFF)}
        errors = self.errors(config.DEFAULT_TARGET, locked,
                             [("acceptance_tests/test_ac.py", plank(None))])
        self.assertEqual(len(errors), 1)
        self.assertIn("test_ac.py", errors[0])

    def test_pre_rule_plank_external_target_and_unread_lock_are_not_checked(self):
        """Лок без строк группы, внешний target, нечитаемый лок — правка
        без строки группы ошибок не даёт.

        Ловит мутацию: `amend-tests` требует строку группы у любой планки
        без различения момента фиксации и target — старая планка
        получает ошибку.
        """
        edit = [("acceptance_tests/test_ac.py", plank(None))]
        old = {f"{self.TDIR}/test_ac.py": plank(None)}
        new = {f"{self.TDIR}/test_ac.py": plank(guard.GROUP_ONE_OFF)}
        self.assertEqual(self.errors(config.DEFAULT_TARGET, old, edit), [])
        self.assertEqual(self.errors("sled", new, edit), [])
        self.assertEqual(self.errors(config.DEFAULT_TARGET, None, edit), [])


if __name__ == "__main__":
    unittest.main()
