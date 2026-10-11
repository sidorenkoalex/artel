"""Общая песочница приёмочных тестов T101 (не test_*.py — не подхватывается
`unittest discover` напрямую, только импортом из test_ac*.py).

## Почему отдельный процесс на сценарий

Требование 3/AC-6 говорит о кэшировании «в рамках ОДНОГО процесса
оркестратора». Тесты этого набора управляют доступностью git/claude
(доступны/недоступны/таймаут) через подмену `subprocess.run` — если бы все
сценарии шли в одном процессе `unittest discover`, сценарий «git недоступен»
рисковал бы унаследовать уже закэшированное значение сценария «git доступен»
из другого теста ТОГО ЖЕ процесса (независимо от того, в каком именно модуле
разработчик разместит кэш — `agent_log.py`/`acceptance.py`/`runner.py`,
SPEC требование 6 оставляет это ему). Каждый сценарий поэтому запускается
отдельным `python3`-подпроцессом (`run_driver` ниже) — так вопрос «где
живёт кэш» не встаёт вовсе, а гарантия «один процесс» проверяется буквально.

## Допущение об интерфейсе

Сбор версии git/claude CLI предположительно идёт тем же приёмом, что уже
есть в кодовой базе для claude (`orchestrator/doctor.py::cli_version` —
прямой `subprocess.run([<бинарь>, "--version"], capture_output=True,
text=True, timeout=<секунды>)`, без обращения к `gitcmd.git` — тот
привязан к `cwd=config.ROOT` и создан для операций над репозиторием
пульта, а не для разовой проверки версии внешнего инструмента). Проверки
ниже нацелены на глобальный `subprocess.run` (мокается по образцу
`tests/test_brief.py`/`tests/test_fsm_map_regen.py`,
`mock.patch("subprocess.run", ...)` — перехватывает вызов из ЛЮБОГО
модуля, независимо от того, где разработчик разместит саму функцию сбора),
а не на конкретное имя функции/модуля сборщика — SPEC требование 6 отдаёт
выбор модуля (`acceptance.py`/`agent_log.py`) разработчику, тесты не
должны ломаться от этого выбора.
"""
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, config, fsm, gitcmd, store  # noqa: E402
from tests.sandbox import (TmpRootTest, capture_new_task_id,  # noqa: E402
                           fake_git)

DRIVERS_DIR = Path(__file__).resolve().parent

# Таймаут ОБЁРТКИ подпроцесса-драйвера — не тот таймаут, что проверяет
# AC-2 (тот — внутри самого сбора fingerprint, единицы секунд). Это —
# страховка теста: если реализация не передаст `timeout=` во внешний
# вызов вовсе (дефект AC-2), сценарий "timeout" не зависнет навечно, а
# уронит тест по этой явной внешней границе.
DRIVER_WALL_CLOCK_TIMEOUT_SEC = 45


def run_driver(driver_name: str, *args: str,
               timeout: int = DRIVER_WALL_CLOCK_TIMEOUT_SEC) -> dict:
    """Прогоняет `_driver_<driver_name>.py` отдельным процессом python3,
    разбирает последнюю строку его stdout как JSON.

    Ошибка процесса (ненулевой rc, не-JSON, таймаут обёртки) — явный
    провал теста с полным stdout/stderr в сообщении, не тихий `{}`:
    драйверы этого набора гоняют настоящий код оркестратора, их
    собственный traceback — самая частая причина падения теста, и он
    обязан быть виден.
    """
    driver_path = DRIVERS_DIR / f"_driver_{driver_name}.py"
    try:
        res = subprocess.run(
            [sys.executable, str(driver_path), *args],
            capture_output=True, text=True, timeout=timeout, cwd=REPO_ROOT)
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            f"драйвер {driver_name} не уложился в {timeout}с обёртки теста "
            f"(похоже, реализация не передаёт короткий timeout= во внешний "
            f"вызов, AC-2) — stdout так далеко: {exc.stdout!r}") from exc
    if res.returncode != 0:
        raise AssertionError(
            f"драйвер {driver_name} упал (rc={res.returncode}):\n"
            f"--- stdout ---\n{res.stdout}\n--- stderr ---\n{res.stderr}")
    lines = [ln for ln in res.stdout.splitlines() if ln.strip()]
    if not lines:
        raise AssertionError(f"драйвер {driver_name} не напечатал JSON; "
                             f"stderr: {res.stderr}")
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"драйвер {driver_name}: последняя строка stdout — не JSON "
            f"({exc}): {lines[-1]!r}") from exc


