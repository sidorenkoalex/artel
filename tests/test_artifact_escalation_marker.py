"""Юнит-тесты маркера эскалации по содержимому артефакта роли (SPEC
01M2XFSJ1Z7BS6HR69SAT1D81Y): запись `fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER`
точками эскалации `fsm_advance.tests_writing`/`fsm_advance.spec_writing`
(требования 1-2) и её чтение анкером рубежа
`auto._role_step_since_state_entry` (требования 3-4). Третья точка —
эскалация ревьювера `fsm_advance._review_escalate` (SPEC
01M31JWD10728N5YGWVQGWYACW, требование 1): случай, который SPEC
01M2XFSJ1Z7BS6HR69SAT1D81Y счёл невоспроизводимым, а инциденты 20.09 и
21.09 воспроизвели.

Сквозной сценарий инцидента 13.09 через цикл `auto` кроет планка задачи
(`tasks/01M2XFSJ1Z7BS6HR69SAT1D81Y/acceptance_tests/`); здесь — обе
половины механики в изоляции: чтение анкера по журналу, собранному
руками (как `tests/test_auto_escalated_return_rework_gate.py`), и запись
маркера одним `fsm.cmd_advance` в лёгкой песочнице цикла
(`tests/test_auto_cycle.py::AutoCycleTest` — тот же `fake_git`, диск как
единственный источник артефактов).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import auto, budget, fsm, fsm_advance, store  # noqa: E402
from tests.sandbox import SchemaConnTmpRootTest  # noqa: E402
from tests.test_auto_cycle import AutoCycleTest  # noqa: E402

TASK_ID = "T001"
MARKER = fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER
RETURN_DETAIL = auto._ESCALATED_RETURN_DETAILS[0]
FIRST_ENTRY_DETAIL = "гейт SPEC пройден — приёмочные тесты до кода"


class RoleStepAnchorAfterTheMarkerTest(SchemaConnTmpRootTest):
    """Чтение маркера анкером рубежа (требования 3-4)."""

    def _journal(self, actor: str, action: str, detail: str = "") -> None:
        store.journal(self.conn, TASK_ID, actor, action, detail)

    def _since_entry(self, state: str, role: str):
        return auto._role_step_since_state_entry(self.conn, TASK_ID, state, role)

    def _escalate_by_artifact(self, detail: str = "test_author: критерий "
                              "неисполним тестом — AC-2: противоречив") -> None:
        self._journal("fsm", "state -> escalated", detail)
        self._journal("fsm", MARKER, detail)

    def test_return_after_the_marker_blocks_until_the_role_step(self):
        """Сценарий инцидента: test_author отработал ДО эскалации по
        пометке, Оператор вернул задачу общим текстом `_approve_escalated`
        — запись возврата, идущая за маркером, сама анкер, и шаг до
        эскалации её не отрабатывает.

        Ловит мутацию: `_role_step_since_state_entry` не читает
        `fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER` (ветка маркера знает
        только `pull.PULL_CONFLICT_ROLE_STEP_MARKER`) — запись возврата
        пропускается как `_ESCALATED_RETURN_DETAILS`, анкером остаётся
        первый вход, после которого шаг уже был: `ran` станет `True`.
        """
        self._journal("fsm", "state -> tests_writing", FIRST_ENTRY_DETAIL)
        self._journal("test_author", "agent run finished", "rc=0")
        self._escalate_by_artifact()
        self._journal("operator", "state -> tests_writing", RETURN_DETAIL)

        ran, detail = self._since_entry("tests_writing", "test_author")

        self.assertFalse(ran, "возврат после маркера не стал анкером — "
                         "пред-advance повторит отвеченную эскалацию")
        self.assertEqual(detail, RETURN_DETAIL)

    def test_role_step_after_the_marked_return_unblocks(self):
        """Шаг test_author ПОСЛЕ возврата закрывает рубеж — маркер не
        держит пред-advance дольше одного шага роли (AC-5).

        Ловит мутацию: анкер на маркерном возврате выставляется, но шаг
        роли ищется не ПОСЛЕ него, а до (например, перепутан срез
        `rows[last_entry + 1:]`) — `ran` останется `False`, и цикл крутил
        бы шаги роли, не давая advance прочитать исправленную планку.
        """
        self._journal("fsm", "state -> tests_writing", FIRST_ENTRY_DETAIL)
        self._escalate_by_artifact()
        self._journal("operator", "state -> tests_writing", RETURN_DETAIL)
        self._journal("test_author", "agent run finished", "rc=0")

        ran, _detail = self._since_entry("tests_writing", "test_author")

        self.assertTrue(ran)

    def test_first_spec_writing_visit_return_after_the_marker_is_an_anchor(self):
        """`spec_writing` (требование 2): первый вход задачи туда
        `cmd_new` не журналирует — до правки анкера не было вовсе и рубеж
        вырождался в «сверять нечем». Возврат за маркером становится
        первым и единственным анкером и держит до шага analyst.

        Ловит мутацию: маркер читается только вслед за уже существующей
        записью `state -> {state}` (например, `role_step_required`
        учитывается лишь при `last_entry is not None`) — для первого
        визита `spec_writing` результат снова `(True, None)`.
        """
        self._journal("operator", "created", "ТЗ принято")
        self._escalate_by_artifact("analyst: батч вопросов по ТЗ — "
                                   "ветка task/x:tasks/T001/QUESTIONS.md")
        self._journal("operator", "state -> spec_writing", RETURN_DETAIL)

        ran, detail = self._since_entry("spec_writing", "analyst")

        self.assertFalse(ran)
        self.assertEqual(detail, RETURN_DETAIL)

    def test_return_without_a_marker_is_still_skipped(self):
        """Эскалация другого класса (падение агента) маркера не несёт —
        её возврат по-прежнему пропускается, и шаг роли, отработанный до
        эскалации, засчитывается (существующее поведение, AC-7).

        Ловит мутацию: рубеж починен «в лоб» — запись возврата из
        `escalated` становится анкером ВСЕГДА, не только вслед за маркером
        — `ran` станет `False` при уже отработанном шаге.
        """
        self._journal("fsm", "state -> tests_writing", FIRST_ENTRY_DETAIL)
        self._journal("test_author", "agent run finished", "rc=0")
        self._journal("fsm", "state -> escalated", "агент упал")
        self._journal("operator", "state -> tests_writing", RETURN_DETAIL)

        ran, detail = self._since_entry("tests_writing", "test_author")

        self.assertTrue(ran)
        self.assertEqual(detail, FIRST_ENTRY_DETAIL)

    def test_marker_is_consumed_by_the_first_return(self):
        """Требование 4, расход: маркер израсходован первой же записью
        возврата — вторая эскалация (без маркера) и её возврат анкером не
        становятся, а шаг роли между ними засчитан.

        Ловит мутацию: `role_step_required` не сбрасывается на записи
        `state -> {state}` — второй возврат тоже становится анкером, шага
        после него нет, `ran` станет `False`.
        """
        self._escalate_by_artifact()
        self._journal("operator", "state -> tests_writing", RETURN_DETAIL)
        self._journal("test_author", "agent run finished", "rc=0")
        self._journal("fsm", "state -> escalated", "агент упал")
        self._journal("operator", "state -> tests_writing", RETURN_DETAIL)

        ran, detail = self._since_entry("tests_writing", "test_author")

        self.assertTrue(ran, "израсходованный маркер снова сделал возврат "
                        "анкером")
        self.assertEqual(detail, RETURN_DETAIL)

    def test_marker_is_reset_by_another_state_transition(self):
        """Требование 4, сброс (AC-6): между маркером и возвратом задача
        прошла другой переход (`state -> in_dev`) — маркер не долетает
        до последующего визита `tests_writing`, и беcмаркерный возврат
        туда не анкер.

        Ловит мутацию: маркер гасится только записью `state -> {state}`,
        а любой другой переход `state -> X` его не сбрасывает — возврат
        станет анкером, шага роли после него нет, `ran` станет `False`.
        """
        self._escalate_by_artifact()
        self._journal("operator", "state -> in_dev", RETURN_DETAIL)
        self._journal("fsm", "state -> escalated", "агент упал")
        self._journal("operator", "state -> tests_writing", RETURN_DETAIL)

        ran, detail = self._since_entry("tests_writing", "test_author")

        self.assertTrue(ran, "маркер пережил чужой переход состояния")
        self.assertIsNone(detail)

    def test_escalated_transition_between_marker_and_return_keeps_it(self):
        """`state -> escalated` — единственный переход, который маркер не
        гасит (это собственный переход эскалации): повторная запись
        эскалации до возврата не снимает требование шага роли.

        Ловит мутацию: сброс маркера сделан на ЛЮБОМ `state -> X` без
        исключения для `escalated` — возврат перестанет быть анкером,
        `ran` станет `True`.
        """
        self._escalate_by_artifact()
        self._journal("fsm", "state -> escalated", "повторная запись")
        self._journal("operator", "state -> tests_writing", RETURN_DETAIL)

        ran, _detail = self._since_entry("tests_writing", "test_author")

        self.assertFalse(ran)


# ---------------------------------------------------------------- запись

SPEC_MD = """---
task: {task}
type: spec
author_role: analyst
status: draft
schema_version: 2
---

