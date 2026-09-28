"""AC-7, AC-8 — предохранитель повторных эскалаций и учёт эскалаций в
строке прогона задачей не меняются.

Источник — SPEC.md, «Критерии приёмки»:

AC-7. Предохранитель повторных эскалаций работает как до задачи:
`config.CANARY_MAX_ESCALATION_CYCLES` равен 3; превышение снимает задачу
исходом «не сошлась» с открытым алертом; `tests/test_canary.py::
DriveTaskEscalationCapTest` (оба метода) и `tests/
test_canary_budget_ceiling.py` зелены без правки их ожиданий.

AC-8. Учёт эскалаций в строке прогона и вердикт по маркеру шаблона не
изменились: `tests/test_canary.py::MetricsFromJournalTest` и
`tests/test_canary.py::ExpectedEscalationMarkerTest` зелены без правки их
ожиданий.

Зелёный с рождения: оба критерия держат СУЩЕСТВУЮЩЕЕ поведение (порог,
исход «не сошлась» с алертом, учёт эскалаций и вердикт по маркеру) —
задача меняет только текст ответа, и до её реализации всё перечисленное
уже работает; краснеть эти тесты обязаны на правке предохранителя или на
ослаблении чужих ожиданий, не на отсутствии кода задачи.

Порог сверяется не литералом «3», а значением в ТОЧКЕ РАСХОЖДЕНИЯ ветки
задачи с основной ветвью: «работает как до задачи» — это «задача его не
двигала». Зашитое сегодняшнее число закрепило бы под локом крутилку
Оператора и покраснело бы от её законного поворота (урок 28.08:
`MAX_PARALLEL_TASKS` в фикстуре залоченного теста; ADR-0018).

Чужие ожидания сверяются отношением «ни одно не исчезло»: набор ассертов
базы обязан остаться подмножеством набора ассертов ветки. Так тест ловит
ослабление и удаление ожидания, но не мешает законному ДОБАВЛЕНИЮ теста
в тот же класс.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _synthetic_answer  # noqa: E402
from orchestrator import canary, config, store  # noqa: E402
from tests.sandbox import SchemaConnTmpRootTest  # noqa: E402

CANARY_TEST_FILE = "tests/test_canary.py"
BUDGET_CEILING_TEST_FILE = "tests/test_canary_budget_ceiling.py"
CAP_TEST_CLASS = "DriveTaskEscalationCapTest"
METRICS_TEST_CLASS = "MetricsFromJournalTest"
MARKER_TEST_CLASS = "ExpectedEscalationMarkerTest"


def _assert_expectations_kept(testcase, rel: str, class_name: str = None):
    """Ни одно ожидание существующего теста не исчезло между базой диффа и
    рабочим деревом ветки задачи."""
    base = _synthetic_answer.assert_statements(
        _synthetic_answer.base_source(rel), class_name)
    head = _synthetic_answer.assert_statements(
        (_synthetic_answer.REPO_ROOT / rel).read_text(encoding="utf-8"),
        class_name)
    lost = sorted(base - head)
    testcase.assertEqual(
        [], lost,
        f"ветка задачи убрала или переписала ожидания {rel}"
        + (f"::{class_name}" if class_name else "") + f": {lost}")


class EscalationCapThresholdTest(unittest.TestCase):

    def test_ac7_escalation_cap_threshold_is_untouched_by_the_task(self):
        """Порог повторных эскалаций ветки задачи равен порогу в точке
        расхождения с основной веткой — задача его не двигала.

        Ловит мутацию: разработчик «подгоняет» предохранитель под новый
        текст (поднимает или снимает `config.CANARY_
        MAX_ESCALATION_CYCLES`), хотя SPEC относит это к «Не входит» —
        значение расходится с базой диффа, и тест краснеет.
        """
        name = "CANARY_MAX_ESCALATION_CYCLES"
        self.assertEqual(_synthetic_answer.base_config_value(name),
                         getattr(config, name),
                         "порог повторных эскалаций изменён веткой задачи")

    def test_ac7_existing_cap_expectations_are_not_edited(self):
        """Ожидания `DriveTaskEscalationCapTest` и
        `tests/test_canary_budget_ceiling.py` остались на месте.

        Ловит мутацию: чужое ожидание ослаблено вместо правки кода
        (`assert_called_once_with` -> `assert_called`, снятая проверка
        алерта) — ассерт базы не находится среди ассертов ветки, и тест
        краснеет.
        """
        _assert_expectations_kept(self, CANARY_TEST_FILE, CAP_TEST_CLASS)
        _assert_expectations_kept(self, BUDGET_CEILING_TEST_FILE)

    def test_ac7_existing_cap_tests_stay_green(self):
        """`DriveTaskEscalationCapTest` (оба метода) и весь
        `tests/test_canary_budget_ceiling.py` проходят на коде ветки
        задачи.

        Ловит мутацию: правка текста ответа задела ветку `escalated`
        цикла `_drive_task` (счётчик, развилка бюджетной эскалации,
        порядок проверок) — эти тесты краснеют, и красный код возврата
        прогона виден здесь.
        """
        code, tail = _synthetic_answer.run_pytest(
            f"{CANARY_TEST_FILE}::{CAP_TEST_CLASS}", BUDGET_CEILING_TEST_FILE)
        self.assertEqual(0, code, f"тесты предохранителя красные:\n{tail}")

    def test_ac8_escalation_accounting_expectations_are_not_edited(self):
        """Ожидания `MetricsFromJournalTest` и
        `ExpectedEscalationMarkerTest` остались на месте.

        Ловит мутацию: ожидание учёта эскалаций или вердикта по маркеру
        шаблона переписано под новое поведение вместо сохранения прежнего
        — ассерт базы не находится среди ассертов ветки, и тест краснеет.
        """
        _assert_expectations_kept(self, CANARY_TEST_FILE, METRICS_TEST_CLASS)
        _assert_expectations_kept(self, CANARY_TEST_FILE, MARKER_TEST_CLASS)

    def test_ac8_escalation_accounting_tests_stay_green(self):
        """`MetricsFromJournalTest` и `ExpectedEscalationMarkerTest`
        проходят на коде ветки задачи: учёт эскалаций в строке прогона и
        вердикт по маркеру шаблона не изменились.

        Ловит мутацию: `_escalation_notes`/`_task_metrics` начали считать
        эскалации иначе (например пропускать ту, что закрыта синтетическим
        ответом) — эти тесты краснеют, и красный код возврата виден здесь.
        """
        code, tail = _synthetic_answer.run_pytest(
            f"{CANARY_TEST_FILE}::{METRICS_TEST_CLASS}",
            f"{CANARY_TEST_FILE}::{MARKER_TEST_CLASS}")
        self.assertEqual(0, code, f"тесты учёта эскалаций красные:\n{tail}")


class EscalationCapBehaviourTest(SchemaConnTmpRootTest):
    """Повторные эскалации подряд на РЕАЛЬНОМ пути возврата (сам
    `_pass_escalated_with_synthetic_answer`, подменён только канал записи
    ANSWER — настоящий требует lease и артефактной ветки)."""

    def setUp(self):
        super().setUp()
        self.task = _synthetic_answer.TASK
        store.insert_task(self.conn, self.task, "Канареечная задача прогона",
                          "escalated", f"task/{self.task.lower()}-kanareyka",
                          config.DEFAULT_TARGET, 25.0, is_canary=True)
        store.update_task(self.conn, self.task, escalated_from="in_dev")

        def fake_auto(task_id):
            # Роль доработала, ревьювер снова вернул — задача эскалирует
            # заново; тот же сценарий, что у чужого теста предохранителя.
            if store.get_task(self.conn, task_id)["state"] == "in_dev":
                store.set_state(self.conn, task_id, "escalated", "test",
                                expected_state="in_dev")

        patcher = mock.patch.object(canary.auto, "cmd_auto",
                                    side_effect=fake_auto)
        patcher.start()
        self.addCleanup(patcher.stop)
        for module, name in ((canary.answer, "cmd_answer"),
                            (canary.cleanup, "cmd_kill")):
            patcher = mock.patch.object(module, name)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_ac7_cap_excess_kills_the_task_as_inconclusive_with_alert(self):
        """Превышение порога повторных эскалаций снимает задачу: штатный
        `cleanup.cmd_kill`, открытый алерт Оператору и исход отчёта «не
        сошлась».

        Ловит мутацию: закрытие эскалации синтетическим ответом перестало
        считаться циклом предохранителя (счётчик двигают не там, где
        возвращают задачу) — `_drive_task` крутил бы `escalated` <->
        `in_dev` без снятия задачи: `cmd_kill` не вызван, алерта нет,
        исход не «не сошлась».
        """
        canary._drive_task(self.conn, self.task)

        canary.cleanup.cmd_kill.assert_called_once_with(self.task)
        alert_targets = [row["target"]
                         for row in store.open_alerts(self.conn, "threshold")]
        self.assertIn(self.task, alert_targets,
                      "алерт Оператору о снятой задаче не открыт")
        steps = store.task_steps(self.conn, self.task)
        note = canary._kill_outcome_note(self.conn, self.task, steps)
        self.assertTrue(note.startswith("не сошлась"),
                        f"исход прогона не «не сошлась»: {note!r}")
        escalations = sum(1 for row in steps
                          if row["action"] == "state -> escalated")
        self.assertLessEqual(escalations, config.CANARY_MAX_ESCALATION_CYCLES,
                             "эскалаций больше, чем позволяет порог")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