# ---------------------------------------------------------------------------
# Песочница AC-5/AC-7 (fingerprint в исходе прогона приёмочных тестов и его
# видимость в `artel.py log`): здесь достаточно ОДНОГО процесса на весь
# файл — сценарии не переключают доступность git/claude между собой (везде
# `version_stub_run` ниже отвечает одинаково), так что риск утечки кэша
# фингерпринта между сценариями ТОГО ЖЕ процесса (см. докстринг модуля выше
# про AC-6) здесь не встаёт — в отличие от `_driver_agent_step.py`, эти
# тесты не сравнивают доступный/недоступный инструмент друг с другом.

_REAL_SUBPROCESS_RUN = subprocess.run


def version_stub_run(git_stdout: str = "git version 2.43.0\n",
                     claude_stdout: str | None = None):
    """`subprocess.run` side_effect: отвечает на `git --version`/
    `claude --version`, остальное (в первую очередь — реальный `python3 -m
    unittest discover` внутри `orchestrator/acceptance.py::run`) уходит в
    настоящий `subprocess.run` — тот же приём, что `tests/sandbox.
    claude_only_run`, но отвечает и на git, и на claude сразу (см.
    докстринг `_sandbox.py`, «Допущение об интерфейсе»)."""
    if claude_stdout is None:
        claude_stdout = f"{config.CLI_VERSION_PIN} (Claude Code)\n"

    def run(cmd, *a, **kw):
        if cmd and cmd[0] == "git" and "--version" in cmd:
            return subprocess.CompletedProcess(cmd, 0, git_stdout, "")
        if cmd and cmd[0] == "claude" and "--version" in cmd:
            return subprocess.CompletedProcess(cmd, 0, claude_stdout, "")
        return _REAL_SUBPROCESS_RUN(cmd, *a, **kw)
    return run


SPEC_V2 = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: песочница T101 (review -> acceptance)

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Единственный критерий песочницы, проверяемый тестом.

## Не входит
"""

PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: песочница T101

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

# REVIEW: песочница T101

## Соответствие SPEC

## Замечания

## Вердикт
approved

## Проверено исполнением
`python3 -m unittest discover -s tests` — зелёный.
"""

AC_TEST_PASS = """import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_ok(self):
        self.assertTrue(True)
"""

AC_TEST_FAIL = """import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_ok(self):
        self.fail("намеренно красный сценарий песочницы T101")
"""


class ReviewAdvanceSandbox(TmpRootTest):
    """Задача в состоянии `review`, готовая к `fsm.cmd_advance` (тот же
    рецепт, что `tests/test_acceptance_tests_flow.py::AcceptanceRunTest` —
    лёгкая песочница, `gitcmd.git` заглушкой, `on_foreign_branch` — False,
    поэтому `acc_tdir` берётся с диска главной копии, а не из worktree)."""

    PATCHED_ATTRS = ("DB", "TASKS", "LOGS", "ROLE_HOME", "ROLE_CONFIG_DIR",
                     "WORKTREES", "ROOT")

    def setUp(self):
        super().setUp()
        import shutil
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        # id — ULID из возврата `cmd_new` (SPEC T094, требование 2):
        # классовый хардкод "T001" сломался мержем M1.
        self.TASK = capture_new_task_id(
            catalog.cmd_new, "Песочница T101 review->acceptance")[1]
        self.tdir = config.TASKS / self.TASK
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(SPEC_V2.format(task=self.TASK),
                                           encoding="utf-8")
        (self.tdir / "PLAN.md").write_text(PLAN_MD.format(task=self.TASK),
                                           encoding="utf-8")
        (self.tdir / "REVIEW.md").write_text(REVIEW_MD.format(task=self.TASK),
                                             encoding="utf-8")
        self._set_state("review")

    def _set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def state(self) -> str:
        return store.db().execute(
            "SELECT state FROM tasks WHERE id=?", (self.TASK,)).fetchone()[0]

    def write_acceptance_tests(self, content: str,
                               name: str = "test_ac.py") -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def journal_details(self, action: str) -> list:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]

    def advance(self) -> str:
        return self.capture(fsm.cmd_advance, self.TASK)
