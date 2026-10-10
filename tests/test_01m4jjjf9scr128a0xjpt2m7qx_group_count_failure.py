"""Сбой подсчёта членов группы не выдаётся за пустую группу.

Группа: долгоживущий

`orchestrator.liveness.terminate_process_group` и строка `status`
(`catalog.cmd_status`, держатель lease) при сбое внешней команды `ps`:
не запустилась (`OSError`), не ответила в срок (`TimeoutExpired`),
завершилась с ненулевым кодом на живой группе. Плюс два регресса при
исправном `ps`: живая группа снимается с числом ≥ 1, пустая даёт 0.

Подмена `ps` — на уровне внешней команды, не по имени функций модуля:
`subprocess.Popen` подменён обёрткой, которая узнаёт запуск команды с
именем `ps` (голым или по абсолютному пути) и разыгрывает сбой, всё
остальное пропускает к настоящему `Popen`. Способ подсчёта и форму
сигнала сбоя выбирает реализация; `subprocess.run`/`check_output`
ходят через тот же `Popen`.

Группа — реальный процесс-лидер собственной сессии (pgid == pid), как
у `runner.spawn_agent`. Лидер, игнорирующий `SIGTERM`, сообщает о
поставленном обработчике строкой в stdout — тест ждёт её, а не время.
Тестовый процесс — родитель лидера, поэтому смерть лидера проверяется
`proc.wait(...)` и кодом возврата `-SIGKILL`, не `os.kill(pid, 0)`
(недожатый зомби отвечает «жив»).

Красен до реализации: сегодня `_group_member_count` на любой сбой `ps` отдаёт 0 как для пустой группы — `terminate_process_group` не шлёт `SIGKILL` лидеру, игнорирующему `SIGTERM`, и возвращает 0 (AC-1, AC-2); AC-3/AC-4/AC-5 держат сегодняшнее поведение и зелены с рождения.
"""
import errno
import os
import random
import shutil
import signal
import socket
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, liveness, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest, _dead_pid, capture  # noqa: E402

REAL_POPEN = subprocess.Popen

#: Виды сбоя `ps` (AC-1 — не запустился/не ответил в срок, AC-2 —
#: ненулевой код на живой группе: и молча, как `ps` на пустой группе, и
#: с сообщением об ошибке).
LAUNCH_FAILURES = ("not_found", "permission_denied", "timeout")
EXIT_FAILURES = ("exit_1_silent", "exit_2_stderr")

EXIT_SCRIPTS = {
    "exit_1_silent": "import sys; sys.exit(1)",
    "exit_2_stderr": ("import sys; sys.stderr.write('ps: fake failure\\n');"
                      " sys.exit(2)"),
}

IGNORE_TERM_LEADER = (
    "import signal, sys, time\n"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "print('ready', flush=True)\n"
    "time.sleep(60)\n"
)
OBEY_TERM_LEADER = (
    "import sys, time\n"
    "print('ready', flush=True)\n"
    "time.sleep(60)\n"
)


def is_ps_command(args) -> bool:
    argv = args.split() if isinstance(args, (str, bytes)) else list(args)
    if not argv:
        return False
    first = argv[0].decode() if isinstance(argv[0], bytes) else str(argv[0])
    return os.path.basename(first) == "ps"


class HangingPs(REAL_POPEN):
    """Запуск `ps`, который не отвечает: ожидание с конечным сроком сразу
    бросает `TimeoutExpired` (без реального ожидания), ожидание без срока
    — к настоящему спящему процессу, который убьёт вызывающий."""

    def __init__(self, args, **kwargs):
        self.ps_args = args
        super().__init__([sys.executable, "-c", "import time; time.sleep(30)"],
                         **kwargs)

    def communicate(self, input=None, timeout=None):
        if timeout is not None:
            raise subprocess.TimeoutExpired(self.ps_args, timeout)
        return super().communicate(input)

    def wait(self, timeout=None):
        if timeout is not None and self.poll() is None:
            raise subprocess.TimeoutExpired(self.ps_args, timeout)
        return super().wait()


def failing_ps(kind: str, spawned: list):
    """Подмена `subprocess.Popen`: запуск `ps` разыгрывает сбой `kind`,
    прочие команды — настоящий `Popen`."""

    def popen(args, *rest, **kwargs):
        if not is_ps_command(args):
            return REAL_POPEN(args, *rest, **kwargs)
        if kind == "not_found":
            raise FileNotFoundError(errno.ENOENT, "fake: ps not found", "ps")
        if kind == "permission_denied":
            raise PermissionError(errno.EACCES, "fake: ps not runnable", "ps")
        if kind == "timeout":
            proc = HangingPs(args, **kwargs)
        else:
            proc = REAL_POPEN([sys.executable, "-c", EXIT_SCRIPTS[kind]],
                              **kwargs)
        spawned.append(proc)
        return proc

    return mock.patch("subprocess.Popen", popen)


