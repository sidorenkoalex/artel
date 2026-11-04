"""Надзор эпика: перезапуск остановленных задач, предел аварий, снятое ожидание зоны, места `parallel`, завершение надзора (AC-1 … AC-12).

Группа: долгоживущий
Красен до реализации: надзор держит задачу после аварийного выхода дочернего до `epic retry` и сам не перезапускает её, `resume` после `stop` журнала не пишет, остановка потолком ожидания зоны держит задачу и после освобождения зоны, живой дочерний, ждущий зону или CI, занимает место `parallel`, а надзор открытого эпика с окончательными задачами завершается сам на первом опросе.

Перезапуск по действию Оператора после выхода (AC-1), удержание прочих
остановок (AC-4, кроме именованных отказов дочернего), гейт, пауза и
эскалация (AC-6) и глобальная оценка мест (AC-10) зелены с рождения: они
держат сегодняшнее поведение против новой ветки перезапуска, которая
пройдёт мимо него.

Провалидировано временным стабом реализации поверх ветки задачи (правка
`_child_holds`/`_epic_view`/`_supervise` надзора, ветка `resume` после
`stop`, запись отказа lease `auto`; удалён, не закоммичен): все методы
файла зелёные.

Связка, которую держит файл: команда CLI (`artel.main` с `sys.argv`) — БД
пульта (`tasks`, `steps`, `leases`, `epics`, `epic_supervisors`,
`epic_children`, `observations`, `alerts`) — порождение отвязанных
процессов (`subprocess.Popen`) — сигналы процессам (`os.kill`) — дозор
`watch`.

Стенд — тот же приём, что у файла надзора эпика
(`tests/test_01m5tbf7jrz6fgrr4k53kpajds_epic_supervisor.py`), копией: помощник
долгоживущего файла берётся только из `tests/sandbox.py`.

- Запуск процесса пульта (`artel.py`) не исполняется: вместо него
  порождается настоящий процесс-заместитель, который ждёт сигнала; на
  SIGTERM он пишет имя сигнала в файл-метку и выходит, SIGKILL его убивает.
- Запуск с id задачи эпика и `auto` — дочерний `auto`. Его заместитель на
  ближайшей паузе надзора ведёт себя как стартовавший цикл: берёт lease
  задачи своим pid и пишет `zone_lock.AUTO_START_ACTION`. «Немой» дочерний
  (задача в `Pult.mute`) не стартует — так разыгрывается выход до записи
  старта цикла. Остановки и ожидания дочернего сценарий пишет теми
  записями журнала, которые оставляет настоящий цикл (`auto остановлен`
  с причиной в детали, `цикл оборван`, вход в ожидание зоны и выход из
  него — `zone_lock.wait_*_action`), снимает lease и гасит процесс.
- Запуск с id эпика — надзирающий процесс; сам надзор исполняется в
  процессе теста той же командной строкой, пока заместитель жив.
  Пауза надзора (`time.sleep` модулей пульта) — шаг сценария: между двумя
  шагами сценария ровно один опрос надзора. Длительность каждой паузы
  записывается (`Pult.sleeps`).
- Действия Оператора — его командами CLI там, где команде не нужен git
  (`resume`, `pause`, `pause --now`, `stop`, `epic retry`, `zone-release`,
  `zone-reorder`, `epic close`, `epic stop`), иначе — записью журнала,
  которую команда оставляет (`approve`/`reject` — `state -> …` актора
  `operator`, `budget` — «бюджет изменён», `answer`/`zones-extend` —
  «ANSWER создан …», `amend-tests` — `amend.AMEND_ACTION`, `ci-rerun` —
  `ci_rerun.CI_RERUN_ACTION`).
- Причины остановки цикла, у которых в коде нет публичного имени
  (потолок ожидания зоны, потеря lease в ожидании, команда `stop`), —
  литералами детали записи `auto остановлен`.

Идентификаторы задач и эпика, зоны, вид аварии и число задач порождаются
модулем `random` при каждом запуске; зерно печатается и входит в текст
провала.
"""
import importlib
import io
import os
import random
import runpy
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import (amend, artel, auto, ci_rerun, config, fsm, pause,
                          runner, store, targets, watch, zone_lock)
from tests.sandbox import patch_pult_sleep, patch_sleep

REAL_POPEN = subprocess.Popen
REAL_KILL = os.kill
REAL_KILLPG = os.killpg
REAL_GETPID = os.getpid
ULID = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ROLE_STEP_STARTED = "agent run started"
ROLE_STEP_FINISHED = "agent run finished"
STOPPING_SIGNALS = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
NOW_FORMAT = "%Y-%m-%d %H:%M:%SZ"  # формат `store.now()`
IDLE = 8  # пауз надзора на «ничего не происходит»
RELAUNCH_POLLS = 3  # «ограниченное число опросов» перезапуска после аварии
IDLE_POLL_SEC = 5 * 60  # период опроса без неокончательных задач (SPEC: 5 минут)
# Причины остановки цикла — детали записи `auto остановлен` (`<состояние>: <причина>`).
STOP_COMMAND_REASON = "штатная остановка — команда stop"
ZONE_CEILING_REASON = "потолок ожидания зоны исчерпан"
ZONE_LEASE_LOST_REASON = "lease задачи потерян во время ожидания зоны"
STEP_LIMIT_REASON = f"лимит {config.AUTO_MAX_STEPS} шагов за вызов исчерпан"
# Перечень действий Оператора надзора (SPEC, требование 4: auto.py:1224-1226).
OPERATOR_ACTIONS = ("бюджет изменён", "resume", amend.AMEND_ACTION,
                    ci_rerun.CI_RERUN_ACTION, auto.EPIC_RETRY_ACTION)
OPERATOR_PREFIXES = ("state -> ", "ANSWER создан", "pause")
CRASH_KINDS = ("нет старта", "нет остановки", "цикл оборван")

STAND_SCRIPT = """\
import pathlib, signal, sys
mark = pathlib.Path(sys.argv[1])
def on_signal(signum, frame):
    mark.write_text(signal.Signals(signum).name)
    raise SystemExit(0)
for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
    signal.signal(sig, on_signal)
print("ready", flush=True)
while True:
    signal.pause()
"""


class StopScenario(BaseException):
    """Сценарий окончен: разматывает надзор, исполняемый в процессе теста."""


class SupervisorKilled(BaseException):
    """Сигнал надзору без его обработчика: процесс кончился бы действием по умолчанию."""


class WatchDone(Exception):
    """Первая пауза дозора: одна итерация доставки прошла."""


