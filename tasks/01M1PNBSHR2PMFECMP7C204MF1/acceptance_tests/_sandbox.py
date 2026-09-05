"""Общая песочница приёмочных тестов задачи 01M1PNBSHR2PMFECMP7C204MF1
(не test_*.py — не подхватывается `unittest discover` напрямую, только
импортом из `test_ac*.py`, тот же приём, что `tasks/T074/acceptance_tests/
_sandbox.py`).

## Допущения интерфейса

SPEC (tasks/01M1PNBSHR2PMFECMP7C204MF1/SPEC.md) называет модули
(`orchestrator/runner.py`, `pause.py`, `lease.py`, `doctor.py`,
`cleanup.py`/`artel.py`), но не имена новых функций/констант. По
прецеденту `tasks/T074/acceptance_tests/_sandbox.py` — SPEC тоже не
фиксировала имя `cmd_pause_now` — здесь приняты следующие допущения,
явно названные, чтобы отказ по НЕВЕРНОМУ имени был отличим от отказа по
отсутствующему поведению:

- Группа процессов агентного шага заводится ВНУТРИ существующей точки
  спавна `orchestrator.runner.spawn_agent`/`run_agent_once` (AC-1) — сам
  факт проверяется НАБЛЮДАЕМО (pgid потомка), не именем нового
  параметра/kwarg, поэтому тест не зависит от того, каким именно
  способом (`start_new_session`, `preexec_fn=os.setsid`, …) это сделано.
- Хранилище pgid (AC-2, «в lease и/или журнал шага») тесты AC-2/AC-4..
  AC-7/AC-14 НЕ фиксируют явно: сценарии закрытые — pgid записывает
  РЕАЛЬНЫЙ прогон `run_agent_once`, а пути kill/pause_now/release читают
  его РЕАЛЬНЫМ кодом этой же кодовой базы. Тест не знает и не проверяет,
  колонка это `leases` или текст журнала — только то, что запись и
  чтение СОГЛАСОВАНЫ (AC-2) и что адресуемая группа реально гибнет
  (AC-3..AC-7/AC-14).
- Возрастной порог сторожа зависших прогонов (AC-8, «именованная
  константа, по умолчанию 10 минут») — SPEC не называет буквальное имя;
  здесь принято `orchestrator.config.HUNG_TEST_RUN_AGE_SEC` (тот же
  модуль и тот же стиль имени, что `LEASE_STALE_AFTER_SEC`,
  `AGENT_TIMEOUT_SEC` — системные пороги живут в `config.py`, не в
  `doctor.py`). Прогон ДО реализации либо ПОСЛЕ реализации под другим
  именем константы падает `AttributeError` на попытке подмены — это
  расхождение имени, а не поведения; чинится переименованием константы
  в этом файле под фактический выбор разработчика (REVIEW.md).

Прогон ДО реализации падает по разным причинам в зависимости от файла
(`AttributeError`/`TypeError` на ещё не заведённой функции/константе,
либо содержательный `assertFalse`/`assertTrue` на потомке, который
сегодня переживает завершение шага) — соответствующий маркер красноты
называет причину в каждом файле отдельно.

## Песочница

`AgentStepSandbox` — `tests.sandbox.TmpRootTest` (пути `config` во
временном каталоге, `gitcmd.subprocess.run` подменён `SpyRun`) плюс:
реальный (не замоканный) `runner.spawn_agent`/`subprocess.Popen` для
самого агентного шага — механику группы процессов заглушкой не
проверить (тот же довод, что даёт `RealGitSandbox` реальному git); git-
идентичность, `workspace.ensure` и чекпоинты шага заглушены — они не
относятся к предмету этой задачи и уже покрыты своими тестами
(T041/T074/T094).
"""
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (catalog, checkpoint, cleanup, config, doctor,  # noqa: E402
                          gitcmd, lease, liveness, pause, release, runner,
                          store, workspace)
from tests.sandbox import TmpRootTest, capture  # noqa: E402

__all__ = ["checkpoint", "cleanup", "config", "doctor", "gitcmd", "lease",
          "liveness", "pause", "release", "runner", "store", "workspace",
          "AgentStepSandbox", "capture", "wait_for", "wait_while_alive"]


