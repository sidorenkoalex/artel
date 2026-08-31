"""Общая песочница приёмочных тестов T085 (не test_*.py — не подхватывается
`unittest discover` напрямую, только импортом из test_ac*.py).

Автогейт acceptance читает `gates.yaml` из главной копии пульта (`config.
ROOT`) и реально прогоняет приёмочные тесты задачи + полный набор `tests/`
В WORKTREE ВЕТКИ ЗАДАЧИ — подменять эти прогоны заглушками нечем проверить
критерии буквально: тест обязан увидеть настоящий зелёный/красный результат
настоящего `python3 -m unittest discover`. Тот же приём временного
git-репозитория и per-task worktree, что и `tasks/T066/acceptance_tests/
_sandbox.py` (эта задача исполняет ADR-0010 поверх той же механики
`orchestrator/fsm.py::_autogate_conditions`, введённой T066).

Своя копия песочницы, не импорт из tasks/T066/acceptance_tests/ (тот же
приём, что у tasks/T079/acceptance_tests/_sandbox.py — у каждой задачи
своя самодостаточная копия, без межзадачных импортов): `REVIEW_APPROVED_MD`
здесь ОБЯЗАНА нести секцию '## Проверено исполнением' (обязательна для
status: approved с tasks/T072/SPEC.md, `scripts/guard.py::EVIDENCE_
SECTION`) — фикстура T066 её не несёт (та задача принята ДО T072) и
поэтому сегодня красна по причине, не имеющей отношения к ADR-0010 (см.
эскалацию AC-6 в test_ac6_t066_composition_escalation.py). Тесты ЭТОЙ
задачи не должны наследовать чужую стухшую фикстуру.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, ci, config, store, workspace  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]

TASK = "T001"
OTHER_SPENDER_TASK = "T002"

# Приёмочный тест задачи (условие "б"), который всегда проходит.
PASSING_ACCEPTANCE_TEST = '''"""Маркер: заведомо зелёный приёмочный тест песочницы T085."""
import unittest


class MarkerTest(unittest.TestCase):
    def test_ac1_marker_always_passes(self):
        self.assertTrue(True)
'''

# Приёмочный тест задачи с 0 тестов, но с одним AC, помеченным manual
# (условие "а" — 0 manual обязателен для автопрохода).
MANUAL_MARKER_ACCEPTANCE_TEST = (
    '"""Маркер: приёмочные тесты с одним manual-критерием."""\n'
    "import unittest\n\n\n"
    "class MarkerTest(unittest.TestCase):\n"
    "    def test_ac1_marker_always_passes(self):\n"
    "        self.assertTrue(True)\n\n\n"
    "# AC-2: manual — маркер песочницы T085: критерий с пометкой manual "
    "обязан блокировать условие (а) автопрохода.\n"
)

# То же для skip.
SKIP_MARKER_ACCEPTANCE_TEST = (
    '"""Маркер: приёмочные тесты с одним skip-критерием."""\n'
    "import unittest\n\n\n"
    "class MarkerTest(unittest.TestCase):\n"
    "    def test_ac1_marker_always_passes(self):\n"
    "        self.assertTrue(True)\n\n\n"
    "# AC-2: skip — маркер песочницы T085: критерий с пометкой skip "
    "обязан блокировать условие (а) автопрохода.\n"
)

# Полный набор `tests/` worktree ветки (условие "в") — всегда проходит.
PASSING_FULL_SUITE_TEST = '''"""Маркер: заведомо зелёный тест полного набора песочницы T085."""
import unittest


class FullSuiteMarkerTest(unittest.TestCase):
    def test_full_suite_marker_always_passes(self):
        self.assertTrue(True)
'''

# Полный набор `tests/` worktree ветки, который всегда падает.
FAILING_FULL_SUITE_TEST = '''"""Маркер: заведомо красный тест полного набора песочницы T085."""
import unittest


class FullSuiteMarkerTest(unittest.TestCase):
    def test_full_suite_marker_always_passes(self):
        self.assertTrue(True)

    def test_zz_full_suite_marker_deliberately_red(self):
        self.fail("MARKER-FULL-SUITE-RED")
'''

# REVIEW.md approved свежей итерации (условие "д") — с секцией
# '## Проверено исполнением', обязательной с T072 (см. докстринг модуля).
REVIEW_APPROVED_MD = """---
task: {task}
type: review
author_role: reviewer
status: approved
iteration: {iteration}
schema_version: 2
---