class Stand:
    """Процесс-заместитель отвязанного процесса пульта."""

    def __init__(self, directory: Path):
        self.mark = directory / f"signal-{uuid.uuid4().hex}"
        self.popen = REAL_POPEN([sys.executable, "-c", STAND_SCRIPT, str(self.mark)],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, start_new_session=True)
        # Обработчики сигналов стоят до ответа «ready»: сигнал не опередит их.
        self.popen.stdout.readline()
        self.popen.stdout.close()
        self.pid = self.popen.pid
        # Завершившийся процесс сразу пожинается: зомби отвечал бы «жив».
        threading.Thread(target=self.popen.wait, daemon=True).start()

    def alive(self) -> bool:
        return self.popen.poll() is None

    def finish(self) -> None:
        """Ждёт выхода процесса; предел — страховка от зависания."""
        self.popen.wait(timeout=30)

    def kill(self) -> None:
        if self.popen.poll() is None:
            try:
                REAL_KILL(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.popen.wait(timeout=30)


@dataclass
class Launch:
    kind: str  # "надзор" | "дочерний"
    task: str | None
    stand: Stand
    argv: list
    started: bool = False


def is_pult_launch(argv: list) -> bool:
    if any(Path(a).name == "artel.py" for a in argv):
        return True
    return any(a == "-m" and i + 1 < len(argv) and argv[i + 1].startswith("orchestrator")
               for i, a in enumerate(argv))


def run_command_line(argv: list) -> None:
    """Исполняет в процессе теста командную строку, отданную `Popen`."""
    i = 1
    while i < len(argv) and argv[i].startswith("-") and argv[i] != "-m":
        i += 1
    if argv[i] == "-m":
        with mock.patch.object(sys, "argv", [argv[i + 1], *argv[i + 2:]]):
            runpy.run_module(argv[i + 1], run_name="__main__", alter_sys=True)
        return
    with mock.patch.object(sys, "argv", [argv[i], *argv[i + 1:]]):
        if Path(argv[i]).name == "artel.py":
            artel.main()
        else:
            runpy.run_path(argv[i], run_name="__main__")


@dataclass
class Pult:
    """Пульт сценария: эпик, задачи, наблюдения, запуски и сигналы."""

    seed: int
    root: Path
    rng: random.Random = None
    session: str = ""
    project: str = config.DEFAULT_TARGET
    epic: str | None = None
    task_ids: list = field(default_factory=list)
    stands: list = field(default_factory=list)
    launches: list = field(default_factory=list)
    kills: list = field(default_factory=list)

    def __post_init__(self):
        self.rng = random.Random(self.seed)
        self.session = f"сессия-{self.seed:x}"
        self.prefix = "".join(self.rng.choices(ULID, k=20))
        self.counter = 0
        self.stack = ExitStack()
        self.cond = threading.Condition()
        self.pending: list = []
        self.sup: Stand | None = None
        self.sup_dead = False
        self.supervising = False
        self.in_step = False
        self.stopper: threading.Thread | None = None
        self.stop_result = None
        self.error = None
        self.exit = None
        self.ticks = 0
        self.limit = 0
        self.script = None
        self.run_from = 0
        self.mute: set = set()
        self.sleeps: list = []

    # --- общее ---

    def msg(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def fail(self, text: str):
        raise AssertionError(self.msg(text))

    def cli(self, *argv: str) -> tuple:
        """(код отказа или None, вывод) команды `artel.py <argv>`."""
        buf = io.StringIO()
        code = None
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                redirect_stdout(buf), redirect_stderr(buf):
            try:
                artel.main()
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    code = exc.code
        return code, buf.getvalue()

    def ok(self, *argv: str) -> str:
        code, out = self.cli(*argv)
        if code is not None:
            self.fail(f"`{' '.join(argv)}` отказала: {code}\n{out}")
        return out

    def global_limit(self, value: int) -> None:
        self.stack.enter_context(mock.patch.object(config, "MAX_PARALLEL_TASKS", value))

    # --- эпик, задачи, наблюдения ---

    def new_epic(self, project: str | None = None) -> str:
        if project is not None:
            self.project = project
        title = f"Эпик {self.seed:x}-{self.rng.randrange(1 << 30):x}"
        self.ok("epic", "new", self.project, title, "--goal", "Цель сценария")
        row = store.db().execute("SELECT id FROM epics WHERE title=?", (title,)).fetchone()
        if row is None:
            self.fail("эпик не заведён")
        self.epic = row["id"]
        return self.epic

    def task(self, state: str = "in_dev", *, epic: bool = True, started: bool = False,
             zone: str | None = None) -> str:
        self.counter += 1
        task_id = f"01{self.prefix}{self.counter:04d}"
        conn = store.db()
        store.insert_task(conn, task_id, f"Задача {self.counter}", state,
                          f"task/{task_id.lower()}-epik", self.project, 1000.0)
        if epic:
            store.update_task(conn, task_id, epic_id=self.epic)
        if zone is not None:
            store.update_task(conn, task_id, zones=zone)
        if started:
            store.journal(conn, task_id, "developer", ROLE_STEP_STARTED, "попытка 1/3")
        self.task_ids.append(task_id)
        return task_id

    def set_state(self, task: str, state: str, actor: str = "fsm") -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task))
        conn.commit()
        store.journal(conn, task, actor, f"state -> {state}", "")

    def state(self, task: str) -> str:
        return store.db().execute("SELECT state FROM tasks WHERE id=?", (task,)).fetchone()[0]

    def paused(self, task: str) -> bool:
        return bool(store.get_task(store.db(), task)["paused"])

    def observation(self, tasks: list) -> str:
        """Свежее наблюдение сессии сценария с задачами `tasks`."""
        conn = store.db()
        obs = store.register_observation(conn, self.project, "", "",
                                         self.session, list(tasks))
        now = datetime.now(timezone.utc)
        with conn:
            conn.execute("UPDATE observations SET last_seen_at=?, created_at=? WHERE id=?",
                         (now.isoformat(), now.strftime(NOW_FORMAT), obs))
        return obs

    def take_lease(self, task: str, session: str, pid: int) -> None:
        conn = store.db()
        if store.lease_row(conn, task) is None:
            store.insert_lease(conn, task, session, pid, socket.gethostname(), store.now())
        else:
            store.update_lease(conn, task, session, pid, socket.gethostname(), store.now())

    def foreign_auto(self, task: str) -> Stand:
        """`auto <id>` другой сессии: живой процесс держит lease задачи."""
        stand = Stand(self.root)
        self.stands.append(stand)
        self.take_lease(task, f"чужой-auto-{stand.pid}", stand.pid)
        return stand

    def release_foreign(self, task: str, stand: Stand) -> None:
        conn = store.db()
        row = store.lease_row(conn, task)
        if row is not None:
            store.release_lease(conn, task, row["session_id"])
        stand.kill()

    def top_step(self) -> int:
        return store.db().execute("SELECT COALESCE(MAX(id), 0) FROM steps").fetchone()[0]

    def top_alert(self) -> int:
        return store.db().execute("SELECT COALESCE(MAX(id), 0) FROM alerts").fetchone()[0]

    def records(self, task: str, since: int = 0) -> list:
        return store.db().execute("SELECT * FROM steps WHERE task_id=? AND id>? ORDER BY id",
                                  (task, since)).fetchall()

    def lost_records(self, task: str) -> list:
        return [r for r in self.records(task) if r["action"] == auto.EPIC_CHILD_LOST_ACTION]

    def task_alerts(self, task: str, since: int = 0) -> list:
        """Тревоги `attention` по задаче (открытые и закрытые), заведённые после `since`."""
        return store.db().execute(
            "SELECT * FROM alerts WHERE kind='attention' AND id>? "
            "AND (target=? OR message LIKE ?)", (since, task, f"%{task}%")).fetchall()

    def epic_alerts(self) -> list:
        return [row for row in store.open_alerts(store.db(), "attention")
                if row["target"] == self.epic or self.epic in (row["message"] or "")]

    def epic_has_open_tasks(self) -> bool:
        if self.epic is None:
            return False
        return any(t["state"] not in fsm.TERMINAL_STATES
                   for t in store.epic_tasks(store.db(), self.epic))

    # --- записи надзора по задаче ---

    def supervisor_notes(self, task: str, since: int, until: int | None = None) -> list:
        """Записи журнала задачи и записи эпика, называющие задачу, после `since`
        (до `until` включительно), кроме записей запуска и потери дочернего."""
        conn = store.db()
        bound = until if until is not None else 1 << 62
        rows = conn.execute("SELECT * FROM steps WHERE id>? AND id<=? AND "
                            "(task_id=? OR (task_id=? AND (action LIKE ? OR detail LIKE ?))) "
                            "ORDER BY id",
                            (since, bound, task, self.epic, f"%{task}%", f"%{task}%")).fetchall()
        return [r for r in rows if r["action"] not in (auto.EPIC_CHILD_LAUNCH_ACTION,
                                                       auto.EPIC_CHILD_LOST_ACTION)]

    def limit_records(self, task: str, since: int) -> list:
        """Записи после `since` с действием, которого у задачи до `since` не было:
        запись предела аварий (записи каждой аварии повторяют прежние действия)."""
        known = {r["action"] for r in self.supervisor_notes(task, 0, since)}
        return [r for r in self.supervisor_notes(task, since) if r["action"] not in known]

    # --- запуски ---

    def supervisor_launches(self) -> list:
        return [l for l in self.launches if l.kind == "надзор"]

    def children(self, task: str | None = None) -> list:
        return [l for l in self.launches
                if l.kind == "дочерний" and (task is None or l.task == task)]

    def launched(self) -> list:
        return [l.task for l in self.children()]

    def count(self, task: str) -> int:
        return len(self.children(task))

    def start(self) -> str:
        before = len(self.supervisor_launches())
        out = self.ok("auto", "--epic", self.epic)
        if len(self.supervisor_launches()) == before:
            self.fail(f"`auto --epic {self.epic}` не запустил надзирающий процесс:\n{out}")
        return out

    def popen(self, cmd, *args, **kwargs):
        argv = [str(a) for a in cmd] if isinstance(cmd, (list, tuple)) else [str(cmd)]
        if not is_pult_launch(argv):
            return REAL_POPEN(cmd, *args, **kwargs)
        task = next((t for t in self.task_ids if t in argv), None)
        if task is not None and "auto" in argv:
            kind = "дочерний"
        elif self.epic is not None and self.epic in argv:
            kind = "надзор"
        else:
            self.error = self.error or AssertionError(
                self.msg(f"неожиданный запуск процесса пульта: {argv}"))
            raise self.error
        stand = Stand(self.root)
        self.stands.append(stand)
        self.launches.append(Launch(kind, task if kind == "дочерний" else None, stand, argv))
        return stand.popen

    def start_children(self) -> None:
        """Заместители дочерних `auto` стартуют: lease задачи и запись старта цикла."""
        for launch in self.children():
            if launch.started or not launch.stand.alive() or launch.task in self.mute:
                continue
            launch.started = True
            self.take_lease(launch.task, f"дочерний-{launch.stand.pid}", launch.stand.pid)
            store.journal(store.db(), launch.task, "operator", zone_lock.AUTO_START_ACTION,
                          f"состояние {self.state(launch.task)}, сценарий")

    # --- сигналы и pid ---

    def addressed_to_supervisor(self, pid: int, sig: int) -> bool:
        return (sig != 0 and self.supervising and not self.sup_dead
                and self.sup is not None and pid == self.sup.pid)

    def queue_signal(self, sig: int) -> None:
        with self.cond:
            self.pending.append(sig)
            self.cond.notify_all()

    def kill(self, pid, sig):
        self.kills.append((pid, sig))
        if self.addressed_to_supervisor(pid, sig):
            self.queue_signal(sig)
            return None
        if sig != 0 and pid == REAL_GETPID():
            self.error = self.error or AssertionError(self.msg(f"сигнал {sig} процессу теста"))
            return None
        return REAL_KILL(pid, sig)

    def killpg(self, pgid, sig):
        self.kills.append((pgid, sig))
        if self.addressed_to_supervisor(pgid, sig):
            self.queue_signal(sig)
            return None
        return REAL_KILLPG(pgid, sig)

    def getpid(self):
        if (self.supervising and not self.in_step and self.sup is not None
                and threading.current_thread() is threading.main_thread()):
            return self.sup.pid
        return REAL_GETPID()

    def deliver(self) -> None:
        with self.cond:
            pending, self.pending = self.pending, []
        for sig in pending:
            handler = signal.getsignal(sig)
            if callable(handler):
                handler(sig, None)
            elif handler != signal.SIG_IGN:
                raise SupervisorKilled()

    # --- надзор в процессе теста ---

    def tick(self, seconds) -> None:
        if (threading.current_thread() is not threading.main_thread()
                or self.in_step or not self.supervising):
            # Пауза кода пульта вне шага сценария — только уступка потоку.
            time.sleep(0)
            return
        self.ticks += 1
        self.sleeps.append((seconds, self.epic_has_open_tasks()))
        if self.ticks > self.limit:
            self.error = self.error or AssertionError(
                self.msg(f"сценарий не закончился за {self.limit} пауз надзора"))
            raise StopScenario()
        if self.stopper is not None and self.stopper.is_alive():
            with self.cond:
                self.cond.wait_for(lambda: self.pending or not self.stopper.is_alive(),
                                   timeout=0.05)
        self.deliver()
        self.in_step = True
        try:
            self.start_children()
            next(self.script)
        except StopIteration:
            raise StopScenario() from None
        except StopScenario:
            raise
        except BaseException as exc:
            self.error = self.error or exc
            raise StopScenario() from None
        finally:
            self.in_step = False

    def supervise(self, script, limit: int = 200) -> None:
        """Надзор последнего запуска `auto --epic` — до конца сценария или своего выхода."""
        launches = self.supervisor_launches()
        if not launches:
            self.fail("надзирающий процесс не запускался")
        launch = launches[-1]
        self.sup, self.sup_dead = launch.stand, False
        self.script, self.ticks, self.limit = script, 0, limit
        self.error, self.exit = None, None
        self.run_from = self.top_step()
        saved = {sig: signal.getsignal(sig) for sig in STOPPING_SIGNALS}
        self.supervising = True
        try:
            with patch_pult_sleep(self.tick):
                run_command_line(launch.argv)
            self.exit = "сам"
        except StopScenario:
            self.exit = "сценарий"
        except SupervisorKilled:
            self.exit = "сигнал"
        except SystemExit:
            self.exit = "сам"
        finally:
            self.supervising = False
            for sig, handler in saved.items():
                signal.signal(sig, handler)
            self.sup.kill()
            if self.stopper is not None:
                self.stopper.join(timeout=60)
        if self.error is not None:
            raise self.error

    def wait_until(self, predicate, what: str, limit: int = 40):
        for _ in range(limit):
            if predicate():
                return
            yield
        if not predicate():
            self.fail(f"не дождались за {limit} пауз надзора: {what}")

    def never(self, predicate, what: str, count: int = IDLE):
        for _ in range(count):
            if predicate():
                self.fail(what)
            yield
        if predicate():
            self.fail(what)

    def forever(self):
        while True:
            yield

    def first_launch(self, task: str):
        yield from self.wait_until(lambda: self.count(task) >= 1, f"первый запуск {task}")

    def relaunched(self, task: str, what: str, limit: int = 1):
        """Ещё один запуск задачи не позже `limit` опросов."""
        before = self.count(task)
        yield from self.wait_until(lambda: self.count(task) > before, what, limit)

    def held(self, task: str, what: str, count: int = IDLE):
        """Нового запуска задачи нет `count` опросов."""
        before = self.count(task)
        yield from self.never(lambda: self.count(task) > before, what, count)

    # --- остановки дочернего `auto` ---

    def child_stops(self, task: str, detail: str, *,
                    action: str | None = zone_lock.AUTO_STOPPED_ACTION,
                    before: tuple = ()) -> None:
        conn = store.db()
        for act, det, actor in before:
            store.journal(conn, task, actor, act, det)
        if action is not None:
            store.journal(conn, task, "operator", action, detail)
        self.child_exits(task)

    def child_exits(self, task: str) -> None:
        """Процесс дочернего выходит, сняв lease задачи (если взял его)."""
        conn = store.db()
        row = store.lease_row(conn, task)
        if row is not None and row["session_id"].startswith("дочерний-"):
            store.release_lease(conn, task, row["session_id"])
        self.children(task)[-1].stand.kill()

    def stop_with(self, task: str, reason: str, before: tuple = ()) -> None:
        """Штатная остановка цикла с причиной `reason` и выход дочернего."""
        self.child_stops(task, f"{self.state(task)}: {reason}", before=before)

    def stop_by_command(self, task: str) -> None:
        """`stop <id>`: SIGTERM дочернему, тот дописывает остановку и выходит."""
        self.ok("stop", task)
        self.children(task)[-1].stand.finish()
        self.stop_with(task, STOP_COMMAND_REASON)

    def stop_by_pause(self, task: str) -> None:
        self.ok("pause", task)
        self.stop_with(task, config.AUTO_STOP_PAUSE[0],
                       before=((pause.REFUSAL_ACTION, "задача на паузе", "fsm"),))

    def crash(self, task: str, kind: str) -> None:
        """Аварийный выход дочернего вида `kind` (требование 4: а, б, в)."""
        if kind == "нет старта":
            self.children(task)[-1].stand.kill()
        elif kind == "нет остановки":
            self.children(task)[-1].stand.kill()
        else:
            self.child_stops(task, "RuntimeError: обрыв цикла",
                             action=zone_lock.CYCLE_ABORTED_ACTION)

    def prepare_crashes(self, task: str, kind: str) -> None:
        """Дочерние задачи для аварии «нет старта» — немые."""
        if kind == "нет старта":
            self.mute.add(task)

    def crash_and_relaunch(self, task: str, kind: str):
        """Авария; на опросе, заметившем выход, запуска нет; затем перезапуск."""
        before = self.count(task)
        self.crash(task, kind)
        yield
        if self.count(task) > before:
            self.fail(f"задача {task} перезапущена на опросе, заметившем аварию «{kind}»")
        yield from self.wait_until(lambda: self.count(task) > before,
                                   f"перезапуск {task} после аварии «{kind}»",
                                   RELAUNCH_POLLS)

    def third_crash(self, task: str, kind: str, seen: dict, count: int = IDLE):
        """Третья авария подряд: метки начала для записей и тревог, затем запусков нет."""
        before = self.count(task)
        self.crash(task, kind)
        seen["since"], seen["alert_from"] = self.top_step(), self.top_alert()
        yield from self.never(lambda: self.count(task) > before,
                              f"запуск {task} после трёх аварий подряд «{kind}»", count)

    # --- зоны ---

    def zone(self) -> str:
        return f"zona{self.rng.randrange(1 << 24):x}/modul.py"

    def zone_of(self, task: str) -> str:
        return store.get_task(store.db(), task)["zones"]

    def holder(self, zone: str) -> str:
        """Задача вне эпика, уже занявшая зону шагом разработчика."""
        return self.task(epic=False, started=True, zone=zone)

    def waits_zone(self, task: str, holder: str) -> None:
        """Цикл дочернего вошёл в ожидание зоны (вход без закрытия)."""
        store.journal(store.db(), task, "operator",
                      zone_lock.wait_enter_action(self.zone_of(task), holder,
                                                  self.state(holder)), "")

    def zone_freed_for(self, task: str, holder: str) -> None:
        """Цикл дочернего вышел из ожидания: зона свободна, шаг продолжается."""
        conn = store.db()
        store.journal(conn, task, "operator", zone_lock.wait_exit_action(holder, 1), "")
        store.journal(conn, task, "developer", ROLE_STEP_STARTED, "попытка 1/3")

    def zone_stop(self, task: str, holder: str, kind: str) -> None:
        """Остановка цикла в ожидании зоны: потолок, потеря lease, `stop`, пауза."""
        if kind == "stop":
            self.ok("stop", task)
            self.children(task)[-1].stand.finish()
            reason = STOP_COMMAND_REASON
        elif kind == "пауза":
            self.ok("pause", task)
            reason = config.AUTO_STOP_PAUSE[0]
        elif kind == "потолок":
            reason = ZONE_CEILING_REASON
        else:
            reason = (f"{ZONE_LEASE_LOST_REASON}: [{task}] задачу ведёт сессия "
                      f"чужая-{self.seed:x} с host {socket.gethostname()}")
        store.journal(store.db(), task, "operator",
                      zone_lock.wait_interrupted_action(reason, 0, holder), "")
        self.stop_with(task, reason)

    def release_zone(self, kind: str, holder: str, waiting: list) -> None:
        if kind == "окончательное":
            self.set_state(holder, "done", actor="operator")
        elif kind == "вне BLOCKING_STATES":
            self.set_state(holder, "spec_writing", actor="operator")
        elif kind == "zone-release":
            for task in waiting:
                self.ok("zone-release", task)
        else:
            self.set_state(holder, "awaiting_human")

    # --- действия Оператора записью журнала ---

    def operator_record(self, task: str, action: str, detail: str = "") -> None:
        store.journal(store.db(), task, "operator", action, detail)

    def answer_record(self, task: str) -> None:
        self.operator_record(task, f"ANSWER создан (мандат на ослабление тестов: "
                                   f"tests/test_{self.rng.randrange(1 << 20):x}.py)",
                             f"ANSWER-{self.rng.randrange(1, 9)}.md")

    def zones_extend_record(self, task: str) -> None:
        self.operator_record(task, f"ANSWER создан (мандат на расширение зон: "
                                   f"orchestrator/m{self.rng.randrange(1 << 20):x}.py)",
                             f"ANSWER-{self.rng.randrange(1, 9)}.md")

    # --- `epic stop` при живом надзоре ---

    def stop_epic_concurrently(self) -> None:
        def run():
            try:
                importlib.import_module("orchestrator.epics").cmd_epic(["stop", self.epic])
                self.stop_result = None
            except SystemExit as exc:
                self.stop_result = None if exc.code in (None, 0) else exc.code
            except BaseException as exc:
                self.stop_result = repr(exc)
            finally:
                with self.cond:
                    self.cond.notify_all()

        self.stopper = threading.Thread(target=run, daemon=True)
        self.stopper.start()

    # --- дозор ---

    def watch_once(self, obs: str) -> str:
        buf = io.StringIO()

        def stop(_seconds):
            raise WatchDone()

        with patch_sleep(watch, stop), redirect_stdout(buf), redirect_stderr(buf):
            try:
                watch.cmd_watch(["--observation", obs])
            except WatchDone:
                pass
        return buf.getvalue()

    def close(self) -> None:
        if self.stopper is not None:
            self.stopper.join(timeout=60)
        for stand in self.stands:
            stand.kill()
        self.stack.close()