# SPEC: фикстура песочницы

## Контекст

## Требования

1. Фикстура.

## Критерии приёмки

AC-1. Первый критерий фикстуры — покрыт тестовым методом планки.
AC-2. Второй критерий фикстуры — помечен escalate.

## Не входит
"""

QUESTIONS_MD = """---
task: {task}
type: questions
author_role: analyst
status: draft
schema_version: 2
---

# QUESTIONS: раунд 1

## Вопросы

1. **Вопрос раунда 1?** — варианты: A) да; B) нет — дефолт: A.
"""

PLANK_WITH_ESCALATE = '''"""Красен до реализации: планка-фикстура песочницы."""
import unittest


class PlankFixtureTest(unittest.TestCase):

    def test_ac1_pervyj_kriterij(self):
        """Заглушка первого критерия фикстуры."""
        self.assertEqual(1, 1)


# AC-2: escalate — критерий фикстуры сформулирован противоречиво
'''

# Бухгалтерия вокруг перехода, не событие самого перехода: lease пишется
# до разбора перехода, фиксация sha — хуком внутри `store.set_state`
# после КАЖДОГО перехода (см. `orchestrator/store.py::record_fixation`).
FIXATION_ACTION = "sha зафиксирован"


class MarkerWrittenByTheEscalationPointsTest(AutoCycleTest):
    """Запись маркера точками эскалации (требования 1-2)."""

    def meaningful_rows(self) -> list:
        return [r for r in store.task_steps(store.db(), self.TASK)
                if r["actor"] != "lease" and r["action"] != FIXATION_ACTION]

    def row_after_escalation(self):
        rows = self.meaningful_rows()
        indexes = [i for i, r in enumerate(rows)
                   if r["action"] == "state -> escalated"]
        self.assertTrue(indexes, "задача не эскалировала — сценарий не "
                        "воспроизведён")
        last = indexes[-1]
        self.assertLess(last + 1, len(rows), "после state -> escalated "
                        "в журнале ничего нет")
        return rows[last], rows[last + 1]

    def write_spec(self) -> None:
        (self.tdir / "SPEC.md").write_text(SPEC_MD.format(task=self.TASK),
                                           encoding="utf-8")

    def write_plank_with_escalate(self) -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_plank_fixture.py").write_text(
            PLANK_WITH_ESCALATE, encoding="utf-8")

    def write_questions(self) -> None:
        (self.tdir / "QUESTIONS.md").write_text(
            QUESTIONS_MD.format(task=self.TASK), encoding="utf-8")

    def test_tests_writing_escalation_journals_the_marker_after_the_transition(self):
        """Пометка `AC-n: escalate` в планке: сразу за `state -> escalated`
        стоит запись `fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER` с тем же
        `detail`, что у самой эскалации (требование 1).

        Ловит мутацию: `fsm_advance.tests_writing` после `set_state(...,
        "escalated")` маркер не журналирует — следующей записью после
        эскалации будет что угодно, кроме маркера (в этой песочнице —
        ничего, `assertLess` в `row_after_escalation` упадёт).
        """
        self.write_spec()
        self.write_plank_with_escalate()
        self.set_state("tests_writing")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated")
        escalated, marker = self.row_after_escalation()
        self.assertEqual(marker["action"], MARKER)
        self.assertEqual(marker["actor"], "fsm")
        self.assertEqual(marker["detail"], escalated["detail"])

    def test_spec_writing_escalation_by_a_batch_journals_the_same_marker(self):
        """Батч `QUESTIONS.md` на ветке-источнике (`foreign=True`, штатный
        путь песочницы): та же запись маркера тем же порядком
        (требование 2).

        Ловит мутацию: маркер заведён только в `tests_writing`, ветка
        батча на чужой ветке-источнике в `spec_writing` не тронута —
        после `state -> escalated` записи нет.
        """
        self.write_spec()
        self.write_questions()
        self.set_state("spec_writing")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated")
        escalated, marker = self.row_after_escalation()
        self.assertEqual(marker["action"], MARKER)
        self.assertEqual(marker["detail"], escalated["detail"])

    def test_spec_writing_disk_path_journals_the_marker_too(self):
        """Второй путь `spec_writing` — дерево на своей ветке
        (`foreign=False`), батч читается с диска: маркер ставится и здесь.

        Ловит мутацию: маркер добавлен только в ветку чужой
        ветки-источника `spec_writing`, дисковый путь (`questions.exists()`)
        остался без него — после `state -> escalated` записи нет.
        """
        self.write_spec()
        self.write_questions()
        self.set_state("spec_writing")
        with mock.patch.object(fsm_advance.artifact_source, "resolve",
                               lambda conn, task_id: ("main", False)):
            self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated")
        escalated, marker = self.row_after_escalation()
        self.assertEqual(marker["action"], MARKER)
        self.assertEqual(marker["detail"], escalated["detail"])

    def test_review_escalation_journals_the_marker(self):
        """Эскалация от ревьювера (`REVIEW.md status: escalate`) — тот же
        класс, что пометка `AC-n: escalate` и батч `QUESTIONS.md` (SPEC
        01M31JWD10728N5YGWVQGWYACW, требование 1): сразу за
        `state -> escalated` стоит запись маркера с тем же `detail`, что у
        самой эскалации. Прежнее ожидание этого теста («маркера нет»)
        опиралось на решение SPEC 01M2XFSJ1Z7BS6HR69SAT1D81Y о
        невоспроизводимости случая review и опровергнуто инцидентами 20.09
        и 21.09: без маркера ответ Оператора до developer не доходил.

        Ловит мутацию: `_review_escalate` после `set_state(...,
        "escalated")` маркер не журналирует (или журналирует ДО перехода)
        — следующей записью после эскалации будет не маркер, и
        `row_after_escalation` вернёт не ту строку либо упадёт на
        `assertLess`; `auto._role_step_since_state_entry` такой маркер
        тоже не прочитал бы.
        """
        self.write_review("escalate", 1)
        self.set_state("review")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated")
        escalated, marker = self.row_after_escalation()
        self.assertEqual(marker["action"], MARKER)
        self.assertEqual(marker["actor"], "fsm")
        self.assertEqual(marker["detail"], escalated["detail"])

    def test_budget_escalation_from_review_journals_no_marker(self):
        """Сохранённая половина прежнего ожидания: маркер ставит ИМЕННО
        `_review_escalate`, а не любой переход в `escalated` из `review`.
        Эскалация по исчерпанному потолку (`budget.enforce_budget`)
        собственного основания переделки не несёт — разрешать ей нечего,
        кроме поднятого потолка, — и журнал маркера не получает
        (01M1VBEDGMEXHVGWAH42FTDZ4X, требование 2).

        Ловит мутацию: маркер вынесен в общий узел эскалации (в
        `store.set_state` на любой переход в `escalated` либо в
        `fsm_advance.review` до разбора вердикта) — бюджетная эскалация
        тоже пометит себя, её запись возврата станет анкером рубежа, и
        пульт потребует лишнего шага роли там, где раньше продолжал
        работу.
        """
        self.set_state("review", budget_usd=1.0, spent_usd=2.0)

        escalated = budget.enforce_budget(store.db(), self.TASK, "review")

        self.assertTrue(escalated, "потолок не сработал — сценарий не "
                        "воспроизведён")
        self.assertEqual(self.state(), "escalated")
        self.assertNotIn(MARKER, [r["action"] for r in self.meaningful_rows()])


if __name__ == "__main__":
    unittest.main()
