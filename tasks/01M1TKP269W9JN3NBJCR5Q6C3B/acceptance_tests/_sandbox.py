"""Общая песочница приёмочных тестов «Канарейка — диагностика незелёного
прогона» (не test_*.py — не подхватывается `unittest discover` напрямую,
только импортом из test_ac*.py). Прямой потомок песочницы канарейки v2
(`tasks/01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/_sandbox.py`) — тот же
приём (настоящий git-репозиторий пульта, `SmartAgent` — подмена
`runner.cmd_run`, пул шаблонов вне корня пульта, перехват
`tempfile.mkdtemp`/`shutil.rmtree`), скопированный сюда, а не
импортированный из чужого каталога задачи: `tasks/<id>/acceptance_tests/`
этой задачи — единственное, что коммитит автокоммит оркестратора в
артефактную ветку ЭТОЙ задачи (SPEC 01M1NKTF173WV5CPDZ1C3WW69K); чужой
каталог другой, уже смерженной задачи не гарантированно доступен на
диске рабочей копии разработчика этой задачи.

Единственное содержательное расширение относительно оригинала:
`SmartAgent._commit` теперь пишет ЕЩЁ и файл лога роли
(`orchestrator.agent_log.new_agent_log`) с узнаваемым маркером в
содержимом — оригинал полностью подменяет `runner.cmd_run`, поэтому
реальный `.artel/logs/<task_id>-*.log` в эфемерном клоне никогда не
появляется сам по себе; без этого расширения проверка AC-2 (копирование
логов ролей клона до его удаления) не имела бы что копировать и была бы
тавтологией (пустой каталог логов копируется в пустой каталог логов).
"""
import io
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (agent_log, artel, ci, catalog, checkpoint,  # noqa: E402
                          config, gitcmd, runner, store)

SPEC_READY = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: канареечная задача — диагностика

## Контекст

синтетическое ТЗ канарейки, неподвижный вход

## Требования

1. сделать маленькую синтетическую правку

## Критерии приёмки

1. правка сделана