@pytest.fixture
def pult(initialized_tmp_root):
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    world = Pult(seed, initialized_tmp_root.root)
    env = {"ARTEL_SESSION_ID": world.session, config.ARTEL_ROLE_ENV: "",
           "CODEX_SANDBOX": "", "CODEX_SANDBOX_NETWORK_DISABLED": ""}
    with ExitStack() as stack:
        stack.enter_context(mock.patch.dict(os.environ, env))
        stack.enter_context(mock.patch.object(subprocess, "Popen", world.popen))
        stack.enter_context(mock.patch.object(os, "kill", world.kill))
        stack.enter_context(mock.patch.object(os, "killpg", world.killpg))
        stack.enter_context(mock.patch.object(os, "getpid", world.getpid))
        stack.enter_context(mock.patch.object(config, "MAX_PARALLEL_TASKS", 8))
        stack.callback(world.close)
        yield world


def single_task(pult, *, state: str = "in_dev", started: bool = False) -> str:
    pult.new_epic()
    task = pult.task(state, started=started)
    pult.observation([task])
    return task


def holds_false_project(pult) -> str:
    """Проект с `policy.awaiting_holds_zones: false` в локальном слое записей."""
    name = f"bezzon{pult.seed % 100000}"
    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(
        f"targets:\n  {name}:\n"
        f"    description:\n      base: {config.MAIN_BRANCH}\n"
        f"      test_profile:\n        command: [python3, -m, pytest]\n"
        f"        long_lived_dir: tests\n"
        f"        long_lived_name: test_<id>_<name>.py\n"
        f"    policy:\n      no_paths: []\n      project_skills: []\n"
        f"      merge_gate: operator\n"
        f"      weakening_scope: [tests/**/*.py]\n"
        f"      mutation_claim_scope: [tests/test_*.py]\n"
        f"      awaiting_holds_zones: false\n"
        f"    machine:\n      forge: github\n"
        f"      url: https://localhost/team/{name}\n"
        f"      token_slot: {name}-token\n", encoding="utf-8")
    return name


def is_operator_action_name(action: str) -> bool:
    return action in OPERATOR_ACTIONS or action.startswith(OPERATOR_PREFIXES)


