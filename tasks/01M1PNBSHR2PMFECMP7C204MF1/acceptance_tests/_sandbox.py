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
- Сторож зависших прогонов (AC-8..AC-12/AC-15) тесты НЕ зовут напрямую
  по имени новой функции — SPEC называет только модуль (`doctor.py`) и
  поведение, не имя. Наблюдение идёт целиком через `doctor.cmd_doctor()`
  (реальный CLI-путь, тот же приём, что уже применяет
  `test_ac6_dead_lease_group_cleanup.py`), а находка/фильтрация/gating
  --fix — через наблюдаемые эффекты: строки `alerts` (AC-10) и реальную
  живость/смерть подставного OS-процесса (AC-11/AC-12). Это одновременно
  избавляет от догадки об имени внутренней функции И обязывает пройти
  РЕАЛЬНУЮ маршрутизацию `--fix` внутри `cmd_doctor`, которую как раз и
  проверяют AC-11/AC-12 (по прецеденту `sweep_orphan_artifact_branches`/
  `_fix_ignored_artifact_files` — обе аналогичные «уборки под --fix»
  этого же модуля вызываются именно из ветки `if fix:` внутри
  `cmd_doctor`, не из отдельно экспортированной функции верхнего уровня).

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
import json
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (alerts, catalog, checkpoint, cleanup, config,  # noqa: E402
                          doctor, gitcmd, lease, liveness, pause, release,
                          runner, store, workspace)
from tests.sandbox import (TmpRootTest, capture, claude_only_popen,  # noqa: E402
                           claude_only_run)

__all__ = ["alerts", "checkpoint", "cleanup", "config", "doctor", "gitcmd",
          "lease", "liveness", "pause", "release", "runner", "store",
          "workspace", "AgentStepSandbox", "capture", "wait_for",
          "wait_while_alive", "run_doctor", "fake_claude_cli",
          "spawn_hung_test_run"]


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


def run_doctor(fix: bool = False) -> None:
    """`doctor.cmd_doctor(fix=...)`, проглатывая `SystemExit` — обычный
    исход этой команды при ЛЮБОЙ провалившейся проверке (`sys.exit(1)` в
    конце `cmd_doctor`, не только от предмета этой задачи); тестам
    сторожа зависших прогонов (AC-8..AC-12/AC-15) важны побочные эффекты
    вызова (строки `alerts`, живость/смерть подставного процесса), не
    код возврата всей команды `doctor`."""
    try:
        doctor.cmd_doctor(fix=fix)
    except SystemExit:
        pass


class _FakeLiveSmokeProc:
    """Замена `subprocess.Popen` для `doctor.live_smoke` — только
    `.communicate` (по образцу `tests/test_doctor.py::FakeLiveSmokeProc`)."""

    def __init__(self, output: str, returncode: int = 0):
        self.output = output
        self.returncode = returncode

    def communicate(self, timeout=None):
        return self.output, None

    def kill(self) -> None:
        pass

    def wait(self, timeout=None) -> int:
        return self.returncode


@contextmanager
def fake_claude_cli():
    """Три подмены, без которых `doctor.cmd_doctor()` (реальный CLI-путь,
    которым тесты AC-6/AC-8..AC-12/AC-15 наблюдают сторожа) либо не
    находит `claude`, либо реально дозванивается наружу:

    - `shutil.which` — "найден" только `claude` (в т.ч. делает `gh`
      ненайденным для `check_base_branch`, у которой иначе ушёл бы
      настоящий сетевой запрос на фиктивный `targets.yaml`-URL);
    - `subprocess.run`/`subprocess.Popen` — версия CLI и живой смоук без
      реального запуска `claude`;
    - `doctor.isolation_smoke` — застаблена ЦЕЛИКОМ: она зовёт
      `runner.role_cmd()` собственной, не относящейся к предмету этих
      тестов проверкой (`--strict-mcp-config`), а пока фоновый шаг ещё
      не присоединён, `AgentStepSandbox.run_step_in_background` держит
      `runner.role_cmd` подменённым на argv тестовой пробы — без стаба
      здесь `cmd_doctor` ловил бы ЭТУ подмену как настоящий провал
      isolation-smoke (ловушка мока, не относящаяся к предмету теста) и
      падал на `sys.exit(1)` раньше, чем тест успевал проверить своё
      собственное свойство (тот же дефект был найден и починен в
      `test_ac6_dead_lease_group_cleanup.py`).
    """
    ok_check = doctor.Check("isolation-smoke", "ok", "стаб — не предмет этой задачи")
    live_smoke_proc = _FakeLiveSmokeProc(
        '{"type":"result","total_cost_usd":0.0,"usage":{}}\n')
    with mock.patch.object(
            doctor.shutil, "which",
            lambda name: "/usr/bin/claude" if name == "claude" else None), \
         mock.patch.object(doctor.subprocess, "run",
                           side_effect=claude_only_run("0.0.1 (Claude Code)\n")), \
         mock.patch.object(doctor.subprocess, "Popen",
                           side_effect=claude_only_popen(live_smoke_proc)), \
         mock.patch.object(doctor, "isolation_smoke", return_value=ok_check):
        yield


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

