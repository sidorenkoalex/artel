"""Приёмочные тесты 01M1RHFRQ2C0P4A57XJJ1WZV8N — AC-1, AC-4 (часть
`orchestrator/auto.py`) и AC-9.

Красен до реализации: `orchestrator/auto.py::_cmd_auto` (строки 291-306,
прочитано перед написанием этого файла) зовёт `fsm.cmd_advance` СРАЗУ,
без предварительной проверки журнала на «был ли уже шаг роли developer
после последнего возврата в in_dev» — предварительный `advance` увидит
PLAN.md `status: ready` (фикстура ниже не трогает файл) и продвинет
задачу в `review` мимо developer; на текущем коде REVIEW.md той же
итерации, ещё не «учтённой» вторично (`reviewed_iter`), даже уводит цикл
обратно в `in_dev` и снова в `review` тем же путём, прежде чем упереться
в «вердикт уже учтён» и наконец позвать РЕВЬЮВЕРА (не developer) —
проверено прогоном этого файла на коде до фикса. Тест ниже (AC-1) требует
ровно ОДНОЙ записи журнала `agent run finished` и именно под именем
`developer`; ни оскилляция, ни чужая роль его не удовлетворяют, и он
покраснеет на текущем коде. AC-4 читает журнал того же вызова и ожидает
буквальную фразу «замечания ревью не отработаны: нет шага developer
после итерации 1» — в коде до этой задачи такой фразы не существует ни в
одном `store.journal(...)` вызове `orchestrator/auto.py`/`orchestrator/
fsm.py` (проверено `grep -rn "не отработаны" orchestrator/` — пусто),
так что и этот тест красен по той же причине.

AC-9 — регресс без новой логики (ANSWER-1, п.3): `tests_writing` уже
сегодня даёт `test_author` шаг на КАЖДОЙ итерации после отказа
трассируемости (`orchestrator/auto.py`, комментарий у `other_class_
refusal`, требование 4: класс «роль ждёт нового прогона» применяется
только к `in_dev`, не к `review`/`tests_writing`) — тест ниже зелёный уже
сегодня, эта задача обязана не сломать его.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AutoCycleTest, agent_run_finished_actors,  # noqa: E402
                      agent_step)
from orchestrator import store  # noqa: E402

SPEC_MD = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
budget_usd: 15
---

# SPEC: фикстура регресс-теста tests_writing

## Контекст
Фикстура приёмочного теста 01M1RHFRQ2C0P4A57XJJ1WZV8N, не связана с
реальной механикой пульта.

## Требования
1. Требование фикстуры.

## Критерии приёмки
AC-1. Критерий фикстуры.

## Не входит
- Всё остальное.
"""


class PreAdvanceYieldsToDeveloperAfterReviewReworkTest(AutoCycleTest):
    """`in_dev`, вошедший переходом `review -> in_dev` (замечания ревью),
    ещё не видел ни одного завершённого шага developer — PLAN.md уже
    `status: ready` с ПРЕЖНЕГО прогона разработчика (файл не тронут этим
    сценарием), REVIEW.md текущей итерации несёт `changes_requested`.
    """

    def setUp(self):
        super().setUp()
        self.write_plan("ready")
        self.write_review("changes_requested", 1)
        self.set_state("in_dev")
        # Журнал перехода `review -> in_dev`, тем же action/detail, что и
        # настоящий `orchestrator/fsm_advance.py::review` (строка 279:
        # `detail=f"замечания ревью, итерация {iters}"`) — `self.set_state`
        # выше правит колонку `state` напрямую (в обход FSM, по
        # соглашению `AutoCycleTest`), не журналируя переход, поэтому
        # запись добавляется явно здесь.
        store.journal(store.db(), self.TASK, "fsm", "state -> in_dev",
                      "замечания ревью, итерация 1")

    def test_ac1_developer_step_runs_before_any_preadvance_on_return_to_in_dev(self):
        """Ловит мутацию: убрать проверку журнала («был ли уже шаг
        developer с последнего state -> in_dev») перед предварительным
        `advance` — цикл снова прочитает готовый PLAN.md и продвинет
        задачу мимо developer (проверено: на текущем коде цикл в итоге
        зовёт РЕВЬЮВЕРА вместо него — см. докстринг модуля).
        """
        conn = store.db()
        self.agent.script = [
            agent_step(conn, self.TASK, lambda: self.set_state("escalated"))]

        out = self.auto()

        self.assertEqual(
            agent_run_finished_actors(conn, self.TASK), ["developer"],
            "developer не отработал шаг ровно один раз до какого-либо "
            "перехода — предварительный advance сам продвинул задачу (или "
            "шаг достался другой роли) по готовому PLAN.md")
        self.assertEqual(self.state(), "escalated")
        self.assertNotIn(
            "шаг developer не нужен: переход выполнен по готовым "
            "артефактам (in_dev -> review)", out,
            "цикл пропустил шаг developer и продвинул задачу сам")