def check_limit(pult, task: str, seen: dict) -> None:
    """Предел аварий: одна тревога `attention` по задаче, одна запись предела с именем вне перечня."""
    assert "since" in seen, pult.msg("сценарий не дошёл до третьей аварии")
    alerts_after = pult.task_alerts(task, seen["alert_from"])
    assert len(alerts_after) == 1, pult.msg(
        f"тревог attention по {task} после предела: {[dict(a) for a in alerts_after]}")
    notes = pult.limit_records(task, seen["since"])
    assert len(notes) == 1, pult.msg(
        f"записей предела аварий по {task}: {[(r['action'], r['detail']) for r in notes]}")
    assert not is_operator_action_name(notes[0]["action"]), pult.msg(
        f"имя записи предела совпало с действием Оператора: {notes[0]['action']!r}")


# ===== AC-1: перезапуск по действию Оператора =====


@pytest.mark.parametrize("action", ["approve", "reject", "budget", "answer", "zones-extend",
                                    "amend-tests", "ci-rerun", "resume снявший паузу"])
def test_ac1_operator_action_after_exit_relaunches_next_poll(pult, action):
    """Действие Оператора после остановки и выхода дочернего — перезапуск на следующем опросе.

    Сценарий: дочерний единственной задачи останавливается так, как
    остановил бы цикл перед этим действием (лимит шагов; «CI ветки
    красный» в `verifying` для `reject`/`ci-rerun`; пауза для `resume`), и
    выходит; три опроса перезапуска нет. Затем Оператор пишет действие
    (`approve` — после эскалации задачи) — на следующем же опросе надзор
    запускает задаче второй дочерний `auto`, без `epic retry`.

    Ловит мутацию: действие выпало из перечня `_operator_actions` (задача
    не перезапускается); либо перезапуск по действию отложен якорем аварии
    на опрос позже; либо новое действие ищется до записи остановки.
    """
    task = single_task(pult)
    pult.start()

    def script():
        yield from pult.first_launch(task)
        yield
        if action in ("reject", "ci-rerun"):
            pult.set_state(task, "verifying")
            pult.stop_with(task, f"{config.AUTO_STOP_VERIFYING_RED[0]} — CI коммита "
                                 f"aaaaaaaa не зелёный")
        elif action == "resume снявший паузу":
            pult.stop_by_pause(task)
        else:
            pult.stop_with(task, STEP_LIMIT_REASON)
        yield from pult.held(task, f"перезапуск до действия «{action}»", 3)
        if action == "approve":
            pult.set_state(task, "escalated")
            yield
            pult.set_state(task, "in_dev", actor="operator")
        elif action == "reject":
            pult.set_state(task, "in_dev", actor="operator")
        elif action == "budget":
            pult.operator_record(task, "бюджет изменён", "1000.0 -> 1500.0")
        elif action == "answer":
            pult.answer_record(task)
        elif action == "zones-extend":
            pult.zones_extend_record(task)
        elif action == "amend-tests":
            pult.operator_record(task, amend.AMEND_ACTION, "правка теста по мандату")
        elif action == "ci-rerun":
            pult.operator_record(task, ci_rerun.CI_RERUN_ACTION, "повтор джобов")
        else:
            pult.ok("resume", task)
        yield from pult.relaunched(task, f"перезапуск на следующем опросе после «{action}»")

    pult.supervise(script())
    assert pult.count(task) == 2, pult.msg(f"запусков {pult.count(task)}")


def test_ac1_resume_while_child_alive_after_pause_stop_relaunches(pult):
    """`resume`, снявший паузу, записан при живом дочернем, остановленном паузой, — перезапуск после выхода.

    Сценарий: `pause` задачи, цикл дочернего пишет остановку паузой, но
    процесс ещё жив; опрос; Оператор зовёт `resume`, процесс ещё жив;
    опрос; процесс выходит — надзор запускает второй дочерний на
    следующем опросе, без `epic retry`.

    Ловит мутацию: действие Оператора засчитывается, только если записано
    после обнаружения выхода (`resume` раньше выхода не открывает
    перезапуск — нужен `epic retry`); либо надзор пишет запись потери
    дочернего поверх записи остановки и считает от неё.
    """
    task = single_task(pult)
    pult.start()

    def script():
        yield from pult.first_launch(task)
        yield
        pult.ok("pause", task)
        conn = store.db()
        store.journal(conn, task, "fsm", pause.REFUSAL_ACTION, "задача на паузе")
        store.journal(conn, task, "operator", zone_lock.AUTO_STOPPED_ACTION,
                      f"in_dev: {config.AUTO_STOP_PAUSE[0]}")
        yield
        pult.ok("resume", task)
        yield
        if pult.count(task) != 1:
            pult.fail("второй дочерний при живом первом")
        pult.child_exits(task)
        yield from pult.relaunched(task, "перезапуск после выхода дочернего")

    pult.supervise(script())


def test_ac1_pause_resume_while_alive_then_step_limit_holds(pult):
    """`pause`, `resume` при живом дочернем, затем остановка лимитом шагов — перезапуска нет.

    Сценарий: `pause` и `resume` задачи, пока её дочерний жив и цикл ещё
    не останавливался; затем цикл останавливается лимитом шагов (первая
    запись остановки — не пауза) и выходит; за `IDLE` пауз надзор задачу
    не перезапускает.

    Ловит мутацию: `resume`, записанный при живом дочернем, засчитывается
    без сверки первой записи остановки (перезапуск после лимита шагов); либо
    засчитывается любая запись `pause`/`resume` до остановки.
    """
    task = single_task(pult)
    pult.start()

    def script():
        yield from pult.first_launch(task)
        yield
        pult.ok("pause", task)
        yield
        pult.ok("resume", task)
        yield
        pult.stop_with(task, STEP_LIMIT_REASON)
        yield from pult.held(task, "перезапуск после остановки лимитом шагов")

    pult.supervise(script())
    assert pult.exit == "сценарий", pult.msg(f"надзор завершился: {pult.exit}")


# ===== AC-2: `resume` после `stop` =====


def test_ac2_resume_after_stop_records_and_relaunches(pult):
    """`resume` задачи не на паузе после `stop` пишет запись актора `operator` и перезапускает её.

    Сценарий: `stop` задачи — дочерний получает SIGTERM, дописывает
    остановку командой `stop` и выходит; три опроса перезапуска нет.
    `resume` (задача не на паузе) добавляет в журнал задачи запись актора
    `operator`, и надзор на следующем опросе запускает второй дочерний.

    Ловит мутацию: `resume` без паузы по-прежнему журнала не пишет
    (записи нет, перезапуска нет); либо последняя остановка берётся не по
    записи остановки цикла после старта, а по иному признаку, — запись не
    появляется.
    """
    task = single_task(pult)
    pult.start()
    seen = {}

    def script():
        yield from pult.first_launch(task)
        yield
        pult.stop_by_command(task)
        yield from pult.held(task, "перезапуск после stop до resume", 3)
        since = pult.top_step()
        pult.ok("resume", task)
        seen["records"] = [(r["actor"], r["action"]) for r in pult.records(task, since)]
        yield from pult.relaunched(task, "перезапуск после resume")

    pult.supervise(script())
    assert any(actor == "operator" for actor, _ in seen.get("records", [])), pult.msg(
        f"resume после stop не записал журнал актором operator: {seen}")
    assert not pult.paused(task), pult.msg("задача на паузе")


# ===== AC-3: аварийный выход и предел аварий =====


@pytest.mark.parametrize("kind", ["нет старта", "нет остановки", "цикл оборван"])
def test_ac3_crash_relaunched_not_on_noticing_poll(pult, kind):
    """Аварийный выход каждого вида: на опросе, заметившем выход, запуска нет; затем перезапуск.

    Сценарий: дочерний задачи гибнет: до записи старта цикла; после
    старта без записи остановки; с первой записью остановки «цикл
    оборван» без именованного отказа. Следующий опрос (заметивший выход)
    второго дочернего не запускает; не позже `RELAUNCH_POLLS` опросов
    после него задача перезапущена без действий Оператора.

    Ловит мутацию: аварийный выход держит задачу до `epic retry`, как
    раньше (перезапуска нет); либо перезапуск на том же опросе, что
    заметил выход (нет паузы между аварией и запуском); либо вид (а) без
    записи старта не распознан аварией.
    """
    task = single_task(pult)
    pult.prepare_crashes(task, kind)
    pult.start()

    def script():
        yield from pult.first_launch(task)
        yield
        yield from pult.crash_and_relaunch(task, kind)

    pult.supervise(script())


def test_ac3_three_crashes_stop_relaunch_alert_once(pult):
    """Три аварии подряд: четвёртого запуска нет, одна тревога `attention` и одна запись предела.

    Сценарий (вид аварии — от зерна): три аварии подряд, после первых двух
    задача перезапускается сама; после третьей за `IDLE` пауз запуска нет;
    за эти паузы заведена ровно одна тревога `attention` по задаче и
    ровно одна новая запись журнала (предел аварий), её имя не совпадает
    ни с одним действием и не начинается ни с одного префикса
    `_operator_actions`.

    Ловит мутацию: счёт аварий не ведётся (перезапуски без предела); либо
    тревога и запись повторяются на каждом опросе; либо запись предела
    названа «pause…»/«resume»/«state -> …» и сама снимает удержание.
    """
    kind = pult.rng.choice(CRASH_KINDS)
    task = single_task(pult)
    pult.prepare_crashes(task, kind)
    pult.start()
    seen = {}

    def script():
        yield from pult.first_launch(task)
        yield
        yield from pult.crash_and_relaunch(task, kind)
        yield
        yield from pult.crash_and_relaunch(task, kind)
        yield
        yield from pult.third_crash(task, kind, seen)

    pult.supervise(script())
    check_limit(pult, task, seen)


def test_ac3_state_change_between_crashes_does_not_reset(pult):
    """Смена состояния задачи между авариями счёт не сбрасывает: третья авария — предел.

    Сценарий: авария, задача (переходом `fsm`) уходит в `review`, авария,
    задача возвращается в `in_dev`, третья авария — четвёртого запуска за
    `IDLE` пауз нет, тревога `attention` по задаче открыта.

    Ловит мутацию: счёт аварий сбрасывается любой записью `state -> …`
    (после смены состояния серия начинается заново, четвёртый запуск есть).
    """
    kind = pult.rng.choice(("нет остановки", "цикл оборван"))
    task = single_task(pult)
    pult.start()
    seen = {}

    def script():
        yield from pult.first_launch(task)
        yield
        yield from pult.crash_and_relaunch(task, kind)
        pult.set_state(task, "review")
        yield
        yield from pult.crash_and_relaunch(task, kind)
        pult.set_state(task, "in_dev")
        yield
        yield from pult.third_crash(task, kind, seen)

    pult.supervise(script())
    check_limit(pult, task, seen)


