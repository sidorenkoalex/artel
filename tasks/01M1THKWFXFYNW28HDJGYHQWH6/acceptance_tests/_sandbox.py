"""Общая песочница приёмочных тестов задачи (не test_*.py — не подхватывается
`unittest discover` напрямую, только импортом из test_ac*.py).

FSM читает SPEC.md/PLAN.md/REVIEW.md всегда с АРТЕФАКТНОЙ ветки пульта
(`artifact/<id>`, `orchestrator/artifact_source.py::resolve` — «всегда
foreign=True»), не с диска и не из worktree кодовой ветки: пишем туда
плотницки, тем же приёмом, что `tests/test_git_fixation.py::
RealPultGitTest._seed_artifact_branch` (`artifact_branch.commit_files`).
Кодовая ветка задачи (`t["branch"]`, `task/<id>-...`) нужна отдельно —
её читают гейты `_capacity_gate_refuses`/`_zones_gate_refuses`/
`_review_rework_gate_refuses`/`_pull_main_or_escalate` (`git diff`/`git
log` в `config.ROOT`) и, для сценария AC-4 «возврат из приёмки»,
`github_adapter.ensure_head_in_origin` (реальный push в origin) — заводится
здесь ОБЫЧНЫМ `git branch` от `main`, без worktree: ни одна из этих точек
не требует чекаута, только существования ref'а.

Флоу до `review` нарочно короткий: SPEC.md несёт `schema_version: 1` (без
AC-разметки и без `zones:`) — `tests_writing` пропускается, гейт зон
(`_zones_gate_refuses`) не участвует (задача без заявленной зоны — гейт не
звонится, `t["zones"]` пуст). Это решение теста, не факт SPEC этой задачи
— если разработчик собьёт эту цепочку, сама песочница откажет явным
`assert`, а не тихо разойдётся с реализацией.

Потолок задачи (`budget_usd`/`budget_source`) эта песочница выставляет
НАПРЯМУЮ через `store.update_task` (`set_budget`), в обход
`budget.apply_spec_budget` — часть 1 ADR-0014 (`ROLE_BUDGET_CAP`,
двусторонний потолок из SPEC) на момент написания этой планки ещё не
смержена (см. маркер красноты в докстринге каждого `test_ac*.py`), и
фиксировать здесь предположения о деталях ЕЁ реализации не входит в задачу
части 2 — эта песочница проверяет только переоценку потолка НА PLAN,
отталкиваясь от УЖЕ УСТАНОВЛЕННОГО потолка, каким бы каналом он ни был
установлен.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import (artifact_branch, catalog, ci, config, fsm,  # noqa: E402
                          gitcmd, store)
from tests.sandbox import capture, capture_new_task_id, resilient_tmp_cleanup  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]

SPEC_SCHEMA1 = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: маркер песочницы (переоценка бюджета на PLAN)

## Контекст
Маркер.

## Требования
1. Маркер.

## Критерии приёмки
AC-1. Маркер.

## Не входит
"""

REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: {status}
iteration: {iteration}
schema_version: 2
---

# REVIEW: маркер песочницы

## Соответствие SPEC
| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | |

## Замечания
- ...

## Вердикт
{status}

