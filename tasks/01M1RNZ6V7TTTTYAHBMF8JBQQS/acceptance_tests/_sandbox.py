"""Общая песочница приёмочных тестов задачи 01M1RNZ6V7TTTTYAHBMF8JBQQS (не
test_*.py — не подхватывается `unittest discover` напрямую, только импортом
из test_ac*.py).

НАСТОЯЩИЙ git на всём протяжении (тот же принцип, что и `tasks/
01M1R9YEK08XEQWBFX0929WFVJ/acceptance_tests/_sandbox.py`): предмет
проверки этой задачи — резолвинг `orchestrator/` кодовой ветки ПОСЛЕ
материализации планки и с ПРАВИЛЬНЫМ `cwd`, заглушкой git/файловой
системы это не изобразить.

`MarkerPullSandbox` — предмет проверки AC-1, AC-2, AC-3, AC-4, AC-6, AC-7,
AC-8: узел `fsm._pull_main_or_escalate` (self-target). Кодовая ветка
задачи СПЕЦИАЛЬНО заводится ПОЗАДИ main на origin (main получает лишний
коммит уже после ответвления кодовой ветки) — иначе `_pull_main_or_escalate`
вернёт `"fresh"` и планка не прогоняется вовсе (тот же приём, что
`tasks/01M1R9YEK08XEQWBFX0929WFVJ/acceptance_tests/_sandbox.py::
AcceptancePullSandbox`).

Фикстура-маркер (`MARKER_NEW_MODULE`) — модуль `orchestrator/marker.py`
внутри ПЕСОЧНИЦЫ (не настоящий пакет пульта: `self.root` — отдельный
временный git-репозиторий с ОДНИМ файлом `marker.txt` на main, см.
`RealGitSandbox.setUp`), с функцией `value()`, возвращающей `"new"`.
Кодовая ветка задачи несёт этот модуль; main — нет вовсе (`ModuleNotFoundError`
при попытке импортировать его от main). Планка, читающая `orchestrator.marker.
value()`, различает два источника кода однозначно: `"new"` — код резолвился
в кодовую ветку задачи, `ModuleNotFoundError`/иное — код резолвился в main
(регрессия №14, «Контекст» SPEC).

`ExternalWorkspaceReviewSandbox` — предмет проверки AC-5: та же фикстура
для внешнего target, чей код — обычный каталог `config.PROJECTS/<target>/
workspace/` (не git worktree пульта, ADR-0003 §4) — без git вовсе на
стороне кода, только на стороне артефактной ветки пульта (`self.root`).
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import (acceptance, artifact_branch, catalog, config,  # noqa: E402
                          fsm, fsm_advance, gitcmd, store, workspace)
from tests.sandbox import RealGitSandbox, capture, capture_new_task_id  # noqa: E402

SPEC_MARKER_FIXTURE = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: фикстура планки-маркера (не собственный SPEC этой задачи)

## Контекст
Фикстура для песочницы 01M1RNZ6V7TTTTYAHBMF8JBQQS.

## Требования
1. Фикстура.

## Критерии приёмки

AC-1. Фикстура — маркер кода ветки задачи.
"""

# Модуль-маркер: кодовая ветка задачи несёт "new", main его не несёт вовсе.
MARKER_NEW_MODULE = '''"""Зелёный с рождения: фикстура — значение несёт ТОЛЬКО кодовая ветка
задачи, не main (регрессия №14, песочница 01M1RNZ6V7TTTTYAHBMF8JBQQS)."""


def value():
    return "new"
'''

# Планка, резолвящая `orchestrator` от __file__ (парадигма регрессии №14,
# "Контекст" SPEC: `Path(__file__).resolve().parents[3]`) — зелёная, только
# если МАТЕРИАЛИЗАЦИЯ (AC-1) положила планку в тот же каталог, что несёт
# кодовую ветку задачи.
MARKER_TEST_VIA_FILE = '''"""Зелёный с рождения: фикстура — планка резолвит orchestrator/ от
__file__ (та же парадигма, что реальные планки задач, SPEC «Контекст»)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import marker  # noqa: E402


class MarkerViaFileTest(unittest.TestCase):

    def test_marker_resolves_from_file(self):
        self.assertEqual(marker.value(), "new")
'''

# Планка БЕЗ sys.path.insert от __file__ — резолвит orchestrator/ ТОЛЬКО
# через неявную вставку cwd в sys.path, которую делает `python3 -m
# unittest discover` (SPEC «Контекст»: «запасной путь через cwd»). Зелёная,
# только если ПРОГОН (AC-2) идёт с cwd, равным тому же каталогу.
MARKER_TEST_VIA_CWD = '''"""Зелёный с рождения: фикстура — планка резолвит orchestrator/ ТОЛЬКО
через cwd процесса (без sys.path.insert от __file__), в отличие от
MarkerViaFileTest рядом."""
import unittest

from orchestrator import marker


class MarkerViaCwdTest(unittest.TestCase):

    def test_marker_resolves_from_cwd(self):
        self.assertEqual(marker.value(), "new")
'''