@pytest.mark.parametrize("action", ["epic retry", "answer", "approve", "reject", "amend-tests",
                                    "resume снявший паузу", "resume после stop"])
def test_ac3_reset_action_lifts_limit_and_resets_count(pult, action):
    """Действие из перечня сброса после предела снова запускает задачу, и две аварии подряд перезапуски не останавливают.

    Сценарий: три аварии подряд — предел (для «resume после stop» серии
    предшествуют `stop`, `resume` и аварии до записи старта цикла, так что
    последняя остановка цикла — остановка командой `stop`). Действие
    Оператора по задаче — задача снова запущена; затем ещё две аварии, и
    после каждой задача снова запущена.

    Ловит мутацию: действие не входит в перечень сброса (после предела
    задача не запускается); либо предел снят, а счёт не сброшен (после
    первой же новой аварии — снова предел, третьего запуска после действия
    нет).
    """
    kind = "нет старта" if action == "resume после stop" else pult.rng.choice(CRASH_KINDS)
    task = single_task(pult)
    if action != "resume после stop":
        pult.prepare_crashes(task, kind)
    pult.start()
    seen = {}

    def script():
        yield from pult.first_launch(task)
        yield
        if action == "resume после stop":
            pult.stop_by_command(task)
            yield from pult.held(task, "перезапуск после stop", 2)
            pult.mute.add(task)
            pult.ok("resume", task)
            yield from pult.relaunched(task, "перезапуск после resume")
            yield
        yield from pult.crash_and_relaunch(task, kind)
        yield
        yield from pult.crash_and_relaunch(task, kind)
        yield
        yield from pult.third_crash(task, kind, seen, count=3)
        if action == "epic retry":
            pult.ok("epic", "retry", pult.epic, task)
        elif action == "answer":
            pult.answer_record(task)
        elif action == "approve":
            pult.set_state(task, "escalated")
            yield
            pult.set_state(task, "in_dev", actor="operator")
        elif action == "reject":
            pult.set_state(task, "acceptance")
            yield
            pult.set_state(task, "in_dev", actor="operator")
        elif action == "amend-tests":
            pult.operator_record(task, amend.AMEND_ACTION, "правка теста по мандату")
        elif action == "resume снявший паузу":
            pult.ok("pause", task)
            yield
            pult.ok("resume", task)
        else:
            pult.ok("resume", task)
        yield from pult.relaunched(task, f"запуск после предела и «{action}»", RELAUNCH_POLLS)
        yield
        yield from pult.crash_and_relaunch(task, kind)
        yield
        yield from pult.crash_and_relaunch(task, kind)

    pult.supervise(script())


@pytest.mark.parametrize("action", ["budget", "zones-extend"])
def test_ac3_budget_or_zones_extend_does_not_lift_limit(pult, action):
    """После предела аварий `budget` или `zones-extend` задачу не запускают.

    Сценарий: три аварии подряд — предел; Оператор пишет «бюджет изменён»
    либо «ANSWER создан (мандат на расширение зон: …)»; за `IDLE` пауз
    задача не запущена.

    Ловит мутацию: предел аварий снимается всем перечнем
    `_operator_actions`, а не только перечнем сброса (после `budget` или
    `zones-extend` задача снова запущена).
    """
    kind = pult.rng.choice(CRASH_KINDS)
    task = single_task(pult)
    pult.prepare_crashes(task, kind)
    pult.start()
    seen = {}

    def script():
        yield from pult.first_launch(task)
        yield
        yield from pult.crash_and_relaunch(task, kind)
        yield
        yield from pult.crash_and_relaunch(task, kind)
        yield
        yield from pult.third_crash(task, kind, seen, count=2)
        if action == "budget":
            pult.operator_record(task, "бюджет изменён", "1000.0 -> 1500.0")
        else:
            pult.zones_extend_record(task)
        yield from pult.held(task, f"запуск после предела и «{action}»")

    pult.supervise(script())


def test_ac3_supervisor_restart_keeps_crash_count(pult):
    """Две аварии под одним надзором, третья под перезапущенным — предел: запуска нет, тревога открыта.

    Сценарий: две аварии подряд, задача перезапущена; процесс надзора
    заканчивается, `auto --epic` запускает новый; третья авария подряд —
    за `IDLE` пауз нового надзора четвёртого запуска нет, тревога
    `attention` по задаче открыта.

    Ловит мутацию: счёт аварий хранится в памяти процесса надзора (новый
    надзор начинает серию с нуля и перезапускает задачу).
    """
    kind = pult.rng.choice(CRASH_KINDS)
    task = single_task(pult)
    pult.prepare_crashes(task, kind)
    pult.start()
    seen = {}

    def first():
        yield from pult.first_launch(task)
        yield
        yield from pult.crash_and_relaunch(task, kind)
        yield
        yield from pult.crash_and_relaunch(task, kind)

    pult.supervise(first())
    pult.start()

    def second():
        yield
        yield from pult.third_crash(task, kind, seen)

    pult.supervise(second())
    check_limit(pult, task, seen)


def test_ac3_bare_resume_after_crash_does_not_reset(pult):
    """Голый `resume` задачи не на паузе после аварии счёт не сбрасывает.

    Сценарий: две аварии подряд «нет остановки»; `resume` задачи не на
    паузе — записи журнала актора `operator` не появилось; третья авария —
    четвёртого запуска за `IDLE` пауз нет, тревога открыта.

    Ловит мутацию: `resume` без паузы после аварии пишет журнал (и
    сбрасывает счёт — четвёртый запуск есть); либо счёт сбрасывается
    любым вызовом `resume`.
    """
    kind = "нет остановки"
    task = single_task(pult)
    pult.start()
    seen = {}

    def script():
        yield from pult.first_launch(task)
        yield
        yield from pult.crash_and_relaunch(task, kind)
        yield
        yield from pult.crash_and_relaunch(task, kind)
        yield
        since = pult.top_step()
        pult.ok("resume", task)
        seen["resume"] = [(r["actor"], r["action"]) for r in pult.records(task, since)]
        yield from pult.third_crash(task, kind, seen)

    pult.supervise(script())
    assert seen.get("resume") == [], pult.msg(f"голый resume записал журнал: {seen.get('resume')}")
    check_limit(pult, task, seen)


def test_ac3_stop_resume_then_three_crashes_then_bare_resume_holds(pult):
    """`stop`, `resume`, перезапуск с новым стартом, три аварии «нет остановки», голый `resume` — запуска нет.

    Сценарий: `stop` задачи, `resume` (запись есть), задача перезапущена
    и её цикл записал новый старт; затем три аварии вида (б) подряд —
    предел; голый `resume` задачи не на паузе: записи журнала нет, за
    `IDLE` пауз задача не запущена.

    Ловит мутацию: «последняя остановка цикла» ищется по всему журналу, а
    не после последней записи старта (давняя остановка `stop` открывает
    запись `resume` и сброс счёта — задача снова запущена).
    """
    kind = "нет остановки"
    task = single_task(pult)
    pult.start()
    seen = {}

    def script():
        yield from pult.first_launch(task)
        yield
        pult.stop_by_command(task)
        yield from pult.held(task, "перезапуск после stop", 2)
        pult.ok("resume", task)
        yield from pult.relaunched(task, "перезапуск после resume")
        yield
        yield from pult.crash_and_relaunch(task, kind)
        yield
        yield from pult.crash_and_relaunch(task, kind)
        yield
        yield from pult.third_crash(task, kind, seen, count=2)
        since = pult.top_step()
        pult.ok("resume", task)
        seen["resume"] = [(r["actor"], r["action"]) for r in pult.records(task, since)]
        yield from pult.held(task, "запуск после голого resume при пределе")

    pult.supervise(script())
    assert seen.get("resume") == [], pult.msg(f"голый resume записал журнал: {seen.get('resume')}")


def test_ac3_ci_red_and_ci_rerun_do_not_break_crash_series(pult):
    """Авария, штатная остановка «CI ветки красный», `ci-rerun`, ещё две аварии — три подряд, предел.

    Сценарий: авария, задача перезапущена; задача в `verifying`, цикл
    останавливается «CI ветки красный»; `ci-rerun` — задача запущена; ещё
    две аварии — после второй из них четвёртого запуска за `IDLE` пауз
    нет, тревога `attention` по задаче открыта.

    Ловит мутацию: штатная остановка или действие вне перечня сброса
    (`ci-rerun`) обрывают серию аварий — после двух новых аварий задача
    снова запущена.
    """
    kind = pult.rng.choice(("нет остановки", "цикл оборван"))
    task = single_task(pult, started=True)
    pult.start()
    seen = {}

    def script():
        yield from pult.first_launch(task)
        yield
        yield from pult.crash_and_relaunch(task, kind)
        yield
        pult.set_state(task, "verifying")
        pult.stop_with(task, f"{config.AUTO_STOP_VERIFYING_RED[0]} — CI коммита "
                             f"aaaaaaaa не зелёный")
        yield from pult.held(task, "перезапуск после красного CI", 2)
        pult.operator_record(task, ci_rerun.CI_RERUN_ACTION, "повтор джобов")
        yield from pult.relaunched(task, "запуск после ci-rerun")
        yield
        yield from pult.crash_and_relaunch(task, kind)
        yield
        yield from pult.third_crash(task, kind, seen)

    pult.supervise(script())
    check_limit(pult, task, seen)


# ===== AC-4: прочие остановки держат задачу =====


@pytest.mark.parametrize("reason", ["run отказался стартовать", "стоп-кран волны",
                                    "конверт эпика", "start_after", "лимит шагов",
                                    "CI ветки красный", "бюджет", "stop без resume",
                                    "потолок ожидания зоны", "потеря lease в ожидании"])
