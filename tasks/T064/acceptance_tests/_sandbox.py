"""Общая песочница и фикстуры для приёмочных тестов T064.

Не подпадает под маркерную проверку самой задачи (SPEC требование 1
называет только `test_*.py` — этот файл в выборку не входит).

Копия лёгкой песочницы `_AcceptanceFlowTmpRootTest`
(tests/test_acceptance_tests_flow.py) — тот же приём (БД/артефакты во
временном каталоге, `gitcmd.git` заглушкой `fake_git`), которым уже
покрыт соседний механизм трассируемости AC -> тест (T023), тем же
местом вызова FSM (`orchestrator/fsm.py::_tests_writing_ac_state`,
SPEC T064 «Материалы»). Не переиспользуется напрямую импортом из
tests/, потому что `_AcceptanceFlowTmpRootTest` — приватный класс
модуля, не публичный интерфейс tests/sandbox.py.
"""
import shutil
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, config, fsm, gitcmd, store  # noqa: E402
from tests.sandbox import TmpRootTest as _BaseTmpRootTest  # noqa: E402
from tests.sandbox import fake_git  # noqa: E402

SPEC_V2 = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
{extra}---

# SPEC: guard объяснённая краснота (песочница T064)

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Первый критерий, проверяемый тестом.
AC-2. Второй критерий, проверяемый тестом.

## Не входит
"""

PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: guard объяснённая краснота (песочница T064)

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: guard объяснённая краснота (песочница T064)

## Соответствие SPEC

## Замечания

## Вердикт

## Проверено исполнением
`python3 -m unittest discover -s tests` — зелёный (фикстура; секция
обязательна для approved с T072 — дочинено Оператором 01.09, ANSWER T085).
"""

# Полное покрытие AC-1/AC-2 реальными тестами, БЕЗ маркера красноты в
# докстринге модуля — сценарий AC-1 (SPEC T064).
AC_TEST_NO_MARKER = """import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)

    def test_ac2_second_criterion(self):
        self.assertEqual(1 + 1, 2)
"""

# То же покрытие, докстринг несёт маркер «Красен до реализации:» с
# непустым объяснением — первый вариант сценария AC-2 (SPEC T064).
AC_TEST_WITH_RED_MARKER = '''"""Красен до реализации: код проверки маркера в guard.py ещё не
написан — это фикстура-песочница, не сама задача T064."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)

    def test_ac2_second_criterion(self):
        self.assertEqual(1 + 1, 2)
'''

# То же покрытие, докстринг несёт маркер «Зелёный с рождения:» —
# второй допустимый вариант формы маркера (SPEC T064, требование 1).
AC_TEST_WITH_GREEN_MARKER = '''"""Зелёный с рождения: фикстура-песочница проверяет сохранение
существующего поведения, реализации задачи не требует."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)

    def test_ac2_second_criterion(self):
        self.assertEqual(1 + 1, 2)
'''


class _T064TmpRootTest(_BaseTmpRootTest):
    """Лёгкая песочница: БД и артефакты во временном каталоге, git — заглушка.

    `ROOT` тоже уводится (холодный старт сканирует его для посева
    счётчика) — `templates/`/`skills/` копируются рядом, `cmd_new`
    продолжает читать настоящий `templates/SPEC.md`, только уже из
    песочницы (см. tests/test_acceptance_tests_flow.py, тот же приём).
    """

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
        self.capture(catalog.cmd_new, "Guard объяснённая краснота (песочница)")
        self.tdir = config.TASKS / self.TASK
        self.tdir.mkdir(parents=True, exist_ok=True)

    def state(self) -> str:
        return store.db().execute("SELECT state FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()[0]

    def row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def write_spec(self, template: str, extra: str = "") -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            template.format(task=self.TASK, extra=extra), encoding="utf-8")

    def write(self, name: str, text: str) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / name).write_text(text.format(task=self.TASK),
                                      encoding="utf-8")

    def write_acceptance_tests(self, content: str,
                               name: str = "test_ac.py") -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]

    def enter_tests_writing(self) -> None:
        self.write_spec(SPEC_V2)
        self.set_state("tests_writing")

    def enter_review(self) -> None:
        self.write_spec(SPEC_V2)
        self.write("PLAN.md", PLAN_MD)
        self.write("REVIEW.md", REVIEW_MD)
        self.set_state("review")


TmpRootTest = _T064TmpRootTest
