"""Приёмочные тесты 01M2XFSJ1Z7BS6HR69SAT1D81Y — AC-5, AC-6: что
происходит ПОСЛЕ того, как роль получила свой шаг, и как долго живёт
маркер эскалации.

AC-5 — оба исхода шага `test_author` в `tests_writing`: пометка снята —
переход в `in_dev`; пометка оставлена — НОВАЯ эскалация, с новым
`answer_baseline`, и следующий `approve` законно требует очередной ANSWER.
Оба исхода проверяются ИМЕННО после состоявшегося шага роли: сегодняшнее
поведение (эскалация до роли) второй исход внешне повторяет, и без сверки
порядка записей тест был бы зелёным на несломанном месте.

AC-6 — маркер прежней эскалации не держит пред-advance на несвязанном
последующем визите состояния: задача прошла переход, отличный от пары
`escalated`/возврат в то же состояние, и более поздняя, уже беcмаркерная
запись возврата анкером не становится.

Красен до реализации: маркера эскалации по содержимому артефакта сегодня
нет вовсе, а `auto._role_step_since_state_entry` не отличает эту
эскалацию от любой другой — цикл `auto` повторяет её предварительным
advance раньше единственного шага роли. Из-за этого в первом тесте задача
уходит в `escalated` вместо `in_dev`, во втором — эскалация оказывается
РАНЬШЕ записи `agent run finished`, а третий падает ещё на подготовке
сценария: `marker_action()` не находит записи маркера, из которой он
только и может взять её фиксированный текст.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (EscalationByArtifactSandbox,  # noqa: E402
                      agent_run_finished_actors)
from orchestrator import auto, fsm, store  # noqa: E402


class AfterTheTestAuthorStepTest(EscalationByArtifactSandbox):
    """AC-5: исход шага роли в `tests_writing` после возврата."""

    def test_ac5_mark_removed_by_the_role_step_advances_to_in_dev(self):
        """test_author, получив ответ, переписывает планку без пометки
        `escalate` — следующий же advance цикла обязан увести задачу в
        `in_dev` обычным путём трассируемости AC.

        Ловит мутацию: маркер эскалации не гасится шагом роли (рубеж
        `auto._rework_gate_blocks` продолжает держать пред-advance и
        ПОСЛЕ записи `agent run finished`) — цикл крутит шаги роли, ни
        разу не давая advance прочитать уже исправленную планку, и задача
        так и остаётся в `tests_writing`.
        """
        self.escalate_tests_writing()
        self.answer_and_approve()
        self.assertEqual(self.state(), "tests_writing",
                         "сценарий не воспроизведён: approve не вернул задачу")

        self.agent.script = [lambda: self.write_plank(escalate=False)]
        self.auto()

        self.assertEqual(
            agent_run_finished_actors(store.db(), self.TASK)[:1],
            ["test_author"],
            "шаг test_author не состоялся — исход «после шага роли» не "
            "воспроизведён")
        self.assertEqual(
            self.state(), "in_dev",
            "планка без пометки escalate не увела задачу в in_dev")

    def test_ac5_mark_left_after_the_role_step_escalates_with_a_new_baseline(self):
        """test_author оставил пометку на месте — задача законно уходит в
        `escalated` СНОВА, но уже ПОСЛЕ своего шага, с `answer_baseline`,
        снятым по текущему числу ANSWER-файлов: следующий `approve`
        требует очередной ANSWER.

        Ловит мутацию: маркер гасится не шагом роли, а самим возвратом,
        и рубеж пропускает пред-advance вперёд — эскалация снова случается
        РАНЬШЕ единственного вызова `cmd_run`, и `assertGreater` порядка
        записей поймает это, даже несмотря на совпадающий внешний исход
        (`escalated` + требование следующего ANSWER).
        """
        self.escalate_tests_writing()
        self.answer_and_approve()
        self.assertEqual(self.state(), "tests_writing",
                         "сценарий не воспроизведён: approve не вернул задачу")
        answers_after_return = self.answer_count()

        # Роль отработала, но пометку не сняла — планка остаётся прежней.
        self.agent.script = []
        self.auto()

        self.assertEqual(self.state(), "escalated",
                         "оставленная пометка escalate обязана эскалировать "
                         "задачу заново")
        self.assertGreater(
            self.index_of_last("state -> escalated"),
            self.index_of_first_role_step("test_author"),
            "новая эскалация случилась РАНЬШЕ шага test_author — это не "
            "исход «после шага роли», а повтор старой эскалации")
        self.assertEqual(
            self.task_row()["answer_baseline"], answers_after_return,
            "новая эскалация сняла answer_baseline не по текущему числу "
            "ANSWER-файлов")

        out = self.capture(fsm.cmd_approve, self.TASK)
        self.assertIn(
            f"ANSWER-{answers_after_return + 1}", out,
            "после НОВОЙ эскалации approve обязан требовать очередной "
            "ANSWER — новый baseline не действует")


class MarkerDoesNotOutliveItsEscalationTest(EscalationByArtifactSandbox):
    """AC-6: маркер прежней эскалации не долетает до несвязанного
    последующего визита состояния."""

    def test_ac6_marker_stops_making_the_return_an_anchor_after_another_transition(self):
        """Задача эскалировала по содержимому планки, вернулась, роль
        отработала свой шаг и ушла переходом `tests_writing -> in_dev`.
        Позже она эскалировала СНОВА, но по другому основанию (падение
        агента — такая эскалация маркера не ставит) и вернулась в
        `tests_writing` тем же общим текстом `fsm._approve_escalated`: эта
        запись возврата анкером быть не должна, и рубеж не обязан
        требовать ещё один шаг test_author.

        Ловит мутацию: маркер не гасится ни расходом (первой же записью
        `state -> tests_writing`), ни другим переходом состояния — тогда
        ВТОРАЯ, беcмаркерная запись возврата тоже становится анкером, шага
        роли после неё нет, и `_role_step_since_state_entry` вернёт
        `ran=False`.
        """
        self.escalate_tests_writing()
        # Фиксированный текст маркера берётся из самой реализации, а не из
        # литерала планки: значение константы — решение разработчика.
        self.marker_action()

        self.answer_and_approve()
        self.assertEqual(self.state(), "tests_writing",
                         "сценарий не воспроизведён: approve не вернул задачу")

        conn = store.db()
        # Шаг роли и штатный выход из состояния — тот самый «переход,
        # отличный от пары escalated/возврат», после которого маркер
        # прежней эскалации обязан перестать действовать.
        store.journal(conn, self.TASK, "test_author", "agent run finished",
                      "rc=0, тестовая заглушка приёмочного теста")
        store.journal(conn, self.TASK, "fsm", "state -> in_dev",
                      "приёмочные тесты готовы — трассируемость AC пройдена")
        # Новая эскалация другого класса (падение шага агента): маркера
        # «ответ Оператора должен дойти до роли» она не ставит.
        store.journal(conn, self.TASK, "fsm", "state -> escalated",
                      "шаг агента упал")
        store.journal(conn, self.TASK, "operator", "state -> tests_writing",
                      auto._ESCALATED_RETURN_DETAILS[0])

        ran, _detail = auto._role_step_since_state_entry(
            conn, self.TASK, "tests_writing", "test_author")

        self.assertTrue(
            ran, "маркер прежней эскалации пережил свой визит состояния — "
            "беcмаркерная запись возврата снова стала анкером рубежа")


if __name__ == "__main__":
    unittest.main()