# Тестовый модуль-подстава «зависшего прогона тестов» (AC-8: «python -m
# unittest/pytest», cwd внутри `.artel/worktrees/`) — РЕАЛЬНЫЙ `python -m
# unittest <модуль>` с тестовым методом, который надолго спит; `ps`/`lsof`
# видят настоящую командную строку с «unittest» и настоящий cwd процесса —
# сторожу не подсунуть заглушку вместо реального сканирования ОС (тот же
# довод, что уже даёт `AgentStepSandbox` реальному `subprocess.Popen`
# агентного шага).
_HUNG_TEST_MODULE_SOLO = """
import time
import unittest


class SlowTest(unittest.TestCase):
    def test_it(self):
        time.sleep({sleep_sec})
"""

# Вариант с РЕАЛЬНЫМ потомком (аналог pytest-xdist воркера) — для AC-11
# (групповое, не одиночное, снятие сторожем под --fix). Пишет пару
# (свой pid, pid потомка) в файл из `$HUNG_TEST_PIDFILE` — тем же приёмом,
# что `_AGENT_WITH_CHILD` выше.
_HUNG_TEST_MODULE_WITH_CHILD = """
import json
import os
import subprocess
import sys
import time
import unittest


class SlowTest(unittest.TestCase):
    def test_it(self):
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep({sleep_sec})"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open(os.environ["HUNG_TEST_PIDFILE"], "w") as fh:
            json.dump({{"leader": os.getpid(), "child": child.pid}}, fh)
        time.sleep({sleep_sec})
"""

HUNG_TEST_MODULE_NAME = "test_hang_probe"


class _OrphanedProc:
    """Дескриптор уже оторвавшегося от тестового раннера процесса — сам
    объект `subprocess.Popen` обёрточной оболочки (см. `spawn_hung_
    test_run`) к моменту возврата функции УЖЕ завершился и не годится:
    его `.pid` — pid оболочки, не настоящего `python -m unittest`, а
    `.wait()` на чужом (не своём) потомке невозможен в принципе.
    Duck-type достаточно узкий, чтобы `AgentStepSandbox._reap`/
    `wait_while_alive`/`liveness._pid_alive` работали с ним так же, как
    с обычным `Popen`."""

    def __init__(self, pid: int):
        self.pid = pid

    def poll(self):
        return None if liveness._pid_alive(self.pid) else 0

    def kill(self) -> None:
        try:
            os.kill(self.pid, signal.SIGKILL)
        except OSError:
            pass

    def wait(self, timeout=None) -> int:
        return 0


