"""Общая песочница приёмочных тестов T075 (не test_*.py — не подхватывается
unittest discover напрямую, только импортом из test_ac*.py).

Лёгкая песочница (`gitcmd.git` заглушкой `fake_git`, тот же приём, что
`tests/test_acceptance_tests_flow.py::_AcceptanceFlowTmpRootTest` и
`tests/test_analyst_role.py::_AnalystRoleTmpRootTest`): с этой заглушкой
`gitcmd.current_branch()` пустая строка, `gitcmd.on_foreign_branch()`
всегда False — артефакты читаются с диска (`config.TASKS/<id>/...`), не
с ветки git. SPEC T075 формулирует критерии через «ANSWER-n.md на ветке
задачи», но сама механика гейта (нужен ли ANSWER для этого класса
эскалации, что происходит после его появления) не зависит от того,
берётся ли файл с диска или с ветки — эта ортогональная ось
(«ветко-корректное чтение») уже отдельный инвариант 28 реестра
(docs/invariants.md, T031/T047), который T075 не расширяет явно ни в
одном AC. Дублировать его здесь для ANSWER.md — не критерий этой задачи.

`fixation.read()` в этой песочнице возвращает пустой sha (вырожденный
случай — git не отвечает) — `fsm.cmd_approve` не требует sha явно,
тем же приёмом, что `tests/test_analyst_role.py::
test_approve_from_escalated_returns_to_spec_writing`.

Обёртки `write_answer` кладут `tasks/<id>/ANSWER-n.md` НАПРЯМУЮ на диск,
минуя CLI-команду Оператора `answer` (AC-2, покрыта отдельно —
`test_ac2_answer_command.py`, песочница `RealPultGitTest` с настоящим
git: эта лёгкая песочница с заглушкой `gitcmd.git` не воспроизводит ни
коммит, ни авторство, см. её же докстринг выше): тестам AC-3/AC-4/AC-5/
AC-6 нужен только ФАКТ существования файла как входного условия гейта
возврата, не то, как он туда попал.
"""
import shutil
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import catalog, config, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest as _BaseTmpRootTest  # noqa: E402
from tests.sandbox import fake_git  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]

SPEC_V2_READY = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: песочница T075

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Первый критерий фиктивной задачи.
AC-2. Второй критерий фиктивной задачи.

## Не входит
"""

QUESTIONS_VALID = """---
task: {task}
type: questions
author_role: analyst
status: draft
schema_version: 2
---

# QUESTIONS: батч песочницы T075

## Вопросы

1. **Какой вариант выбрать?** — варианты: A) первый; B) второй — дефолт: A.

МАРКЕР-ВОПРОСА-T075-ПЕСОЧНИЦЫ
"""

# Покрытие AC-1 тестом, AC-2 — escalate-пометкой (тот же приём, что
# tests/test_acceptance_tests_flow.py::AC_TEST_ESCALATE_AC2): эскалация
# проверяется раньше трассируемости остальных критериев (fsm.py,
# `_cmd_advance`, ветка `tests_writing`), так что непокрытый AC-1 не мешает.
# Маркер собран конкатенацией, чтобы литерал «AC-n: escalate» не встречался
# в тексте ЭТОГО файла: сканер AC-маркеров (scripts/guard.py::
# scan_acceptance_tests) читает все *.py каталога, включая _sandbox.py,
# и принял бы фикстуру за настоящую эскалацию задачи T075 (случилось
# 31.08, ложная эскалация; системный фикс сканера — отдельная строка
# роадмапа, приём «только test_*.py» уже применён T064 к маркерам красноты).
AC_TEST_ESCALATE = """import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)


""" + "# AC-2: esca" + "late — критерий сформулирован противоречиво, тест не пишется\n"

REVIEW_ESCALATE = """---
task: {task}
type: review
author_role: reviewer
status: escalate
iteration: 1
schema_version: 2
---

# REVIEW: песочница T075

## Соответствие SPEC

## Замечания

МАРКЕР-ЭСКАЛАЦИИ-РЕВЬЮВЕРА-T075

## Вердикт

escalate
"""

REVIEW_CHANGES_REQUESTED = """---
task: {task}
type: review
author_role: reviewer
status: changes_requested
iteration: {iteration}
schema_version: 2
---