def test_ac4_other_stops_hold_task(pult, reason):
    """Остановка цикла по причине вне перечня — задача за `IDLE` пауз не перезапущена.

    Сценарий: дочерний единственной задачи останавливается с записью
    причины так, как её оставляет цикл (отказ `run` стартовать не по
    глобальному лимиту, стоп-кран волны, конверт эпика, `start_after`,
    лимит шагов, «CI ветки красный» в `verifying`, бюджет в `escalated`,
    `stop`, потолок ожидания зоны и потеря lease в ожидании при занятой
    зоне), и выходит; действий Оператора нет — за `IDLE` пауз второго
    дочернего нет.

    Ловит мутацию: новая ветка перезапуска срабатывает на любом выходе
    дочернего после записи остановки (задача перезапущена без действия
    Оператора); либо остановка ожидания зоны снимается без освобождения
    зоны.
    """
    pult.new_epic()
    zone = pult.zone()
    holder = pult.holder(zone)
    task = pult.task(zone=zone if reason.startswith(("потолок", "потеря")) else None)
    pult.observation([task])
    pult.start()

    def script():
        yield from pult.first_launch(task)
        yield
        if reason == "run отказался стартовать":
            pult.stop_with(task, "run отказался стартовать")
        elif reason == "стоп-кран волны":
            pult.stop_with(task, config.AUTO_STOP_WAVE_BREAKER[0],
                           before=((runner.WAVE_BREAKER_REFUSAL_ACTION, "алерт волны", "fsm"),))
        elif reason == "конверт эпика":
            pult.stop_with(task, "исчерпан конверт эпика — первый шаг роли не начат",
                           before=((runner.ENVELOPE_REFUSAL_ACTION, "конверт", "fsm"),))
        elif reason == "start_after":
            pult.stop_with(task, "зависимость запуска start_after не в done",
                           before=((runner.START_AFTER_REFUSAL_ACTION, "start_after", "fsm"),))
        elif reason == "лимит шагов":
            pult.stop_with(task, STEP_LIMIT_REASON)
        elif reason == "CI ветки красный":
            pult.set_state(task, "verifying")
            pult.stop_with(task, f"{config.AUTO_STOP_VERIFYING_RED[0]} — CI коммита "
                                 f"aaaaaaaa не зелёный")
        elif reason == "бюджет":
            pult.set_state(task, "escalated")
            pult.stop_with(task, config.AUTO_STOP_BUDGET[0])
        elif reason == "stop без resume":
            pult.stop_by_command(task)
        else:
            pult.waits_zone(task, holder)
            yield
            pult.zone_stop(task, holder, "потолок" if reason.startswith("потолок")
                           else "потеря lease")
        yield from pult.held(task, f"перезапуск после остановки «{reason}»")

    pult.supervise(script())
    assert pult.count(task) == 1, pult.msg(f"запусков {pult.count(task)}")


def run_auto_in_process(task: str) -> str:
    """`auto <id>` этой командой процесса (обработчик SIGTERM восстанавливается)."""
    saved = signal.getsignal(signal.SIGTERM)
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            try:
                auto.cmd_auto(task)
            except SystemExit as exc:
                buf.write(f"\n{exc}")
    finally:
        signal.signal(signal.SIGTERM, saved)
    return buf.getvalue()


@pytest.mark.parametrize("refusal", ["отказ lease самого auto", "неподдержанный проект"])
def test_ac4_named_child_refusal_holds_and_not_counted(pult, refusal):
    """Штатный отказ дочернего после двух аварий: задача держится, тревоги предела нет.

    Сценарий: две аварии «нет старта» подряд, задача перезапущена; третий
    дочерний отказывает: «отказ lease самого auto» — lease задачи держит
    другая живая сессия, и настоящий `auto <id>` этой задачи отказывает
    (в журнале задачи появляется именованная запись отказа; затем чужой
    lease снят); «неподдержанный проект» — запись
    `runner.UNSUPPORTED_PROJECT_ACTION`, затем «цикл оборван» с
    «SystemExit: …». Дочерний выходит; за `IDLE` пауз задача не запущена,
    тревоги `attention` по задаче нет (отказ в счёт аварий не пошёл). Для
    отказа lease — у записей, которые `auto` оставил, имя не совпадает ни
    с одним действием и не начинается ни с одного префикса
    `_operator_actions`.

    Ловит мутацию: отказ lease `auto` по-прежнему только печатается (записи
    нет — выход принят за аварию «нет старта», третья подряд: тревога
    предела); либо отказ неподдержанного проекта не распознан и «цикл
    оборван» считается аварией; либо после именованного отказа задача
    перезапущена без действия Оператора.
    """
    task = single_task(pult)
    pult.prepare_crashes(task, "нет старта")
    pult.start()
    seen = {}

    def script():
        yield from pult.first_launch(task)
        yield
        yield from pult.crash_and_relaunch(task, "нет старта")
        yield
        yield from pult.crash_and_relaunch(task, "нет старта")
        since = pult.top_step()
        if refusal == "отказ lease самого auto":
            foreign = pult.foreign_auto(task)
            seen["out"] = run_auto_in_process(task)
            seen["named"] = [(r["actor"], r["action"]) for r in pult.records(task, since)]
            pult.children(task)[-1].stand.kill()
            pult.release_foreign(task, foreign)
        else:
            conn = store.db()
            store.journal(conn, task, "operator", runner.UNSUPPORTED_PROJECT_ACTION,
                          f"auto: проект {pult.project}: хостинг не поддержан")
            pult.child_stops(task, f"SystemExit: [{task}] auto отклонён: проект "
                                   f"{pult.project}: хостинг не поддержан",
                             action=zone_lock.CYCLE_ABORTED_ACTION)
        seen["alert_from"] = pult.top_alert()
        yield from pult.held(task, f"перезапуск после «{refusal}»")

    pult.supervise(script())
    assert "alert_from" in seen, pult.msg("сценарий не дошёл до отказа")
    assert pult.task_alerts(task, seen["alert_from"]) == [], pult.msg(
        f"«{refusal}» засчитан аварией: тревога предела по {task}")
    if refusal == "отказ lease самого auto":
        assert seen["named"], pult.msg(f"отказ lease auto не оставил записи:\n{seen['out']}")
        named = [action for _, action in seen["named"] if is_operator_action_name(action)]
        assert named == [], pult.msg(f"запись отказа lease названа действием Оператора: {named}")


# ===== AC-5: `pause --now` =====


def test_ac5_pause_now_exit_not_relaunched_not_counted(pult):
    """Выход после `pause --now` после двух аварий: задача не запущена, тревоги предела нет.

    Сценарий: две аварии «нет остановки» подряд, задача перезапущена;
    `pause --now` прерывает процесс третьего дочернего (запись «pause
    --now: процесс агента прерван», пометка паузы); за `IDLE` пауз запуска
    нет, задача на паузе, тревоги `attention` по задаче нет.

    Ловит мутацию: выход после `pause --now` (SIGKILL без записи
    остановки) считается аварией — третья подряд, тревога предела; либо
    задача на паузе перезапускается по правилу аварии.
    """
    task = single_task(pult)
    pult.start()
    seen = {}

    def script():
        yield from pult.first_launch(task)
        yield
        yield from pult.crash_and_relaunch(task, "нет остановки")
        yield
        yield from pult.crash_and_relaunch(task, "нет остановки")
        yield
        seen["alert_from"] = pult.top_alert()
        pult.ok("pause", "--now", task)
        pult.children(task)[-1].stand.kill()
        yield from pult.held(task, "перезапуск после pause --now")

    pult.supervise(script())
    assert "alert_from" in seen, pult.msg("сценарий не дошёл до pause --now")
    assert pult.paused(task), pult.msg("задача не на паузе")
    assert pult.task_alerts(task, seen["alert_from"]) == [], pult.msg(
        "выход после pause --now засчитан аварией: тревога предела")


def test_ac5_resume_before_exit_noticed_relaunches_next_poll(pult):
    """`pause --now`, затем `resume` раньше, чем надзор заметил выход, — перезапуск на следующем опросе.

    Сценарий: `pause --now` прерывает процесс дочернего, тем же шагом
    сценария Оператор зовёт `resume` (пауза снята); первый же опрос после
    выхода запускает второй дочерний, без `epic retry`.

    Ловит мутацию: выход после `pause --now` считается аварией (якорь
    аварии откладывает запуск на опрос позже); либо надзор пишет запись
    потери дочернего позже `resume` и держит задачу до `epic retry`.
    """
    task = single_task(pult)
    pult.start()

    def script():
        yield from pult.first_launch(task)
        yield
        pult.ok("pause", "--now", task)
        pult.children(task)[-1].stand.kill()
        pult.ok("resume", task)
        yield from pult.relaunched(task, "перезапуск после pause --now и resume")

    pult.supervise(script())
    assert not pult.paused(task), pult.msg("задача на паузе")


# ===== AC-6: гейт, пауза и эскалация не перезапускаются =====


@pytest.mark.parametrize("exit_kind", ["остановка", "аварийный выход"])
@pytest.mark.parametrize("where", ["spec_gate", "acceptance", "merge_gate", "пауза", "escalated"])
def test_ac6_gate_pause_escalated_not_relaunched_no_gate_transition(pult, where, exit_kind):
    """Задача на гейте, на паузе или в `escalated` не перезапускается ни после остановки, ни после аварии; переходов гейта надзор не пишет.

    Сценарий: задача уходит на гейт (`spec_gate`, `acceptance`,
    `merge_gate`), на паузу или в `escalated`; дочерний либо штатно
    останавливается там, либо гибнет без записи остановки. За `IDLE` пауз
    запуска нет, `fsm.cmd_approve`/`fsm.cmd_reject` не вызваны, записей
    `state -> …` автора надзора нет, состояние прежнее.

    Ловит мутацию: правило перезапуска после аварии не сверяет гейт, паузу
    и эскалацию (задача на гейте перезапущена); либо надзор сам проходит
    гейт (`approve`).
    """
    approve = mock.Mock(side_effect=AssertionError("approve из надзора"))
    reject = mock.Mock(side_effect=AssertionError("reject из надзора"))
    pult.stack.enter_context(mock.patch.object(fsm, "cmd_approve", approve))
    pult.stack.enter_context(mock.patch.object(fsm, "cmd_reject", reject))
    task = single_task(pult)
    pult.start()
    state = "in_dev" if where == "пауза" else where

    def script():
        yield from pult.first_launch(task)
        yield
        if where == "пауза":
            pult.ok("pause", task)
        else:
            pult.set_state(task, where)
        if exit_kind == "аварийный выход":
            pult.crash(task, "нет остановки")
        elif where == "пауза":
            pult.stop_with(task, config.AUTO_STOP_PAUSE[0],
                           before=((pause.REFUSAL_ACTION, "задача на паузе", "fsm"),))
        else:
            pult.stop_with(task, "ждёт Оператора")
        yield from pult.held(task, f"перезапуск задачи «{where}» после «{exit_kind}»")

    pult.supervise(script())
    assert approve.call_count == 0 and reject.call_count == 0, pult.msg("надзор позвал approve/reject")
    by_supervisor = [r["action"] for r in pult.records(task)
                     if r["actor"] == store.EPIC_SUPERVISOR_ACTOR
                     and r["action"].startswith("state -> ")]
    assert by_supervisor == [], pult.msg(f"переходы от надзора: {by_supervisor}")
    assert pult.state(task) == state, pult.msg(f"состояние {pult.state(task)}")


