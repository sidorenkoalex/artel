"""Приёмочные тесты 01M1TQ0TRCZPRZX22C4084NCPB — AC-14, AC-15, AC-16:
`verifying` в цикле `auto` остаётся состоянием с опросом CI, из
которого цикл сам продолжает движение дальше; остановка на красном CI
и потолок ожидания — без изменений по существу; подсказка «дальше:»
после красного CI называет `reject` применительно к `in_dev`.

Красен до реализации: test_ac14 падает, потому что сегодня `verifying`
(зелёный CI) продолжает цикл в `acceptance`
(`orchestrator/fsm_advance.py::verifying`, строка 312), а по новому
порядку обязан продолжить в `review` — тест ниже проверяет именно это
конечное состояние цикла `auto`, не сам факт «цикл не встал» (тот уже
работает сегодня, см. `tests/
test_auto_cycle.py::test_cycle_runs_the_task_from_dev_to_acceptance_when_ci_is_green`).

Зелёный с рождения: test_ac15_* и test_ac16 не меняются этой задачей по
существу (`_advance_verifying_poll`/`fsm_advance.verifying` — те же
функции, требования 4-5 их не трогают) — тесты зелёные уже сегодня,
закрепляют отсутствие регрессии на новом маршруте.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import FsmOrderScenarioTest, green_ci  # noqa: E402
from orchestrator import auto, config, fsm, runner, store  # noqa: E402


class FakeRun:
    """Подмена `runner.cmd_run`: вместо агента — заготовленные исходы
    шагов (тот же по смыслу приём, что `tests/test_auto_cycle.py::
    FakeRun`, сведённый к минимуму, нужному этому файлу)."""

    def __init__(self):
        self.script: list = []
        self.calls: list = []
        self.limit = None

    def arm(self, steps: int) -> None:
        self.limit = len(self.calls) + steps

    def __call__(self, task_id: str, session_id=None) -> None:
        if self.limit is not None and len(self.calls) >= self.limit:
            raise AssertionError("цикл не остановился вовремя")
        self.calls.append(task_id)
        conn = store.db()
        role = runner.step_role(store.get_task(conn, task_id))
        if self.script:
            self.script.pop(0)()
        store.journal(conn, task_id, role, "agent run finished",
                     "rc=0, тестовая заглушка приёмочного теста")


class AutoVerifyingLoopTest(FsmOrderScenarioTest):

    def setUp(self):
        super().setUp()
        self.agent = FakeRun()
        self._patch(runner, "cmd_run", self.agent)

    def auto(self) -> str:
        self.agent.arm(config.AUTO_MAX_STEPS)
        return self.capture(auto.cmd_auto, self.TASK)

    def test_ac14_auto_continues_past_verifying_into_review_on_green_ci(self):
        """Цикл `auto`, начатый из `in_dev`, сам (без ручного `advance`)
        доходит до `review` через `verifying` на зелёном CI — единственный
        переход `state -> review` этого вызова несёт в detail'е ИМЕННО
        строку статуса CI (то, чем `verifying` помечает СВОЙ переход), не
        текст, которым сегодня помечает прямой переход `in_dev -> review`
        ("MR готов — прогон ревьювера"). developer и reviewer позваны
        ровно по разу, `verifying` не потребовал третьего вызова агента
        (в нём нет роли). Цикл идёт дальше `review` в `acceptance` тем же
        ходом (REVIEW.md уже approved) — это ожидаемое, не предмет ЭТОГО
        теста.

        Ловит мутацию: `in_dev` продолжает вести прямиком в `review`
        (старый маршрут не поменяли, `verifying` тут ни при чём) — запись
        `state -> review` в журнале найдётся (тот же action), но её
        detail останется "MR готов — прогон ревьювера", не строкой CI —
        сверка по detail отличит один переход от другого там, где сверка
        по одному имени action'а не отличила бы.
        """
        ci_note = "CI коммита aaaaaaaa зелёный (2 проверок), тест AC-14"
        with green_ci(note=ci_note):
            self.set_state("in_dev")
            self.agent.script = [
                lambda: self.write_plan("ready"),
                lambda: self.write_review("approved", 1),
            ]

            self.auto()

        transitions = [d for a, d in self.journal_actions()
                      if a == "state -> review"]
        self.assertEqual(len(transitions), 1,
                         "цикл не прошёл ровно один раз через переход "
                         "'state -> review'")
        self.assertIn(ci_note, transitions[0],
                      "переход в review не несёт статус CI verifying — "
                      "похоже, задача попала в review не через verifying")
        self.assertEqual(len(self.agent.calls), 2)

    def test_ac15_red_ci_stops_auto_immediately_same_as_before(self):
        """Зелёный с рождения: красный CI в `verifying` останавливает
        `auto` немедленно (не дожидаясь потолка), тем же путём
        `_advance_verifying_poll`/`config.AUTO_STOP_VERIFYING_RED`, что и
        до этой задачи — реорганизация переходов вокруг `verifying` не
        трогает эту логику.

        Ловит мутацию: остановка на красном CI перестала срабатывать
        (например, из-за путаницы в том, какое состояние теперь
        `verifying` в маршруте) — задача не осталась бы в 'verifying',
        либо в выводе не было бы причины остановки.
        """
        self.set_state("verifying")

        out = self.auto()

        self.assertEqual(self.task_row()["state"], "verifying")
        reason, _ = config.AUTO_STOP_VERIFYING_RED
        self.assertIn(reason, out)

    def test_ac15_ceiling_still_escalates_same_as_before(self):
        """Зелёный с рождения: потолок ожидания CI в `verifying`
        (`config.VERIFYING_CEILING_SEC`) по-прежнему эскалирует задачу,
        когда время с момента входа в состояние превышает его, — та же
        проверка `fsm._verifying_elapsed_seconds`, что и до этой задачи.

        Ловит мутацию: потолок больше не считается (например, время
        входа в `verifying` теперь берётся по-другому) — задача осталась
        бы в 'verifying' вместо 'escalated'.
        """
        self.set_state("verifying")
        stale = (datetime.now(timezone.utc)
                - timedelta(seconds=config.VERIFYING_CEILING_SEC + 60))
        conn = store.db()
        conn.execute("UPDATE tasks SET updated_at=? WHERE id=?",
                     (stale.strftime("%Y-%m-%d %H:%M:%SZ"), self.TASK))
        conn.commit()

        self.advance()

        self.assertEqual(self.state(), "escalated")
        details = [detail for _, detail in self.journal_actions()]
        self.assertTrue(
            any("потолок ожидания CI в verifying" in d for d in details),
            f"причина эскалации не найдена в журнале: {details}")

    def test_ac16_stop_hint_names_reject_and_reject_returns_to_in_dev(self):
        """Подсказка «дальше:» после остановки на красном CI называет
        команду `reject`, и её реальное исполнение переводит задачу
        именно в `in_dev` — не в какое-то другое состояние.

        Ловит мутацию: подсказка называет другую команду (или не
        называет команду вовсе), либо `reject` из `verifying` перестал
        вести в `in_dev`.
        """
        self.set_state("verifying")

        out = self.auto()

        self.assertIn(f"artel.py reject {self.TASK}", out)
        self.assertIn("дальше:", out)

        self.capture(fsm.cmd_reject, self.TASK, "CI красный — чиню")

        self.assertEqual(self.state(), "in_dev")


if __name__ == "__main__":
    import unittest
    unittest.main()