# REVIEW: песочница T075

## Соответствие SPEC

## Замечания

- почини X

## Вердикт

changes_requested
"""

# Не guard-валиден по формальной схеме (templates/ANSWER.md ещё не
# существует на момент написания этих тестов, RULES guard'а не знает тип
# "answer" — AC-1) — но несёт разумный набор полей по аналогии с прочими
# артефактами Оператора (tasks/<id>/TZ.md), этого достаточно как входного
# условия для гейта возврата (AC-3/AC-4/AC-6): им нужен факт существования
# файла с текстом ответа, не прохождение guard'а самим этим файлом.
ANSWER_TEXT = """---
task: {task}
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-{n}: ответ Оператора

Ответ Оператора по батчу вопросов: используем вариант A.

МАРКЕР-ОТВЕТА-T075-ПЕСОЧНИЦЫ-{n}
"""


class AnswerGateTmpRootTest(_BaseTmpRootTest):
    """Задача T001 в лёгкой песочнице: БД и артефакты во временном
    каталоге, `gitcmd.git` — заглушка `fake_git` (артефакты читаются с
    диска, не с ветки — см. докстринг модуля)."""

    TASK = "T001"
    PATCHED_ATTRS = ("DB", "TASKS", "LOGS", "ROLE_HOME", "ROLE_CONFIG_DIR",
                     "WORKTREES", "ROOT")

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Песочница T075")
        self.tdir = config.TASKS / self.TASK
        self.tdir.mkdir(parents=True, exist_ok=True)

    # -- задача / состояние -------------------------------------------

    def state(self) -> str:
        return store.db().execute(
            "SELECT state FROM tasks WHERE id=?", (self.TASK,)).fetchone()[0]

    def row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def set_state(self, state: str, **fields) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()
        if fields:
            store.update_task(conn, self.TASK, **fields)

    def journal_details(self, action: str | None = None) -> list[str]:
        if action is None:
            return [r["detail"] for r in store.db().execute(
                "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
                (self.TASK,))]
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? "
            "ORDER BY id", (self.TASK, action))]

    # -- артефакты -------------------------------------------------

    def write(self, name: str, template: str, **extra) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / name).write_text(
            template.format(task=self.TASK, **extra), encoding="utf-8")

    def write_spec(self) -> None:
        self.write("SPEC.md", SPEC_V2_READY)

    def write_questions(self) -> None:
        self.write("QUESTIONS.md", QUESTIONS_VALID)

    def write_acceptance_tests(self, content: str,
                               name: str = "test_ac.py") -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def write_review(self, template: str, iteration: int = 1) -> None:
        self.write("REVIEW.md", template, iteration=iteration)

    def write_answer(self, n: int = 1) -> Path:
        path = self.tdir / f"ANSWER-{n}.md"
        path.write_text(ANSWER_TEXT.format(task=self.TASK, n=n),
                        encoding="utf-8")
        return path

    # -- сценарии эскалации (общие для AC-3/AC-4/AC-5) -----------------

    def escalate_from_spec_writing_questions(self) -> None:
        """spec_writing + QUESTIONS.md -> escalated (эскалация analyst,
        существующая механика fsm.py — не проверяется здесь заново)."""
        from orchestrator import fsm
        self.write_questions()
        self.capture(fsm.cmd_advance, self.TASK)
        assert self.state() == "escalated", "подготовка сценария не удалась"

    def escalate_from_tests_writing_ac_marker(self) -> None:
        """tests_writing + `AC-2: escalate` -> escalated (существующая
        механика fsm.py, SPEC T023 требование 4)."""
        from orchestrator import fsm
        self.write_spec()
        self.set_state("tests_writing")
        self.write_acceptance_tests(AC_TEST_ESCALATE)
        self.capture(fsm.cmd_advance, self.TASK)
        assert self.state() == "escalated", "подготовка сценария не удалась"

    def escalate_from_review_verdict(self) -> None:
        """review + REVIEW.md `status: escalate` -> escalated (существующая
        механика fsm.py:746-748)."""
        from orchestrator import fsm
        self.set_state("review")
        self.write_review(REVIEW_ESCALATE)
        self.capture(fsm.cmd_advance, self.TASK)
        assert self.state() == "escalated", "подготовка сценария не удалась"
