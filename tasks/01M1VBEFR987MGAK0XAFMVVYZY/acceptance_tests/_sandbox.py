"""Общая песочница приёмочных тестов задачи 01M1VBEFR987MGAK0XAFMVVYZY
(«answer для задачи в in_dev (мандат на расширение зон), zones-extend,
amend-tests --from-branch»).

Настоящий git (`tests.sandbox.RealGitSandbox`) — все три требования этой
задачи наблюдаемы только через реальные git-объекты артефактной ветки
пульта (`artifact_branch.commit_files`/`gitcmd.ls_tree_files`/`gitcmd.show`)
и реальный `tests_locked_sha`: заглушкой `gitcmd.git` (как в лёгких
песочницах `tests/sandbox.TmpRootTest`) их не изобразить — тот же довод,
что уже несёт `tests/test_amend.py::AmendThenReviewGateTest`, чей каркас
`enter_in_dev` эта песочница дословно расширяет полем `zones`.

Команда `zones-extend` этой задачи ещё не существует ни в одном модуле
(SPEC не называет, в каком файле её заводит разработчик — материалы
SPEC перечисляют только уже существующий канал `_answer_zones_mandate`/
`_plan_zones_extension_paths`/`_zones_gate` в `fsm_advance.py`, а не
адрес самой новой команды). Тесты на неё зовут её ЕДИНСТВЕННЫМ стабильным
адресом, который SPEC называет буквально — CLI-синтаксисом `zones-extend
<id> <путь>[, <путь>]` — через настоящий диспетчер `orchestrator/
artel.py::main()` с подменённым `sys.argv` (тот же приём, что уже
применяет `tests/test_invariants.py::WorktreeGuardTest.
test_worktree_root_refuses_before_touching_the_db`), а не через прямой
вызов внутренней функции конкретного модуля, чьё имя SPEC не фиксирует.

Список путей CLI (`<путь>[, <путь>]`) — ОДНА строка через запятую, тем же
форматом, что уже несут ВСЕ похожие поля системы (`zones:` SPEC, `Пути:`
PLAN.md, `Расширение зон разрешено:` ANSWER-n.md, `fsm_advance.
_split_zone_paths`) — не несколько позиционных argv (в отличие от
`zone-reorder <id1> <id2> ...`, где каждый id — самостоятельный
позиционный аргумент другой природы).
"""
import subprocess
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import (artel, artifact_branch, catalog, config, fsm,  # noqa: E402
                          gitcmd, store, workspace)
from tests.sandbox import RealGitSandbox, capture, capture_new_task_id  # noqa: E402
from tests.test_acceptance_tests_flow import AC_TEST_BOTH_COVERED, SPEC_V2  # noqa: E402

# PLAN.md обычный, БЕЗ раздела «## Расширение зон» — тот же минимум,
# что `tests/test_amend.py::PLAN_MD`/`AmendThenReviewGateTest`.
PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: приёмочные тесты до кода

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

# Раздел «## Расширение зон» (образец —
# tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/_sandbox.py::
# PLAN_WITH_ZONES_EXTENSION) — строка `Пути: <путь1>, <путь2>`, тем же
# приёмом CSV, что и `zones:` SPEC.
PLAN_WITH_ZONES_EXTENSION = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: приёмочные тесты до кода

## Подход

## Шаги

## Покрытие требований

## Влияние на систему

## Расширение зон

Пути: {paths}

{justification}
"""

QUESTIONS_TEXT = """---
task: {task}
type: questions
author_role: analyst
status: draft
schema_version: 2
---

# QUESTIONS: батч

## Вопросы

1. **Какой вариант выбрать?** — варианты: A) первый; B) второй — дефолт: A.
"""

# Правка планки (ANSWER-3, вопрос 2 tests/test_amend.py) — тот же приём,
# что `tests/test_amend.py::AC_TEST_AMENDED`: содержательно другой текст,
# по-прежнему покрывает оба критерия SPEC_V2 песочницы и проходит
# обязательный прогон (guard.scan_redness_markers не находит нарушений).
AC_TEST_DIVERGED = '''"""Красен до реализации: фикстура покрывает оба критерия SPEC_V2
песочницы (автокоммит шага роли добавил вторую проверку AC-1)."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)

    def test_ac1_first_criterion_again(self):
        self.assertEqual(1 + 1, 2)


