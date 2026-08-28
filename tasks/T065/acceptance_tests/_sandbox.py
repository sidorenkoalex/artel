"""Общая песочница приёмочных тестов T065 (не test_*.py — не подхватывается
`unittest discover` напрямую, только импортом из test_ac*.py).

Реальный git-репозиторий, не `fake_git`/`SpyRun` из `tests/test_invariants.py`
и `tests/test_auto_cycle.py`: требование 1 SPEC — `canary` заводит задачи
через `catalog.cmd_new(..., tz_path=...)`, а с SPEC T048 TZ.md/SPEC.md
коммитятся СРАЗУ В ВЕТКУ задачи, не на диск main. `runner.step_role`
(роль `analyst` на `spec_writing` живёт только при наличии `TZ.md`, SPEC
T025) и переходы `fsm.cmd_advance` при «чужом чекауте» (`gitcmd.
on_foreign_branch`, SPEC T031/T047) читают статусы артефактов С ВЕТКИ
задачи (`git show`), не с диска — фейковый `gitcmd.git`
(`current_branch()` всегда "") держит `on_foreign_branch` вечно ложным и
не даёт увидеть роль `analyst` вовсе, а значит и не даёт `canary` вообще
завести задачу через `--tz`. Тот же приём реального git, что и у
`tests/test_invariants.py::KillKeepsMainIntactTest`.

`runner.cmd_run` подменён «умной» заглушкой (`SmartAgent`): вместо
реального агента она смотрит ТЕКУЩЕЕ состояние вызвавшей её задачи и
коммитит в её ветку тот артефакт, которого ждёт следующий
`fsm.cmd_advance` (SPEC.md ready на `spec_writing`, PLAN.md ready на
`in_dev`, REVIEW.md approved на `review`) — тот же по духу приём «умного
стаба», которым `tests/test_auto_cycle.py::FakeRun` кормит цикл
заготовленным сценарием, но не по списку заранее записанных шагов на
ОДНУ задачу, а по фактическому состоянию — canary-прогон ведёт НЕСКОЛЬКО
независимых задач одной и той же подменой. SPEC пишется `schema_version:
1` (без AC-разметки) — `tests_writing` не заводится
(`guard.requires_ac_markup` ложно), CLI-цикл заканчивается в `in_dev`
сразу после `spec_gate`: T065 не про сам A4-конвейер, лишний агентский
шаг только раздувал бы песочницу.
"""
import io
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

from orchestrator import artel, catalog, config, fixation, runner, store  # noqa: E402

SPEC_READY = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: канареечная задача

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

# PLAN: канареечная задача

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

# REVIEW: канареечная задача

## Соответствие SPEC

## Замечания

