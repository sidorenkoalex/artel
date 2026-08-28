"""Общая песочница приёмочных тестов T066 (не test_*.py — не подхватывается
`unittest discover` напрямую, только импортом из test_ac*.py).

Автогейт acceptance читает `gates.yaml` из главной копии пульта (`config.
ROOT`, "ветка main" в терминах комментария самого `gates.yaml`: "Policy-
движок обязан читать его ТОЛЬКО из main") и реально прогоняет приёмочные
тесты задачи + полный набор `tests/` В WORKTREE ВЕТКИ ЗАДАЧИ (SPEC
требование 2, б-в) — подменять эти прогоны заглушками нечем проверить
критерии буквально: тест обязан увидеть настоящий зелёный/красный
результат настоящего `python3 -m unittest discover`. Тот же приём
временного git-репозитория и per-task worktree, что и
`tasks/T051/acceptance_tests/_sandbox.py` / `tasks/T045/acceptance_tests/
_sandbox.py`.

Тесты не переоткрывают конкретную функцию/имя, которым разработчик решит
исполнить автогейт (её ещё нет — эту задачу впервые пишет developer после
test_author, SPEC требование 1: точный формат `gates.yaml` — его решение
в PLAN) — только наблюдаемое поведение публичных точек входа
`fsm.cmd_advance`/`fsm.cmd_approve`, состояние задачи в БД, журнал шагов
и печать команды.

## Допущения интерфейса, которые вводит этот файл

- Формат политики `gates.yaml` — плоское отображение `gates: {<имя
  гейта>: <auto|manual>}` с именами гейтов, буквально совпадающими с
  состояниями FSM (`spec_gate`, `acceptance`, `merge_gate`) — дословно
  пример из SPEC требования 1 и ADR-0007 (п.2 решения и раздел
  «Раскатка»), а не нынешняя нерабочая заглушка `gates.yaml` (там —
  вложенный `mode:` для гейтов, которых в FSM не существует; сам файл
  помечен «НЕ ДЕЙСТВУЕТ», «регенерируется», «policy-движка нет» — не
  образец формата для активной политики ADR-0007).
- Порог программы (A1, `config.PROGRAM_STOP_LOSS_USD` /
  `config.PROGRAM_ALERT_RATIOS`) читается через `config`, не литералом
  (урок T062 28.08, скил test-authoring): «пробит» в тестах — расход
  далеко за пределами САМОГО СТРОГОГО из настроенных отношений, чтобы
  сценарий не зависел от того, какое именно отношение разработчик
  выберет точкой блокировки.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, gitcmd, store, workspace  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]

TASK = "T001"
OTHER_SPENDER_TASK = "T002"

# Приёмочный тест задачи (акт "б" SPEC), который всегда проходит.
PASSING_ACCEPTANCE_TEST = '''"""Маркер: заведомо зелёный приёмочный тест песочницы T066."""
import unittest


class MarkerTest(unittest.TestCase):
    def test_ac1_marker_always_passes(self):
        self.assertTrue(True)
'''

# Приёмочный тест задачи, который всегда падает.
FAILING_ACCEPTANCE_TEST = '''"""Маркер: заведомо красный приёмочный тест песочницы T066."""
import unittest


class MarkerTest(unittest.TestCase):
    def test_ac1_marker_always_passes(self):
        self.assertTrue(True)

    def test_zz_marker_deliberately_red(self):
        self.fail("MARKER-RED")
'''

# `_HASH`-косвенность НАМЕРЕННАЯ: собранная ниже строка-фикстура несёт
# буквальный текст решётка+пробел+"AC"+дефис+"2"+двоеточие+manual (и то
# же для skip) — если записать его В ЭТОМ файле как обычный литерал,
# `scripts/guard.py` (`AC_MARKER`, чисто текстовый разбор БЕЗ импорта
# файлов) прочитал бы его как пометку САМОГО T066 поверх реального
# теста AC-2 (`_sandbox.py` лежит рядом в `tasks/T066/acceptance_tests/`
# и тоже сканируется на выходе из tests_writing) — ложный manual/skip
# у критерия, который на
# самом деле полностью покрыта тестом. Косвенность через `_HASH` не
# меняет получившуюся строку (её и видит FSM, сканируя ФИКСТУРУ
# отдельной симулированной задачи в песочнице), только не даёт
# буквальному `#\\s*AC-2:` появиться в исходнике ЭТОГО файла.
_HASH = "#"

# Приёмочный тест задачи с 0 тестов, но с одним AC, помеченным manual
# (условие "а" — 0 manual обязателен для автопрохода).
MANUAL_MARKER_ACCEPTANCE_TEST = (
    '"""Маркер: приёмочные тесты с одним manual-критерием."""\n'
    "import unittest\n\n\n"
    "class MarkerTest(unittest.TestCase):\n"
    "    def test_ac1_marker_always_passes(self):\n"
    "        self.assertTrue(True)\n\n\n"
    + _HASH + " AC-2: manual — маркер песочницы T066: критерий с "
    "пометкой manual обязан блокировать условие (а) автопрохода.\n"
)

# То же для skip.
SKIP_MARKER_ACCEPTANCE_TEST = (
    '"""Маркер: приёмочные тесты с одним skip-критерием."""\n'
    "import unittest\n\n\n"
    "class MarkerTest(unittest.TestCase):\n"
    "    def test_ac1_marker_always_passes(self):\n"
    "        self.assertTrue(True)\n\n\n"
    + _HASH + " AC-2: skip — маркер песочницы T066: критерий с "
    "пометкой skip обязан блокировать условие (а) автопрохода.\n"
)

# Полный набор `tests/` worktree ветки (акт "в" SPEC) — всегда проходит.
PASSING_FULL_SUITE_TEST = '''"""Маркер: заведомо зелёный тест полного набора песочницы T066."""
import unittest


class FullSuiteMarkerTest(unittest.TestCase):
    def test_full_suite_marker_always_passes(self):
        self.assertTrue(True)
'''

# Полный набор `tests/` worktree ветки, который всегда падает.
FAILING_FULL_SUITE_TEST = '''"""Маркер: заведомо красный тест полного набора песочницы T066."""
import unittest


class FullSuiteMarkerTest(unittest.TestCase):
    def test_full_suite_marker_always_passes(self):
        self.assertTrue(True)

    def test_zz_full_suite_marker_deliberately_red(self):
        self.fail("MARKER-FULL-SUITE-RED")
'''

REVIEW_APPROVED_MD = """---
task: {task}
type: review
author_role: reviewer
status: approved
iteration: {iteration}
schema_version: 1
---