# REVIEW: автогейт acceptance (песочница T085)

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | |

## Замечания

## Вердикт
approved

## Проверено исполнением
`python3 -m unittest discover -s tests` — все тесты зелёные (песочница).
"""

# Политика `gates.yaml` (плоское отображение `gates: {{<имя гейта>:
# <auto|manual>}}`, ADR-0007) — acceptance открыт автогейту.
GATES_ACCEPTANCE_AUTO = """gates:
  spec_gate: manual
  acceptance: auto
  merge_gate: manual
"""

# Состояние `verifying` (SPEC T079) сегодня стоит МЕЖДУ `review` и
# `acceptance`: одного `cmd_advance` из `review` уже недостаточно, чтобы
# добраться до оценки автогейта acceptance — нужен второй `advance`,
# обрабатывающий `verifying`, и ему нужен зелёный CI головного коммита
# ветки. Это условие не входит в состав автогейта acceptance (SPEC T085
# требования 1-2) — здесь просто убирается с дороги фикстурой,
# постоянно зелёной, тем же приёмом (`ci.gh`/`ci.head_sha`), что
# `tasks/T079/acceptance_tests/_sandbox.py::VerifyingTest.set_ci_dual`.
GREEN_CHECK_RUNS = json.dumps({"total_count": 2, "check_runs": [
    {"name": "guard", "status": "completed", "conclusion": "success"},
    {"name": "python", "status": "completed", "conclusion": "success"},
]})


class AutogateSandbox(unittest.TestCase):
    """Задача T001 в свежем временном git-репозитории с веткой main;
    ветка задачи заводится через `make_worktree`."""

    TASK = TASK

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # resolve(): на macOS /var — симлинк на /private/var.
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel-tests@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        (self.root / "shared.txt").write_text("base\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        for attr, value in (
            ("ROOT", self.root),
            ("DB", self.root / ".artel" / "state.db"),
            ("TASKS", self.root / "tasks"),
            ("LOGS", self.root / ".artel" / "logs"),
            ("WORKTREES", self.root / ".artel" / "worktrees"),
            ("PROJECTS", self.root / ".artel" / "projects"),
            ("TARGETS", self.root / "targets.yaml"),
            ("ROLE_HOME", self.root / ".artel" / "home"),
            ("ROLE_CONFIG_DIR", self.root / ".artel" / "home" / ".claude"),
            ("BACKUP_MARKER", self.root / ".artel" / "backup-marker"),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        self.branch = f"task/{self.TASK.lower()}-avtogeyt"
        store.insert_task(store.db(), self.TASK, "Автогейт acceptance",
                          "review", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self._set_ci_green()

    def _set_ci_green(self) -> None:
        def gh(*args: str, **kwargs) -> subprocess.CompletedProcess:
            joined = " ".join(args)
            if "check-runs" in joined:
                return subprocess.CompletedProcess(list(args), 0,
                                                    GREEN_CHECK_RUNS, "")
            return subprocess.CompletedProcess(list(args), 0, "[]", "")

        def head_sha(branch: str) -> tuple[str, str]:
            return self.git("rev-parse", branch).stdout.strip(), ""

        for target, value in (("gh", gh), ("head_sha", head_sha)):
            patcher = mock.patch.object(ci, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ утилиты

    def git(self, *args: str, cwd=None,
           check: bool = True) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=cwd or self.root,
                             capture_output=True, text=True)
        if check:
            self.assertEqual(res.returncode, 0,
                             f"git {' '.join(args)} упал: {res.stderr}")
        return res

    @staticmethod
    def capture(fn, *args):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def task_row(self, task_id=None):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?",
            (task_id or self.TASK,)).fetchone()

    def state(self, task_id=None) -> str:
        return self.task_row(task_id)["state"]

    def journal_rows(self, task_id=None) -> list:
        """(actor, action, detail) журнала задачи по порядку записи."""
        return [(r["actor"], r["action"], r["detail"]) for r in store.db().execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? "
            "ORDER BY id", (task_id or self.TASK,))]

    def advance_to_autogate(self, task_id=None) -> str:
        """Два `cmd_advance` подряд: первый — `review -> verifying`,
        второй обрабатывает `verifying` (CI зелёный по фикстуре setUp) и
        входит в `acceptance` в том же вызове, включая попытку автогейта
        (`orchestrator/fsm.py`, ветка `state == "verifying"`, исход
        `ci.VERIFYING_GREEN`, тот же вызов `_maybe_autogate_acceptance`,
        что раньше срабатывал прямо на входе `review -> acceptance`)."""
        from orchestrator import fsm
        out = self.capture(fsm.cmd_advance, task_id or self.TASK)
        out += self.capture(fsm.cmd_advance, task_id or self.TASK)
        return out

    def make_worktree(self, task_id=None, branch=None) -> Path:
        wt_path, error = workspace.ensure(task_id or self.TASK,
                                          branch or self.branch)
        self.assertIsNone(error, error)
        return wt_path

    def commit_all(self, path: Path, message: str) -> str:
        self.git("add", "-A", cwd=path)
        self.git("commit", "-q", "-m", message, cwd=path)
        return self.git("rev-parse", "HEAD", cwd=path).stdout.strip()

    def write_review_approved(self, wt: Path, iteration: int = 1,
                              task_id=None) -> None:
        tdir = wt / "tasks" / (task_id or self.TASK)
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "REVIEW.md").write_text(
            REVIEW_APPROVED_MD.format(task=task_id or self.TASK,
                                      iteration=iteration),
            encoding="utf-8")

    def write_acceptance_test(self, wt: Path, content: str,
                              task_id=None) -> None:
        acc_dir = wt / "tasks" / (task_id or self.TASK) / "acceptance_tests"
        acc_dir.mkdir(parents=True, exist_ok=True)
        (acc_dir / "test_marker.py").write_text(content, encoding="utf-8")

    def write_full_suite_test(self, wt: Path, content: str) -> None:
        tests_dir = wt / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_marker.py").write_text(content, encoding="utf-8")

    def write_gates_policy(self, content: str) -> None:
        """Политика гейтов — файл ГЛАВНОЙ копии пульта (`config.ROOT`),
        не worktree задачи: `gates.yaml` читается только из main."""
        (self.root / "gates.yaml").write_text(content, encoding="utf-8")

    def set_task_budget(self, budget_usd: float, spent_usd: float,
                        task_id=None) -> None:
        store.update_task(store.db(), task_id or self.TASK,
                          budget_usd=budget_usd, spent_usd=spent_usd)

    def seed_program_overspend(self) -> None:
        """Другая задача с расходом далеко за пределами самого строгого
        порога программы (A1) — `store.total_spent` суммирует по ВСЕМ
        задачам (roadmap §5), не только текущей. Отношение читается из
        `config.PROGRAM_ALERT_RATIOS` (крутилка Оператора), не литералом
        (урок T062 28.08, скил test-authoring)."""
        conn = store.db()
        store.insert_task(conn, OTHER_SPENDER_TASK, "Расход другой задачи",
                          "done", "", config.DEFAULT_TARGET,
                          config.PROGRAM_STOP_LOSS_USD * 2)
        store.update_task(conn, OTHER_SPENDER_TASK,
                          spent_usd=config.PROGRAM_STOP_LOSS_USD * 2)

    def prepare_scenario(self, *, gates_content: str = GATES_ACCEPTANCE_AUTO,
                         acceptance_content: str = PASSING_ACCEPTANCE_TEST,
                         full_suite_content: str = PASSING_FULL_SUITE_TEST,
                         budget_usd: float | None = None,
                         spent_usd: float = 0.0,
                         iteration: int = 1) -> Path:
        """Задача `review` с настраиваемым набором условий автопрохода —
        по умолчанию все выполнены (зелёный сценарий); каждый именованный
        параметр меняет ровно одно условие, остальные остаются зелёными.
        Возвращает worktree."""
        self.write_gates_policy(gates_content)
        if budget_usd is not None:
            self.set_task_budget(budget_usd, spent_usd)
        wt = self.make_worktree()
        self.write_review_approved(wt, iteration=iteration)
        self.write_acceptance_test(wt, acceptance_content)
        self.write_full_suite_test(wt, full_suite_content)
        self.commit_all(wt, f"{self.TASK}: сценарий автогейта")
        return wt

    def prepare_green_scenario(self, gates_content: str = GATES_ACCEPTANCE_AUTO):
        """Задача `review` со всеми условиями автопрохода выполненными
        (порог A1, если он вообще проверяется, — тоже не пробит: расход
        программы по умолчанию нулевой). Возвращает worktree."""
        return self.prepare_scenario(gates_content=gates_content)


if __name__ == "__main__":
    unittest.main()
