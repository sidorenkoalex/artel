"""Общая фикстура приёмочных тестов 01M2XFSJ1Z7BS6HR69SAT1D81Y: задача,
эскалированная СОДЕРЖИМЫМ артефакта роли (пометка `escalate` в планке —
`tests_writing`; батч вопросов — `spec_writing`), возвращённая Оператором
через ответ и `approve`, и цикл `auto` поверх неё.

Не копия `tests/sandbox.py::LightTransitionSandbox` и не копия её набора
патчей (скил test-authoring, «Лёгкая песочница переходов — не копия,
импорт»): базой взята уже готовая песочница цикла `auto` из
`tests/test_auto_cycle.py::AutoCycleTest` (тот же `fake_git`, те же
`disk_backed_show`/`disk_backed_ls_tree_files` из `tests/sandbox.py`, тот
же `FakeRun` вместо агента) — тем же приёмом, что уже использовали планки
`tasks/01M1RHFRQ2C0P4A57XJJ1WZV8N/` и `tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/`
для того же самого цикла. Здесь — только надстройка сценария этой задачи:
артефакты, поднимающие эскалацию по содержимому, ответ Оператора и чтение
журнала вокруг записи `state -> escalated`.

Ответ Оператора кладётся файлом `ANSWER-n.md` на диск, а не через
`orchestrator/answer.py::cmd_answer`: `cmd_answer` коммитит файл в
артефактную ветку настоящим git, которого в этой песочнице нет вовсе
(`gitcmd.git` — заглушка), а единственный потребитель ответа в сценарии —
`fsm._answer_file_count`, который читает ровно тот же диск через
подменённый `gitcmd.ls_tree_files`. Тот же приём, что и
`tasks/01M290PYPV5T2NFW1Y0HB8BD6E/acceptance_tests/_sandbox.py`.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from orchestrator import fsm, store  # noqa: E402
from tests.test_auto_cycle import AutoCycleTest  # noqa: E402

__all__ = ["EscalationByArtifactSandbox", "ac_mark",
           "agent_run_finished_actors", "escalation_marker_index",
           "meaningful_rows"]

# Символ решётки отдельной константой, а сам текст пометки собирается в
# `ac_mark` ниже: литерал `# AC-n: escalate — ...`, написанный в этом
# файле как есть, прочитался бы разбором планки ЭТОЙ задачи
# (`scripts/guard.py::scan_ac_content` читает ВСЕ `*.py` каталога, не
# только `test_*.py`, — см. `orchestrator/fsm.py::_tests_writing_ac_state`)
# как настоящая пометка её собственного критерия. По той же причине имена
# тестовых методов фикстуры ниже собираются через `{n}`: образец
# `TEST_AC` (`def test_ac<цифры>_`) буквальным текстом здесь не стоит.
_HASH = "#"


def ac_mark(n: int, kind: str, reason: str) -> str:
    """Строка-пометка критерия планки-фикстуры в том виде, в каком её
    разбирает `scripts/guard.py::AC_MARKER` (начало строки, без отступа)."""
    return f"{_HASH} AC-{n}: {kind} — {reason}"


SPEC_MD = """---
task: {task}
type: spec
author_role: analyst
status: {status}
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

# QUESTIONS: раунд {n}

## Вопросы

1. **Вопрос раунда {n}?** — варианты: A) да; B) нет — дефолт: A.
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

Раунд {n}: OK, продолжаем.
"""

TZ_MD = """# ТЗ

