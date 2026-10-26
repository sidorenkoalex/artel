"""Надзирающий процесс эпика `auto --epic`: запуск дочерних `auto`, лимиты, гейты, остановки, `epic parallel|stop|retry`, наблюдение и самостоятельное завершение (AC-1 … AC-33).

Группа: долгоживущий
Красен до реализации: команды `auto --epic`, подкоманд `epic parallel|stop|retry` и таблицы `epic_supervisors` ещё нет — `epic parallel|stop|retry` отказывают «epic: нужна подкоманда», `auto --epic` не порождает надзирающий процесс, чтение `epic_supervisors` падает «no such table» (на базе ветки без Э1 — уже `epic new`: «Неизвестная команда epic»).

Провалидировано временным стабом реализации поверх main с Э1 и Э2а (надзор,
`epic parallel|stop|retry`, таблица блокировки, доставка `watch`; удалён, не
закоммичен): все методы файла зелёные на шести прогонах с разными зёрнами;
33 правдоподобные мутации стаба, названные в заявках, красят свои тесты.

Связка, которую держит файл: команда CLI (`artel.main` с `sys.argv`) — БД
пульта (`tasks`, `steps`, `leases`, `epics`, `epic_supervisors`,
`observations`, `alerts`) — порождение отвязанных процессов
(`subprocess.Popen`) — сигналы процессам (`os.kill`/`os.killpg`) — дозор
`watch`.

Как разыгрывается надзор (шов теста — то, чем пульт уже отвязывает
процессы: `subprocess.Popen` с командной строкой `artel.py`):

- Запуск процесса пульта (команда с `artel.py` или `-m orchestrator…`) не
  исполняется: вместо него порождается настоящий процесс-заместитель —
  питон, который ждёт сигнала; на SIGTERM/SIGINT/SIGHUP он пишет имя
  сигнала в файл-метку и выходит сам, SIGKILL его убивает без метки.
  Прочие команды (`git`, `ps`) уходят в настоящий `Popen`.
- Запуск, в командной строке которого есть id задачи эпика и `auto`, —
  дочерний `auto`. Его заместитель на ближайшей паузе надзора ведёт себя
  как стартовавший цикл: берёт lease задачи своим pid и пишет
  `zone_lock.AUTO_START_ACTION`. Остановки дочернего `auto` сценарий
  разыгрывает так, как их оставляет настоящий цикл: записи журнала
  (`AUTO_STOPPED_ACTION`, `CYCLE_ABORTED_ACTION`, отказ лимита
  параллельных задач), снятие lease и выход процесса.
- Запуск с id эпика — надзирающий процесс: его pid — pid заместителя.
  Сам надзор исполняется в процессе теста той же командной строкой,
  которую получил `Popen` (`artel.main`), пока заместитель жив;
  `os.getpid()` в коде надзора отвечает pid заместителя. Пауза надзора
  (`time.sleep` модулей пульта, `tests.sandbox.patch_pult_sleep`) — шаг
  сценария. Сигнал, адресованный pid надзора, доставляется обработчику,
  который надзор поставил (`signal.getsignal`), на ближайшей паузе — как
  ОС доставила бы его во сне; без обработчика надзор кончается, как от
  действия по умолчанию. Конец надзора — заместитель убит.
- `epic stop` при живом надзоре идёт отдельным потоком (в жизни — другой
  процесс); пауза надзора в это время — короткое ожидание события.
- Состояние задачи меняется прямой записью `tasks.state` с записью
  журнала «state -> …» — так его оставили бы шаг роли и `approve`; гейты
  и мерж в песочнице не разыгрываются.
- Время старта процесса — настоящее (`ps`); AC-33 подменяет
  `process_start_time` (фасад `doctor` и модуль `stale_cycles` — адрес,
  названный SPEC) для одного pid.

Идентификаторы задач и эпика, проект, число задач и лимиты сценариев
порождаются модулем `random` при каждом запуске; зерно печатается и входит
в текст провала.
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

from orchestrator import artel, config, doctor, fsm, pause, store, watch, zone_lock
from tests.sandbox import declare_target, patch_pult_sleep, patch_sleep

# Модуль, а не одноимённая функция фасада `doctor.stale_cycles`.
stale_cycles = importlib.import_module("orchestrator.doctor.stale_cycles")

REAL_POPEN = subprocess.Popen
REAL_KILL = os.kill
REAL_KILLPG = os.killpg
REAL_GETPID = os.getpid
ULID = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
# Маркер первого шага роли (SPEC Э2а, требование 6) и отказ `run` по
# глобальному лимиту (`runner.py`) — литералы журнала, названные SPEC.
ROLE_STEP_STARTED = "agent run started"
LIMIT_REFUSAL_ACTION = "run отклонён: лимит параллельных задач"
STOPPING_SIGNALS = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
NOW_FORMAT = "%Y-%m-%d %H:%M:%SZ"  # формат `store.now()`
IDLE = 8  # пауз надзора на «ничего не происходит»

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

    def caught(self) -> str | None:
        return self.mark.read_text() if self.mark.exists() else None

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
    snapshot: dict
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
        self.stop_from = 0
        self.stop_kill_from = 0
        self.error = None
        self.exit = None
        self.ticks = 0
        self.limit = 0
        self.script = None
        self.delivered_at = None
        self.ended_at = 0
        self.run_from = 0

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

    def refused(self, *argv: str) -> str:
        code, out = self.cli(*argv)
        if code is None:
            self.fail(f"`{' '.join(argv)}` не отказала:\n{out}")
        return f"{code}\n{out}"

    def global_limit(self, value: int) -> None:
        self.stack.enter_context(mock.patch.object(config, "MAX_PARALLEL_TASKS", value))

    # --- эпик, задачи, наблюдения ---

    def new_epic(self, envelope: float | None = None, project: str | None = None) -> str:
        if project is not None:
            self.project = project
        title = f"Эпик {self.seed:x}-{self.rng.randrange(1 << 30):x}"
        extra = ["--envelope", str(envelope)] if envelope is not None else []
        self.ok("epic", "new", self.project, title, "--goal", "Цель сценария", *extra)
        row = store.db().execute("SELECT id FROM epics WHERE title=?", (title,)).fetchone()
        if row is None:
            self.fail("эпик не заведён")
        self.epic = row["id"]
        return self.epic

    def task(self, state: str = "in_dev", *, epic: bool = True, started: bool = False,
             spent: float | None = None, project: str | None = None) -> str:
        self.counter += 1
        task_id = f"01{self.prefix}{self.counter:04d}"
        conn = store.db()
        store.insert_task(conn, task_id, f"Задача {self.counter}", state,
                          f"task/{task_id.lower()}-epik", project or self.project, 1000.0)
        if epic:
            store.update_task(conn, task_id, epic_id=self.epic)
        if started:
            store.journal(conn, task_id, "developer", ROLE_STEP_STARTED, "попытка 1/3")
        if spent is not None:
            store.update_task(conn, task_id, spent_usd=spent)
        self.task_ids.append(task_id)
        return task_id

    def set_state(self, task: str, state: str, actor: str = "fsm") -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task))
        conn.commit()
        store.journal(conn, task, actor, f"state -> {state}", "")

    def state(self, task: str) -> str:
        return store.db().execute("SELECT state FROM tasks WHERE id=?", (task,)).fetchone()[0]

    def observation(self, tasks: list, *, session: str | None = None,
                    seen_ago: float = 0.0, created_ago: float = 0.0,
                    project: str | None = None) -> str:
        conn = store.db()
        obs = store.register_observation(conn, project or self.project, "", "",
                                         session or self.session, list(tasks))
        now = datetime.now(timezone.utc)
        with conn:
            conn.execute("UPDATE observations SET last_seen_at=?, created_at=? WHERE id=?",
                         ((now - timedelta(seconds=seen_ago)).isoformat(),
                          (now - timedelta(seconds=created_ago)).strftime(NOW_FORMAT), obs))
        return obs

    def make_stale(self, obs: str) -> None:
        moment = datetime.now(timezone.utc) - timedelta(
            seconds=config.OBSERVATION_STALE_SECONDS + 600)
        conn = store.db()
        with conn:
            conn.execute("UPDATE observations SET last_seen_at=? WHERE id=?",
                         (moment.isoformat(), obs))

    def obs_tasks(self, obs: str) -> set:
        return set(store.observation_tasks(store.db(), obs))

    def take_lease(self, task: str, session: str, pid: int) -> None:
        conn = store.db()
        if store.lease_row(conn, task) is None:
            store.insert_lease(conn, task, session, pid, socket.gethostname(), store.now())
        else:
            store.update_lease(conn, task, session, pid, socket.gethostname(), store.now())

    def foreign_auto(self, task: str) -> Stand:
        """`auto <id>`, запущенный не надзором: живой процесс держит lease задачи."""
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

    def records(self, task: str, since: int) -> list:
        return store.db().execute("SELECT * FROM steps WHERE task_id=? AND id>? ORDER BY id",
                                  (task, since)).fetchall()

    def lock_rows(self, epic: str | None = None) -> list:
        return store.db().execute("SELECT * FROM epic_supervisors WHERE epic_id=?",
                                  (epic or self.epic,)).fetchall()

    def plant_lock(self, pid: int, started_at: str) -> None:
        conn = store.db()
        with conn:
            conn.execute("INSERT INTO epic_supervisors (epic_id, pid, host, started_at, "
                         "session_id) VALUES (?, ?, ?, ?, ?)",
                         (self.epic, pid, socket.gethostname(), started_at, self.session))

    def epic_alerts(self) -> list:
        return [row for row in store.open_alerts(store.db(), "attention")
                if row["target"] == self.epic or self.epic in (row["message"] or "")]

    # --- запуски ---

    def supervisor_launches(self) -> list:
        return [l for l in self.launches if l.kind == "надзор"]

    def children(self, task: str | None = None) -> list:
        return [l for l in self.launches
                if l.kind == "дочерний" and (task is None or l.task == task)]

    def launched(self) -> list:
        return [l.task for l in self.children()]

    def live_children(self) -> list:
        return [l for l in self.children() if l.stand.alive()]

    def start(self, *extra: str) -> str:
        before = len(self.supervisor_launches())
        out = self.ok("auto", "--epic", self.epic, *extra)
        if len(self.supervisor_launches()) == before:
            self.fail(f"`auto --epic {self.epic}` не запустил надзирающий процесс:\n{out}")
        return out

    def snapshot(self) -> dict:
        conn = store.db()
        observed: dict = {}
        for row in conn.execute("SELECT observation_id, task_id FROM observation_tasks "
                                "WHERE enabled=1"):
            observed.setdefault(row[0], set()).add(row[1])
        return {"states": {row[0]: row[1] for row in conn.execute("SELECT id, state FROM tasks")},
                "observed": observed}

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
        self.launches.append(Launch(kind, task if kind == "дочерний" else None,
                                    stand, argv, self.snapshot()))
        return stand.popen

    def start_children(self) -> None:
        """Заместители дочерних `auto` стартуют: lease задачи и запись старта цикла."""
        for launch in self.children():
            if launch.started or not launch.stand.alive():
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
            if self.delivered_at is None:
                self.delivered_at = len(self.launches)
            handler = signal.getsignal(sig)
            if callable(handler):
                handler(sig, None)
            elif handler != signal.SIG_IGN:
                raise SupervisorKilled()

    # --- надзор в процессе теста ---

    def tick(self, seconds) -> None:
        if (threading.current_thread() is not threading.main_thread()
                or self.in_step or not self.supervising):
            # Пауза кода пульта вне шага сценария (`epic stop` другим
            # потоком, команда внутри шага) — только уступка потоку.
            time.sleep(0)
            return
        self.ticks += 1
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

    def supervise(self, script, limit: int = 160) -> None:
        """Надзор последнего запуска `auto --epic` — до конца сценария или своего выхода."""
        launches = self.supervisor_launches()
        if not launches:
            self.fail("надзирающий процесс не запускался")
        launch = launches[-1]
        self.sup, self.sup_dead = launch.stand, False
        self.script, self.ticks, self.limit = script, 0, limit
        self.error, self.exit, self.delivered_at = None, None, None
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
            self.ended_at = len(self.kills)
            for sig, handler in saved.items():
                signal.signal(sig, handler)
            self.sup.kill()
            if self.stopper is not None:
                self.stopper.join(timeout=60)
        if self.error is not None:
            raise self.error

    def supervisor_dies(self) -> None:
        """Процесс надзора погибает без уборки (SIGKILL): код надзора больше не исполняется."""
        self.sup_dead = True
        self.sup.kill()

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

    # --- остановки дочернего `auto` ---

    def child_stops(self, task: str, detail: str, *,
                    action: str | None = zone_lock.AUTO_STOPPED_ACTION,
                    before: tuple = ()) -> None:
        conn = store.db()
        for act, det, actor in before:
            store.journal(conn, task, actor, act, det)
        if action is not None:
            store.journal(conn, task, "operator", action, detail)
        row = store.lease_row(conn, task)
        if row is not None:
            store.release_lease(conn, task, row["session_id"])
        self.children(task)[-1].stand.kill()

    def gate_stop(self, task: str, gate: str) -> None:
        self.set_state(task, gate)
        self.child_stops(task, f"{gate}: ручной гейт Оператора")

    def not_on_gate_stop(self, task: str, kind: str) -> None:
        """Остановка не на гейте: «пауза» (с командой `pause`), «лимит шагов»."""
        if kind == "пауза":
            self.ok("pause", task)
            self.child_stops(task, f"{self.state(task)}: {config.AUTO_STOP_PAUSE[0]}",
                             before=((pause.REFUSAL_ACTION, "задача на паузе", "fsm"),))
        else:
            self.child_stops(task, f"{self.state(task)}: лимит шагов за вызов")

    def child_vanishes(self, task: str) -> None:
        self.children(task)[-1].stand.kill()

    def child_refused_by_limit(self, task: str) -> None:
        self.child_stops(task, f"{self.state(task)}: run отказался стартовать",
                         before=((LIMIT_REFUSAL_ACTION,
                                  f"[{task}] лимит параллельных задач достигнут", "fsm"),))

    # --- `epic stop` при живом надзоре ---

    def stop_epic_concurrently(self) -> None:
        self.stop_from = self.top_step()
        self.stop_kill_from = len(self.kills)

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


def ready_epic(pult, count: int, parallel: str | None = None) -> list:
    """Эпик из `count` готовых задач (`in_dev`, без зависимостей) и наблюдение сессии с ними."""
    pult.new_epic()
    tasks = [pult.task() for _ in range(count)]
    if parallel is not None:
        pult.ok("epic", "parallel", pult.epic, parallel)
    pult.observation(tasks)
    return tasks


# ===== Запуск и лимиты =====


def test_ac1_only_first_task_launched_with_parallel_one(pult):
    """Три задачи (вторая — `start_after` первой), `epic parallel 1`: запущена только первая.

    Сценарий: после `auto --epic` надзор запускает дочерний `auto` первой
    задачи; пока он жив, за `IDLE` пауз ни вторая (ждёт `start_after`), ни
    третья (нет места) не запускаются.

    Ловит мутацию: лимит `epic parallel` не читается — третья задача
    запускается рядом с первой; либо `start_after` не проверяется — вторая
    запускается; либо порядок задач не по эпику — первой запускается не
    первая задача.
    """
    pult.new_epic()
    t1, t2, t3 = pult.task(), pult.task(), pult.task()
    pult.ok("epic", "start-after", t2, t1)
    pult.ok("epic", "parallel", pult.epic, "1")
    pult.observation([t1, t2, t3])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: pult.launched() == [t1], "запуск первой задачи")
        yield from pult.never(lambda: pult.launched() != [t1],
                              f"запущено сверх первой задачи: {pult.launched()}")

    pult.supervise(script())
    assert pult.launched() == [t1], pult.msg(f"запуски: {pult.launched()}")


def test_ac2_third_after_place_freed_second_only_after_first_done(pult):
    """Третья задача — после освобождения места первой, вторая — только после `done` первой.

    Сценарий (`epic parallel 1`): дочерний `auto` первой останавливается
    на гейте `acceptance` — место свободно, запускается третья; её дочерний
    останавливается на `spec_gate` — место снова свободно, но вторая за
    `IDLE` пауз не запускается (первая не в `done`); первая переводится в
    `done` — вторая запускается, и в момент её запуска первая в `done`.

    Ловит мутацию: освободившееся место не отдаётся следующей готовой задаче
    (третья не запускается); либо `start_after` считается выполненным при
    первой на гейте (вторая запускается раньше `done` первой); либо
    задача, открывшаяся по `start_after`, не подхватывается после мержа.
    """
    pult.new_epic()
    t1, t2, t3 = pult.task(), pult.task(), pult.task()
    pult.ok("epic", "start-after", t2, t1)
    pult.ok("epic", "parallel", pult.epic, "1")
    pult.observation([t1, t2, t3])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: pult.launched() == [t1], "запуск первой задачи")
        pult.gate_stop(t1, "acceptance")
        yield from pult.wait_until(lambda: t3 in pult.launched(),
                                   "запуск третьей после освобождения места")
        if t2 in pult.launched():
            pult.fail("вторая запущена до done первой")
        pult.gate_stop(t3, "spec_gate")
        yield from pult.never(lambda: t2 in pult.launched(), "вторая запущена до done первой")
        pult.set_state(t1, "done", actor="operator")
        yield from pult.wait_until(lambda: t2 in pult.launched(),
                                   "запуск второй после done первой")

    pult.supervise(script())
    launch = pult.children(t2)[0]
    assert launch.snapshot["states"][t1] == "done", pult.msg(
        f"вторая запущена при первой в {launch.snapshot['states'][t1]}")


@pytest.mark.parametrize("parallel, expected", [("2", 2), (None, 1)])
def test_ac3_live_children_never_exceed_epic_limit(pult, parallel, expected):
    """Живых дочерних `auto` эпика не больше лимита `epic parallel`; без лимита — не больше одного.

    Сценарий: готовых задач больше лимита (от зерна, 3–5), места под
    `MAX_PARALLEL_TASKS` хватает на все. Надзор доходит до `expected`
    живых дочерних и за `IDLE` пауз не превышает их.

    Ловит мутацию: лимит по умолчанию не 1 (без `epic parallel` запущены
    все готовые задачи); либо `epic parallel 2` не сохраняется или не
    читается (живых один либо больше двух); либо проверка лимита по числу
    запусков за итерацию, а не по живым (на следующей итерации запускается
    ещё одна).
    """
    ready_epic(pult, 3 + pult.rng.randrange(3), parallel)
    pult.start()

    def script():
        yield from pult.wait_until(lambda: len(pult.live_children()) >= expected,
                                   f"{expected} живых дочерних")
        yield from pult.never(lambda: len(pult.live_children()) > expected,
                              f"живых дочерних больше {expected}")

    pult.supervise(script())
    assert len(pult.live_children()) == expected, pult.msg(
        f"живых дочерних {len(pult.live_children())}, ждали {expected}")


@pytest.mark.parametrize("bad", ["0", "-1", "два", "3x"])
def test_ac4_invalid_parallel_refused_and_limit_kept(pult, bad):
    """`epic parallel <id> 0|-1|неразборное` — отказ с причиной, прежний лимит 2 действует.

    Сценарий: лимит эпика задан `epic parallel 2`; затем недопустимое
    значение — отказ с непустым текстом; надзор над четырьмя готовыми
    задачами доходит ровно до двух живых дочерних и не превышает их.

    Ловит мутацию: значение принимается без проверки (`0` или `-1`
    сохраняются и снимают лимит — живых больше двух; «два» падает
    исключением, а не отказом); либо отказ всё же переписывает лимит на
    умолчание 1 (живых один).
    """
    ready_epic(pult, 4, "2")
    text = pult.refused("epic", "parallel", pult.epic, bad)
    assert text.strip(), pult.msg("отказ без причины")
    pult.start()

    def script():
        yield from pult.wait_until(lambda: len(pult.live_children()) >= 2, "двух живых дочерних")
        yield from pult.never(lambda: len(pult.live_children()) > 2,
                              f"после отказа {bad!r} живых больше двух")

    pult.supervise(script())
    assert len(pult.live_children()) == 2, pult.msg(
        f"после отказа {bad!r} живых {len(pult.live_children())}")


def test_ac5_foreign_live_leases_take_global_places(pult):
    """Прочие живые lease пульта занимают места `MAX_PARALLEL_TASKS`: дочерних не больше остатка.

    Сценарий (числа от зерна): потолок пульта M (3–5), L (1…M−2) задач вне
    эпика держат живые lease; `epic parallel` выше остатка M−L. Сначала
    готова одна задача эпика — её дочерний запущен и взял lease; затем
    Оператор проходит гейт остальных задач (их больше остатка). Надзор
    доходит до M−L живых дочерних и не превышает их: lease самих дочерних
    в счёт «прочих» не идут.

    Ловит мутацию: надзор не считает чужие lease (живых дочерних до
    лимита эпика); либо считает и lease своих дочерних «прочими» (после
    первого запуска мест на одно меньше — живых M−L−1); либо сверяет с
    потолком только число дочерних.
    """
    pult.new_epic()
    ceiling = 3 + pult.rng.randrange(3)
    others = 1 + pult.rng.randrange(ceiling - 2)
    free = ceiling - others
    parallel = free + 1 + pult.rng.randrange(3)
    pult.global_limit(ceiling)
    first = pult.task()
    gated = [pult.task("spec_gate") for _ in range(parallel)]
    for _ in range(others):
        pult.foreign_auto(pult.task(epic=False))
    pult.ok("epic", "parallel", pult.epic, str(parallel))
    pult.observation([first, *gated])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: pult.launched() == [first], "запуск первой задачи")
        yield from pult.wait_until(lambda: store.lease_row(store.db(), first) is not None,
                                   "lease дочернего первой задачи")
        for task in gated:
            pult.set_state(task, "tests_writing", actor="operator")
        yield from pult.wait_until(lambda: len(pult.live_children()) >= free,
                                   f"{free} живых дочерних")
        yield from pult.never(lambda: len(pult.live_children()) > free,
                              f"живых дочерних больше {free} (потолок {ceiling}, "
                              f"чужих lease {others})")

    pult.supervise(script())
    assert len(pult.live_children()) == free, pult.msg(
        f"живых {len(pult.live_children())}, ждали {free}")


# ===== Блокировка надзора =====


def test_ac6_second_supervisor_refused_with_live_pid(pult):
    """Второй `auto --epic` при живом надзоре — отказ с pid живого процесса, второго надзора нет.

    Сценарий: надзор запущен и жив (задача эпика на гейте); на его паузе
    Оператор зовёт `auto --epic` того же эпика ещё раз. Отказ называет pid
    из строки `epic_supervisors`, это pid живого надзора; нового запуска
    надзирающего процесса нет.

    Ловит мутацию: живость блокировки не проверяется (второй надзор
    запускается); либо отказ без pid; либо блокировка пишется с pid
    команды запуска, а не надзирающего процесса.
    """
    pult.new_epic()
    gate = pult.task("spec_gate")
    pult.observation([gate])
    pult.start()
    seen = {}

    def script():
        yield
        before = len(pult.supervisor_launches())
        seen["text"] = pult.refused("auto", "--epic", pult.epic)
        seen["launches"] = len(pult.supervisor_launches()) - before
        seen["rows"] = [dict(r) for r in pult.lock_rows()]

    pult.supervise(script())
    assert len(seen["rows"]) == 1, pult.msg(f"строки блокировки: {seen['rows']}")
    pid = seen["rows"][0]["pid"]
    assert pid == pult.sup.pid, pult.msg(f"в блокировке pid {pid}, надзор {pult.sup.pid}")
    assert str(pid) in seen["text"], pult.msg(f"нет pid {pid} в отказе: {seen['text']}")
    assert seen["launches"] == 0, pult.msg("второй надзор запущен")


def stale_lock_takeover(pult, lock_pid: int, started_at: str) -> tuple:
    """(записей эпика без блокировки, записей эпика с мёртвой блокировкой) за запуск надзора.

    Два эпика одинакового вида (задача на гейте, наблюдение): у второго до
    запуска в `epic_supervisors` строка с `lock_pid`/`started_at`. Каждый
    раз — `auto --epic` и одна пауза надзора."""
    counts = []
    for planted in (False, True):
        pult.new_epic()
        gate = pult.task("spec_gate")
        pult.observation([gate])
        if planted:
            pult.plant_lock(lock_pid, started_at)
        since = pult.top_step()
        pult.start()

        def script():
            yield

        pult.supervise(script())
        counts.append(len(pult.records(pult.epic, since)))
    return counts[0], counts[1]


def test_ac7_dead_pid_lock_removed_with_record_and_supervisor_started(pult):
    """Блокировка с pid, не живым на этом хосте: `auto --epic` снимает её с записью журнала и запускает надзор.

    Сценарий: два одинаковых эпика, у второго строка `epic_supervisors` с
    pid завершившегося процесса. Надзор второго запущен; строки с мёртвым
    pid не осталось; записей журнала эпика за запуск больше, чем у эпика
    без блокировки (снятие записано).

    Ловит мутацию: мёртвая блокировка принимается за живую (отказ запуска
    — надзор не запущен); либо снимается молча, без записи журнала; либо
    новый надзор запускается, а старая строка остаётся.
    """
    dead = Stand(pult.root)
    dead.kill()
    plain, planted = stale_lock_takeover(pult, dead.pid, store.now())
    rows = [dict(r) for r in pult.lock_rows()]
    assert all(r["pid"] != dead.pid for r in rows), pult.msg(f"мёртвая строка осталась: {rows}")
    assert planted > plain, pult.msg(
        f"снятие мёртвой блокировки не записано: записей {planted} против {plain}")


def test_ac8_lock_of_process_started_later_is_dead(pult):
    """Pid блокировки занят процессом, стартовавшим позже `started_at`: блокировка мёртвая.

    Сценарий 1: два одинаковых эпика, у второго строка `epic_supervisors`
    с pid живого процесса и `started_at` на час раньше его старта —
    `auto --epic` снимает её с записью журнала (записей больше, чем у
    эпика без блокировки) и запускает надзор; строки с этим pid не
    осталось. Сценарий 2: третий эпик с такой же блокировкой — `epic stop`
    не шлёт этому процессу ни одного сигнала, процесс жив, блокировка
    снята.

    Ловит мутацию: живость блокировки — только по pid, без сверки времени
    старта (отказ запуска «надзор жив», `epic stop` шлёт SIGTERM чужому
    процессу); либо `epic stop` при мёртвой блокировке не снимает строку.
    """
    stranger = Stand(pult.root)
    pult.stands.append(stranger)
    hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime(NOW_FORMAT)
    plain, planted = stale_lock_takeover(pult, stranger.pid, hour_ago)
    rows = [dict(r) for r in pult.lock_rows()]
    assert all(r["pid"] != stranger.pid for r in rows), pult.msg(f"строка осталась: {rows}")
    assert planted > plain, pult.msg(f"снятие не записано: записей {planted} против {plain}")

    pult.new_epic()
    pult.task("spec_gate")
    pult.plant_lock(stranger.pid, hour_ago)
    sent_from = len(pult.kills)
    pult.ok("epic", "stop", pult.epic)
    signals = [(pid, sig) for pid, sig in pult.kills[sent_from:]
               if pid == stranger.pid and sig != 0]
    assert signals == [], pult.msg(f"сигналы чужому процессу: {signals}")
    assert stranger.alive(), pult.msg("чужой процесс остановлен")
    assert pult.lock_rows() == [], pult.msg("блокировка не снята")


def test_ac9_supervisor_records_lock_row_and_no_lease(pult):
    """Записи надзора — с id эпика и проектом эпика; блокировка — не lease; в ней сессия запуска.

    Сценарий: эпик проекта вне артели (имя от зерна) с одной задачей;
    дочерний `auto` доводит её до `done`, надзор завершается сам. Каждая
    запись журнала с `task_id` = id эпика, сделанная за надзор, несёт
    `target` = проект эпика (и такие записи есть); пока надзор жив, в
    `leases` нет строки с id эпика или pid надзора, а строка
    `epic_supervisors` несёт `session_id` сессии, звавшей `auto --epic`.

    Ловит мутацию: журнал надзора пишется без `target` (проект пульта по
    умолчанию) или с `task_id` задачи; либо блокировка берётся через
    `lease.acquire` по id эпика; либо `session_id` блокировки — не сессия
    запуска.
    """
    project = f"proekt{pult.seed % 100000}"
    declare_target(project)
    pult.new_epic(project=project)
    task = pult.task()
    pult.observation([task])
    pult.start()
    seen = {}

    def script():
        yield from pult.wait_until(lambda: pult.launched() == [task], "запуск задачи")
        seen["rows"] = [dict(r) for r in pult.lock_rows()]
        seen["leases"] = [dict(r) for r in store.all_leases(store.db())]
        pult.set_state(task, "done")
        pult.child_stops(task, "done: задача слита")
        yield from pult.forever()

    pult.supervise(script())
    assert pult.exit == "сам", pult.msg(f"надзор не завершился сам: {pult.exit}")
    records = pult.records(pult.epic, pult.run_from)
    assert records, pult.msg("за надзор нет записей журнала с id эпика")
    wrong = [(r["action"], r["target"]) for r in records if r["target"] != project]
    assert wrong == [], pult.msg(f"записи эпика не с проектом {project}: {wrong}")
    assert [r["session_id"] for r in seen["rows"]] == [pult.session], pult.msg(
        f"строки блокировки: {seen['rows']}")
    leased = [r for r in seen["leases"] if r["task_id"] == pult.epic or r["pid"] == pult.sup.pid]
    assert leased == [], pult.msg(f"блокировка в leases: {leased}")


# ===== Готовность и гейты =====


def test_ac10_task_with_foreign_live_lease_skipped(pult):
    """Задача эпика с живым lease чужого `auto <id>` не получает дочернего `auto`.

    Сценарий (`epic parallel 2`): у одной задачи живой lease процесса, не
    запущенного надзором; другая свободна. Надзор запускает свободную, а
    задачу под чужим lease за `IDLE` пауз не запускает.

    Ловит мутацию: надзор не сверяет lease задач (дочерний запущен и
    задаче под чужим `auto`); либо считает чужой lease только той же
    сессии.
    """
    pult.new_epic()
    held, free = pult.task(), pult.task()
    pult.foreign_auto(held)
    pult.ok("epic", "parallel", pult.epic, "2")
    pult.observation([held, free])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: free in pult.launched(), "запуск свободной задачи")
        yield from pult.never(lambda: held in pult.launched(), "запущена задача под чужим lease")

    pult.supervise(script())


def test_ac11_spec_gate_task_not_launched_not_approved_supervisor_waits(pult):
    """Задача на `spec_gate`: надзор её не запускает, `approve` не зовёт и не завершается.

    Сценарий: единственная задача эпика на гейте SPEC; за `IDLE` пауз нет
    ни дочернего запуска, ни вызова `fsm.cmd_approve`, состояние прежнее,
    надзор жив до конца сценария.

    Ловит мутацию: гейты не исключены из готовых (дочерний запущен); либо
    надзор проходит гейт сам (`approve`); либо задача на гейте не держит
    надзор, и он завершается сам.
    """
    pult.new_epic()
    gate = pult.task("spec_gate")
    pult.observation([gate])
    approve = mock.Mock(side_effect=AssertionError("approve из надзора"))
    pult.stack.enter_context(mock.patch.object(fsm, "cmd_approve", approve))
    pult.start()

    def script():
        yield from pult.never(lambda: pult.launched(), "запущена задача на гейте")

    pult.supervise(script())
    assert pult.exit == "сценарий", pult.msg(f"надзор завершился при задаче на гейте: {pult.exit}")
    assert approve.call_count == 0, pult.msg("надзор позвал approve")
    assert pult.state(gate) == "spec_gate", pult.msg(f"состояние {pult.state(gate)}")


def test_ac12_gate_stopped_task_relaunched_after_approve(pult):
    """Дочерний `auto` остановился на гейте: после `approve` задача снова запускается.

    Сценарий: дочерний доводит задачу до `spec_gate` и выходит; за `IDLE`
    пауз повторного запуска нет; Оператор проходит гейт (задача в
    `tests_writing`) — надзор запускает задаче второй дочерний `auto`.

    Ловит мутацию: остановка на гейте принимается за остановку не на
    гейте (после `approve` нового действия «по списку» нет — задача не
    перезапускается); либо задача на гейте перезапускается.
    """
    pult.new_epic()
    task = pult.task()
    pult.observation([task])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: len(pult.children(task)) == 1, "первый запуск")
        pult.gate_stop(task, "spec_gate")
        yield from pult.never(lambda: len(pult.children(task)) > 1, "перезапуск на гейте")
        pult.set_state(task, "tests_writing", actor="operator")
        yield from pult.wait_until(lambda: len(pult.children(task)) == 2,
                                   "перезапуск после approve")

    pult.supervise(script())


# ===== Остановки не на гейте =====


def cycle_records(pult, task: str) -> None:
    conn = store.db()
    store.journal(conn, task, "operator", zone_lock.AUTO_START_ACTION, "состояние in_dev")
    store.journal(conn, task, "operator", zone_lock.AUTO_STOPPED_ACTION, "in_dev: сценарий")
    store.journal(conn, task, "operator", zone_lock.CYCLE_ABORTED_ACTION, "RuntimeError: сценарий")


@pytest.mark.parametrize("kind", ["пауза", "лимит шагов"])
def test_ac13_not_on_gate_stop_holds_task_and_supervisor(pult, kind):
    """Остановка не на гейте: задача не перезапускается, надзор жив; записи цикла `auto` перезапуск не открывают.

    Сценарий: дочерний `auto` единственной задачи останавливается
    (`kind`) и выходит; за `IDLE` пауз перезапуска нет; затем по задаче
    пишутся записи цикла `AUTO_START_ACTION`, `AUTO_STOPPED_ACTION`,
    `CYCLE_ABORTED_ACTION` — за следующие `IDLE` пауз перезапуска нет;
    надзор жив до конца сценария.

    Ловит мутацию: выход дочернего не на гейте перезапускает задачу сразу;
    либо записи цикла `auto` (актор «operator») считаются новым действием
    Оператора; либо задача, ждущая Оператора, не держит надзор — он
    завершается сам.
    """
    pult.new_epic()
    task = pult.task()
    pult.observation([task])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: len(pult.children(task)) == 1, "первый запуск")
        pult.not_on_gate_stop(task, kind)
        yield from pult.never(lambda: len(pult.children(task)) > 1,
                              f"перезапуск после остановки «{kind}»")
        cycle_records(pult, task)
        yield from pult.never(lambda: len(pult.children(task)) > 1,
                              "записи цикла auto открыли перезапуск")

    pult.supervise(script())
    assert pult.exit == "сценарий", pult.msg(f"надзор завершился сам: {pult.exit}")


def test_ac14_resume_after_pause_stop_relaunches(pult):
    """Остановка паузой, затем `resume`, снявший паузу: задача снова запускается.

    Сценарий: `pause` задачи, её дочерний останавливается паузой и
    выходит; за `IDLE` пауз перезапуска нет; `resume` (запись журнала
    позже остановки) — надзор запускает второй дочерний `auto`.

    Ловит мутацию: `resume` не входит в перечень новых действий Оператора
    (задача не перезапускается); либо новое действие ищется до записи
    остановки, а не после.
    """
    pult.new_epic()
    task = pult.task()
    pult.observation([task])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: len(pult.children(task)) == 1, "первый запуск")
        pult.not_on_gate_stop(task, "пауза")
        yield from pult.never(lambda: len(pult.children(task)) > 1, "перезапуск до resume")
        pult.ok("resume", task)
        yield from pult.wait_until(lambda: len(pult.children(task)) == 2, "перезапуск после resume")

    pult.supervise(script())


def test_ac15_resume_without_pause_does_not_reopen(pult):
    """Остановка лимитом шагов (задача не на паузе): `resume` перезапуск не открывает.

    Сценарий: дочерний останавливается лимитом шагов и выходит; Оператор
    зовёт `resume` по задаче не на паузе; за `IDLE` пауз перезапуска нет.

    Ловит мутацию: любой вызов `resume` (или любая запись после остановки)
    считается новым действием — задача перезапускается.
    """
    pult.new_epic()
    task = pult.task()
    pult.observation([task])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: len(pult.children(task)) == 1, "первый запуск")
        pult.not_on_gate_stop(task, "лимит шагов")
        yield
        pult.ok("resume", task)
        yield from pult.never(lambda: len(pult.children(task)) > 1,
                              "resume без паузы открыл перезапуск")

    pult.supervise(script())


def test_ac16_epic_retry_records_and_relaunches_and_refuses_outsider(pult):
    """`epic retry` пишет запись журнала задачи и перезапускает её; задача вне эпика — отказ без записи.

    Сценарий: дочерний останавливается не на гейте (лимит шагов) и
    выходит; `epic retry <эпик> <задача>` добавляет запись журнала задачи,
    и надзор запускает второй дочерний `auto`. После надзора `epic retry`
    с задачей вне эпика отказывает с непустой причиной, записей по ней нет.

    Ловит мутацию: `epic retry` не пишет журнал задачи (или пишет его
    эпику) — новое действие не видно, перезапуска нет; либо не проверяет
    принадлежность задачи эпику — задаче вне эпика пишется запись.
    """
    pult.new_epic()
    task = pult.task()
    outsider = pult.task(epic=False)
    pult.observation([task])
    pult.start()
    seen = {}

    def script():
        yield from pult.wait_until(lambda: len(pult.children(task)) == 1, "первый запуск")
        pult.not_on_gate_stop(task, "лимит шагов")
        yield from pult.never(lambda: len(pult.children(task)) > 1, "перезапуск до retry",
                              count=3)
        since = pult.top_step()
        pult.ok("epic", "retry", pult.epic, task)
        seen["records"] = len(pult.records(task, since))
        yield from pult.wait_until(lambda: len(pult.children(task)) == 2, "перезапуск после retry")

    pult.supervise(script())
    assert seen["records"] >= 1, pult.msg("epic retry не записал журнал задачи")
    since = pult.top_step()
    text = pult.refused("epic", "retry", pult.epic, outsider)
    assert text.strip(), pult.msg("отказ без причины")
    assert pult.records(outsider, since) == [], pult.msg("записи по задаче вне эпика")


def test_ac17_manual_stop_holds_until_operator_action(pult):
    """Ручной `stop <id>` дочерней задачи: перезапуска нет до нового действия Оператора, после — есть.

    Сценарий: Оператор зовёт `stop` задачи — её дочерний получает SIGTERM,
    дописывает остановку и выходит; за `IDLE` пауз перезапуска нет; затем
    `epic retry` — надзор запускает второй дочерний `auto`.

    Ловит мутацию: остановка командой `stop` не считается остановкой не на
    гейте — надзор сразу перезапускает задачу; либо после `stop` задача не
    возвращается в набор наблюдения и перезапуск отказывает.
    """
    pult.new_epic()
    task = pult.task()
    pult.observation([task])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: len(pult.children(task)) == 1, "первый запуск")
        yield
        pult.ok("stop", task)
        stand = pult.children(task)[-1].stand
        stand.finish()
        pult.child_stops(task, f"{pult.state(task)}: остановлен командой stop")
        yield from pult.never(lambda: len(pult.children(task)) > 1, "перезапуск после stop")
        pult.ok("epic", "retry", pult.epic, task)
        yield from pult.wait_until(lambda: len(pult.children(task)) == 2, "перезапуск после retry")

    pult.supervise(script())


@pytest.mark.parametrize("variant", ["запись CYCLE_ABORTED", "выход без записи"])
def test_ac18_abnormal_child_exit_holds_until_operator_action(pult, variant):
    """Аварийный выход дочернего `auto`: перезапуска нет до нового действия Оператора, после — есть.

    Сценарий: (а) дочерний пишет `CYCLE_ABORTED_ACTION` и выходит; (б)
    процесс дочернего гибнет без записи о своей остановке (lease остаётся
    с мёртвым pid). За `IDLE` пауз перезапуска нет; `epic retry` — второй
    дочерний `auto`.

    Ловит мутацию: аварийный выход принимается за обычное освобождение
    места — задача сразу перезапускается; либо выход без записи не
    замечается (надзор ждёт мёртвого дочернего вечно и не перезапускает
    задачу и после `epic retry`).
    """
    pult.new_epic()
    task = pult.task()
    pult.observation([task])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: len(pult.children(task)) == 1, "первый запуск")
        yield
        if variant == "выход без записи":
            pult.child_vanishes(task)
        else:
            pult.child_stops(task, "RuntimeError: обрыв цикла",
                             action=zone_lock.CYCLE_ABORTED_ACTION)
        yield from pult.never(lambda: len(pult.children(task)) > 1,
                              f"перезапуск после «{variant}»")
        pult.ok("epic", "retry", pult.epic, task)
        yield from pult.wait_until(lambda: len(pult.children(task)) == 2, "перезапуск после retry")

    pult.supervise(script())


# ===== Наблюдение эпика =====


@pytest.mark.parametrize("rule", ["названное", "с задачей эпика", "самое свежее"])
def test_ac19_observation_choice_and_child_in_its_set(pult, rule):
    """Выбор наблюдения эпика: `--observation`, затем с задачей эпика, затем самое свежее; дочерняя — в его наборе.

    Сценарий: у сессии надзора два активных наблюдения проекта, `chosen`
    и `other`. «названное»: `chosen` старше, передано `--observation`.
    «с задачей эпика»: в наборе `chosen` (оно старше) есть задача эпика, в
    `other` (свежее) — нет. «самое свежее»: задач эпика нет ни в одном,
    `chosen` свежее. В момент запуска дочернего `auto` задача — в наборе
    `chosen`, а в `other` задач эпика нет.

    Ловит мутацию: `--observation` не передаётся выбору (берётся самое
    свежее); либо правило (б) пропущено — берётся самое свежее без задач
    эпика; либо дочерняя задача не добавляется в набор выбранного
    наблюдения перед запуском.
    """
    pult.new_epic()
    task, sibling = pult.task(), pult.task("spec_gate")
    stale = config.OBSERVATION_STALE_SECONDS
    older = {"seen_ago": stale * 0.5, "created_ago": 600}
    newer = {"seen_ago": stale * 0.1, "created_ago": 60}
    if rule == "названное":
        chosen = pult.observation([pult.task(epic=False)], **older)
        other = pult.observation([pult.task(epic=False)], **newer)
        extra = ("--observation", chosen)
    elif rule == "с задачей эпика":
        chosen = pult.observation([sibling], **older)
        other = pult.observation([pult.task(epic=False)], **newer)
        extra = ()
    else:
        other = pult.observation([pult.task(epic=False)], **older)
        chosen = pult.observation([pult.task(epic=False)], **newer)
        extra = ()
    pult.start(*extra)

    def script():
        yield from pult.wait_until(lambda: task in pult.launched(), "запуск дочернего")

    pult.supervise(script())
    observed = pult.children(task)[0].snapshot["observed"]
    assert task in observed.get(chosen, set()), pult.msg(
        f"{rule}: задачи нет в наборе выбранного наблюдения при запуске: {observed}")
    assert not observed.get(other, set()) & {task, sibling}, pult.msg(
        f"{rule}: задачи эпика попали в невыбранное наблюдение: {observed}")


def test_ac20_foreign_session_observation_refused_and_not_chosen(pult):
    """Наблюдение другой сессии: с `--observation` — отказ без надзора и блокировки; без флага — не выбирается.

    Сценарий 1: `--observation` наблюдения другой сессии — отказ с
    причиной, надзор не запущен, строки `epic_supervisors` нет. Сценарий 2:
    у другой сессии наблюдение с задачей эпика, у своей — наблюдение
    проекта без задач эпика; без флага выбрано своё: задача при запуске в
    его наборе.

    Ловит мутацию: принадлежность названного наблюдения сессии не
    сверяется (надзор запущен); либо правило (б) ищет наблюдения всех
    сессий — выбрано чужое; либо отказ оставляет строку блокировки.
    """
    pult.new_epic()
    task = pult.task()
    alien = pult.observation([task], session=f"чужая-{pult.seed:x}")
    own = pult.observation([pult.task(epic=False)])
    text = pult.refused("auto", "--epic", pult.epic, "--observation", alien)
    assert text.strip(), pult.msg("отказ без причины")
    assert pult.supervisor_launches() == [], pult.msg("надзор запущен")
    assert pult.lock_rows() == [], pult.msg("строка блокировки после отказа")
    pult.start()

    def script():
        yield from pult.wait_until(lambda: task in pult.launched(), "запуск дочернего")

    pult.supervise(script())
    observed = pult.children(task)[0].snapshot["observed"]
    assert task in observed.get(own, set()), pult.msg(
        f"задачи нет в своём наблюдении при запуске: {observed}")


def test_ac21_no_observation_by_rule_refused(pult):
    """Наблюдения по правилу эпика нет: `auto --epic` — отказ, надзора и строки блокировки нет.

    Сценарий: у другой сессии есть наблюдение с задачей эпика, у своей —
    только наблюдение другого проекта. `auto --epic` отказывает с
    непустой причиной; запуска надзора и строки `epic_supervisors` нет.

    Ловит мутацию: при отсутствии своего наблюдения берётся чужое или
    наблюдение другого проекта (надзор запущен); либо блокировка
    создаётся до выбора наблюдения и остаётся после отказа.
    """
    elsewhere = f"drugoi{pult.seed % 100000}"
    declare_target(elsewhere)
    pult.new_epic()
    task = pult.task()
    pult.observation([task], session=f"чужая-{pult.seed:x}")
    pult.observation([pult.task(epic=False, project=elsewhere)], project=elsewhere)
    text = pult.refused("auto", "--epic", pult.epic)
    assert text.strip(), pult.msg("отказ без причины")
    assert pult.supervisor_launches() == [], pult.msg("надзор запущен")
    assert pult.lock_rows() == [], pult.msg("строка блокировки после отказа")


def test_ac22_stale_observation_ends_supervisor_with_record_and_alert(pult):
    """Наблюдение устарело к запуску дочернего: надзор не запускает его, завершается с записью и алертом.

    Сценарий: задача эпика на гейте, наблюдение свежее — надзор запущен;
    связь наблюдения устаревает, Оператор проходит гейт — задача готова, но
    `_launch_observation` отказал бы. Дочерних запусков нет, надзор
    завершился сам, за надзор есть запись журнала эпика и открыт алерт
    `kind=attention` по эпику.

    Ловит мутацию: отказ наблюдения глотается — надзор ждёт молча (не
    завершается); либо завершается без записи журнала или без алерта;
    либо запускает дочерний в обход свежести.
    """
    pult.new_epic()
    task = pult.task("spec_gate")
    obs = pult.observation([task])
    pult.start()

    def script():
        yield
        yield
        pult.make_stale(obs)
        pult.set_state(task, "tests_writing", actor="operator")
        yield from pult.forever()

    pult.supervise(script())
    assert pult.launched() == [], pult.msg(f"дочерний запущен: {pult.launched()}")
    assert pult.exit == "сам", pult.msg(f"надзор не завершился сам: {pult.exit}")
    assert pult.records(pult.epic, pult.run_from), pult.msg("нет записи журнала эпика")
    assert pult.epic_alerts(), pult.msg("нет алерта attention по эпику")


# ===== epic stop =====


def epic_stop_scenario(pult) -> dict:
    """`epic stop` при живом надзоре: дочерний A надзора, ждущая места C, `auto` Оператора у B."""
    pult.new_epic()
    a, b, c = pult.task(), pult.task(), pult.task()
    operator_auto = pult.foreign_auto(b)
    pult.ok("epic", "parallel", pult.epic, "1")
    pult.observation([a, b, c])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: pult.launched() == [a], "запуск A")
        yield
        pult.stop_epic_concurrently()
        yield from pult.forever()

    pult.supervise(script())
    return {"a": a, "b": b, "c": c, "operator_auto": operator_auto,
            "child": pult.children(a)[0].stand}


def test_ac23_epic_stop_supervisor_first_then_children_by_sigterm(pult):
    """`epic stop`: сначала надзор, после него новых запусков нет; затем дочерние — SIGTERM, без kill.

    Сценарий (`epic parallel 1`): дочерний `auto` задачи A жив, задача C
    ждёт места. `epic stop` из другого процесса: сигнал надзору (или его
    выход) раньше SIGTERM дочернему A; после остановки надзора C не
    запущена, хоть место A освободилось; A получила SIGTERM, SIGKILL ей не
    слали, процесс A сам дописал остановку и вышел (ожидание выхода — с
    предельным сроком).

    Ловит мутацию: дочерние останавливаются раньше надзора — надзор
    успевает отдать место C; либо дочерние убиваются SIGKILL
    (`pause --now`-путь) вместо штатного `stop`; либо надзор не
    останавливается вовсе (сценарий упирается в предел пауз).
    """
    seen = epic_stop_scenario(pult)
    assert pult.stop_result is None, pult.msg(f"epic stop отказала: {pult.stop_result}")
    assert pult.exit in ("сам", "сигнал"), pult.msg(f"надзор не остановлен: {pult.exit}")
    kills = pult.kills[pult.stop_kill_from:]
    child = seen["child"]
    to_child = [i for i, (pid, sig) in enumerate(kills) if pid == child.pid and sig != 0]
    assert to_child, pult.msg(f"дочернему A сигнал не отправлен: {kills}")
    assert all(kills[i][1] == signal.SIGTERM for i in to_child), pult.msg(
        f"дочернему A не только SIGTERM: {[kills[i] for i in to_child]}")
    to_sup = [i for i, (pid, sig) in enumerate(kills) if pid == pult.sup.pid and sig != 0]
    if to_sup:
        assert to_sup[0] < to_child[0], pult.msg(f"дочерний остановлен раньше надзора: {kills}")
    else:
        assert pult.ended_at <= pult.stop_kill_from + to_child[0], pult.msg(
            "дочерний остановлен раньше выхода надзора")
    assert seen["c"] not in pult.launched(), pult.msg("после остановки надзора запущена C")
    if pult.delivered_at is not None:
        assert len(pult.launches) == pult.delivered_at, pult.msg("запуски после сигнала надзору")
    child.finish()
    assert child.caught() == "SIGTERM", pult.msg(f"дочерний A вышел не по SIGTERM: {child.caught()}")


def test_ac24_epic_stop_spares_operator_auto(pult):
    """`epic stop` не трогает `auto <id>` задачи эпика, запущенный Оператором.

    Сценарий тот же, что в AC-23: у задачи B эпика живой `auto` Оператора
    (не запуск надзора). После `epic stop` его процесс жив, сигналов ему
    не слали, записи остановки цикла по B за `epic stop` нет.

    Ловит мутацию: `epic stop` останавливает всех держателей lease задач
    эпика, а не только дочерних, запущенных надзором.
    """
    seen = epic_stop_scenario(pult)
    operator_auto = seen["operator_auto"]
    signals = [(pid, sig) for pid, sig in pult.kills[pult.stop_kill_from:]
               if pid == operator_auto.pid and sig != 0]
    assert signals == [], pult.msg(f"сигналы auto Оператора: {signals}")
    assert operator_auto.alive(), pult.msg("auto Оператора остановлен")
    stops = [r["action"] for r in pult.records(seen["b"], pult.stop_from)
             if r["action"] in (zone_lock.AUTO_STOPPED_ACTION, zone_lock.CYCLE_ABORTED_ACTION)]
    assert stops == [], pult.msg(f"записи остановки по B: {stops}")


def test_ac25_epic_stop_with_dead_supervisor(pult):
    """`epic stop` при мёртвом надзоре: живые дочерние остановлены штатно, блокировка снята, записи в журнале.

    Сценарий: надзор запустил дочерний `auto` и погиб без уборки (SIGKILL,
    строка блокировки осталась). `epic stop`: дочерний получил SIGTERM и
    вышел сам, строк `epic_supervisors` эпика нет, за `epic stop` есть
    запись журнала эпика.

    Ловит мутацию: при мёртвом pid блокировки `epic stop` отказывает
    («надзор не запущен») и дочерних не трогает; либо не снимает строку;
    либо действует молча, без записи журнала.
    """
    pult.new_epic()
    task = pult.task()
    pult.observation([task])
    pult.start()
    seen = {}

    def script():
        yield from pult.wait_until(lambda: pult.launched() == [task], "запуск дочернего")
        yield
        seen["rows_before"] = len(pult.lock_rows())
        pult.supervisor_dies()
        since = pult.top_step()
        pult.ok("epic", "stop", pult.epic)
        child = pult.children(task)[0].stand
        child.finish()
        seen["caught"] = child.caught()
        seen["rows"] = [dict(r) for r in pult.lock_rows()]
        seen["records"] = len(pult.records(pult.epic, since))

    pult.supervise(script())
    assert seen["rows_before"] == 1, pult.msg("до гибели надзора нет строки блокировки")
    assert seen["caught"] == "SIGTERM", pult.msg(f"дочерний вышел не по SIGTERM: {seen['caught']}")
    assert seen["rows"] == [], pult.msg(f"блокировка не снята: {seen['rows']}")
    assert seen["records"] >= 1, pult.msg("за epic stop нет записи журнала эпика")


# ===== Конверт и самостоятельное завершение =====


def test_ac26_exhausted_envelope_only_started_tasks_launched(pult):
    """Исчерпанный конверт: задача без первого шага роли не запускается, с начатым — запускается.

    Сценарий: конверт $5, потрачено по эпику $6 (на задаче с записью
    «agent run started»); `epic parallel 2`. Надзор запускает начатую
    задачу, а задачу без первого шага за `IDLE` пауз не запускает; надзор
    жив.

    Ловит мутацию: конверт не проверяется (запущены обе); либо проверяется
    у всех задач, без различения первого шага (начатая не запускается).
    """
    pult.new_epic(envelope=5.0)
    started = pult.task(started=True, spent=6.0)
    fresh = pult.task()
    pult.ok("epic", "parallel", pult.epic, "2")
    pult.observation([started, fresh])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: started in pult.launched(), "запуск начатой задачи")
        yield from pult.never(lambda: fresh in pult.launched(),
                              "запущена задача без первого шага при исчерпанном конверте")

    pult.supervise(script())
    assert pult.exit == "сценарий", pult.msg(f"надзор завершился: {pult.exit}")


def final_epic(pult, case: str) -> tuple:
    """(наблюдение, неокончательные либо все задачи эпика) случая самозавершения.

    AC-27: наблюдение с окончательной задачей эпика (правило (б));
    AC-28, AC-29: наблюдение проекта без задач эпика (правило (в))."""
    if case == "все окончательны":
        pult.new_epic()
        done, killed = pult.task("done"), pult.task("killed")
        return pult.observation([done]), [done, killed]
    if case == "start_after на killed":
        pult.new_epic()
        dependency, waiting = pult.task(), pult.task()
        pult.ok("epic", "start-after", waiting, dependency)
        pult.set_state(dependency, "killed", actor="operator")
        return pult.observation([pult.task(epic=False)]), [waiting]
    pult.new_epic(envelope=5.0)
    pult.task("done", spent=6.0)
    waiting = [pult.task(), pult.task("tests_writing")]
    return pult.observation([pult.task(epic=False)]), waiting


def supervisor_ends_itself(pult, case: str) -> None:
    final_epic(pult, case)
    pult.start()
    pult.supervise(pult.forever(), limit=IDLE * 3)
    assert pult.exit == "сам", pult.msg(f"{case}: надзор не завершился сам: {pult.exit}")
    assert pult.launched() == [], pult.msg(f"{case}: дочерние запущены: {pult.launched()}")
    assert pult.records(pult.epic, pult.run_from), pult.msg(f"{case}: нет записи журнала эпика")


def test_ac27_all_tasks_final_supervisor_ends_itself(pult):
    """Все задачи эпика `done`/`killed`: надзор завершается сам с записью журнала эпика.

    Сценарий: эпик из задачи в `done` и задачи в `killed`; надзор
    завершается сам, без дочерних запусков, и за надзор есть запись
    журнала с id эпика.

    Ловит мутацию: условие выхода «нет задач» вместо «нет неокончательных»
    — надзор живёт до предела пауз; либо выходит молча, без записи журнала.
    """
    supervisor_ends_itself(pult, "все окончательны")


def test_ac28_start_after_on_killed_supervisor_ends_itself(pult):
    """Единственная неокончательная задача ждёт `start_after` на задачу в `killed`: надзор завершается сам.

    Сценарий: вторая задача эпика — `start_after` первой, первая убита;
    надзор завершается сам, без дочерних запусков, с записью журнала эпика.

    Ловит мутацию: ожидание `start_after` на убитую задачу считается
    обычным ожиданием зависимости — надзор живёт до предела пауз.
    """
    supervisor_ends_itself(pult, "start_after на killed")


def test_ac29_exhausted_envelope_unstarted_only_supervisor_ends_itself(pult):
    """Конверт исчерпан, неокончательные — только без первого шага роли: надзор завершается сам.

    Сценарий: конверт $5, потрачено $6 на слитой задаче; две задачи без
    записи «agent run started». Надзор завершается сам, без дочерних
    запусков, с записью журнала эпика.

    Ловит мутацию: исчерпанный конверт держит задачи «готовыми к запуску
    позже» — надзор живёт до предела пауз; либо запускает их в обход
    конверта.
    """
    supervisor_ends_itself(pult, "конверт исчерпан")


@pytest.mark.parametrize("case", ["все окончательны", "start_after на killed",
                                  "конверт исчерпан"])
def test_ac30_watch_delivers_attention_alert_and_end_record(pult, case):
    """Самозавершение надзора видно в сессии: `watch` наблюдения выводит алерт attention по эпику и запись завершения.

    Случаи AC-27, AC-28, AC-29. Для AC-28 и AC-29 наблюдение выбрано по
    правилу (в): до старта в его наборе задач эпика не было — после старта
    неокончательные задачи эпика в наборе. Для AC-27 (неокончательных нет)
    — наблюдение с окончательной задачей эпика. Одна итерация
    `watch --observation` после завершения надзора выводит строку
    `alert:attention` с id эпика и строку журнала с id эпика.

    Ловит мутацию: неокончательные задачи эпика не добавляются в набор при
    старте (доставки нет); либо `watch` не доставляет записи и алерты с
    id эпика; либо самозавершение не открывает алерт.
    """
    obs, waiting = final_epic(pult, case)
    pult.start()
    pult.supervise(pult.forever(), limit=IDLE * 3)
    assert pult.exit == "сам", pult.msg(f"{case}: надзор не завершился сам: {pult.exit}")
    if case != "все окончательны":
        missing = set(waiting) - pult.obs_tasks(obs)
        assert not missing, pult.msg(f"{case}: задачи эпика не в наборе наблюдения: {missing}")
    lines = [ln for ln in pult.watch_once(obs).splitlines() if pult.epic in ln]
    assert any("alert:attention" in ln for ln in lines), pult.msg(
        f"{case}: нет алерта attention по эпику в watch: {lines}")
    assert any("alert:" not in ln for ln in lines), pult.msg(
        f"{case}: нет записи журнала эпика в watch: {lines}")


def test_ac31_escalated_task_not_launched_and_holds_supervisor(pult):
    """Задача в `escalated`: дочернего нет, надзор не завершается, пока она в эскалации.

    Сценарий: одна задача эпика в `escalated`, другая готова. Надзор
    запускает готовую; её дочерний доводит задачу до `done`; остаётся
    только задача в `escalated` — за `IDLE` пауз ей нет запуска, и надзор
    жив до конца сценария.

    Ловит мутацию: `escalated` не исключено из готовых (дочерний
    запущен); либо эскалированная задача не держит надзор — он
    завершается сам после `done` второй.
    """
    pult.new_epic()
    escalated, ready = pult.task("escalated"), pult.task()
    pult.observation([escalated, ready])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: ready in pult.launched(), "запуск готовой задачи")
        pult.set_state(ready, "done")
        pult.child_stops(ready, "done: задача слита")
        yield from pult.never(lambda: escalated in pult.launched(),
                              "запущена задача в escalated")

    pult.supervise(script())
    assert pult.exit == "сценарий", pult.msg(f"надзор завершился при escalated: {pult.exit}")


# ===== Место лимита =====


def test_ac32_global_limit_refusal_requeues_without_operator(pult):
    """Отказ `run` дочернего по глобальному лимиту — не остановка не на гейте: после освобождения места перезапуск.

    Сценарий (потолок пульта 1): дочерний задачи запущен, место занимает
    живой lease задачи вне эпика; дочерний пишет «run отклонён: лимит
    параллельных задач», останавливается и выходит. Пока чужой lease жив —
    перезапуска нет; чужой lease снят — надзор запускает задаче второй
    дочерний без действий Оператора.

    Ловит мутацию: отказ лимита классифицируется как остановка не на гейте
    (задача ждёт Оператора и не перезапускается); либо надзор запускает
    при занятом месте.
    """
    pult.global_limit(1)
    pult.new_epic()
    task = pult.task()
    rival = pult.task(epic=False)
    pult.observation([task])
    pult.start()
    holder = {}

    def script():
        yield from pult.wait_until(lambda: len(pult.children(task)) == 1, "первый запуск")
        yield
        holder["stand"] = pult.foreign_auto(rival)
        pult.child_refused_by_limit(task)
        yield from pult.never(lambda: len(pult.children(task)) > 1, "запуск при занятом месте")
        pult.release_foreign(rival, holder["stand"])
        yield from pult.wait_until(lambda: len(pult.children(task)) == 2,
                                   "перезапуск после освобождения места")

    pult.supervise(script())


@pytest.mark.parametrize("variant", ["pid не жив", "pid занят процессом позже запуска"])
def test_ac33_place_counted_by_child_pid(pult, variant):
    """Место лимита — по pid дочернего: мёртвый pid или pid процесса, стартовавшего позже запуска, места не занимает.

    Сценарий (`epic parallel 1`, задачи A и B): дочерний A запущен. «pid не
    жив» — процесс A гибнет, lease с его pid остаётся в таблице. «pid
    занят процессом позже запуска» — процесс жив и держит lease, но
    `process_start_time` его pid позже записанного запуска. В обоих
    случаях надзор запускает на освободившееся место B.

    Ловит мутацию: место считается по lease задач эпика, а не по pid
    дочерних (B не запускается, пока lease A «жив»); либо живость pid без
    сверки времени старта (во втором случае B не запускается).
    """
    pult.new_epic()
    a, b = pult.task(), pult.task()
    pult.ok("epic", "parallel", pult.epic, "1")
    pult.observation([a, b])
    pult.start()

    def script():
        yield from pult.wait_until(lambda: pult.launched() == [a], "запуск A")
        yield
        child = pult.children(a)[0].stand
        if variant == "pid не жив":
            pult.child_vanishes(a)
        else:
            real = stale_cycles.process_start_time

            def later(pid):
                if pid == child.pid:
                    return datetime.now(timezone.utc) + timedelta(hours=1)
                return real(pid)

            pult.stack.enter_context(mock.patch.object(doctor, "process_start_time", later))
            pult.stack.enter_context(mock.patch.object(stale_cycles, "process_start_time", later))
        yield from pult.wait_until(lambda: b in pult.launched(), f"запуск B ({variant})")

    pult.supervise(script())