# ===== AC-7: снятое ожидание зоны =====


@pytest.mark.parametrize("stop", ["потолок", "потеря lease"])
@pytest.mark.parametrize("release", ["окончательное", "вне BLOCKING_STATES", "zone-release",
                                     "awaiting_human"])
def test_ac7_released_zone_wait_relaunches_next_poll(pult, release, stop):
    """Ожидание зоны снято — задача, остановленная потолком ожидания или потерей lease, запущена на следующем опросе.

    Сценарий: зону задачи эпика держит задача вне эпика (шаг разработчика
    начат); цикл дочернего входит в ожидание и останавливается (`stop`);
    три опроса перезапуска нет. Ожидание снимается (`release`): держатель
    в `done`; держатель вернулся в `spec_writing`; `zone-release` задачи;
    держатель в `awaiting_human` проекта с `awaiting_holds_zones: false`.
    На следующем опросе надзор запускает второй дочерний, без `epic retry`.

    Ловит мутацию: остановка ожидания зоны держит задачу до действия
    Оператора и после освобождения (перезапуска нет); либо освобождение
    проверяется только по окончательному состоянию держателя (выход из
    `BLOCKING_STATES`, `zone-release`, `awaiting_human` не замечены).
    """
    project = holds_false_project(pult) if release == "awaiting_human" else None
    pult.new_epic(project=project)
    zone = pult.zone()
    holder = pult.holder(zone)
    task = pult.task(zone=zone)
    pult.observation([task])
    pult.start()

    def script():
        yield from pult.first_launch(task)
        yield
        pult.waits_zone(task, holder)
        yield
        pult.zone_stop(task, holder, stop)
        yield from pult.held(task, "перезапуск при занятой зоне", 3)
        pult.release_zone(release, holder, [task])
        yield from pult.relaunched(task, f"перезапуск после «{release}»")

    pult.supervise(script())


def two_waiting(pult, *, first_outside: bool = False) -> tuple:
    """(первая по `queue_order`, вторая, держатель): две задачи одной зоны,
    порядок очереди обратен порядку эпика; `epic parallel 2`."""
    pult.new_epic()
    zone = pult.zone()
    holder = pult.holder(zone)
    second = pult.task(zone=zone)
    first = pult.task(zone=zone, epic=not first_outside)
    pult.ok("zone-reorder", first, second)
    pult.ok("epic", "parallel", pult.epic, "2")
    pult.observation([second] if first_outside else [second, first])
    return first, second, holder


def test_ac7_queue_order_first_relaunched_second_after_it(pult):
    """Две задачи одной зоны, обе остановлены потолком: первой запущена первая по `queue_order`, вторая — после неё.

    Сценарий: порядок `queue_order` обратен порядку эпика; держатель
    уходит в `done`. На следующем опросе запущена первая по очереди, вторая
    — нет; первая занимает зону (шаг разработчика) — вторая не запущена;
    первая уходит в `done` — вторая запущена.

    Ловит мутацию: перезапуск из снятого ожидания — в порядке эпика
    (`view.ready`), а не `queue_order` (первой запущена вторая); либо обе
    запущены сразу.
    """
    first, second, holder = two_waiting(pult)
    pult.start()

    def script():
        yield from pult.wait_until(lambda: pult.count(first) and pult.count(second),
                                   "запуск обеих")
        yield
        pult.waits_zone(first, holder)
        pult.waits_zone(second, holder)
        yield
        pult.zone_stop(first, holder, "потолок")
        pult.zone_stop(second, holder, "потолок")
        yield from pult.never(lambda: pult.count(first) > 1 or pult.count(second) > 1,
                              "перезапуск при занятой зоне", 3)
        pult.set_state(holder, "done", actor="operator")
        yield from pult.relaunched(first, "перезапуск первой по queue_order")
        if pult.count(second) > 1:
            pult.fail("вторая запущена вместе с первой")
        yield
        yield from pult.held(second, "вторая запущена до занятия зоны первой", 3)
        store.journal(store.db(), first, "developer", ROLE_STEP_STARTED, "попытка 1/3")
        yield from pult.held(second, "вторая запущена, пока зону держит первая", 3)
        pult.set_state(first, "done")
        pult.stop_with(first, "задача слита")
        yield from pult.relaunched(second, "перезапуск второй после первой", RELAUNCH_POLLS)

    pult.supervise(script())


@pytest.mark.parametrize("variant", ["stop", "пауза"])
def test_ac7_first_stopped_or_paused_skipped_next_relaunched(pult, variant):
    """Первая по `queue_order` остановлена в ожидании `stop` или паузой: она не запущена, следующая запущена.

    Сценарий: первая по очереди задача эпика остановлена в ожидании
    командой `stop` (или паузой), вторая — потолком ожидания; держатель
    уходит в `done`. На следующем опросе запущена вторая; первая за `IDLE`
    пауз не запущена.

    Ловит мутацию: задача, остановленная `stop`/паузой, держит очередь
    (вторая не запускается); либо остановка `stop`/паузой в ожидании
    снимается освобождением зоны (первая запущена).
    """
    first, second, holder = two_waiting(pult)
    pult.start()

    def script():
        yield from pult.wait_until(lambda: pult.count(first) and pult.count(second),
                                   "запуск обеих")
        yield
        pult.waits_zone(first, holder)
        pult.waits_zone(second, holder)
        yield
        pult.zone_stop(first, holder, variant)
        pult.zone_stop(second, holder, "потолок")
        yield from pult.held(second, "перезапуск при занятой зоне", 3)
        pult.set_state(holder, "done", actor="operator")
        yield from pult.relaunched(second, "запуск следующей по queue_order")
        yield from pult.held(first, f"запущена задача, остановленная «{variant}»")

    pult.supervise(script())


@pytest.mark.parametrize("variant", ["вне эпика", "предел аварий"])
def test_ac7_first_outside_epic_or_crash_limited_skipped(pult, variant):
    """Первая по `queue_order` — задача вне эпика или задача эпика на пределе аварий: следующая задача эпика запущена.

    Сценарий: «вне эпика» — первая по очереди задача не из эпика, её цикл
    остановлен потолком ожидания; «предел аварий» — первая по очереди
    задача эпика после трёх аварий подряд. Вторая (задача эпика)
    остановлена потолком ожидания; держатель уходит в `done` — на
    следующем опросе вторая запущена, первая за `IDLE` пауз — нет.

    Ловит мутацию: очередь для задачи эпика держит любая задача впереди
    по `queue_order` (вторая не запускается); либо надзор запускает задачу
    вне эпика или задачу на пределе аварий.
    """
    first, second, holder = two_waiting(pult, first_outside=variant == "вне эпика")
    kind = pult.rng.choice(("нет остановки", "цикл оборван"))
    pult.start()

    def script():
        yield from pult.wait_until(lambda: pult.count(second) and (
            variant == "вне эпика" or pult.count(first)), "запуск задач эпика")
        yield
        pult.waits_zone(second, holder)
        if variant == "вне эпика":
            conn = store.db()
            store.journal(conn, first, "operator", zone_lock.AUTO_START_ACTION,
                          "состояние in_dev, сценарий")
            pult.waits_zone(first, holder)
            store.journal(conn, first, "operator", zone_lock.wait_interrupted_action(
                ZONE_CEILING_REASON, 0, holder), "")
            store.journal(conn, first, "operator", zone_lock.AUTO_STOPPED_ACTION,
                          f"in_dev: {ZONE_CEILING_REASON}")
        yield
        pult.zone_stop(second, holder, "потолок")
        if variant == "предел аварий":
            yield
            yield from pult.crash_and_relaunch(first, kind)
            yield
            yield from pult.crash_and_relaunch(first, kind)
            yield
            yield from pult.third_crash(first, kind, {}, count=2)
        yield from pult.held(second, "перезапуск при занятой зоне", 2)
        pult.set_state(holder, "done", actor="operator")
        yield from pult.relaunched(second, f"запуск задачи эпика за «{variant}»")
        yield from pult.held(first, f"запущена первая по очереди («{variant}»)")

    pult.supervise(script())
    if variant == "вне эпика":
        assert first not in pult.launched(), pult.msg("надзор запустил задачу вне эпика")


# ===== AC-8 … AC-10: места `parallel` =====


def no_second_child_no_lost(pult, tasks: list) -> None:
    for task in tasks:
        assert pult.count(task) == 1, pult.msg(f"задаче {task} запусков {pult.count(task)}")
        assert pult.lost_records(task) == [], pult.msg(
            f"по живому ждущему {task} записана потеря дочернего")


def test_ac8_children_waiting_zone_free_parallel_places(pult):
    """Два живых дочерних ждут зону, `parallel` 2 — третья готовая задача запущена.

    Сценарий: зону задач A и B держит задача вне эпика; надзор запускает A
    и B (`epic parallel 2`), их циклы входят в ожидание зоны; надзор
    запускает третью задачу C. Задачам A и B второго дочернего нет, записи
    потери дочернего по ним нет.

    Ловит мутацию: живой дочерний, ждущий зону, занимает место `parallel`
    (C не запускается); либо ждущему дочернему запускается второй `auto`
    или пишется «дочерний auto вышел без записи об остановке».
    """
    pult.new_epic()
    zone = pult.zone()
    holder = pult.holder(zone)
    a, b, c = pult.task(zone=zone), pult.task(zone=zone), pult.task()
    pult.ok("epic", "parallel", pult.epic, "2")
    pult.observation([a, b, c])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: pult.count(a) and pult.count(b), "запуск A и B")
        yield
        if c in pult.launched():
            pult.fail("C запущена до ожидания A и B")
        pult.waits_zone(a, holder)
        pult.waits_zone(b, holder)
        yield from pult.wait_until(lambda: c in pult.launched(), "запуск C", 2)
        yield from pult.never(lambda: pult.count(a) > 1 or pult.count(b) > 1,
                              "второй дочерний ждущей задаче")

    pult.supervise(script())
    no_second_child_no_lost(pult, [a, b])