## Не входит
"""

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: канареечная задача — диагностика

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: {status}
iteration: {iteration}
schema_version: 1
---

# REVIEW: канареечная задача — диагностика

## Соответствие SPEC

## Замечания

## Проверено исполнением

синтетический прогон канарейки: `python3 -m unittest` (заглушка агента,
guard.py требует эту секцию для approved-ревью, SPEC T072).

## Вердикт
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

# Синтетический маркер лога роли, которым `SmartAgent._commit` заполняет
# файл `.artel/logs/<task_id>-<role>-N.log` клона — тестам AC-2 нужно
# узнаваемое содержимое, отличимое от случайного текста.
ROLE_LOG_MARKER = "CANARY-DIAG-SANDBOX-ROLE-LOG"

# Подстрока в title заведённой задачи, по которой `SmartAgent` решает
# эскалировать эту задачу вместо обычного happy path (см. оригинал —
# тот же приём).
ESCALATE_TITLE_MARKER = "triggers-escalation"


class SmartAgent:
    """Подмена `runner.cmd_run` — см. докстринг модуля выше и оригинал
    `tasks/01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/_sandbox.py::
    SmartAgent` (тот же приём: пишет файл в рабочий каталог роли и
    переносит его в артефактную ветку `checkpoint.commit_step_artifacts`,
    не голым `git commit` в рабочем дереве кодовой ветки — post-A7
    `artifact_source.resolve` для любого target всегда `foreign=True`)."""

    def __init__(self):
        self.calls: list[str] = []
        self.extra_review_rounds: dict[str, int] = {}
        self.extra_review_rounds_by_title: dict[str, int] = {}
        self.extra_review_rounds_default = 0
        self._review_rounds_done: dict[str, int] = {}
        self._escalated_once: set[str] = set()
        self._nonce = 0

    def __call__(self, task_id: str, session_id: str | None = None) -> None:
        self.calls.append(task_id)
        conn = store.db()
        t = store.get_task(conn, task_id)
        state = t["state"]
        title = t["title"] or ""

        if state == "spec_writing":
            if (ESCALATE_TITLE_MARKER in title
                    and task_id not in self._escalated_once):
                self._escalated_once.add(task_id)
                self._commit(conn, task_id, "analyst", "QUESTIONS.md",
                            QUESTIONS_TEXT.format(task=task_id))
                return
            self._commit(conn, task_id, "analyst", "SPEC.md",
                        SPEC_READY.format(task=task_id))
        elif state == "in_dev":
            self._commit(conn, task_id, "developer", "PLAN.md",
                        PLAN_READY.format(task=task_id))
        elif state == "review":
            done = self._review_rounds_done.get(task_id, 0)
            if task_id in self.extra_review_rounds:
                need = self.extra_review_rounds[task_id]
            elif title in self.extra_review_rounds_by_title:
                need = self.extra_review_rounds_by_title[title]
            else:
                need = self.extra_review_rounds_default
            iteration = t["reviewed_iter"] + 1
            if done < need:
                self._review_rounds_done[task_id] = done + 1
                status = "changes_requested"
            else:
                status = "approved"
            self._commit(conn, task_id, "reviewer", "REVIEW.md",
                        REVIEW_MD.format(task=task_id, status=status,
                                         iteration=iteration))
        # Прочие агентские состояния (tests_writing и т.п.) вне охвата
        # песочницы.

    def _commit(self, conn, task_id: str, role: str, name: str, text: str) -> None:
        self._nonce += 1
        text = f"{text}\n<!-- agent stub, вызов {self._nonce} -->\n"
        wt_path = config.WORKTREES / task_id
        path = wt_path / "tasks" / task_id / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        # Симулирует то, что делал бы настоящий `runner.cmd_run`
        # (`agent_log.new_agent_log`, `orchestrator/runner.py:684`) —
        # без этого файла AC-2 (копирование логов ролей клона) нечего
        # было бы копировать.
        log_path = agent_log.new_agent_log(task_id, role)
        log_path.write_text(
            f"{ROLE_LOG_MARKER} роль={role} задача={task_id} вызов={self._nonce}\n",
            encoding="utf-8")
        checkpoint.commit_step_artifacts(conn, task_id, role)


class _NeverSpecsAgent(SmartAgent):
    """Вариант `SmartAgent`, который на `spec_writing` ВСЕГДА кладёт
    `QUESTIONS.md` вместо готового SPEC.md, вне зависимости от того,
    эскалировалась ли задача уже раньше — задача никогда не доходит до
    `in_dev`/`review`, PLAN.md/REVIEW.md в артефактной ветке клона не
    появляются НИ РАЗУ. Нужен тесту «отсутствие PLAN/REVIEW не роняет
    canary» (AC-3, вторая половина критерия)."""

    def __call__(self, task_id: str, session_id: str | None = None) -> None:
        self.calls.append(task_id)
        conn = store.db()
        t = store.get_task(conn, task_id)
        if t["state"] == "spec_writing":
            self._commit(conn, task_id, "analyst", "QUESTIONS.md",
                        QUESTIONS_TEXT.format(task=task_id))
            return
        super().__call__(task_id, session_id)


def extract_run_stamp(out: str) -> str:
    """Штамп прогона из первой строки вывода `canary` (`_run_one_task`
    печатает его буквально до какой-либо диагностической правки этой
    задачи — формат существующей, не меняемой этой SPEC строки)."""
    m = re.search(r"\[canary\] прогон (\S+):", out)
    assert m, f"не найден штамп прогона в выводе: {out!r}"
    return m.group(1)


def extract_task_ids(out: str) -> list:
    """id всех заведённых задач прогона, по порядку появления в выводе."""
    return re.findall(r"\[canary\] (\S+) заведена из", out)


def task_metrics(data, task_id: str):
    if not isinstance(data, dict):
        return None
    if task_id in data:
        return data[task_id]
    tasks = data.get("tasks")
    if isinstance(tasks, dict) and task_id in tasks:
        return tasks[task_id]
    return None


class CanarySandbox(unittest.TestCase):
    """Настоящий git-репозиторий пульта (main) + отдельный от `self.root`
    каталог пула вне корня (`Path.home()` подменена) + настоящие
    worktree/ветки задач (`catalog.cmd_new`) — единственная логическая
    подмена: агент шага (`SmartAgent`)."""

    AGENT_CLASS = SmartAgent

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # resolve(): на macOS /var — симлинк на /private/var.
        self.root = Path(tmp.name).resolve()

        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "artel-tests@example.invalid")
        self._git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        gitignore = REPO_ROOT / ".gitignore"
        if gitignore.exists():
            shutil.copy(gitignore, self.root / ".gitignore")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "init")

        for attr, value in (
            ("ROOT", self.root),
            ("DB", self.root / ".artel" / "state.db"),
            ("TASKS", self.root / "tasks"),
            ("LOGS", self.root / ".artel" / "logs"),
            ("PROJECTS", self.root / ".artel" / "projects"),
            ("TARGETS", self.root / "targets.yaml"),
            ("ROLE_HOME", self.root / ".artel" / "home"),
            ("ROLE_CONFIG_DIR", self.root / ".artel" / "home" / ".claude"),
            ("BACKUP_MARKER", self.root / ".artel" / "backup-marker"),
            ("WORKTREES", self.root / ".artel" / "worktrees"),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)

        # --- без реальных ожиданий CI (тот же приём, что оригинал) -----
        for attr, value in (
            ("VERIFYING_CEILING_SEC", 5),
            ("MERGE_GATE_CI_WAIT_CEILING_SEC", 5),
            ("MERGE_GATE_CI_WAIT_POLL_SEC", 0),
            ("CI_RERUN_WAIT_SEC", 0),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for name, value in (
            ("verifying_status", ("green", "CI зелёный (заглушка песочницы)")),
            ("branch_status", (True, "CI зелёный (заглушка песочницы)")),
            ("trigger_rerun", "заглушка песочницы: перезапуск не нужен"),
        ):
            patcher = mock.patch.object(ci, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        gh_patcher = mock.patch.object(
            ci, "gh", side_effect=AssertionError("песочница: вызов gh запрещён"))
        gh_patcher.start()
        self.addCleanup(gh_patcher.stop)

        self.agent = self.AGENT_CLASS()
        agent_patcher = mock.patch.object(runner, "cmd_run", self.agent)
        agent_patcher.start()
        self.addCleanup(agent_patcher.stop)

        # --- пул шаблонов вне корня пульта -----------------------------
        home_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(home_tmp.cleanup)
        self.fake_home = Path(home_tmp.name).resolve()
        self.pool_dir = self.fake_home / ".artel-canary"
        self.pool_dir.mkdir(parents=True)
        home_patcher = mock.patch.object(Path, "home",
                                         return_value=self.fake_home)
        home_patcher.start()
        self.addCleanup(home_patcher.stop)
        env_patcher = mock.patch.dict("os.environ", {"HOME": str(self.fake_home)})
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

    # ------------------------------------------------------------ утилиты

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], stdin=subprocess.DEVNULL, cwd=self.root, timeout=30,
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)} упал: {res.stderr}")
        return res

    @staticmethod
    def capture(fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def write_pool_templates(self, texts: dict) -> Path:
        for name, text in texts.items():
            (self.pool_dir / name).write_text(text, encoding="utf-8")
        return self.pool_dir

    def run_cli(self, *argv_tail: str) -> str:
        argv = ["artel.py", *argv_tail]
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", argv):
            with redirect_stdout(buf):
                try:
                    artel.main()
                except SystemExit as exc:
                    buf.write(f"\n[SystemExit] {exc}\n")
        return buf.getvalue()

    def run_canary_pool(self, k: int, *extra_args: str) -> str:
        return self.run_cli("canary", "--k", str(k), *extra_args)

    def task_ids(self) -> list[str]:
        return [t["id"] for t in store.all_tasks(store.db())]

    def artifact_branch_files(self, task_id: str) -> list:
        from orchestrator import artifact_branch
        branch = artifact_branch.branch_name(task_id)
        return gitcmd.ls_tree_files(branch, f"tasks/{task_id}") or []

    def artifact_branch_text(self, task_id: str, rel: str) -> str | None:
        from orchestrator import artifact_branch
        branch = artifact_branch.branch_name(task_id)
        text, _reason = gitcmd.show(branch, f"tasks/{task_id}/{rel}")
        return text


if __name__ == "__main__":
    unittest.main()