def path_with_real_ps() -> str:
    """`PATH`, в котором штатный `ps` находится (окружение роли бывает без
    `/bin`, где `ps` лежит на macOS) — для критериев «при исправном `ps`»."""
    path = os.environ.get("PATH", "")
    found = shutil.which("ps", path=os.pathsep.join([path, "/bin", "/usr/bin"]))
    if found is None:
        raise AssertionError("штатный ps не найден ни в PATH, ни в /bin, /usr/bin")
    return os.pathsep.join([str(Path(found).parent), path])


class GroupFixture:
    """Живые лидеры групп и подменные `ps` теста — дожимаются в cleanup."""

    def setup_groups(self):
        self.leaders = []
        self.fake_ps = []
        self.addCleanup(self.reap_all)
        self.seed = random.randrange(2 ** 32)
        self.rng = random.Random(self.seed)
        print(f"зерно: {self.seed}")

    def reap_all(self):
        for proc in self.leaders + self.fake_ps:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            for stream in (proc.stdout, proc.stderr):
                if stream is not None:
                    stream.close()

    def spawn_leader(self, script: str) -> subprocess.Popen:
        proc = REAL_POPEN([sys.executable, "-c", script],
                          start_new_session=True, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, text=True)
        self.leaders.append(proc)
        self.assertEqual(proc.stdout.readline().strip(), "ready",
                         "лидер группы не стартовал")
        self.assertEqual(os.getpgid(proc.pid), proc.pid,
                         "лидер не стал лидером своей группы")
        return proc

    def grace(self) -> float:
        return round(self.rng.uniform(0.1, 0.4), 3)

    def assert_killed_with_sigkill(self, proc, kind: str, grace: float):
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.fail(f"[{kind}, grace={grace}, зерно: {self.seed}] лидер, "
                      "игнорирующий SIGTERM, пережил terminate_process_group")
        self.assertEqual(
            proc.returncode, -signal.SIGKILL,
            f"[{kind}, grace={grace}, зерно: {self.seed}] лидер снят не SIGKILL")


class FailedCountTerminateTest(GroupFixture, unittest.TestCase):

    def setUp(self):
        self.setup_groups()

    def run_failure_case(self, kind: str) -> None:
        leader = self.spawn_leader(IGNORE_TERM_LEADER)
        grace = self.grace()

        with failing_ps(kind, self.fake_ps):
            count = liveness.terminate_process_group(
                leader.pid, grace_sec=grace, poll_sec=0.02)

        self.assert_killed_with_sigkill(leader, kind, grace)
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(
            count, 1, f"[{kind}, grace={grace}, зерно: {self.seed}] сбой "
            "подсчёта занизил число снятых до 0")

    def test_ac1_launch_or_timeout_failure_of_ps_still_kills_and_counts(self):
        """`ps` не запускается (`FileNotFoundError`/`PermissionError`) либо не отвечает в срок.

        Группа с живым лидером, игнорирующим `SIGTERM`, и случайным малым
        `grace_sec`: после вызова `terminate_process_group` лидер мёртв от
        `SIGKILL` (код возврата `-SIGKILL`), возвращено число ≥ 1.

        Ловит мутацию: сбой подсчёта снова читается как «группа пуста»
        (`except (OSError, TimeoutExpired): return 0`) — `SIGKILL` не
        посылается, лидер жив после вызова (`proc.wait` падает по
        таймауту), возврат 0.
        """
        for kind in LAUNCH_FAILURES:
            with self.subTest(kind=kind):
                self.run_failure_case(kind)

    def test_ac2_nonzero_exit_of_ps_on_live_group_still_kills_and_counts(self):
        """`ps` завершается с ненулевым кодом, хотя группа жива.

        Два вида: код 1 с пустыми stdout/stderr (так штатный `ps` отвечает
        на пустую группу) и код 2 с сообщением в stderr. Лидер игнорирует
        `SIGTERM`: после вызова он мёртв от `SIGKILL`, возврат ≥ 1.

        Ловит мутацию: ненулевой код `ps` безусловно трактуется как
        «группа пуста» (`if res.returncode != 0: return 0`) без сверки,
        что в группе есть живые процессы — лидер переживает вызов,
        возврат 0.
        """
        for kind in EXIT_FAILURES:
            with self.subTest(kind=kind):
                self.run_failure_case(kind)


