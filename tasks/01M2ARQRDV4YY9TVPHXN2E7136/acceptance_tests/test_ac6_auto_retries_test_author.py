"""AC-6 (tasks/01M2ARQRDV4YY9TVPHXN2E7136/SPEC.md): отказ сухого сбора на
выходе `tests_writing` относится к тому же классу отказа, что и сегодняшний
отказ трассируемости AC — «шаг роли», не «вне зоны агента» по стоп-крану
T038 (`orchestrator/auto.py`): `auto` на этом отказе повторно запускает
test_author, а не останавливается навсегда; test_author получает в брифе
историю отказа предыдущего шага.

Зелёный с рождения: обе проверки этого файла — про уже существующую,
не меняющуюся этой задачей механику `orchestrator/auto.py`/
`orchestrator/brief.py` (стоп-кран T038 сравнивает КЛАССЫ подряд идущих
отказов только в состоянии `in_dev` — `tests_writing` в это сравнение не
попадает структурно, `auto.py::_advance_refusal`/`other_class_refusal`;
история отказов `brief.advance_refusal_history` читает ЛЮБОЙ журналируемый
`fsm`-отказ независимо от его текста). Ни один из двух механизмов не
меняется этой задачей — тест фиксирует текстом отказа AC-5 («переход
отклонён: планка не собирается»), что ОНИ ПРИМЕНЯТСЯ к нему так же, как и
к любому другому отказу `tests_writing`, и защищает именно от регрессии
этого сочетания (например, от классификации `tests_writing` наравне с
`in_dev` при последующей правке auto.py).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import brief, config, fsm, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402
from tests.test_auto_cycle import AutoCycleTest, FakeAdvance  # noqa: E402

COLLECT_REFUSAL_TEXT = "переход отклонён: планка не собирается"


class DryCollectDoesNotTripTheStopCraneTest(AutoCycleTest):
    """`auto` не встаёт стоп-краном T038 на двух подряд одинаковых отказах
    сухого сбора в `tests_writing`."""

    def setUp(self):
        super().setUp()
        self.set_state("tests_writing")
        # Холостой лимит шагов (config.AUTO_STALL_STEPS_LIMIT) — отдельный,
        # не предмет этого теста стоп-триггер (тот же приём, что
        # AutoStopsOnRepeatedAdvanceRefusalTest.setUp в tests/test_auto_cycle.py):
        # поднят выше AUTO_MAX_STEPS, чтобы он не сработал раньше того, что
        # проверяется здесь.
        self.patch_object(config, "AUTO_STALL_STEPS_LIMIT",
                          config.AUTO_MAX_STEPS + 1)
        self.advance = FakeAdvance()
        self.patch_object(fsm, "cmd_advance", self.advance)

    def test_ac6_identical_collect_refusal_twice_does_not_stop_the_cycle(self):
        """Два подряд отказа сухого сбора одним и тем же текстом — цикл
        идёт до штатного лимита шагов, `test_author` вызывается на каждом
        из них, а не останавливается после второго.

        Ловит мутацию: отказ `tests_writing` начинает участвовать в
        сравнении «два подряд отказа одним текстом» стоп-крана T038 (как
        сегодня участвует отказ `in_dev`) — цикл встал бы уже на втором
        шаге, `self.advance.calls` не дошло бы до `config.AUTO_MAX_STEPS`."""
        self.advance.script = [COLLECT_REFUSAL_TEXT, COLLECT_REFUSAL_TEXT]

        out = self.auto()

        self.assertEqual(
            self.advance.calls, config.AUTO_MAX_STEPS,
            "цикл остановился раньше лимита — отказ сухого сбора в "
            "tests_writing ошибочно классифицирован как «другой класс»")
        self.assertIn(f"лимит {config.AUTO_MAX_STEPS} шагов", out)
        self.assertNotIn(
            f"почини причину и повтори artel.py advance {self.TASK}", out)


class DryCollectRefusalReachesTestAuthorBriefTest(TmpRootTest):
    """Текст отказа AC-5 доходит до истории отказов брифа следующего
    запуска `test_author` — тем же общим механизмом, что и любой другой
    отказ `tests_writing` (SPEC T078, `store.refusal_history`/
    `brief.advance_refusal_history`)."""

    TASK = "01DRYCOLLECTBRIEFHIST"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        store.insert_task(store.db(), self.TASK, "заголовок", "tests_writing",
                          f"task/{self.TASK.lower()}", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def test_ac6_refusal_text_surfaces_in_test_author_brief_history(self):
        """Запись «переход отклонён: планка не собирается» — в истории
        отказов, которую видит следующий запуск test_author.

        Ловит мутацию: `fsm_advance.tests_writing` журналирует отказ сухого
        сбора ПОД ДРУГИМ actor'ом/действием, не через `store.journal(conn,
        task_id, "fsm", "переход отклонён: планка не собирается", detail)`
        — `store.refusal_history` (фильтр `actor == "fsm"` и префикс
        `REFUSAL_ACTION_PREFIX`) его не найдёт, история останется пустой."""
        conn = store.db()
        store.journal(conn, self.TASK, "fsm", COLLECT_REFUSAL_TEXT,
                      "хвост pytest: ModuleNotFoundError: No module named 'x'")

        text = brief.advance_refusal_history(
            conn, self.TASK, "test_author", "tests_writing")

        self.assertIn(COLLECT_REFUSAL_TEXT, text)
        self.assertIn("ModuleNotFoundError", text)


if __name__ == "__main__":
    unittest.main()