## Проверено исполнением
`python3 -m unittest discover -s tests` — зелёный.
"""


def plan_ready_text(task: str, budget_usd=None) -> str:
    """PLAN.md `status: ready`, с полем `budget_usd` в frontmatter, если
    оно передано (иначе поле отсутствует вовсе — сценарий AC-2)."""
    budget_line = f"budget_usd: {budget_usd}\n" if budget_usd is not None else ""
    return (
        "---\n"
        f"task: {task}\n"
        "type: plan\n"
        "author_role: developer\n"
        "status: ready\n"
        f"{budget_line}"
        "schema_version: 1\n"
        "---\n\n"
        "# PLAN: маркер песочницы\n\n"
        "## Подход\nМаркер.\n\n"
        "## Шаги\n1. Маркер.\n\n"
        "## Покрытие требований\n"
        "| Требование | Шаг |\n|---|---|\n| 1 | 1 |\n\n"
        "## Влияние на систему\nНет.\n"
    )


class PlanBudgetSandbox(unittest.TestCase):
    """Задача доведена до `in_dev` в настоящем git-репозитории с настоящим
    bare-origin (нужен для сценария AC-4 «возврат из приёмки»: `review()`
    на вердикте `approved` пушит голову кодовой ветки в origin по-настоящему)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel-tests@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
            "---\n\n# Карта\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        bare = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        self.git("init", "-q", "--bare", str(bare))
        self.git("remote", "add", "origin", str(bare))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)
        self.origin = bare

        for attr, value in (
            ("ROOT", self.root),
            ("DB", self.root / ".artel" / "state.db"),
            ("TASKS", self.root / "tasks"),
            ("LOGS", self.root / ".artel" / "logs"),
            ("ROLE_HOME", self.root / ".artel" / "home"),
            ("ROLE_CONFIG_DIR", self.root / ".artel" / "home" / ".claude"),
            ("WORKTREES", self.root / ".artel" / "worktrees"),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Переоценка бюджета PLAN")
        self.branch = store.get_task(store.db(), self.TASK)["branch"]
        # Кодовая ветка — обычный git-ref от main, БЕЗ worktree (см.
        # докстринг модуля): ни один гейт `in_dev -> review`, ни push в
        # origin (AC-4) не требуют чекаута, только существования ref'а.
        self.git("branch", self.branch, config.MAIN_BRANCH)

        self.set_ci_green()

    # ------------------------------------------------------------ утилиты

    def git(self, *args: str, cwd=None,
           check: bool = True) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=cwd or self.root,
                             capture_output=True, text=True)
        if check:
            self.assertEqual(res.returncode, 0,
                             f"git {' '.join(args)} упал: {res.stderr}")
        return res

    capture = staticmethod(capture)

    def _seed_artifact_branch(self, rel: str, text: str, message: str) -> None:
        artifact_branch.commit_files(self.TASK, {rel: text}, message)

    def branch_head(self) -> str:
        return gitcmd.branch_head_sha(self.branch)

    def commit_code_branch_change(self, message: str = "фикс по замечаниям ревью") -> None:
        """Пустой коммит на КОДОВОЙ ветке (тот же tree, новый sha) —
        `_review_rework_gate_refuses` (`orchestrator/fsm_advance.py`)
        отказывает возврат в review, если после коммита REVIEW.md
        `changes_requested` на артефактной ветке нет ни одного коммита
        разработчика на кодовой ветке ПОЗЖЕ него по времени; дифф пуст
        нарочно — гейту зон (`_zones_gate_refuses`) нечего сверять с
        зонами, предмет ЭТОЙ песочницы — переоценка бюджета, не дифф
        кода. Дата коммита — явно в будущем (+5с от системного времени):
        оба коммита (REVIEW.md плотницки и этот) иначе могут лечь в ту же
        секунду системных часов и гейт сравнит `code_ts > review_ts` как
        ложное равенство, а не «после»."""
        parent = self.branch_head()
        tree = self.git("rev-parse", f"{parent}^{{tree}}").stdout.strip()
        future = (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat()
        env = {**os.environ,
              "GIT_AUTHOR_DATE": future, "GIT_COMMITTER_DATE": future}
        commit = subprocess.run(
            ["git", "commit-tree", tree, "-p", parent, "-m", message],
            cwd=self.root, capture_output=True, text=True, env=env)
        self.assertEqual(commit.returncode, 0, commit.stderr)
        self.git("update-ref", f"refs/heads/{self.branch}", commit.stdout.strip())

    def push_branch_to_origin(self) -> None:
        self.git("push", "-q", "-u", "origin", self.branch)

    def set_ci_green(self) -> None:
        for target, value in (
            ("verifying_status", lambda branch: (
                ci.VERIFYING_GREEN, "CI коммита aaaaaaaa зелёный (1 проверок)")),
            ("branch_status", lambda branch: (
                True, "CI коммита aaaaaaaa зелёный (1 проверок)")),
        ):
            patcher = mock.patch.object(ci, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def task_row(self):
        return store.get_task(store.db(), self.TASK)

    def steps(self) -> list:
        return store.task_steps(store.db(), self.TASK)

    def journal_tail(self, since: int = 0) -> str:
        return "\n".join(f"{r['action']} | {r['detail']}"
                         for r in self.steps()[since:])

    def set_budget(self, usd: float, source: str) -> None:
        """Ставит потолок задачи напрямую, в обход `budget.apply_spec_budget`
        (см. докстринг модуля — часть 1 ADR-0014 ещё не смержена)."""
        store.update_task(store.db(), self.TASK, budget_usd=usd,
                          budget_source=source)

    # ------------------------------------------------------------ флоу FSM

    def enter_spec_gate(self) -> None:
        spec_text = SPEC_SCHEMA1.format(task=self.TASK)
        self._seed_artifact_branch(f"tasks/{self.TASK}/SPEC.md", spec_text,
                                   f"{self.TASK}: SPEC готов")
        self.capture(fsm.cmd_advance, self.TASK)
        assert self.state() == "spec_gate", (
            f"предпосылка песочницы: SPEC.md ready обязан завести "
            f"spec_gate, состояние {self.state()!r}")

    def enter_in_dev(self) -> None:
        self.enter_spec_gate()
        sha = self.task_row()["fixed_sha"]
        self.capture(fsm.cmd_approve, self.TASK, sha)
        assert self.state() == "in_dev", (
            f"предпосылка песочницы: approve на spec_gate со "
            f"schema_version 1 обязан пропустить tests_writing "
            f"(без AC-разметки) и завести in_dev напрямую, состояние "
            f"{self.state()!r}")

    def submit_plan(self, budget_usd=None) -> None:
        """Пишет PLAN.md `status: ready` (с `budget_usd` или без него) в
        артефактную ветку и зовёт `advance` — единственная точка входа
        `in_dev`, что для первой сдачи, что для последующих (AC-4)."""
        self._seed_artifact_branch(
            f"tasks/{self.TASK}/PLAN.md", plan_ready_text(self.TASK, budget_usd),
            f"{self.TASK}: PLAN сдан")
        self.capture(fsm.cmd_advance, self.TASK)  # in_dev -> verifying
        # ADR-0015 «CI до ревью» (инвариант 36, смержен после фиксации
        # этой планки): из in_dev задача идёт в verifying, а в review —
        # отдельным advance по зелёному CI (amend-tests 11.09).
        # Отказ перехода (AC-6: бюджет выше потолка ролей) оставляет
        # задачу в in_dev — тогда второго шага нет, тест проверяет отказ.
        if self.state() == "verifying":
            self.push_branch_to_origin()
            self.capture(fsm.cmd_advance, self.TASK)  # verifying -> review

    def write_review(self, status: str, iteration: int) -> None:
        self._seed_artifact_branch(
            f"tasks/{self.TASK}/REVIEW.md",
            REVIEW_MD.format(task=self.TASK, status=status, iteration=iteration),
            f"{self.TASK}: REVIEW {status} #{iteration}")

    def request_changes(self, iteration: int) -> None:
        """review(changes_requested) -> in_dev, `review_iters` растёт."""
        self.write_review("changes_requested", iteration)
        self.capture(fsm.cmd_advance, self.TASK)
        assert self.state() == "in_dev", (
            f"предпосылка песочницы: вердикт changes_requested обязан "
            f"вернуть задачу в in_dev, состояние {self.state()!r}")

    def reach_acceptance(self, iteration: int = 1) -> None:
        """review(approved) -> acceptance: verifying по ADR-0015 уже
        позади (пройден в `submit_plan`). `accept_rejects` ещё не растёт —
        до самого `reject`."""
        self.write_review("approved", iteration)
        self.push_branch_to_origin()
        self.capture(fsm.cmd_advance, self.TASK)  # review -> acceptance
        assert self.state() == "acceptance", (
            f"предпосылка песочницы: зелёный CI обязан завести acceptance "
            f"(автогейт не проходит — каталога acceptance_tests/ в этой "
            f"песочнице нет), состояние {self.state()!r}")

    def reject_from_acceptance(self, reason: str = "не подходит") -> None:
        self.capture(fsm.cmd_reject, self.TASK, reason)
        assert self.state() == "in_dev", (
            f"предпосылка песочницы: reject из acceptance обязан вернуть "
            f"задачу в in_dev, состояние {self.state()!r}")