## Вердикт
"""


class SmartAgent:
    """Подмена `runner.cmd_run`: коммитит в ветку задачи артефакт,
    которого ждёт следующий переход, по ЕЁ текущему состоянию.

    `extra_review_rounds` — task_id -> число обязательных
    `changes_requested` ПЕРЕД `approved` (по умолчанию — из
    `extra_review_rounds_default`, единого на все задачи, заведённые
    ПОСЛЕ его установки: id задач `canary` присваивает сама, до вызова
    их не узнать — AC-3 раздувает шаги второго прогона до нужного
    отклонения именно так, не адресуясь к конкретному task_id).
    `config.LIMIT_REVIEW_ITERS` (3) — верхний предел, при котором задача
    уходит в escalated вместо очередного in_dev; `extra_review_rounds*`
    держи меньше него.
    """

    def __init__(self):
        self.calls: list[str] = []
        self.extra_review_rounds: dict[str, int] = {}
        self.extra_review_rounds_default = 0
        self._review_rounds_done: dict[str, int] = {}
        self._nonce = 0

    def __call__(self, task_id: str, session_id: str | None = None) -> None:
        self.calls.append(task_id)
        conn = store.db()
        t = store.get_task(conn, task_id)
        state = t["state"]
        branch = t["branch"]
        if state == "spec_writing":
            self._commit(task_id, branch, "SPEC.md",
                        SPEC_READY.format(task=task_id))
        elif state == "in_dev":
            self._commit(task_id, branch, "PLAN.md",
                        PLAN_READY.format(task=task_id))
        elif state == "review":
            done = self._review_rounds_done.get(task_id, 0)
            need = self.extra_review_rounds.get(
                task_id, self.extra_review_rounds_default)
            iteration = t["reviewed_iter"] + 1
            if done < need:
                self._review_rounds_done[task_id] = done + 1
                status = "changes_requested"
            else:
                status = "approved"
            self._commit(task_id, branch, "REVIEW.md",
                        REVIEW_MD.format(task=task_id, status=status,
                                         iteration=iteration))
        # Прочие агентские состояния (tests_writing и т.п.) вне охвата
        # песочницы: SPEC версии 1 их не заводит (см. докстринг модуля).

    def _commit(self, task_id: str, branch: str, name: str, text: str) -> None:
        self._nonce += 1
        text = f"{text}\n<!-- agent stub, вызов {self._nonce} -->\n"
        wt_path = config.WORKTREES / task_id
        path = wt_path / "tasks" / task_id / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", f"tasks/{task_id}/{name}"], cwd=wt_path,
                       check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "-c", f"user.name={fixation.FIXATION_AUTHOR_NAME}",
             "-c", f"user.email={fixation.FIXATION_AUTHOR_EMAIL}",
             "commit", "-q", "-m", f"{task_id}: {name} (agent stub #{self._nonce})"],
            cwd=wt_path, check=True, capture_output=True, text=True)


def has_canary_mark(text: str) -> bool:
    """Несёт ли текст пометку canary — по-английски (SPEC требования 2, 3,
    6 буквально называют её `canary`, тем же словом, каким `journal` метит
    гейты) или по-русски (`канарееч*`/`канарейк*` — естественный вариант
    для строк status/RETRO, целиком русскоязычных во всей остальной
    кодовой базе); принимается любой из двух, не только латиница —
    формулировка AC-4 называет ФАКТ отличимости, не язык надписи."""
    lowered = text.lower()
    return "canary" in lowered or "канаре" in lowered


def task_metrics(data, task_id: str):
    """Запись метрик задачи из разобранного JSON-отчёта: либо прямо на
    верхнем уровне (`data[task_id]`), либо под общей обёрткой
    `data["tasks"]` — SPEC называет состав метрик (требование 4), не имя
    обёртки; тест не привязывается к тому, чего SPEC не называет."""
    if not isinstance(data, dict):
        return None
    if task_id in data:
        return data[task_id]
    tasks = data.get("tasks")
    if isinstance(tasks, dict) and task_id in tasks:
        return tasks[task_id]
    return None


def summary_metrics(data):
    """Суммарные метрики набора (стоимость, шаги) из разобранного JSON —
    либо прямо на верхнем уровне, либо под обёрткой `data["summary"]`."""
    if not isinstance(data, dict):
        return None
    if "cost_usd" in data and "steps" in data:
        return data
    summary = data.get("summary")
    if isinstance(summary, dict) and "cost_usd" in summary and "steps" in summary:
        return summary
    return None


class CanarySandbox(unittest.TestCase):
    """Настоящий git-репозиторий (main) + настоящие worktree/ветки задач
    (`catalog.cmd_new`, тем же путём, что и живой `canary`); единственная
    подмена — агент шага (`SmartAgent` выше)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # resolve(): на macOS /var — симлинк на /private/var (тот же приём,
        # что и tests/test_invariants.py::KillKeepsMainIntactTest).
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
            ("ROLE_HOME", self.root / ".artel" / "home"),
            ("ROLE_CONFIG_DIR", self.root / ".artel" / "home" / ".claude"),
            ("WORKTREES", self.root / ".artel" / "worktrees"),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)

        self.agent = SmartAgent()
        agent_patcher = mock.patch.object(runner, "cmd_run", self.agent)
        agent_patcher.start()
        self.addCleanup(agent_patcher.stop)

    # ------------------------------------------------------------ утилиты

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=self.root, timeout=30,
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)} упал: {res.stderr}")
        return res

    def main_sha(self) -> str:
        return self._git("rev-parse", "main").stdout.strip()

    @staticmethod
    def capture(fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def write_tz_files(self, texts: dict) -> Path:
        """Каталог *.md ТЗ-файлов канарейки — ВНЕ репозитория песочницы
        (SPEC, требование 1: Оператор держит их вне репозитория)."""
        tz_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tz_dir, ignore_errors=True)
        for name, text in texts.items():
            (tz_dir / name).write_text(text, encoding="utf-8")
        return tz_dir

    def run_canary(self, tz_dir: Path, *extra_args: str) -> str:
        """`artel.py canary <tz_dir> [extra_args]` — настоящий CLI-диспетчер
        (`orchestrator/artel.py::main`), не прямой вызов внутреннего модуля:
        SPEC называет только интерфейс командной строки (требование 1),
        имя/расположение реализующего модуля — решение developer.

        Команды нет в таблице до реализации задачи — `SystemExit`
        («Неизвестная команда canary») перехватывается и попадает в
        возвращаемый текст: необработанный `SystemExit` — не `Exception`,
        и unittest не ловит его сам, а завершает ИМ ВЕСЬ прогон
        `discover` вместо одного красного теста.
        """
        argv = ["artel.py", "canary", str(tz_dir), *extra_args]
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", argv):
            with redirect_stdout(buf):
                try:
                    artel.main()
                except SystemExit as exc:
                    buf.write(f"\n[SystemExit] {exc}\n")
        return buf.getvalue()

    def task_ids(self) -> list[str]:
        return [t["id"] for t in store.all_tasks(store.db())]

    def task_row(self, task_id: str):
        return store.get_task(store.db(), task_id)

    def journal(self, task_id: str):
        return store.task_steps(store.db(), task_id)

    def journal_text(self, task_id: str) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail']}"
                         for r in self.journal(task_id))
