"""Разовые проверки сохранённого теста, заявок мутаций и PLAN.md.

Группа: разовый
Красен до реализации: проекция сохраняет tests/, указатель молчит об их пропуске, PLAN.md ещё не создан.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, TASK_ID, artifact_text  # noqa: E402
from tests import test_01m4ag4d90b3zyzgh2ec1b48r0_map_projection as durable  # noqa: E402


class TaskContractTest(unittest.TestCase):
    def _run_durable(self, cls, method):
        case = cls(methodName=method)
        result = unittest.TestResult()
        case.run(result)
        details = "\n".join(message for _, message in result.failures + result.errors)
        self.assertTrue(result.wasSuccessful(), details)

    def test_ac1_tests_sections_and_fields_disappear(self):
        """Проверка вложенных и обычных тестовых секций выполняется в постоянной планке.

        Ловит мутацию: фильтр сохраняет вложенный tests/ модуль, и
        постоянный сценарий возвращает провал этому методу.
        """
        self._run_durable(durable.ProjectionTest, "test_ac1_tests_sections_and_their_fields_disappear")

    def test_ac2_other_sections_preserve_previous_bytes(self):
        """Проверка шапки и байтов секций пульта и сценариев выполняется в постоянной планке.

        Ловит мутацию: проекция обрезает «Импортирует» у scripts/,
        и постоянный сценарий возвращает провал этому методу.
        """
        self._run_durable(durable.ProjectionTest, "test_ac2_other_sections_and_header_keep_previous_projection")

    def test_ac3_projection_is_pure_and_idempotent(self):
        """Повторная проекция карты трёх видов проходит проверку без ввода и вывода.

        Ловит мутацию: второй проход меняет scripts/ или читает диск,
        и постоянный сценарий возвращает провал этому методу.
        """
        self._run_durable(durable.ProjectionTest, "test_ac3_projection_is_idempotent_and_does_not_access_io")

    def test_ac4_full_map_preserves_tests_sections(self):
        """Полная карта с одним и несколькими tests/ модулями проверяется постоянной планкой.

        Ловит мутацию: render удаляет «Импортируется» у tests/,
        и постоянный сценарий возвращает провал этому методу.
        """
        self._run_durable(durable.ProjectionTest, "test_ac4_render_keeps_full_tests_sections")

    def test_ac5_note_explains_omission_and_full_map(self):
        """Указание о пропуске и пути полной карты проверяется постоянной планкой.

        Ловит мутацию: из указателя убирают факт отсутствия tests/,
        и постоянный сценарий возвращает провал этому методу.
        """
        self._run_durable(durable.ProjectionTest, "test_ac5_projection_note_names_omission_and_full_map")

    def test_ac6_developer_receives_projection_and_note(self):
        """Бриф разработчика с тестовой картой проверяется постоянной планкой.

        Ловит мутацию: бриф включает полную карту с tests/,
        и постоянный сценарий возвращает провал этому методу.
        """
        self._run_durable(durable.BriefProjectionTest, "test_ac6_developer_brief_carries_projection_and_note")

    def test_ac7_analyst_receives_projection_and_note(self):
        """Бриф аналитика с тестовой картой проверяется постоянной планкой.

        Ловит мутацию: бриф включает полную карту с tests/,
        и постоянный сценарий возвращает провал этому методу.
        """
        self._run_durable(durable.BriefProjectionTest, "test_ac7_analyst_brief_carries_projection_and_note")

    def test_ac8_existing_size_test_and_threshold_remain(self):
        """Размер реальной карты по-прежнему сравнивается с прежним порогом.

        Ловит мутацию: разработчик снимает утверждение assertLessEqual
        или повышает CONTEXT_FILE_MAX_BYTES ради зелёной проверки.
        """
        source = (Path(CODE_ROOT) / "tests" / "test_codebase_map.py").read_text(
            encoding="utf-8")
        tree = ast.parse(source)
        cls = next((node for node in tree.body
                    if isinstance(node, ast.ClassDef)
                    and node.name == "RealMapProjectionSizeTest"), None)
        self.assertIsNotNone(cls)
        method = next((node for node in cls.body
                       if isinstance(node, ast.FunctionDef)
                       and node.name == "test_projection_of_committed_map_fits_the_brief_threshold"), None)
        self.assertIsNotNone(method)
        calls = [node for node in ast.walk(method)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                 and node.func.attr == "assertLessEqual"]
        self.assertTrue(calls, "проверка размера удалена")
        self.assertTrue(any(
            len(call.args) >= 2
            and isinstance(call.args[0], ast.Name)
            and call.args[0].id == "size"
            and isinstance(call.args[1], ast.Attribute)
            and isinstance(call.args[1].value, ast.Name)
            and call.args[1].value.id == "config"
            and call.args[1].attr == "CONTEXT_FILE_MAX_BYTES"
            for call in calls), "прежнее сравнение размера с порогом изменено")
        from orchestrator import config
        self.assertEqual(131072, config.CONTEXT_FILE_MAX_BYTES)

    def test_ac9_ac1_to_ac7_methods_claim_observable_mutations(self):
        """Каждый долгоживущий метод AC-1..AC-7 называет ловимую мутацию.

        Ловит мутацию: при переносе теста из планки в tests/ теряют
        строку «Ловит мутацию», и критерий качества теряет охрану.
        """
        paths = list((Path(CODE_ROOT) / "tests").glob(
            f"test_{TASK_ID.lower()}_*.py"))
        self.assertTrue(paths, "долгоживущие тесты задачи не найдены")
        found = {}
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    match = re.fullmatch(r"test_ac([1-7])_.+", node.name)
                    if match:
                        found[int(match.group(1))] = ast.get_docstring(node) or ""
        self.assertEqual(set(range(1, 8)), set(found))
        for number, doc in found.items():
            self.assertIn("Ловит мутацию:", doc, f"AC-{number}")

    def test_ac10_plan_gives_before_after_sizes_and_days(self):
        """План указывает размеры проекции на main и запас в днях.

        Ловит мутацию: разработчик записывает новый размер без исходного
        или забывает пересчитать запас при росте 5,5 тыс. байт в день.
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md отсутствует в ссылке документов")
        self.assertRegex(plan, r"(?i)main")
        before = re.search(r"(?is)проекц.{0,400}\bдо\b.{0,80}?(\d[\d ]*)\s*байт", plan)
        after = re.search(r"(?is)проекц.{0,400}\bпосле\b.{0,80}?(\d[\d ]*)\s*байт", plan)
        reserve = re.search(r"(?is)запас.{0,200}?(\d+(?:[,.]\d+)?)\s*(?:дн|сут)", plan)
        self.assertIsNotNone(before, "нет размера проекции до задачи")
        self.assertIsNotNone(after, "нет размера проекции после задачи")
        self.assertIsNotNone(reserve, "нет оценки запаса в днях")
        before_size = int(before.group(1).replace(" ", ""))
        after_size = int(after.group(1).replace(" ", ""))
        reserve_days = float(reserve.group(1).replace(",", "."))
        self.assertGreater(before_size, after_size)
        from orchestrator import config
        expected_days = (config.CONTEXT_FILE_MAX_BYTES - after_size) / 5500
        self.assertAlmostEqual(expected_days, reserve_days, delta=1.0)
        self.assertRegex(plan, r"5[,.]5\s*тыс|5500|5\s*500")