def test_ac8_restart_from_wait_only_into_free_place(pult):
    """`parallel` 1: снятое ожидание не запускает задачу, пока место занято шагом другой; после выхода — запускает.

    Сценарий: задача B ждёт зону под живым дочерним — надзор запускает A
    (место свободно); A ведёт шаг; цикл B останавливается потолком
    ожидания, держатель зоны уходит в `done`. Пока дочерний A жив, B не
    запущена; A останавливается на гейте и выходит — B запущена.

    Ловит мутацию: перезапуск из снятого ожидания идёт мимо счёта мест
    `_epic_view` (B запущена рядом с A); либо идущий шаг живого дочернего
    места не занимает.
    """
    pult.new_epic()
    zone = pult.zone()
    holder = pult.holder(zone)
    b, a = pult.task(zone=zone), pult.task()
    pult.ok("epic", "parallel", pult.epic, "1")
    pult.observation([b, a])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: pult.count(b), "запуск B")
        yield
        pult.waits_zone(b, holder)
        yield from pult.wait_until(lambda: pult.count(a), "запуск A при ждущей B", 2)
        yield
        store.journal(store.db(), a, "developer", ROLE_STEP_STARTED, "попытка 1/3")
        pult.zone_stop(b, holder, "потолок")
        pult.set_state(holder, "done", actor="operator")
        yield from pult.held(b, "B запущена при занятом месте", 4)
        pult.set_state(a, "spec_gate")
        pult.stop_with(a, "ждёт Оператора")
        yield from pult.relaunched(b, "запуск B на освободившееся место", 2)

    pult.supervise(script())


def test_ac8_waited_children_continue_and_no_new_launch_without_place(pult):
    """Ждавшие зону дочерние продолжили шаг — пока `view.free` ≤ 0, новых запусков нет.

    Сценарий (`epic parallel 2`): A и B под живыми дочерними ждут зону,
    надзор запускает C. Зона освобождается: циклы A и B выходят из
    ожидания и продолжают шаг; C останавливается на гейте; задача D
    становится готовой (Оператор прошёл её гейт). Шаг ведут два живых
    дочерних при лимите 2 — за `IDLE` пауз D не запущена. Задачам A и B
    второго дочернего нет, записи потери дочернего по ним нет.

    Ловит мутацию: дочерний, ждавший зону, и после выхода из ожидания не
    занимает места (D запущена); либо надзор запускает ему второй `auto`.
    """
    pult.new_epic()
    zone = pult.zone()
    holder = pult.holder(zone)
    a, b, c = pult.task(zone=zone), pult.task(zone=zone), pult.task()
    d = pult.task("spec_gate")
    pult.ok("epic", "parallel", pult.epic, "2")
    pult.observation([a, b, c, d])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: pult.count(a) and pult.count(b), "запуск A и B")
        yield
        pult.waits_zone(a, holder)
        pult.waits_zone(b, holder)
        yield from pult.wait_until(lambda: c in pult.launched(), "запуск C", 2)
        yield
        pult.set_state(holder, "done", actor="operator")
        pult.zone_freed_for(a, holder)
        pult.zone_freed_for(b, holder)
        pult.set_state(c, "acceptance")
        pult.stop_with(c, "ждёт Оператора")
        pult.set_state(d, "tests_writing", actor="operator")
        yield from pult.never(lambda: d in pult.launched(), "D запущена при view.free ≤ 0")

    pult.supervise(script())
    no_second_child_no_lost(pult, [a, b])


def test_ac9_child_waiting_ci_frees_place_until_ci_green(pult):
    """Живой дочерний ждёт CI в `verifying`, `parallel` 1 — вторая запущена; после зелёного CI третья не запущена.

    Сценарий: задача A в `verifying` (шаг роли завершён) под живым
    дочерним — надзор запускает B; CI A зелёный: A переходит в `review`,
    её дочерний продолжает шаг; B останавливается на гейте и выходит.
    Место занято шагом A — за `IDLE` пауз третья готовая задача C не
    запущена.

    Ловит мутацию: живой дочерний в `verifying` занимает место `parallel`
    (B не запускается); либо ждавший CI дочерний и после зелёного CI места
    не занимает (C запущена).
    """
    pult.new_epic()
    a = pult.task("verifying", started=True)
    store.journal(store.db(), a, "developer", ROLE_STEP_FINISHED, "rc=0")
    b, c = pult.task(), pult.task()
    pult.ok("epic", "parallel", pult.epic, "1")
    pult.observation([a, b, c])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: pult.count(a), "запуск A")
        yield from pult.wait_until(lambda: pult.count(b), "запуск B при A, ждущей CI", 3)
        if c in pult.launched():
            pult.fail("C запущена рядом с B")
        yield
        pult.set_state(a, "review")
        pult.set_state(b, "spec_gate")
        pult.stop_with(b, "ждёт Оператора")
        yield from pult.never(lambda: c in pult.launched(), "C запущена при view.free ≤ 0")

    pult.supervise(script())
    assert pult.count(a) == 1, pult.msg(f"задаче A запусков {pult.count(a)}")


def test_ac10_waiting_children_leases_take_global_places(pult):
    """Глобальный лимит 2, два живых дочерних ждут зону, `parallel` 3 — третья не запущена.

    Сценарий: потолок пульта подменён на 2; A и B под живыми дочерними
    (их lease живы) ждут зону; `epic parallel 3`. За `IDLE` пауз третья
    готовая задача C не запущена.

    Ловит мутацию: ждущая зону задача выпадает и из глобальной оценки мест
    (живой lease ждущей задачи не считается — C запущена третьей при
    потолке 2).
    """
    pult.global_limit(2)
    pult.new_epic()
    zone = pult.zone()
    holder = pult.holder(zone)
    a, b, c = pult.task(zone=zone), pult.task(zone=zone), pult.task()
    pult.ok("epic", "parallel", pult.epic, "3")
    pult.observation([a, b, c])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: pult.count(a) and pult.count(b), "запуск A и B")
        yield
        pult.waits_zone(a, holder)
        pult.waits_zone(b, holder)
        yield from pult.never(lambda: c in pult.launched(),
                              "C запущена сверх глобального лимита")

    pult.supervise(script())
    no_second_child_no_lost(pult, [a, b])


# ===== AC-11, AC-12: завершение надзора =====


def end_records(pult) -> list:
    return [r for r in pult.records(pult.epic)
            if r["action"] == auto.EPIC_SUPERVISOR_END_ACTION]


def test_ac11_open_epic_with_final_tasks_keeps_supervising(pult):
    """Открытый эпик, все задачи окончательны: надзор жив, опрос раз в 5 минут; новая задача запущена; `epic stop` завершает.

    Сценарий: эпик из задачи в `done` и задачи в `killed`. За `IDLE` пауз
    надзор не завершился, запусков нет, записи «надзор эпика завершён» и
    тревоги по эпику нет, каждая пауза — 300 секунд. Затем в эпике
    заводится новая задача — надзор запускает её, паузы при
    неокончательной задаче — `EPIC_POLL_SEC`. `epic stop` — надзор
    завершён.

    Ловит мутацию: надзор открытого эпика завершается сам, когда все задачи
    окончательны (как раньше); либо период ожидания новых задач —
    `EPIC_POLL_SEC` или период не возвращается к `EPIC_POLL_SEC` при
    неокончательной задаче; либо новая задача открытого эпика не
    подхватывается.
    """
    pult.new_epic()
    done, _killed = pult.task("done"), pult.task("killed")
    pult.observation([done])
    pult.start()
    seen = {}

    def script():
        for _ in range(IDLE):
            yield
        seen["idle"] = list(pult.sleeps)
        seen["ended"] = end_records(pult)
        seen["alerts"] = pult.epic_alerts()
        seen["launched"] = pult.launched()
        new = pult.task()
        yield from pult.wait_until(lambda: new in pult.launched(), "запуск новой задачи эпика")
        mark = len(pult.sleeps)
        yield
        yield
        seen["busy"] = pult.sleeps[mark:]
        pult.stop_epic_concurrently()
        yield from pult.forever()

    pult.supervise(script())
    assert "idle" in seen, pult.msg(f"надзор завершился, не дождавшись новых задач: {pult.exit}")
    assert seen["launched"] == [], pult.msg(f"запуски: {seen['launched']}")
    assert seen["ended"] == [], pult.msg("записана «надзор эпика завершён»")
    assert seen["alerts"] == [], pult.msg("тревога по эпику")
    assert len(seen["idle"]) >= IDLE and all(s == (IDLE_POLL_SEC, False) for s in seen["idle"]), \
        pult.msg(f"паузы без неокончательных задач: {seen['idle']}")
    assert seen["busy"] and all(s == (auto.EPIC_POLL_SEC, True) for s in seen["busy"]), \
        pult.msg(f"паузы при неокончательной задаче: {seen['busy']}")
    assert pult.exit in ("сам", "сигнал"), pult.msg(f"надзор не завершён epic stop: {pult.exit}")


def test_ac12_closed_epic_supervisor_ends_with_record_and_alert(pult):
    """`epic close`: надзор завершается сам с записью «надзор эпика завершён» и тревогой; `watch` доставляет их.

    Сценарий: эпик из окончательных задач, надзор жив; Оператор закрывает
    эпик `epic close`. Надзор завершается сам после закрытия: запись
    «надзор эпика завершён» позже записи закрытия, тревога `attention` по
    эпику; одна итерация `watch --observation` выводит строку
    `alert:attention` с id эпика и строку журнала с id эпика.

    Ловит мутацию: закрытие эпика не завершает надзор (надзор жив до
    предела пауз); либо завершение без записи журнала или без тревоги;
    либо надзор завершился раньше закрытия (запись завершения раньше).
    """
    pult.new_epic()
    done, _killed = pult.task("done"), pult.task("killed")
    obs = pult.observation([done])
    pult.start()
    seen = {}

    def script():
        yield
        yield
        seen["since"] = pult.top_step()
        pult.ok("epic", "close", pult.epic, "итог сценария")
        yield from pult.forever()

    pult.supervise(script(), limit=IDLE * 3)
    assert "since" in seen, pult.msg("надзор завершился до закрытия эпика")
    assert pult.exit == "сам", pult.msg(f"надзор не завершился сам: {pult.exit}")
    ended = [r for r in end_records(pult) if r["id"] > seen["since"]]
    assert ended, pult.msg("нет записи «надзор эпика завершён» после закрытия")
    assert pult.epic_alerts(), pult.msg("нет тревоги attention по эпику")
    lines = [ln for ln in pult.watch_once(obs).splitlines() if pult.epic in ln]
    assert any("alert:attention" in ln for ln in lines), pult.msg(
        f"нет алерта attention по эпику в watch: {lines}")
    assert any("alert:" not in ln for ln in lines), pult.msg(
        f"нет записи журнала эпика в watch: {lines}")