class HealthyCountTerminateTest(GroupFixture, unittest.TestCase):

    def setUp(self):
        self.setup_groups()
        env = mock.patch.dict(os.environ, {"PATH": path_with_real_ps()})
        env.start()
        self.addCleanup(env.stop)

    def test_ac3_live_group_with_working_ps_is_taken_down_with_positive_count(self):
        """Живая группа при исправном `ps` снимается, число ≥ 1 — как сегодня.

        Два лидера: послушный `SIGTERM` и игнорирующий его (тогда снятие
        обязано дойти до `SIGKILL` по выжившему в подсчёте члену).

        Ловит мутацию: различение «пусто/сбой» перевёрнуто и успешный
        вывод `ps` со списком pid читается как пустая группа — возврат 0
        (`assertGreaterEqual` краснеет), а игнорирующий `SIGTERM` лидер
        не добит `SIGKILL` и переживает вызов.
        """
        for name, script in (("obeys_sigterm", OBEY_TERM_LEADER),
                             ("ignores_sigterm", IGNORE_TERM_LEADER)):
            with self.subTest(leader=name):
                leader = self.spawn_leader(script)
                grace = self.grace()

                count = liveness.terminate_process_group(
                    leader.pid, grace_sec=grace, poll_sec=0.02)

                self.assertGreaterEqual(
                    count, 1, f"[{name}, grace={grace}, зерно: {self.seed}]")
                try:
                    leader.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.fail(f"[{name}, grace={grace}, зерно: {self.seed}] "
                              "лидер группы пережил terminate_process_group")

    def test_ac4_empty_group_with_working_ps_returns_zero(self):
        """Пустая группа (процесс завершён и дожат) при исправном `ps` даёт 0 без исключения.

        Несколько завершённых процессов подряд; штатный `ps` отвечает на
        такую группу ненулевым кодом с пустым выводом.

        Ловит мутацию: любой ненулевой код `ps` объявлен сбоем подсчёта
        без сверки, жива ли группа, — пустая группа даёт возврат ≥ 1
        (или исключение) вместо 0.
        """
        for attempt in range(self.rng.randint(2, 4)):
            with self.subTest(attempt=attempt):
                pid = _dead_pid()
                grace = self.grace()

                count = liveness.terminate_process_group(
                    pid, grace_sec=grace, poll_sec=0.02)

                self.assertEqual(
                    count, 0, f"[pid={pid}, grace={grace}, зерно: {self.seed}]")


class FailedCountStatusTest(GroupFixture, TaskSeededTmpRootTest):

    def setUp(self):
        super().setUp()
        self.setup_groups()

    def insert_lease(self, pid: int, pgid: int) -> None:
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts, pgid) VALUES (?,?,?,?,?,?)",
            (self.TASK, "sess-ps-failure", pid, socket.gethostname(),
             store.now(), pgid))
        conn.commit()

    def test_ac5_status_lease_suffix_survives_failing_ps(self):
        """Строка `status` с lease этой машины, мёртвым `pid` и заданным `pgid` при сбойном `ps`.

        Держатель lease мёртв, `pgid` — живая группа; `ps` подменён каждым
        видом сбоя AC-1/AC-2. `catalog.cmd_status` (держатель — суффикс
        `_lease_holder_suffix`) отрабатывает без исключения, и строка
        задачи несёт суффикс lease с идентификатором сессии.

        Ловит мутацию: сбой подсчёта сигналится исключением, которое
        подсчёт отпускает наружу, — вызов из `catalog` (сравнение с `> 0`)
        падает, `cmd_status` бросает вместо печати строки.
        """
        leader = self.spawn_leader(IGNORE_TERM_LEADER)
        self.insert_lease(_dead_pid(), leader.pid)

        for kind in LAUNCH_FAILURES + EXIT_FAILURES:
            with self.subTest(kind=kind):
                with failing_ps(kind, self.fake_ps):
                    try:
                        out = capture(catalog.cmd_status)
                    except Exception as exc:  # noqa: BLE001
                        self.fail(f"[{kind}] status упал на сбое ps: {exc!r}")

                self.assertIn("[lease: sess-ps-failure ", out, f"[{kind}]")


if __name__ == "__main__":
    unittest.main()
