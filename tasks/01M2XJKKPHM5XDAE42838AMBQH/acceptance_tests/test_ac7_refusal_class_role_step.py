"""AC-7 (tasks/01M2XJKKPHM5XDAE42838AMBQH/SPEC.md): отказ «планка читает
артефакты с диска» — того же класса, что остальные отказы
`tests_writing`: он попадает в историю отказов брифа роли
(`brief.advance_refusal_history`) и шаг `test_author` повторяется,
стоп-кран T038 не срабатывает раньше шага роли.

Зелёный с рождения: обе механики существуют и этой задачей не меняются
— `store.refusal_history`/`brief.advance_refusal_history` отбирают любой
`fsm`-отказ визита состояния по префиксу действия, а стоп-кран T038
(`orchestrator/auto.py`) сравнивает подряд идущие отказы только в
`in_dev`. Тест фиксирует, что ИМЕННО ЭТОТ текст отказа попадает под них
так же, как остальные (тот же приём, что уже применён планкой
tasks/01M2ARQRDV4YY9TVPHXN2E7136/acceptance_tests/
test_ac6_auto_retries_test_author.py к отказу сухого сбора), и держит
оборону против двух правдоподобных решений разработчика: завести отказ
под своим actor'ом/действием мимо `store.journal(..., "fsm", ...)` либо
внести его в список «роль ещё не закончила»
(`brief._ROLE_NOT_FINISHED_REFUSAL_ACTIONS`), из которого история брифа
вычитает записи.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402
from orchestrator import brief, config, fsm, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402
from tests.test_auto_cycle import AutoCycleTest, FakeAdvance  # noqa: E402

REFUSAL_ACTION = _sandbox.REFUSAL_ACTION
REFUSAL_DETAIL = ('test_ac1_plan.py:12: чтение артефакта задачи с диска '
                  '— читай из артефактной ветки: '
                  'gitcmd.show(artifact_branch.branch_name(TASK_ID), '
                  '"tasks/<id>/PLAN.md")')


class RefusalReachesTestAuthorBriefTest(TmpRootTest):
    """Текст отказа доходит до истории отказов брифа следующего запуска
    `test_author` — тем же общим механизмом, что и любой другой отказ
    `tests_writing`."""

    TASK = "01DISKREADBRIEFHIST0"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        store.insert_task(store.db(), self.TASK, "заголовок", "tests_writing",
                          f"task/{self.TASK.lower()}", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def test_ac7_refusal_text_surfaces_in_test_author_brief_history(self):
        """Запись «переход отклонён: планка читает артефакты с диска» с
        текстом ошибок в `detail` видна в блоке истории отказов, который
        `brief.advance_refusal_history` отдаёт следующему запуску
        `test_author` в состоянии `tests_writing`.

        Ловит мутацию: отказ журналируется мимо общего пути (свой
        `actor`, действие без префикса «переход отклонён») либо внесён в
        `brief._ROLE_NOT_FINISHED_REFUSAL_ACTIONS` как «роль ещё не
        закончила» — выборка истории окажется пустой строкой, и роль
        пойдёт на повтор вслепую, не зная, что именно ей вернули.
        """
        conn = store.db()
        store.journal(conn, self.TASK, "fsm", REFUSAL_ACTION, REFUSAL_DETAIL)

        text = brief.advance_refusal_history(
            conn, self.TASK, "test_author", "tests_writing")

        self.assertIn(REFUSAL_ACTION, text)
        self.assertIn("gitcmd.show(artifact_branch.branch_name(TASK_ID)", text)


class RefusalDoesNotTripTheStopCraneTest(AutoCycleTest):
    """`auto` не встаёт стоп-краном T038 на двух подряд одинаковых
    отказах этого класса в `tests_writing` — шаг роли повторяется."""

    def setUp(self):
        super().setUp()
        self.set_state("tests_writing")
        # Холостой лимит шагов (config.AUTO_STALL_STEPS_LIMIT) —
        # отдельный, не предмет этого теста стоп-триггер: поднят выше
        # AUTO_MAX_STEPS, чтобы не сработал раньше проверяемого здесь
        # (тот же приём, что в tests/test_auto_cycle.py).
        self.patch_object(config, "AUTO_STALL_STEPS_LIMIT",
                          config.AUTO_MAX_STEPS + 1)
        self.advance = FakeAdvance()
        self.patch_object(fsm, "cmd_advance", self.advance)

    def test_ac7_identical_refusal_twice_does_not_stop_the_cycle(self):
        """Два подряд отказа «планка читает артефакты с диска» одним и
        тем же текстом — цикл идёт до штатного лимита шагов, шаг роли
        запускается на каждом из них, а не останавливается после
        второго.

        Ловит мутацию: отказ отнесён к классу «вне зоны агента» —
        например, журналируется в состоянии, попадающем в сравнение
        «два подряд отказа одним текстом» стоп-крана T038, как сегодня
        отказ `in_dev` — цикл встал бы на втором шаге, и
        `self.advance.calls` не дошло бы до `config.AUTO_MAX_STEPS`.
        """
        self.advance.script = [REFUSAL_ACTION, REFUSAL_ACTION]

        out = self.auto()

        self.assertEqual(
            self.advance.calls, config.AUTO_MAX_STEPS,
            "цикл остановился раньше лимита — отказ «планка читает "
            "артефакты с диска» ошибочно классифицирован как «другой "
            "класс», шаг test_author не повторяется")
        self.assertIn(f"лимит {config.AUTO_MAX_STEPS} шагов", out)
        self.assertNotIn(
            f"почини причину и повтори artel.py advance {self.TASK}", out)


if __name__ == "__main__":
    unittest.main()