def wait_for(predicate, timeout: float = 5.0, interval: float = 0.02) -> bool:
    """Опрашивает `predicate()` до True или истечения `timeout`; возвращает
    итоговое значение — тот же приём поллинга, что `pause.TERMINATE_POLL_SEC`
    уже использует для опроса живости pid."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def wait_while_alive(pid: int, timeout: float = 5.0) -> bool:
    """True — процесс УМЕР до истечения `timeout` (используется после
    сигнала, вместо фиксированного `time.sleep`, чтобы не завышать время
    прогона на быстрых машинах и не флакать на медленных)."""
    return wait_for(lambda: not liveness._pid_alive(pid), timeout)


# Скрипт-проба: пишет собственный pgid в файл и сразу завершается —
# минимальная проверка AC-1/AC-13 без побочных процессов.
_PGID_PROBE = (
    "import os,sys\n"
    "open(sys.argv[1], 'w').write(str(os.getpgid(0)))\n"
)

# Скрипт-агент: заводит РЕАЛЬНОГО потомка (по образцу пользовательского
# `pytest`/`unittest` из «Контекста» SPEC — процесс, который сам себе не
# ставит новую сессию и потому наследует группу родителя), пишет пары
# (свой pid, pid потомка) в файл, затем оба спят достаточно долго, чтобы
# внешний путь (timeout/kill/pause_now) успел вмешаться. stdout/stderr
# потомка — DEVNULL, не унаследованный пайп: иначе `close_pump` ждёт
# `PUMP_JOIN_TIMEOUT_SEC` закрытия пайпа потомком на каждом прогоне
# ДО реализации (тот же класс, что докстринг `runner.close_pump` уже
# описывает) — предмет ЭТИХ тестов — снятие потомка, не полнота лога.
_AGENT_WITH_CHILD = """
import os, subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c",
                          "import time; time.sleep(60)"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
with open(sys.argv[1], "w") as f:
    f.write(f"{os.getpid()} {child.pid}")
