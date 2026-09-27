"""Юнит-тесты однократного подъёма потолка канареечной задачи и исхода
«исчерпан потолок задачи» (01M3HJQV2QV9BXNXSH3F8STAYH, требования 6-11).

До этой задачи прогон закрывал бюджетную эскалацию синтетическим ANSWER,
не меняя потолка: задача крутилась `escalated` <-> `in_dev`, пока не
упиралась в `config.CANARY_MAX_ESCALATION_CYCLES`, и снималась причиной
«задача не сходится» — диагнозом конвейера там, где шаблон просто не
уложился в потолок (прогон 20260927T123258Z).

Вождение задачи здесь настоящее (`canary._drive_task`), а эскалацию по
бюджету пишет живой `budget.enforce_budget`: требование 6 называет
признаком бюджетной эскалации именно его причину перехода, и подделывать
её литералом теста значило бы проверять свою же копию.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import budget, canary, config, runner, store

TASK = "T920"
#: Потолок задачи «из SPEC клона» — подъём считается от него.
CEILING = 10.0
#: Стоимость шага: двух шагов достаточно, чтобы пробить потолок.
STEP_COST = 6.0


class _CanaryTaskTest(unittest.TestCase):
    """Канареечная задача в `in_dev` со своим потолком, БД в tmp."""

    STATE = "in_dev"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, TASK, "Канареечная задача", self.STATE,
                          "task/t920-x", config.DEFAULT_TARGET, CEILING,
                          is_canary=True)

    def steps(self) -> list:
        return store.task_steps(self.conn, TASK)

    def journal_texts(self) -> list:
        return [f"{r['action']} — {r['detail'] or ''}" for r in self.steps()]

    def transitions(self) -> list:
        return [r["action"] for r in self.steps()
                if r["action"].startswith("state -> ")]

    def task(self):
        return store.get_task(self.conn, TASK)


class CeilingFactorConstantTest(unittest.TestCase):
    """`config.CANARY_BUDGET_CEILING_FACTOR` — крутилка Оператора
    (требование 7)."""

    def test_factor_is_at_least_two(self):
        """Ловит мутацию: множитель опущен до 1.x — наблюдавшийся расход
        прогонов 20-27.09 (до $26.25 при минимуме потолка $25 по скилу
        аналитика) не оставил бы запаса, и прогон падал бы на том же
        месте, где падал до задачи."""
        self.assertGreaterEqual(config.CANARY_BUDGET_CEILING_FACTOR, 2)


class BudgetEscalationMarkTest(_CanaryTaskTest):
    """`canary._budget_escalation` — признак бюджетной эскалации по
    причине перехода (требование 6)."""

    def test_detail_of_the_budget_gate_is_recognized(self):
        """Ловит мутацию: признак читается не из причины перехода, а из
        состояния/счётчика — ЛЮБАЯ эскалация трактовалась бы как
        бюджетная, и прогон поднимал бы потолок задаче, эскалировавшей
        вопросом к Оператору."""
        store.journal(self.conn, TASK, "fsm", "state -> escalated",
                      "бюджет исчерпан: $12.00 из $10.00")

        self.assertTrue(canary._budget_escalation(self.steps()))

    def test_escalation_of_another_reason_is_not_a_budget_one(self):
        """Ловит мутацию: сверка причины подменена проверкой «detail
        непустой» — эскалация разработчика (её `detail` несёт секцию
        «Эскалация» PLAN.md) съедала бы подъём потолка, и настоящая
        бюджетная эскалация осталась бы без него."""
        store.journal(self.conn, TASK, "fsm", "state -> escalated",
                      "вопрос Оператору: SPEC читается двумя способами")

        self.assertFalse(canary._budget_escalation(self.steps()))

    def test_only_the_last_escalation_decides(self):
        """Ловит мутацию: признак ищется по ЛЮБОЙ эскалации журнала
        (`any(...)`) — задача, однажды эскалировавшая по бюджету, дальше
        получала бы бюджетную ветку на каждую следующую эскалацию любой
        природы, минуя потолок повторных эскалаций."""
        store.journal(self.conn, TASK, "fsm", "state -> escalated",
                      "бюджет исчерпан: $12.00 из $10.00")
        store.journal(self.conn, TASK, "canary", "state -> in_dev", "")
        store.journal(self.conn, TASK, "fsm", "state -> escalated",
                      "ревью: changes_requested")

        self.assertFalse(canary._budget_escalation(self.steps()))

    def test_journal_without_escalations_is_not_a_budget_one(self):
        """Ловит мутацию: пустой журнал трактуется как бюджетная
        эскалация (например, `return True` по умолчанию) — первая же
        эскалация любой природы уходила бы в подъём потолка."""
        self.assertFalse(canary._budget_escalation(self.steps()))


class RaiseTaskCeilingTest(_CanaryTaskTest):
    """`canary._raise_task_ceiling` — однократный подъём (требования 7,
    11). Возврат из `escalated` подменён: его предмет — чужая, уже
    смерженная механика синтетического ANSWER."""

    STATE = "escalated"

    def setUp(self):
        super().setUp()
        store.update_task(self.conn, TASK, escalated_from="review",
                          spent_usd=12.0)

        def fake_answer(conn, task_id):
            back = store.get_task(conn, task_id)["escalated_from"] or "in_dev"
            store.update_task(conn, task_id, escalated_from=None)
            store.set_state(conn, task_id, back, "test",
                            expected_state="escalated")

        patcher = mock.patch.object(
            canary, "_pass_escalated_with_synthetic_answer", fake_answer)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ceiling_is_multiplied_by_the_named_constant(self):
        """Ловит мутацию: потолок поднимается прибавкой фиксированной
        суммы либо множителем-литералом в коде — у Оператора не было бы
        крутилки, и правка запаса требовала бы правки `canary.py`."""
        canary._raise_task_ceiling(self.conn, TASK, self.task())

        self.assertAlmostEqual(CEILING * config.CANARY_BUDGET_CEILING_FACTOR,
                               self.task()["budget_usd"])

    def test_raise_is_journalled_with_both_ceilings(self):
        """Ловит мутацию: потолок поднимается молча, одним
        `store.update_task` — по журналу задачи нельзя было бы понять,
        почему расход канареечной задачи выше её SPEC-потолка, и подъём
        читался бы как ошибка учёта."""
        canary._raise_task_ceiling(self.conn, TASK, self.task())

        texts = [text for text in self.journal_texts()
                 if canary._CEILING_RAISE_ACTION in text]
        self.assertTrue(texts, f"нет записи о подъёме: {self.journal_texts()}")
        self.assertIn("10.00", texts[0])
        self.assertIn("20.00", texts[0])

    def test_task_returns_to_the_state_it_escalated_from(self):
        """Ловит мутацию: потолок поднят, но задача оставлена в
        `escalated` (или возвращена в `in_dev` жёстко, мимо
        `escalated_from`) — прогон встал бы на том же месте либо терял
        точку возврата задачи, эскалировавшей не из разработки."""
        canary._raise_task_ceiling(self.conn, TASK, self.task())

        self.assertEqual("review", self.task()["state"])

    def test_ceiling_is_raised_before_the_task_returns(self):
        """Ловит мутацию: подъём делается ПОСЛЕ возврата из `escalated` —
        вернувшаяся задача упёрлась бы в `budget.budget_block` на первом
        же запуске роли, и «прогон продолжается» не выполнялось бы."""
        seen = {}

        def watching_answer(conn, task_id):
            seen["ceiling"] = store.get_task(conn, task_id)["budget_usd"]
            store.set_state(conn, task_id, "review", "test",
                            expected_state="escalated")

        with mock.patch.object(canary,
                               "_pass_escalated_with_synthetic_answer",
                               watching_answer):
            canary._raise_task_ceiling(self.conn, TASK, self.task())

        self.assertAlmostEqual(CEILING * config.CANARY_BUDGET_CEILING_FACTOR,
                               seen.get("ceiling"))

    def test_already_raised_is_read_from_the_journal(self):
        """Ловит мутацию: признак «подъём уже был» живёт в переменной
        цикла `_drive_task` — она обнулялась бы при уходе из состояния
        (как `dev_retries`), каждая новая бюджетная эскалация поднимала бы
        потолок снова, и конечной верхней границы расхода не
        существовало бы."""
        self.assertFalse(canary._ceiling_already_raised(self.steps()))

        canary._raise_task_ceiling(self.conn, TASK, self.task())

        self.assertTrue(canary._ceiling_already_raised(self.steps()))


class KillCeilingExhaustedTest(_CanaryTaskTest):
    """`canary._kill_ceiling_exhausted` — свой исход с числами и ролью
    шага (требование 9)."""

    STATE = "escalated"

    def setUp(self):
        super().setUp()
        store.update_task(self.conn, TASK, escalated_from="in_dev",
                          budget_usd=20.0, spent_usd=24.0)
        patcher = mock.patch.object(canary.cleanup, "cmd_kill")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _reason(self) -> str:
        canary._kill_ceiling_exhausted(self.conn, TASK, self.task())
        texts = [text for text in self.journal_texts()
                 if canary._CEILING_EXHAUSTED_REASON in text]
        self.assertTrue(texts, f"нет записи исхода: {self.journal_texts()}")
        return texts[0]

    def test_reason_names_the_spend_the_ceiling_and_the_role(self):
        """Ловит мутацию: причина журналируется общим текстом без чисел
        («потолок исчерпан») — по журналу нельзя было бы сказать, на
        сколько не хватило поднятого потолка, а именно это число решает,
        куда крутить константу-множитель."""
        reason = self._reason()

        self.assertIn("24.00", reason)
        self.assertIn("20.00", reason)
        self.assertIn(config.STATE_ROLE["in_dev"], reason)

    def test_reason_does_not_claim_the_task_does_not_converge(self):
        """Ловит мутацию: новый исход дописан к прежней причине («не
        сходится: исчерпан потолок задачи…») — в отчёте прогона оба
        диагноза читались бы как один, и вердикт снова обвинял бы
        конвейер."""
        reason = self._reason()

        self.assertNotIn("не сходится", reason)
        self.assertNotIn("не сошлась", reason)

    def test_kill_outcome_note_returns_the_reason_itself(self):
        """Ловит мутацию: `_kill_outcome_note` не узнаёт новый
        литерал-маркер и падает в ветку `_INCONCLUSIVE_KILL_DETAIL` либо
        в общее «не сошлась» — отчёт прогона показал бы Оператору два
        взаимоисключающих диагноза одной задачи."""
        canary._kill_ceiling_exhausted(self.conn, TASK, self.task())

        note = canary._kill_outcome_note(self.conn, TASK, self.steps())

        self.assertIn(canary._CEILING_EXHAUSTED_REASON, note)
        self.assertNotIn("не сошлась", note)

    def test_outcome_raises_the_same_alert_as_other_canary_thresholds(self):
        """Ловит мутацию: алерт не поднимается — задача снята внутри
        эфемерного клона, клон уничтожен, и Оператор узнал бы об исходе
        только вычитав отчёт прогона глазами."""
        canary._kill_ceiling_exhausted(self.conn, TASK, self.task())

        rows = store.open_alerts(self.conn, "threshold")
        self.assertTrue(any(r["target"] == TASK for r in rows))

    def test_ceiling_exhausted_is_observable_for_the_verdict(self):
        """Ловит мутацию: признак исхода для вердикта читается по тексту
        причины, а не по литералу-маркеру — переформулировка причины молча
        вернула бы прогону вердикт `red`, то есть диагноз конвейера."""
        self.assertFalse(canary._ceiling_exhausted(self.steps()))

        canary._kill_ceiling_exhausted(self.conn, TASK, self.task())

        self.assertTrue(canary._ceiling_exhausted(self.steps()))


class RunVerdictTest(unittest.TestCase):
    """`canary._run_verdict` — вердикт строки `canary_runs` (требования
    10-11)."""

    def test_ceiling_exhausted_has_its_own_verdict(self):
        """Ловит мутацию: новый исход оставлен на прежней формуле
        («штатный исход без расхождения — green, иначе red») — по журналу
        прогонов нельзя было бы отличить «шаблон не уложился в потолок» от
        «конвейер не сошёлся»."""
        verdict = canary._run_verdict(False, False, True)

        self.assertEqual(canary.VERDICT_CEILING_EXHAUSTED, verdict)
        self.assertNotEqual("green", verdict)
        self.assertNotEqual(canary._run_verdict(False, False, False), verdict)

    def test_without_ceiling_exhaustion_the_formula_is_unchanged(self):
        """Ловит мутацию: сам факт подъёма потолка попал в вердикт («был
        подъём — значит не green») — прогон, который после подъёма прошёл
        штатно, перестал бы годиться для сдвига пина, то есть механизм
        починки красноты сам красил бы прогоны."""
        for normal_outcome, mismatch, expected in (
            (True, False, "green"),
            (False, False, "red"),
            (True, True, "red"),
            (False, True, "red"),
        ):
            with self.subTest(normal_outcome=normal_outcome, mismatch=mismatch):
                self.assertEqual(
                    expected,
                    canary._run_verdict(normal_outcome, mismatch, False))


class DriveTaskBudgetCeilingTest(_CanaryTaskTest):
    """`canary._drive_task` на бюджетной эскалации (требования 7-9):
    синтетический шаг роли тратит `STEP_COST` и заканчивается живым
    `budget.enforce_budget`."""

    #: Предохранитель от зацикливания: тест обязан падать названной
    #: причиной, а не висеть до таймаута раннера.
    AUTO_CALL_CEILING = 50

    def setUp(self):
        super().setUp()
        self.auto_calls = 0
        self.ceilings_seen = []

        def fake_auto(task_id):
            self.auto_calls += 1
            if self.auto_calls > self.AUTO_CALL_CEILING:
                raise AssertionError(
                    f"вождение не сошлось за {self.AUTO_CALL_CEILING} "
                    "вызовов auto.cmd_auto")
            t = store.get_task(self.conn, task_id)
            if runner.step_role(t) is None:
                return
            self.ceilings_seen.append(t["budget_usd"])
            store.charge(self.conn, task_id, STEP_COST)
            budget.enforce_budget(self.conn, task_id, t["state"])

        def fake_answer(conn, task_id):
            back = store.get_task(conn, task_id)["escalated_from"] or "in_dev"
            store.update_task(conn, task_id, escalated_from=None,
                              answer_baseline=None)
            store.set_state(conn, task_id, back, "test",
                            expected_state="escalated")

        def fake_kill(task_id):
            current = store.get_task(self.conn, task_id)["state"]
            store.set_state(self.conn, task_id, "killed", "test",
                            expected_state=current)

        for target, attr, value in (
                (canary.auto, "cmd_auto", fake_auto),
                (canary, "_pass_escalated_with_synthetic_answer", fake_answer),
                (canary.cleanup, "cmd_kill", fake_kill)):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _distinct_ceilings(self) -> list:
        distinct = []
        for value in self.ceilings_seen:
            if not distinct or abs(distinct[-1] - value) > 1e-9:
                distinct.append(value)
        return distinct

    def test_first_budget_escalation_raises_the_ceiling_and_runs_on(self):
        """Ловит мутацию: бюджетная эскалация закрывается прежним
        синтетическим ANSWER без подъёма потолка — задача крутилась бы до
        `CANARY_MAX_ESCALATION_CYCLES` и снималась как несошедшаяся, ровно
        то поведение, из которого задача заведена."""
        canary._drive_task(self.conn, TASK)

        self.assertEqual(
            [CEILING, CEILING * config.CANARY_BUDGET_CEILING_FACTOR],
            self._distinct_ceilings(),
            f"шаг роли видел потолки {self.ceilings_seen}")
        first = self.transitions().index("state -> escalated")
        self.assertEqual("state -> in_dev", self.transitions()[first + 1],
                         f"переходы: {self.transitions()}")

    def test_second_exhaustion_does_not_raise_again(self):
        """Ловит мутацию: подъём делается на КАЖДОЙ бюджетной эскалации —
        канареечная задача тратила бы кошелёк Оператора без верхней
        границы, ровно от чего требование 8 и ставит границу."""
        canary._drive_task(self.conn, TASK)

        self.assertEqual(CEILING * config.CANARY_BUDGET_CEILING_FACTOR,
                         self.task()["budget_usd"])
        raises = [r for r in self.steps()
                  if r["action"] == canary._CEILING_RAISE_ACTION]
        self.assertEqual(1, len(raises), "подъёмов потолка не один")

    def test_exhausted_raised_ceiling_kills_with_its_own_outcome(self):
        """Ловит мутацию: исчерпание поднятого потолка уходит в прежнюю
        ветку `escalation_cycles` — задача снималась бы причиной «задача
        не сходится», то есть диагнозом конвейера вместо диагноза
        «шаблон не уложился в потолок»."""
        canary._drive_task(self.conn, TASK)

        self.assertEqual("killed", self.task()["state"])
        self.assertTrue(canary._ceiling_exhausted(self.steps()),
                        f"журнал: {self.journal_texts()}")
        for text in self.journal_texts():
            self.assertNotIn("задача не сходится", text)

    def test_cap_of_repeated_escalations_is_not_consumed_by_the_budget_branch(self):
        """Ловит мутацию: бюджетная ветка инкрементирует
        `escalation_cycles` (или обнуляет его) — потолок повторных
        эскалаций для ОСТАЛЬНЫХ эскалаций прогона сдвинулся бы, а раздел
        «Не входит» SPEC требует сохранить его прежним."""
        canary._drive_task(self.conn, TASK)

        escalations = [r for r in self.steps()
                       if r["action"] == "state -> escalated"]
        self.assertEqual(2, len(escalations),
                         "сценарий должен дать ровно две бюджетные "
                         f"эскалации: {self.journal_texts()}")


if __name__ == "__main__":
    unittest.main()
