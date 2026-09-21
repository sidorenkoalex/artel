"""Общая фикстура приёмочных тестов 01M31JWD10728N5YGWVQGWYACW: задача,
эскалированная РЕВЬЮВЕРОМ (`REVIEW.md status: escalate`), возвращённая
Оператором через ответ и `approve`, и цикл `auto` поверх неё.

Не копия `tests/sandbox.py::LightTransitionSandbox` и не копия её набора
патчей (скил test-authoring, «Лёгкая песочница переходов — не копия,
импорт»): базой взята уже готовая песочница цикла `auto` из
`tests/test_auto_cycle.py::AutoCycleTest` (тот же `fake_git`, те же
`disk_backed_show`/`disk_backed_ls_tree_files` и
`seed_developer_brief_fixtures` из `tests/sandbox.py`, тот же `FakeRun`
вместо агента) — тем же приёмом, что и планка предыдущей задачи того же
класса, `tasks/01M2XFSJ1Z7BS6HR69SAT1D81Y/acceptance_tests/_sandbox.py`.
Здесь — только надстройка сценария этой задачи: артефакты трёх точек
эскалации, ответ Оператора, посев журнала инцидента 21.09 и чтение
журнала вокруг записи `state -> escalated`.

Ответ Оператора кладётся файлом `ANSWER-n.md` на диск, а не через
`orchestrator/answer.py::cmd_answer`: `cmd_answer` коммитит файл в
артефактную ветку настоящим git, которого в этой песочнице нет вовсе
(`gitcmd.git` — заглушка), а единственные потребители ответа в сценарии —
`fsm._answer_file_count` и `brief._latest_answer_rel`, оба читают ровно
тот же диск через подменённый `gitcmd.ls_tree_files`.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from orchestrator import config, fsm, store  # noqa: E402
from tests.sandbox import seed_developer_brief_fixtures  # noqa: E402
from tests.test_auto_cycle import AutoCycleTest  # noqa: E402

__all__ = ["ReviewEscalationSandbox", "ac_mark", "agent_run_finished_actors",
           "escalation_marker_index", "meaningful_rows", "PRE_ADVANCE_NOTE",
           "RETURN_DETAIL", "REVIEW_RETURN_DETAIL"]

# Символ решётки отдельной константой, а текст пометки собирается в
# `ac_mark` ниже: литерал `# AC-n: escalate — ...`, написанный в этом файле
# как есть, прочитался бы разбором планки ЭТОЙ задачи как настоящая
# пометка её собственного критерия, если бы `scripts/guard.py::
# scan_acceptance_tests` когда-нибудь снова стал читать не только
# `test_*.py` (до SPEC T081 читал все `*.py`). По той же причине имена
# тестовых методов планки-фикстуры ниже собираются через `{one}`/`{two}`:
# образец `def test_ac<цифры>_` буквальным текстом здесь не стоит.
_HASH = "#"

# Текст, которым `auto._pre_advance_step` отмечает «переход выполнен без
# шага роли» — буквальная формулировка AC-2/AC-4 («не переводит задачу
# in_dev -> verifying по готовым артефактам»).
PRE_ADVANCE_NOTE = "шаг {role} не нужен: переход выполнен по готовым артефактам"

# Общий текст записи возврата Оператора из `escalated`
# (`orchestrator/fsm.py::_approve_escalated`) — он же инцидентный «state ->
# in_dev | эскалация разрешена, продолжаем» 21.09 08:52:09.
RETURN_DETAIL = "эскалация разрешена, продолжаем"

# Detail записи `state -> in_dev`, которой ревью вернуло задачу
# разработчику (`orchestrator/fsm_advance.py::_review_changes_requested`) —
# анкер рубежа переделки ДО эскалации, тот самый, который в инциденте
# маскировал собой запись возврата.
REVIEW_RETURN_DETAIL = "замечания ревью, итерация 1"

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
AC-2. Второй критерий фикстуры — переменная сценария: пометка escalate
либо тестовый метод.

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

ANSWER_MD = """---
task: {task}
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-{n}: ответ Оператора

## Ответы

Раунд {n}: {body}
"""

# Опознаваемое тело ответа — по нему тест AC-3 ищет ANSWER в брифе
# разработчика, не по имени файла: имя могло бы попасть в бриф и описью
# соседнего компонента.
ANSWER_BODY = "трактовка требования 3 — читать буквально, код правится"

TZ_MD = """# ТЗ