class NamedAndJournaledAutoRefusalTest(AutoCycleTest):
    """AC-4 (часть `auto.py`): отказ этого рубежа именован и журналируется
    с номером итерации.
    """

    def setUp(self):
        super().setUp()
        self.write_plan("ready")
        self.write_review("changes_requested", 1)
        self.set_state("in_dev")
        store.journal(store.db(), self.TASK, "fsm", "state -> in_dev",
                      "замечания ревью, итерация 1")

    def test_ac4_auto_names_the_iteration_of_the_unresolved_review(self):
        """Ловит мутацию: рубеж срабатывает (AC-1 держится), но причина в
        журнале — обобщённый текст без номера итерации (например «шаг
        developer ещё не был») — assertion на буквальную фразу AC-4
        падает, даже если поведение перехода уже верно.
        """
        conn = store.db()
        self.agent.script = [
            agent_step(conn, self.TASK, lambda: self.set_state("escalated"))]

        self.auto()

        rows = store.task_steps(conn, self.TASK)
        phrase = ("замечания ревью не отработаны: нет шага developer "
                 "после итерации 1")
        haystacks = [row["action"] for row in rows] + [row["detail"] for row in rows]
        self.assertTrue(
            any(phrase in text for text in haystacks),
            f"журнал не несёт именованной причины «{phrase}»: "
            f"{[(r['action'], r['detail']) for r in rows]}")


class TestsWritingTraceabilityRefusalRegressionTest(AutoCycleTest):
    """AC-9: `tests_writing`, отказавшая трассируемости AC (нет теста и
    нет пометки на объявленный AC-1), продолжает получать шаг test_author
    на КАЖДОЙ итерации подряд — поведение, зафиксированное регресс-тестом
    (ANSWER-1, п.3), не новая логика этой задачи.
    """

    def test_ac9_test_author_gets_a_step_on_every_iteration_after_the_refusal(self):
        """Зелёный с рождения: `other_class_refusal` (`orchestrator/
        auto.py`) уже сегодня применяет стоп-кран требования 4 только к
        `in_dev`, не к `tests_writing` — три подряд идентичных отказа
        трассируемости уже сегодня дают test_author три шага подряд, не
        останавливают цикл на втором. Ловит мутацию: расширение стоп-крана
        требования 4 на `tests_writing` «заодно» с фиксом in_dev (AC-1) —
        третий элемент сценария (эскалация) не наступит, `agent.calls`
        останется короче 3.
        """
        (self.tdir / "SPEC.md").write_text(
            SPEC_MD.format(task=self.TASK), encoding="utf-8")
        (self.tdir / "acceptance_tests").mkdir(parents=True, exist_ok=True)
        self.set_state("tests_writing")
        conn = store.db()
        self.agent.script = [
            agent_step(conn, self.TASK),
            agent_step(conn, self.TASK),
            agent_step(conn, self.TASK, lambda: self.set_state("escalated")),
        ]

        self.auto()

        self.assertEqual(
            len(self.agent.calls), 3,
            "test_author не получил шаг на каждой из трёх итераций подряд")


if __name__ == "__main__":
    import unittest
    unittest.main()