time.sleep(60)
"""


class AgentStepSandbox(TmpRootTest):
    """Реальный `run_agent_once`, но с заглушенным всем, что не относится
    к предмету SPEC 01M1PNBSHR2PMFECMP7C204MF1 (группа процессов
    агентного шага)."""

    TASK = "T001"
    ROLE = "developer"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self._probe_dir = Path(tempfile.mkdtemp(prefix="artel-pgid-probe-"))
        self.addCleanup(shutil.rmtree, self._probe_dir, True)

        # Идентичность роли — без реального git.
        identity = {"user.name": "Роль Артели", "user.email": "role@artel.invalid"}
        def fake_git_config(*args):
            value = identity.get(args[-1], "") if args[:2] == ("config", "--get") else ""
            return subprocess.CompletedProcess(list(args), 0, f"{value}\n", "")
        git_patcher = mock.patch.object(runner.gitcmd, "git", fake_git_config)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)

        # Рабочий каталог шага — обычный temp-каталог, не настоящий git
        # worktree (git-механика чекпоинта — не предмет этой задачи).
        self._cwd = Path(tempfile.mkdtemp(prefix="artel-role-cwd-"))
        self.addCleanup(shutil.rmtree, self._cwd, True)
        wt_patcher = mock.patch.object(
            runner.workspace, "ensure", lambda task_id, branch: (self._cwd, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)

        # Токен — ambient, без обращения к keychain/`security`.
        env_patcher = mock.patch.dict(
            os.environ, {"ANTHROPIC_API_KEY": "тестовый-токен"})
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

        # Чекпоинты шага — git-механика, уже покрытая T041/T074/T094;
        # здесь важна только группа процессов, не коммиты.
        for name in ("commit_step_artifacts", "commit_timeout_checkpoint",
                    "commit_abnormal_checkpoint", "commit_pause_now_checkpoint"):
            patcher = mock.patch.object(checkpoint, name, return_value="")
            patcher.start()
            self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ пробы

    def probe_path(self, name: str) -> Path:
        return self._probe_dir / name

    def pgid_probe_cmd(self, out_name: str = "pgid.txt") -> list:
        """argv агентного шага, который пишет `os.getpgid(0)` в файл и
        завершается — для AC-1/AC-13."""
        return [sys.executable, "-c", _PGID_PROBE, str(self.probe_path(out_name))]

    def agent_with_child_cmd(self, out_name: str = "pids.txt") -> list:
        """argv агентного шага, заводящего собственного потомка
        (по образцу `pytest`/`unittest`, запущенных ролью) — для
        AC-3/AC-4/AC-5/AC-6/AC-7/AC-14."""
        return [sys.executable, "-c", _AGENT_WITH_CHILD,
               str(self.probe_path(out_name))]

    def read_agent_and_child_pid(self, out_name: str = "pids.txt") -> tuple:
        path = self.probe_path(out_name)
        wait_for(path.exists, timeout=5.0)
        agent_pid, child_pid = path.read_text(encoding="utf-8").split()
        return int(agent_pid), int(child_pid)

    # --------------------------------------------------- прогон шага

    def run_step(self, argv: list, timeout_sec: float | None = None):
        """Реальный `run_agent_once` с `role_cmd`, подменённым на `argv`
        (единственная реальная точка расхождения с продакшеном — вместо
        `claude -p`); `spawn_agent`/`subprocess.Popen` НЕ замокан."""
        patches = [mock.patch.object(runner, "role_cmd", lambda: argv)]
        if timeout_sec is not None:
            patches.append(mock.patch.object(config, "AGENT_TIMEOUT_SEC", timeout_sec))
        for p in patches:
            p.start()
        try:
            return runner.run_agent_once(store.db(), self.TASK, self.ROLE,
                                         "тестовый промпт", 1)
        finally:
            for p in reversed(patches):
                p.stop()

    # Таймаут ФОНОВОГО прогона — верхняя граница на случай, если
    # адресующий путь (kill/pause_now/release) ещё не реализован вовсе:
    # тогда сам процесс-агент снимается штатным таймаутом `run_agent_once`
    # (уже существующее поведение, не предмет этой задачи), и фоновый
    # поток не виснет на всё время `AGENT_TIMEOUT_SEC` продакшена —
    # маленькое число здесь ограничивает КРАСНЫЙ прогон, не логику.
    BACKGROUND_STEP_TIMEOUT_SEC = 3.0

    def run_step_in_background(self, argv: list) -> threading.Thread:
        """Тот же `run_step`, но в фоновом потоке — эмулирует «шаг бежит в
        другом процессе пульта, пока эта же кодовая база адресуется к нему
        из отдельной команды» (kill/pause_now/release): `run_agent_once`
        не трогает lease НИ ОДНИМ вызовом (только его вызыватель `_cmd_run`
        через обёртку `lease.run_locked`) — поток безопасен для фоновой
        имитации ровно потому, что нет общих мутируемых структур, кроме
        БД (свежее соединение на каждый вызов, WAL) и файлов, которые сам
        сценарий и читает. `daemon=True` — тестовый процесс не обязан
        ждать зависший поток, если адресующий путь ещё не снимает
        процесс вовсе.
        """
        thread = threading.Thread(
            target=self.run_step, args=(argv,),
            kwargs={"timeout_sec": self.BACKGROUND_STEP_TIMEOUT_SEC},
            daemon=True)
        thread.start()
        return thread

    # ----------------------------------------------------- lease-заглушка

    def install_dummy_lease(self, pid: int, session_id: str = "test-session",
                            hostname: str | None = None) -> None:
        """Строка `leases`, представляющая «шаг сейчас бежит» — pid здесь
        нарочно НЕ pid агентного процесса (см. модульный докстринг
        `orchestrator/lease.py`: `lease.acquire` пишет pid ВЫЗЫВАЮЩЕГО
        процесса пульта, не спавненного потомка) — отдельный, управляемый
        тестом процесс, чтобы пути AC-4/AC-5/AC-6 могли адресоваться по
        `row['pid']`, не рискуя сигналом по процессу самого тестового
        раннера."""
        store.insert_lease(store.db(), self.TASK, session_id, pid,
                           hostname or socket.gethostname(), store.now())

    def assert_lease_pid_unchanged(self, expected_pid: int) -> None:
        """Страховка перед сигналом по `row['pid']` (kill/pause_now/
        release читают его): запись pgid агентного шага (AC-2) обязана
        идти НЕ через перезапись существующего pid лизы. Внезапная
        перезапись на pid этого тестового процесса превратила бы
        следующий SIGTERM в самоубийство раннера — тест обязан упасть
        осмысленной ошибкой раньше, чем это случится."""
        row = store.lease_row(store.db(), self.TASK)
        assert row is not None, "лиза пропала до адресации"
        assert row["pid"] == expected_pid, (
            f"pid лизы изменился с {expected_pid} на {row['pid']} — "
            f"вероятная перезапись существующего pid при записи pgid "
            f"(AC-2); сигнал по нему сейчас был бы опасен, тест "
            f"остановлен")

    @staticmethod
    def dead_pid() -> int:
        proc = subprocess.Popen([sys.executable, "-c", "pass"],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        proc.wait()
        return proc.pid

    def spawn_placeholder_process(self) -> subprocess.Popen:
        """Реальный, безобидный «держатель lease» (представляет процесс
        пульта, не агента) — живёт, пока явно не убран."""
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self._reap, proc)
        return proc

    @staticmethod
    def _reap(proc: subprocess.Popen) -> None:
        if proc.poll() is None:
            proc.kill()
        proc.wait()

    def journal_text(self) -> str:
        rows = store.task_steps(store.db(), self.TASK)
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail']}"
                         for r in rows)