Фикстура приёмочных тестов: наличие этого файла подключает роль analyst
к состоянию `spec_writing` (`orchestrator/runner.py::step_role`).
"""

# Планка-фикстура песочницы: шапка с маркером красноты (его требует выход
# из `tests_writing`), тестовый метод первого критерия и пометка
# `escalate` второго — то, чем эскалирует `fsm_advance.tests_writing`.
_PLANK_HEAD = '''"""Красен до реализации: планка-фикстура песочницы приёмочного теста."""
import unittest


class PlankFixtureTest(unittest.TestCase):

    def test_ac{one}_pervyj_kriterij(self):
        """Заглушка первого критерия фикстуры."""
        self.assertEqual({one}, {one})
'''

_PLANK_SECOND_TEST = '''
    def test_ac{two}_vtoroj_kriterij(self):
        """Заглушка второго критерия фикстуры."""
        self.assertEqual({two}, {two})
'''


def ac_mark(n: int, kind: str, reason: str) -> str:
    """Строка-пометка критерия планки-фикстуры в том виде, в каком её
    разбирает `scripts/guard.py::AC_MARKER` (начало строки, без отступа)."""
    return f"{_HASH} AC-{n}: {kind} — {reason}"


# Бухгалтерия, которую пульт пишет в журнал ВОКРУГ любого перехода, не как
# событие самого перехода:
#
# - `actor == "lease"` («lease взят»/«lease перехвачен»,
#   `orchestrator/lease.py::acquire`) — пишется ДО того, как управление
#   вообще дошло до разбираемого перехода;
# - «sha зафиксирован» (`orchestrator/store.py::record_fixation`, хук
#   внутри самой `store.set_state`) — пишется ПОСЛЕ записи перехода на
#   КАЖДОМ переходе FSM без исключения, поэтому «отдельной записью сразу
#   после `state -> escalated`» в смысле AC-1 считается мимо неё.
FIXATION_ACTION = "sha зафиксирован"


def meaningful_rows(conn, task_id: str) -> list:
    """Журнал задачи без бухгалтерии вокруг переходов (см. выше)."""
    return [r for r in store.task_steps(conn, task_id)
            if r["actor"] != "lease" and r["action"] != FIXATION_ACTION]


def escalation_marker_index(rows: list):
    """Индекс записи, идущей НЕПОСРЕДСТВЕННО за последней
    `state -> escalated` журнала, если это отдельная запись, а не
    следующий переход состояния; иначе `None`.

    Именно эту позицию описывает AC-1 («отдельной записью сразу после
    записи `state -> escalated`»): маркера нет — следующей записью журнала
    оказывается уже запись возврата Оператора (`state -> in_dev`), она
    отсеивается проверкой префикса, и функция честно возвращает `None`.
    Текст `action` маркера здесь не зашит литералом: AC-1 требует «тем же
    вызовом `_mark_artifact_escalation`», то есть совпадения с маркером
    `spec_writing`/`tests_writing`, а не конкретной строки — тесты сверяют
    его между точками эскалации.
    """
    last = None
    for i, row in enumerate(rows):
        if row["action"] == "state -> escalated":
            last = i
    if last is None or last + 1 >= len(rows):
        return None
    if rows[last + 1]["action"].startswith("state -> "):
        return None
    return last + 1


def agent_run_finished_actors(conn, task_id: str) -> list:
    """Роли (`actor`), под которыми журнал несёт `agent run finished`, по
    порядку записи — сильнее голого числа вызовов `FakeRun`: различает,
    КАКАЯ роль отработала шаг."""
    return [row["actor"] for row in store.task_steps(conn, task_id)
            if row["action"] == "agent run finished"]


class ReviewEscalationSandbox(AutoCycleTest):
    """`AutoCycleTest` + артефакты трёх точек эскалации, ответ Оператора,
    посев журнала инцидента и чтение журнала вокруг `state -> escalated`."""

    def setUp(self):
        super().setUp()
        # Роль `analyst` подключается к `spec_writing` только при
        # заведённом TZ.md (`runner.step_role`) — `cmd_new` песочницы
        # зовётся без `--tz`, файл кладётся здесь.
        (self.tdir / "TZ.md").write_text(TZ_MD, encoding="utf-8")
        # Бриф разработчика (AC-3) читает карту и конвенции из
        # `config.ROOT` — без них он падал бы ENOENT ещё до предмета теста.
        seed_developer_brief_fixtures(config.ROOT)

    # ------------------------------------------------------------ артефакты

    def write_spec(self) -> None:
        (self.tdir / "SPEC.md").write_text(SPEC_MD.format(task=self.TASK),
                                           encoding="utf-8")

    def write_plank_with_escalate(self) -> None:
        """Планка-фикстура с пометкой `escalate` второго критерия — то, чем
        эскалирует `tests_writing`."""
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        text = (_PLANK_HEAD.format(one=1) + "\n\n"
                + ac_mark(2, "escalate", "критерий фикстуры сформулирован "
                          "противоречиво") + "\n")
        (tests_dir / "test_plank_fixture.py").write_text(text, encoding="utf-8")

    def write_plank_without_escalate(self) -> None:
        """Та же планка после шага роли: пометка снята, оба критерия
        покрыты тестами."""
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        text = _PLANK_HEAD.format(one=1) + _PLANK_SECOND_TEST.format(two=2)
        (tests_dir / "test_plank_fixture.py").write_text(text, encoding="utf-8")

    def write_questions(self) -> None:
        (self.tdir / "QUESTIONS.md").write_text(
            QUESTIONS_MD.format(task=self.TASK), encoding="utf-8")

    def remove_questions(self) -> None:
        (self.tdir / "QUESTIONS.md").unlink(missing_ok=True)

    def answer_count(self) -> int:
        return len(list(self.tdir.glob("ANSWER-*.md")))

    def write_answer(self) -> None:
        """Следующий по номеру `ANSWER-n.md` — наблюдаемый результат
        команды `answer` для всех её читателей в этом сценарии."""
        n = self.answer_count() + 1
        (self.tdir / f"ANSWER-{n}.md").write_text(
            ANSWER_MD.format(task=self.TASK, n=n, body=ANSWER_BODY),
            encoding="utf-8")

    # ------------------------------------------------------------- переходы

    def escalate_from_review(self) -> str:
        """`review -> escalated` по вердикту `REVIEW.md status: escalate`."""
        self.write_review("escalate", 1)
        self.set_state("review")
        return self.capture(fsm.cmd_advance, self.TASK)

    def escalate_tests_writing(self) -> str:
        """`tests_writing -> escalated` по пометке `escalate` в планке."""
        self.write_spec()
        self.write_plank_with_escalate()
        self.set_state("tests_writing")
        return self.capture(fsm.cmd_advance, self.TASK)

    def escalate_spec_writing(self) -> str:
        """`spec_writing -> escalated` по батчу `QUESTIONS.md`."""
        self.write_spec()
        self.write_questions()
        self.set_state("spec_writing")
        return self.capture(fsm.cmd_advance, self.TASK)

    def answer_and_approve(self) -> str:
        """Ответ Оператора (`answer`) и возврат из эскалации (`approve`)."""
        self.write_answer()
        return self.capture(fsm.cmd_approve, self.TASK)

    # --------------------------------------------------------------- журнал

    def journal(self, actor: str, action: str, detail: str = "") -> None:
        store.journal(store.db(), self.TASK, actor, action, detail)

    def seed_developer_step_before_the_escalation(self) -> None:
        """Журнал задачи 21.09 ДО эскалации ревьювера: возврат из ревью с
        замечаниями, отработанный шаг developer, зелёный CI и вход в
        `review`. Именно этот отработанный шаг инцидент засчитывал вместо
        шага после ответа Оператора."""
        self.journal("fsm", "state -> in_dev", REVIEW_RETURN_DETAIL)
        self.journal("developer", "agent run finished", "rc=0")
        self.journal("fsm", "state -> verifying", "PLAN готов — ждём CI")
        self.journal("fsm", "state -> review", "CI зелёный — вход в ревью")

    def rows(self) -> list:
        return meaningful_rows(store.db(), self.TASK)

    def actions(self) -> list:
        return [row["action"] for row in self.rows()]

    def marker_index(self) -> int:
        """Индекс маркерной записи; проваливает тест, если её нет."""
        index = escalation_marker_index(self.rows())
        self.assertIsNotNone(
            index, "сразу за записью state -> escalated нет отдельной "
            "записи маркера — эскалация ничем себя не пометила")
        return index

    def marker_action(self) -> str:
        """`action` маркерной записи; проваливает тест, если её нет."""
        action = self.rows()[self.marker_index()]["action"]
        self.assertTrue(
            action.strip(),
            "маркерная запись без текста action — читать такой маркер по "
            "фиксированному действию журнала нечем")
        return action

    def index_of_last(self, action: str) -> int:
        rows = self.rows()
        found = [i for i, r in enumerate(rows) if r["action"] == action]
        self.assertTrue(found, f"в журнале нет записи «{action}»")
        return found[-1]

    def index_of_first_role_step(self, role: str, after: int = -1) -> int:
        """Индекс первой записи `agent run finished` роли `role` СТРОГО
        после позиции `after`; проваливает тест, если такой записи нет.

        `after` обязателен там, где у задачи уже был шаг той же роли ДО
        разбираемого возврата (журнал инцидента 21.09): без отсечки окно
        «между возвратом и шагом роли» схлопнулось бы в пустой срез и
        проверки прошли бы вхолостую.
        """
        rows = self.rows()
        for i, r in enumerate(rows):
            if i <= after:
                continue
            if r["action"] == "agent run finished" and r["actor"] == role:
                return i
        self.fail(f"роль {role} не отработала ни одного шага после записи "
                  f"№{after} — `agent run finished` под её именем в журнале "
                  f"нет")

    def assert_role_runs_before_any_pre_advance(self, return_index: int,
                                                role: str) -> None:
        """Окно между возвратом Оператора и первым шагом роли ПОСЛЕ него: в
        нём нет ни заметки пред-advance, ни ухода задачи из состояния
        роли."""
        window = self.rows()[return_index + 1:
                             self.index_of_first_role_step(role, return_index)]
        note = PRE_ADVANCE_NOTE.format(role=role)
        self.assertNotIn(
            note, [r["action"] for r in window],
            f"между возвратом Оператора и шагом роли {role} цикл auto "
            f"успел продвинуть задачу предварительным advance")
        self.assertNotIn(
            "state -> verifying", [r["action"] for r in window],
            f"задача ушла в verifying раньше шага роли {role} — ответ "
            f"Оператора до роли не дошёл")