def spawn_hung_test_run(workdir: Path, with_child: bool = False,
                        sleep_sec: int = 120, pidfile: Path | None = None
                        ) -> _OrphanedProc:
    """Реальный, уже ОТОРВАВШИЙСЯ `python -m unittest test_hang_probe» —
    `workdir` РОВНО тот каталог, что становится настоящим OS-cwd процесса
    (обычно `config.WORKTREES/<task_id>` — см. `AgentStepSandbox.
    worktree_dir`).

    Заводится ЧЕРЕЗ обёрточную оболочку (`sh -c '... & echo $! > pidfile;
    exit 0'`, `start_new_session=True` У ОБОЛОЧКИ), а не напрямую — по
    ДВУМ причинам, обе воспроизводят реальный сценарий инцидента (SPEC
    «Контекст»: shell-команда роли уходит в фон, пульт-обёртка
    завершается, потомок остаётся жить под launchd), а не побочный
    эффект тестового раннера:

    1. Группа процессов: `start_new_session=True` НЕПОСРЕДСТВЕННО на
       `python -m unittest` сделал бы ЕГО процессом-лидером сессии,
       которого этот тестовый процесс сам и породил бы напрямую — а
       значит остался бы ЕГО живым родителем. Здесь сессию заводит
       ОБОЛОЧКА, а бэкграундженная (`&`) команда наследует ЕЁ pgid, не
       pgid тестового раннера — сигнал сторожа по этой группе не
       заденет сам тестовый процесс.
    2. Реpresent («сирота»): после того как оболочка допишет pidfile и
       выйдет (`exit 0`), бэкграундженный `python -m unittest`
       переусыновляется launchd (pid 1) — ТЕМ ЖЕ путём, что и реальный
       инцидент. Без этого шага тестовый процесс остался бы РОДИТЕЛЕМ
       найденного pid: сигнал извне (`os.killpg`) убил бы его, но он
       превратился бы в зомби до `wait()` тестовым раннером — `os.kill
       (pid, 0)` (`liveness._pid_alive`) для НЕ дожатого зомби
       возвращает «жив» даже после успешного `SIGKILL`, что сделало бы
       приёмочные тесты (AC-9/AC-11/AC-12/AC-15) ложно красными
       независимо от корректности снятия сторожем.

    `with_child=True` (для AC-11) — тестовый метод сам заводит РЕАЛЬНОГО
    потомка и пишет пару pid'ов в `pidfile` (обязателен в этом режиме).
    """
    workdir.mkdir(parents=True, exist_ok=True)
    body = (_HUNG_TEST_MODULE_WITH_CHILD if with_child else _HUNG_TEST_MODULE_SOLO
           ).format(sleep_sec=sleep_sec)
    (workdir / f"{HUNG_TEST_MODULE_NAME}.py").write_text(body, encoding="utf-8")
    env = dict(os.environ)
    if with_child:
        assert pidfile is not None, "pidfile обязателен вместе с with_child=True"
        env["HUNG_TEST_PIDFILE"] = str(pidfile)
    leader_pidfile = workdir / ".leader.pid"
    argv = " ".join(shlex.quote(a) for a in
                    (sys.executable, "-m", "unittest", HUNG_TEST_MODULE_NAME, "-v"))
    shell_cmd = f"{argv} & echo $! > {shlex.quote(str(leader_pidfile))}; exit 0"
    wrapper = subprocess.Popen(
        ["/bin/sh", "-c", shell_cmd], cwd=str(workdir), env=env,
        start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wrapper.wait(timeout=5)
    wait_for(leader_pidfile.exists, timeout=5.0)
    leader_pid = int(leader_pidfile.read_text(encoding="utf-8").strip())
    return _OrphanedProc(leader_pid)


# Скрипт-агент AC-14: РЕАЛЬНАЯ команда `sleep` в дочерней оболочке (по
# образцу `spawn_sleep_process`, tests/test_pause_now.py, названному в
# SPEC «Материалы» как образец стаба) — в отличие от `_AGENT_WITH_CHILD`
# (потомок — python-подпроцесс, отслеживаемый через `wait()` самим
# скриптом-агентом), здесь потомок — оболочка ставит его В ФОН (`&`) и
# сама остаётся жить в `wait $!`: `sleep` — РАВНОПРАВНЫЙ член той же
# группы процессов (не «ребёнок, которого кто-то ждёт»), что ближе к
# реальному сценарию инцидента (роль запускает shell-команду, та
# бэкграундит часть работы).
_SHELL_SLEEP_AGENT = (
    "echo $$ > \"$1\"; "
    "sleep \"$3\" & echo $! > \"$2\"; "
    "wait"
)


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

    def shell_sleep_agent_cmd(self, sleep_sec: int = 60,
                              leader_out: str = "shell_leader.txt",
                              child_out: str = "shell_child.txt") -> list:
        """argv агентного шага AC-14: РЕАЛЬНАЯ команда `sleep` в дочерней
        оболочке (SPEC «Материалы», образец `spawn_sleep_process`), не
        python-подпроцесс — оболочка бэкграундит `sleep` (`&`) и сама
        остаётся жить в `wait`, так что оба — равноправные члены одной
        группы процессов, не пара «родитель ждёт ребёнка» (см. докстринг
        `_SHELL_SLEEP_AGENT`)."""
        return ["/bin/sh", "-c", _SHELL_SLEEP_AGENT, "sh",
               str(self.probe_path(leader_out)), str(self.probe_path(child_out)),
               str(sleep_sec)]

    def read_shell_leader_and_child_pid(
            self, leader_out: str = "shell_leader.txt",
            child_out: str = "shell_child.txt") -> tuple:
        leader_path = self.probe_path(leader_out)
        child_path = self.probe_path(child_out)
        wait_for(lambda: leader_path.exists() and child_path.exists(), timeout=5.0)
        return (int(leader_path.read_text(encoding="utf-8").strip()),
               int(child_path.read_text(encoding="utf-8").strip()))

    # ---------------------------------------------- сторож зависших прогонов

    def worktree_dir(self, task_id: str) -> Path:
        """`config.WORKTREES/<task_id>` — тот же путь, что и у настоящего
        per-task worktree (`_is_legit_task_worktree` в `doctor.py`),
        реально созданный на диске: AC-8 требует cwd подставного процесса
        РЕАЛЬНО внутри `.artel/worktrees/`, не просто похожую строку."""
        path = config.WORKTREES / task_id
        path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, path, True)
        return path

    def bootstrap_doctor_environment(self) -> None:
        """Минимальный скелет, которого требует `all_checks()` внутри
        `doctor.cmd_doctor()`, чтобы не падать на предметах, НЕ
        относящихся к сторожу зависших прогонов (skills/templates для
        `isolation_smoke` — впрочем застаблен `fake_claude_cli`, но читает
        файлы до подмены не зовётся; единственный target `targets.yaml` —
        `check_target_layout`/`check_remote_empty`/`check_base_branch`;
        маркер бэкапа — `check_backup_age`). Тот же набор, что уже собирает
        `test_ac6_dead_lease_group_cleanup.py`, вынесен сюда для
        переиспользования остальными тестами сторожа (AC-8..AC-12/AC-15)."""
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills", dirs_exist_ok=True)
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates",
                        dirs_exist_ok=True)
        (self.root / "docs").mkdir(exist_ok=True)
        (self.root / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
            "---\n\n# Карта\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
        config.TARGETS.write_text(
            "targets:\n  artel:\n    forge: github\n"
            "    url: https://example.invalid/artel\n    base: main\n"
            "    token_slot: artel-token\n    no_paths: []\n"
            "    project_skills: []\n    merge_gate: operator\n",
            encoding="utf-8")
        config.BACKUP_MARKER.parent.mkdir(parents=True, exist_ok=True)
        config.BACKUP_MARKER.write_text("ok", encoding="utf-8")

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
                            hostname: str | None = None,
                            task_id: str | None = None) -> None:
        """Строка `leases`, представляющая «шаг сейчас бежит» — pid здесь
        нарочно НЕ pid агентного процесса (см. модульный докстринг
        `orchestrator/lease.py`: `lease.acquire` пишет pid ВЫЗЫВАЮЩЕГО
        процесса пульта, не спавненного потомка) — отдельный, управляемый
        тестом процесс, чтобы пути AC-4/AC-5/AC-6 могли адресоваться по
        `row['pid']`, не рискуя сигналом по процессу самого тестового
        раннера. `task_id` по умолчанию — `self.TASK`; тесты сторожа
        зависших прогонов (AC-9/AC-15) заводят lease для ДРУГОЙ задачи
        (см. `ensure_task`)."""
        store.insert_lease(store.db(), task_id or self.TASK, session_id, pid,
                           hostname or socket.gethostname(), store.now())

    def ensure_task(self, task_id: str) -> None:
        """Строка `tasks` для id, отличного от `self.TASK` (AC-9/AC-15:
        сторож зависших прогонов сравнивает несколько задач разом).
        `store.get_task` на отсутствующем id зовёт `sys.exit` (CLI-
        поведение, не годится для проверки существования) — здесь вместо
        него `store.all_tasks`."""
        known_ids = {r["id"] for r in store.all_tasks(store.db())}
        if task_id not in known_ids:
            store.insert_task(store.db(), task_id, "Задача", "in_dev",
                              f"task/{task_id.lower()}-zadacha",
                              config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)

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

    @staticmethod
    def _kill_pid_if_alive(pid: int) -> None:
        if liveness._pid_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    def spawn_hung(self, task_id: str, with_child: bool = False,
                  sleep_sec: int = 120) -> _OrphanedProc:
        """Подставной «зависший прогон тестов» (AC-8) внутри
        `worktree_dir(task_id)`; уборка регистрируется независимо от
        того, снимет ли его сам сторож в ходе теста."""
        workdir = self.worktree_dir(task_id)
        pidfile = (self.probe_path(f"{task_id}-hung-pids.json")
                  if with_child else None)
        proc = spawn_hung_test_run(workdir, with_child=with_child,
                                   sleep_sec=sleep_sec, pidfile=pidfile)
        self.addCleanup(self._reap, proc)
        return proc

    def read_hung_child_pid(self, task_id: str) -> tuple:
        """(leader_pid, child_pid) подставного «зависшего прогона»,
        заведённого `spawn_hung(task_id, with_child=True)`."""
        pidfile = self.probe_path(f"{task_id}-hung-pids.json")
        wait_for(pidfile.exists, timeout=5.0)
        data = json.loads(pidfile.read_text(encoding="utf-8"))
        leader, child = int(data["leader"]), int(data["child"])
        self.addCleanup(self._kill_pid_if_alive, child)
        return leader, child

    def journal_text(self) -> str:
        rows = store.task_steps(store.db(), self.TASK)
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail']}"
                         for r in rows)

    @staticmethod
    def all_alert_messages() -> list:
        """Тексты ВСЕХ строк `alerts` — открытых и уже подтверждённых.
        `store.py` не несёт отдельного «все алерты без фильтра по ack»
        (только `open_alerts`) — `alerts_older_than` с заведомо будущим
        cutoff возвращает все строки независимо от `ack_ts`, тот же
        приём, что уже применяет `prune` (T073) для архивации."""
        rows = store.alerts_older_than(store.db(), "9999-01-01 00:00:00Z")
        return [r["message"] for r in rows]