# REVIEW: автогейт acceptance

## Соответствие SPEC

## Замечания

## Вердикт
"""

# Политика `gates.yaml` (SPEC требование 1, ADR-0007 п.2 и «Раскатка») —
# см. докстринг модуля, «Допущения интерфейса».
GATES_ACCEPTANCE_AUTO = """gates:
  spec_gate: manual
  acceptance: auto
  merge_gate: manual
"""

GATES_ACCEPTANCE_MANUAL = """gates:
  spec_gate: manual
  acceptance: manual
  merge_gate: manual
"""

GATES_NO_POLICY_SECTION = """# gates.yaml без секции политики — легаси-состояние до ADR-0007.
some_other_key: значение
"""

GATES_UNREADABLE = """gates:
  acceptance: [auto
  это не валидный YAML — незакрытая последовательность
"""

GATES_MERGE_AND_SPEC_ALSO_AUTO = """gates:
  spec_gate: auto
  acceptance: manual
  merge_gate: auto
"""


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

    def set_state(self, state: str, task_id=None) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?",
                     (state, task_id or self.TASK))
        conn.commit()

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
        не worktree задачи: `gates.yaml` читается только из main (см.
        комментарий самого файла в реальном репозитории и докстринг
        модуля)."""
        (self.root / "gates.yaml").write_text(content, encoding="utf-8")

    def set_task_budget(self, budget_usd: float, spent_usd: float,
                        task_id=None) -> None:
        store.update_task(store.db(), task_id or self.TASK,
                          budget_usd=budget_usd, spent_usd=spent_usd)

    def seed_program_overspend(self) -> None:
        """Другая задача с расходом далеко за пределами самого строгого
        порога программы (A1) — `store.total_spent` суммирует по ВСЕМ
        задачам (roadmap §5), не только текущей."""
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
        """Задача `review` с настраиваемым набором условий SPEC требования
        2 — по умолчанию все пять выполнены (зелёный сценарий); каждый
        именованный параметр меняет ровно одно условие, остальные
        остаются зелёными. Возвращает worktree."""
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
        """Задача `review` со всеми условиями автопрохода выполненными:
        acceptance_tests зелёные без manual/skip, полный `tests/` worktree
        зелёный, REVIEW approved свежей итерации, бюджет и порог A1 не
        пробиты. Возвращает worktree."""
        return self.prepare_scenario(gates_content=gates_content)