# AC-2: manual — Оператор проверяет глазами на приёмке
'''


class TaskSandbox(RealGitSandbox):
    """Задача self-target (`config.DEFAULT_TARGET`) с реальной артефактной
    веткой пульта — тот же каркас, что `tests/test_amend.py::
    AmendThenReviewGateTest`/`tests/test_answer.py::_ArtifactBranchAnswerTest`."""

    TITLE = "answer в in_dev, zones-extend, amend-tests --from-branch"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, self.TITLE)
        self.branch = artifact_branch.branch_name(self.TASK)
        self.code_branch = self.row()["branch"]

    def row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.row()["state"]

    def set_state(self, state: str) -> None:
        """Прямая установка состояния в обход полного FSM-цикла — AC-1/
        AC-2/AC-7 проверяют реакцию `answer` НА состояние задачи, не путь,
        которым она до него дошла (тот же приём, что `tests/test_amend.py::
        LockedWindowTest._make_task`/`tests/test_zones_gate.py::
        ZonesGateNoDeclaredZoneSkipsTest`)."""
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def journal_details(self) -> list:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def journal_actions(self) -> list:
        return [r["action"] for r in store.db().execute(
            "SELECT action FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def artifact_commit(self, files: dict, message: str) -> str:
        sha = artifact_branch.commit_files(self.TASK, files,
                                           f"{self.TASK}: {message}")
        assert sha, f"коммит {message!r} на артефактную ветку не удался"
        return sha

    def artifact_branch_files(self) -> list:
        return gitcmd.ls_tree_files(self.branch, f"tasks/{self.TASK}") or []

    def artifact_branch_text(self, rel: str) -> str:
        text, _reason = gitcmd.show(self.branch, rel)
        return text or ""

    def escalate(self) -> None:
        self.artifact_commit(
            {f"tasks/{self.TASK}/QUESTIONS.md": QUESTIONS_TEXT.format(task=self.TASK)},
            "батч вопросов")
        capture(fsm.cmd_advance, self.TASK)
        assert self.state() == "escalated", self.state()

    def enter_in_dev(self, zones: str | None = None) -> None:
        """Как `tests/test_amend.py::AmendThenReviewGateTest.enter_in_dev`,
        плюс опциональное поле `zones:` фронтматтера SPEC — `fsm.
        _approve_spec_gate` сохраняет его в `tasks.zones` независимо от
        `schema_version` (только guard требует его заполненности при
        версии >= 4, `guard.requires_zones`); версия 2 этой планки его не
        требует, но колонка всё равно заполняется, если поле присутствует."""
        extra = f"zones: {zones}\n" if zones else ""
        self.artifact_commit(
            {f"tasks/{self.TASK}/SPEC.md": SPEC_V2.format(task=self.TASK, extra=extra)},
            "SPEC")
        capture(fsm.cmd_advance, self.TASK)  # spec_writing -> spec_gate
        sha = gitcmd.head_sha(config.PROJECTS / config.DEFAULT_TARGET)
        capture(fsm.cmd_approve, self.TASK, sha)  # -> tests_writing
        assert self.state() == "tests_writing", self.state()

        self.artifact_commit(
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py": AC_TEST_BOTH_COVERED},
            "acceptance_tests")
        capture(fsm.cmd_advance, self.TASK)  # tests_writing -> in_dev
        assert self.state() == "in_dev", self.state()

    def commit_code_file(self, rel: str, text: str = "код\n") -> None:
        """Коммит файла КОДА в worktree ветки задачи (`self.code_branch`)
        — та же плоскость, что и `AmendThenReviewGateTest.setUp`
        (`feature.txt`), но параметризуемая по пути: задаёт дифф вне
        заявленных zones для гейта зон."""
        wt_path, error = workspace.ensure(self.TASK, self.code_branch)
        assert error is None, f"worktree не создан: {error}"
        path = wt_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.git_wt(wt_path, "add", "--", rel)
        self.git_wt(wt_path, "commit", "-q", "-m", f"{self.TASK}: {rel}")

    def git_wt(self, wt_path: Path, *args: str) -> str:
        res = subprocess.run(["git", "-C", str(wt_path), *args],
                             capture_output=True, text=True)
        assert res.returncode == 0, f"git -C {wt_path} {' '.join(args)}: {res.stderr}"
        return res.stdout

    def run_cli(self, *args: str) -> str:
        """Прогон команды через настоящий CLI-диспетчер `artel.py main()`
        (см. докстринг модуля) — единственный стабильный адрес ещё не
        реализованной `zones-extend`, и заодно точный CLI-контракт
        `amend-tests ... --from-branch` (реальный разбор argv, а не
        предположение о сигнатуре внутренней функции)."""
        with mock.patch.object(sys, "argv", ["artel.py", *args]):
            return capture(artel.main)