Фикстура приёмочных тестов: наличие этого файла подключает роль analyst
к состоянию `spec_writing` (`orchestrator/runner.py::step_role`).
"""

# Планка-фикстура песочницы: шапка с маркером красноты (его требует выход
# из `tests_writing`), тестовый метод первого критерия и переменный хвост —
# либо пометка `escalate` второго критерия, либо его тестовый метод.
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


# Бухгалтерия, которую пульт пишет в журнал ВОКРУГ любого перехода, не как
# событие самого перехода:
#
# - `actor == "lease"` («lease взят»/«lease перехвачен»,
#   `orchestrator/lease.py::acquire`) — пишется ДО того, как управление
#   вообще дошло до разбираемого перехода; тот же приём отсечки, что уже
#   применяет `orchestrator/advance_gates/tests_writing.py::
#   _tests_writing_stray_plank_files_gate`;
# - «sha зафиксирован» (`orchestrator/store.py::record_fixation`, хук
#   внутри самой `store.set_state`) — пишется ПОСЛЕ записи перехода на
#   КАЖДОМ переходе FSM без исключения, поэтому «запись сразу после
#   `state -> escalated`» в смысле AC-1/AC-2 считается мимо неё.
FIXATION_ACTION = "sha зафиксирован"


def meaningful_rows(conn, task_id: str) -> list:
    """Журнал задачи без бухгалтерии вокруг переходов (см. выше)."""
    return [r for r in store.task_steps(conn, task_id)
            if r["actor"] != "lease" and r["action"] != FIXATION_ACTION]


def escalation_marker_index(rows: list):
    """Индекс записи, идущей НЕПОСРЕДСТВЕННО за последней
    `state -> escalated` журнала, если это отдельная запись, а не
    следующий переход состояния; иначе `None`.

    Именно эту позицию описывают AC-1/AC-2 («сразу после записи
    `state -> escalated`, до возврата»): если маркера нет, следующей
    записью журнала оказывается уже запись возврата Оператора
    (`state -> <состояние роли>`) — она отсеивается проверкой префикса, и
    функция честно возвращает `None`. Текст `action` маркера здесь не
    зашит: его выбирает реализация (SPEC «Оценка объёма и деление» —
    место константы решает разработчик), тесты сверяют его между двумя
    точками эскалации, а не с литералом.
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
    КАКАЯ роль отработала шаг (тот же помощник, что и в планке
    `tasks/01M1RHFRQ2C0P4A57XJJ1WZV8N/`)."""
    return [row["actor"] for row in store.task_steps(conn, task_id)
            if row["action"] == "agent run finished"]


class EscalationByArtifactSandbox(AutoCycleTest):
    """`AutoCycleTest` + артефакты, поднимающие эскалацию по содержимому,
    ответ Оператора и чтение журнала вокруг `state -> escalated`."""

    def setUp(self):
        super().setUp()
        # Роль `analyst` подключается к `spec_writing` только при
        # заведённом TZ.md (SPEC T025, `runner.step_role`) — `cmd_new`
        # песочницы зовётся без `--tz`, файл кладётся здесь.
        (self.tdir / "TZ.md").write_text(TZ_MD, encoding="utf-8")

    # ------------------------------------------------------- артефакты

    def write_spec(self, status: str = "draft") -> None:
        (self.tdir / "SPEC.md").write_text(
            SPEC_MD.format(task=self.TASK, status=status), encoding="utf-8")

    def write_plank(self, *, escalate: bool) -> Path:
        """Планка фикстуры: `escalate=True` — второй критерий помечен
        `escalate` (эскалация `tests_writing` по содержимому артефакта);
        `escalate=False` — пометки нет, оба критерия покрыты тестами
        (выход в `in_dev` открыт)."""
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        text = _PLANK_HEAD.format(one=1)
        if escalate:
            text += "\n\n" + ac_mark(2, "escalate", "критерий фикстуры "
                                     "сформулирован противоречиво") + "\n"
        else:
            text += _PLANK_SECOND_TEST.format(two=2)
        path = tests_dir / "test_plank_fixture.py"
        path.write_text(text, encoding="utf-8")
        return path

    def write_questions(self, n: int = 1) -> Path:
        path = self.tdir / "QUESTIONS.md"
        path.write_text(QUESTIONS_MD.format(task=self.TASK, n=n),
                        encoding="utf-8")
        return path

    def remove_questions(self) -> None:
        """Батч снят самой ролью — так его убирает analyst своим следующим
        шагом (skills/spec-authoring, `orchestrator/checkpoint.py`)."""
        (self.tdir / "QUESTIONS.md").unlink(missing_ok=True)

    def answer_count(self) -> int:
        return len(list(self.tdir.glob("ANSWER-*.md")))

    def write_answer(self) -> Path:
        """Следующий по номеру `ANSWER-n.md` — наблюдаемый результат
        команды `answer` для всех её читателей в этом сценарии."""
        n = self.answer_count() + 1
        path = self.tdir / f"ANSWER-{n}.md"
        path.write_text(ANSWER_MD.format(task=self.TASK, n=n),
                        encoding="utf-8")
        return path

    # -------------------------------------------------------- переходы

    def escalate_tests_writing(self) -> str:
        """`tests_writing -> escalated` по пометке `escalate` в планке."""
        self.write_spec()
        self.write_plank(escalate=True)
        self.set_state("tests_writing")
        return self.capture(fsm.cmd_advance, self.TASK)

    def escalate_spec_writing(self, n: int = 1) -> str:
        """`spec_writing -> escalated` по батчу `QUESTIONS.md`."""
        self.write_spec()
        self.write_questions(n)
        self.set_state("spec_writing")
        return self.capture(fsm.cmd_advance, self.TASK)

    def answer_and_approve(self) -> str:
        """Ответ Оператора (`answer`) и возврат из эскалации (`approve`)."""
        self.write_answer()
        return self.capture(fsm.cmd_approve, self.TASK)

    # --------------------------------------------------------- журнал

    def rows(self) -> list:
        return meaningful_rows(store.db(), self.TASK)

    def marker_index(self) -> int:
        """Индекс маркерной записи; проваливает тест, если её нет."""
        index = escalation_marker_index(self.rows())
        self.assertIsNotNone(
            index, "сразу за записью state -> escalated нет отдельной "
            "записи маркера — эскалация по содержимому артефакта роли "
            "ничем себя не пометила")
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

    def index_of_first_role_step(self, role: str) -> int:
        rows = self.rows()
        for i, r in enumerate(rows):
            if r["action"] == "agent run finished" and r["actor"] == role:
                return i
        self.fail(f"роль {role} не отработала ни одного шага — "
                  f"`agent run finished` под её именем в журнале нет")