STALE_TEST = '''"""Зелёный с рождения: фикстура — заведомо ПАДАЮЩИЙ тест, симулирующий
устаревшую копию планки, оставшуюся в рабочем каталоге от предыдущего
прогона (AC-8)."""
import unittest


class StaleTest(unittest.TestCase):

    def test_stale_fails(self):
        self.fail("устаревшая копия планки не должна остаться после материализации")
'''


class MarkerPullSandbox(RealGitSandbox):
    """Задача в состоянии `acceptance`; кодовая ветка на один коммит
    ПОЗАДИ main на origin (`_pull_main_or_escalate` обязана подтянуть и
    прогнать планку) — байт-в-байт та же топология, что `tasks/
    01M1R9YEK08XEQWBFX0929WFVJ/acceptance_tests/_sandbox.py::
    AcceptancePullSandbox`, только фикстура планки — модуль-маркер, не
    пара RED/GREEN файлов."""

    TASK = "01MARKERPULLSANDBOX0001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)

        self.origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.origin, ignore_errors=True)
        self.git("init", "-q", "--bare", str(self.origin))
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)

        self.branch = f"task/{self.TASK.lower()}-x"
        self.git("checkout", "-q", "-b", self.branch)
        self.write_marker_on_code_branch()
        self.git("checkout", "-q", config.MAIN_BRANCH)

        # main уходит вперёд ПОСЛЕ ответвления кодовой ветки — ветка
        # задачи отстаёт, `_pull_main_or_escalate` обязана подтянуть.
        # main НЕ несёт orchestrator/marker.py вовсе.
        (self.root / "main-advance.txt").write_text(
            "main ушёл вперёд после ответвления\n", encoding="utf-8")
        self.git("add", "main-advance.txt")
        self.git("commit", "-q", "-m", "main ушёл вперёд")
        self.git("push", "-q", "origin", config.MAIN_BRANCH)

        store.insert_task(store.db(), self.TASK, "Песочница планки-маркера",
                          "acceptance", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    # ------------------------------------------------------------ утилиты

    def write_marker_on_code_branch(self, content: str = MARKER_NEW_MODULE) -> None:
        """Пишет `orchestrator/marker.py` ПРЯМО в рабочее дерево `self.root`
        (в этот момент оно уже на кодовой ветке задачи, см. `setUp`/
        вызывающий код) и коммитит — та же техника, что `feature.txt` у
        `tasks/01M1R9YEK08XEQWBFX0929WFVJ/.../_sandbox.py`."""
        pkg = self.root / "orchestrator"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "marker.py").write_text(content, encoding="utf-8")
        self.git("add", "orchestrator")
        self.git("commit", "-q", "-m", f"{self.TASK}: маркер кода ветки")

    def commit_artifact(self, files: dict) -> None:
        sha = artifact_branch.commit_files(self.TASK, files,
                                           f"{self.TASK}: фикстура планки")
        self.assertTrue(sha, "artifact_branch.commit_files не сработал")

    def commit_marker_plank(self, plank_files: dict) -> None:
        """`plank_files` — {имя файла в acceptance_tests/: содержимое}."""
        files = {f"tasks/{self.TASK}/SPEC.md":
                SPEC_MARKER_FIXTURE.format(task=self.TASK)}
        for name, content in plank_files.items():
            files[f"tasks/{self.TASK}/acceptance_tests/{name}"] = content
        self.commit_artifact(files)

    def task_row(self):
        return store.get_task(store.db(), self.TASK)

    def state(self) -> str:
        return self.task_row()["state"]

    def journal_details(self) -> list[str]:
        return [f"{r['action']} {r['detail']}" for r in store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def pull(self, state: str = "acceptance") -> str:
        conn = store.db()
        t = store.get_task(conn, self.TASK)
        return fsm._pull_main_or_escalate(conn, self.TASK, t, state)

    def worktree_dir(self) -> Path:
        """Каталог worktree задачи, если он уже заведён (`_pull_main_or_
        escalate` заводит его сама при первом реальном подтягивании) —
        штатный путь материализации по AC-1 (`workspace.path`), см.
        докстринг `fsm.role_cwd`/использование в `fsm_advance.review`
        (`workspace.path(task_id) / "tasks" / task_id`)."""
        return workspace.path(self.TASK)

    def materialized_acceptance_dir(self) -> Path:
        return self.worktree_dir() / "tasks" / self.TASK / "acceptance_tests"


class BranchWithoutNewBehaviorSandbox(MarkerPullSandbox):
    """Тот же `MarkerPullSandbox`, но кодовая ветка НЕ несёт `orchestrator/
    marker.py` вовсе (родительский `setUp` кладёт его — здесь перекрываем
    коммит пустышкой, чтобы ветка осталась ровно там же, где main) —
    общая фикстура «код без нового поведения» для AC-6 (текст detail) и
    AC-7 (страховка от тавтологии), обе стороны которой не должны сами
    расходиться в топологии песочницы."""

    def write_marker_on_code_branch(self, content: str = "") -> None:
        # Ничего не пишем — кодовая ветка задачи «без нового поведения»,
        # ровно как main; пустой commit --allow-empty делает шаг
        # эксплицитным и симметричным родительскому вызову.
        self.git("commit", "-q", "--allow-empty", "-m",
                f"{self.TASK}: кодовая ветка без нового поведения")


class ExternalWorkspaceReviewSandbox(RealGitSandbox):
    """Задача внешнего target в состоянии `review`, готовая к approved
    вердикту — `fsm_advance.review`/`verifying` вызываются НАПРЯМУЮ (тот
    же приём, что `tasks/01M1R9YEK08XEQWBFX0929WFVJ/.../_sandbox.py::
    MergeGateSnapshotSandbox` зовёт `fsm_merge_gate._cmd_approve_merge_gate`
    напрямую) — полный цикл analyst -> developer -> reviewer не нужен
    предмету проверки (материализация+прогон планки на входе в
    `acceptance`), а его настоящая топология (draft MR, происхождение
    ветки) здесь ни при чём.

    `is_canary=True` на строке задачи — не для канареечного поведения
    само по себе, а чтобы `review()` не требовал реального push головы в
    origin (`github_adapter.ensure_head_in_origin`, ветка кода которой в
    этой песочнице нет вовсе — внешний target здесь не несёт git
    worktree'а с кодовой веткой, только каталог `workspace/`, ADR-0003
    §4) — тот же короткий путь, каким уже пользуется прод для
    канареечных задач по той же причине (`orchestrator/fsm_advance.py`,
    докстринг `review()`).
    """

    TASK = "01EXTWORKSPACEREVIEW01"
    TARGET = "ut-marker-external-target"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)

        self.workspace_root = config.PROJECTS / self.TARGET / "workspace"
        self.workspace_root.mkdir(parents=True, exist_ok=True)

        store.insert_task(store.db(), self.TASK, "Песочница внешнего target",
                          "review", f"task/{self.TASK.lower()}-x",
                          self.TARGET, config.DEFAULT_BUDGET_USD,
                          )
        store.update_task(store.db(), self.TASK, is_canary=1)

    # ------------------------------------------------------------ утилиты

    def write_marker_in_workspace(self, content: str = MARKER_NEW_MODULE) -> None:
        pkg = self.workspace_root / "orchestrator"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "marker.py").write_text(content, encoding="utf-8")

    def commit_review_artifacts(self, plank_files: dict,
                                review_status: str = "approved") -> None:
        files = {
            f"tasks/{self.TASK}/SPEC.md": SPEC_MARKER_FIXTURE.format(task=self.TASK),
            f"tasks/{self.TASK}/PLAN.md": (
                "---\ntask: {task}\ntype: plan\nauthor_role: developer\n"
                "status: ready\nschema_version: 2\n---\n\n"
                "# PLAN\n\n## Подход\n\n## Шаги\n\n"
                "## Покрытие требований\n\n## Влияние на систему\n"
            ).format(task=self.TASK),
            f"tasks/{self.TASK}/REVIEW.md": (
                "---\ntask: {task}\ntype: review\nauthor_role: reviewer\n"
                f"status: {review_status}\niteration: 1\nschema_version: 2\n"
                "---\n\n# REVIEW\n\n## Соответствие SPEC\n\n## Замечания\n\n"
                f"## Вердикт\n{review_status}\n\n"
                "## Проверено исполнением\n`python3 -m unittest discover "
                "-s tests` — зелёный.\n"
            ).format(task=self.TASK),
        }
        for name, content in plank_files.items():
            files[f"tasks/{self.TASK}/acceptance_tests/{name}"] = content
        sha = artifact_branch.commit_files(self.TASK, files,
                                           f"{self.TASK}: фикстура ревью")
        self.assertTrue(sha, "artifact_branch.commit_files не сработал")

    def task_row(self):
        return store.get_task(store.db(), self.TASK)

    def state(self) -> str:
        return self.task_row()["state"]

    def journal_details(self) -> list[str]:
        return [f"{r['action']} {r['detail']}" for r in store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def run_review(self) -> bool:
        conn = store.db()
        t = store.get_task(conn, self.TASK)
        tdir = config.TASKS / self.TASK
        return fsm_advance.review(conn, self.TASK, t, tdir, self.TARGET, "review")

    def run_verifying(self) -> bool:
        conn = store.db()
        t = store.get_task(conn, self.TASK)
        tdir = config.TASKS / self.TASK
        with mock.patch("orchestrator.ci.verifying_status",
                        return_value=("green", "CI зелёный (тест)")):
            return fsm_advance.verifying(conn, self.TASK, t, tdir,
                                         self.TARGET, "verifying")


if __name__ == "__main__":
    unittest.main()
