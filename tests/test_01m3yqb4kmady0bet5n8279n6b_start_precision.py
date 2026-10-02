"""Отбор циклов на коде старше пина учитывает погрешность источника времени
старта процесса: огрубление `ps -o lstart=` не включает молча в перечень
цикл, стартовавший после сдвига пина.

Группа: долгоживущий

Критерии приёмки, которые покрывает файл:

AC-1. На Linux с доступной `/proc` живой цикл этой машины, чей процесс
стартовал больше чем на 0,1 с позже момента сдвига пина, не назван ни в
выводе и журнале `pin-update`, ни в предупреждении `doctor` «циклы на
коде старше пина».

AC-2. Время старта цикла берётся из `ps -o lstart=` (точного источника
нет). Если ответ `ps` раньше момента сдвига, а ответ плюс 2 с не раньше
его, цикл назван в перечне `pin-update` и `doctor` с пометкой «время
старта не различимо от сдвига». Строка такого цикла содержит id задачи,
pid, время старта, состояние задачи и команды `stop <id>` и `auto <id>`.

AC-3. Время старта по `ps -o lstart=` отдано на 2 с раньше настоящего, а
цикл стартовал после сдвига пина. Такой цикл не назван в перечне без
пометки «время старта не различимо от сдвига».

AC-4. Цикл, весь интервал старта которого раньше момента сдвига, назван в
перечне без пометки «время старта не различимо от сдвига». Цикл с
неопределимым временем старта назван с пометкой «не удалось определить»,
и `pin-update` при этом завершается успешно.

Устройство сценариев. «Цикл» — настоящий дочерний процесс Python (спит,
пока тест его не снимет) и строка `leases` с его pid и именем этой
машины. `pin-update` идёт в настоящем git-репозитории песочницы с bare
`origin`, зелёным прогоном канарейки и подменённым зелёным CI на целевом
sha: сдвиг пина успешен. Проверка `doctor` — `doctor.check_stale_cycles`
(SPEC называет её по имени) против записи журнала «pin обновлён».

«Точного источника нет» (AC-2/AC-3/AC-4) разыгрывается так: таблица
процессов `/proc` скрыта — открытие, `stat` и перечисление путей под
`/proc` отвечают `FileNotFoundError` (на macOS её и так нет), а вызов
`subprocess.run` с `lstart` в argv получает ответ, который задаёт тест;
остальные команды (git) исполняются по-настоящему. Так ответ `ps`
известен тесту точно, и класс цикла не зависит от удачи.

Момент сдвига тест знает с нужной точностью: у `doctor` это метка
последней записи «pin обновлён» (секунды); у `pin-update` нижняя граница
— выход подменённой сверки CI (она идёт до `merge --ff-only`), верхняя —
возврат команды. Подмена сверки CI выравнивает свой выход сразу за
границу целой секунды, чтобы целосекундный ответ `ps` лёг строго по
нужную сторону сдвига.

AC-1 разыгрывается только там, где `/proc` есть (Linux, в том числе
раннер CI); на macOS метод пропускается — точного источника там нет по
SPEC. Поэтому стаб-валидацию автор планки прошёл только для AC-2..AC-4
(на macOS); AC-1 впервые исполнится на Linux-раннере CI ветки.

Идентификаторы задач, состояния, число циклов, паузы и сдвиги ответов
`ps` — случайные при каждом запуске; зерно печатается и входит в текст
каждого провала.

Красен до реализации: отбор сравнивает голый ответ `ps` с моментом сдвига, пометки «время старта не различимо от сдвига» в коде нет — цикл из AC-2/AC-3 назван без неё, на Linux поздний цикл AC-1 назван по огрублённому `lstart`; методы AC-4 держат прежнее поведение и зелены уже сейчас.
"""
import builtins
import contextlib
import errno
import io
import math
import os
import random
import socket
import subprocess
import sys
import time
import unittest
from datetime import datetime, timezone
from unittest import mock

from orchestrator import ci, config, doctor, pin, store
from tests.sandbox import RealGitSandbox, TmpRootTest

BORDERLINE = "время старта не различимо от сдвига"
UNDETERMINED = "не удалось определить"
PIN_ACTION = "pin обновлён"
ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen
PROC_AVAILABLE = sys.platform.startswith("linux") and os.path.exists("/proc/self/stat")


def is_proc_path(path) -> bool:
    if isinstance(path, int):
        return False
    try:
        text = os.fsdecode(os.fspath(path))
    except TypeError:
        return False
    return text == "/proc" or text.startswith("/proc/")


@contextlib.contextmanager
def proc_table_hidden():
    """Пути под `/proc` не открываются, не `stat`-ятся и не перечисляются."""
    def guarded(real):
        def wrapper(*args, **kwargs):
            path = args[0] if args else kwargs.get("path", kwargs.get("file"))
            if path is not None and is_proc_path(path):
                raise FileNotFoundError(errno.ENOENT,
                                        "песочница: таблица процессов скрыта",
                                        os.fsdecode(os.fspath(path)))
            return real(*args, **kwargs)
        return wrapper

    targets = [(builtins, "open"), (io, "open"), (os, "open"), (os, "stat"),
               (os, "lstat"), (os, "listdir"), (os, "scandir"), (os, "access")]
    with contextlib.ExitStack() as stack:
        for owner, name in targets:
            stack.enter_context(mock.patch.object(owner, name,
                                                  guarded(getattr(owner, name))))
        yield


def lstart_text(moment: float) -> str:
    """Ответ `ps -o lstart=` под `LC_ALL=C`: местное время, до секунды."""
    local = datetime.fromtimestamp(moment)
    return f"{local:%a %b} {local.day:2d} {local:%H:%M:%S %Y}\n"


def years_of(moment: float) -> set:
    return {str(datetime.fromtimestamp(moment).year),
            str(datetime.fromtimestamp(moment, timezone.utc).year)}


def argv_of(cmd) -> list:
    return [cmd] if isinstance(cmd, (str, bytes)) else list(cmd)


def is_lstart_call(cmd) -> bool:
    return any("lstart" in os.fsdecode(a) if isinstance(a, (str, bytes)) else False
               for a in argv_of(cmd))


class PsLstartStub:
    """Подмена `subprocess.run` для вызовов с `lstart` в argv.

    `answers[pid]` — текст ответа `ps` либо режим сбоя (`raise`, `rc1`,
    `empty`, `garbage`); pid без ответа получает ненулевой код. Прочие
    команды исполняются по-настоящему."""

    def __init__(self):
        self.answers = {}
        self.calls = []

    def pid_in(self, cmd):
        for a in argv_of(cmd):
            text = os.fsdecode(a) if isinstance(a, (str, bytes)) else str(a)
            if text.isdigit() and int(text) in self.answers:
                return int(text)
        return None

    def run(self, cmd, *args, **kwargs):
        if not is_lstart_call(cmd):
            return REAL_RUN(cmd, *args, **kwargs)
        self.calls.append(time.time())
        answer = self.answers.get(self.pid_in(cmd), "rc1")
        if answer == "raise":
            raise FileNotFoundError("песочница: ps недоступен")
        body, code = {"rc1": ("", 1), "empty": ("", 0),
                      "garbage": ("??? не время ???\n", 0)}.get(answer, (answer, 0))
        text = bool(kwargs.get("text") or kwargs.get("universal_newlines")
                    or kwargs.get("encoding"))
        out = body if text else body.encode()
        if kwargs.get("check") and code:
            raise subprocess.CalledProcessError(code, cmd, out, out)
        return subprocess.CompletedProcess(cmd, code, out, "" if text else b"")

    def popen(self, cmd, *args, **kwargs):
        if is_lstart_call(cmd):
            raise FileNotFoundError("песочница: ps недоступен")
        return REAL_POPEN(cmd, *args, **kwargs)

    @contextlib.contextmanager
    def active(self):
        with proc_table_hidden(), \
                mock.patch.object(subprocess, "run", self.run), \
                mock.patch.object(subprocess, "Popen", self.popen):
            yield


def sleep_until(moment: float) -> None:
    while True:
        left = moment - time.time()
        if left <= 0:
            return
        time.sleep(left)


class CyclesMixin:
    """Случайность, циклы-процессы, lease и задачи; разбор перечня."""

    def init_cycles(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.host = socket.gethostname()
        self.used_ids = set()
        self.ps = PsLstartStub()

    def msg(self, text: str = "") -> str:
        return f"зерно {self.seed}: {text}"

    def new_task_id(self) -> str:
        while True:
            tid = "01" + "".join(self.rng.choice(ULID_ALPHABET) for _ in range(24))
            if tid not in self.used_ids:
                self.used_ids.add(tid)
                return tid

    def spawn_process(self) -> int:
        proc = REAL_POPEN([sys.executable, "-c", "import time; time.sleep(600)"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        def cleanup():
            proc.kill()
            proc.wait(timeout=10)

        self.addCleanup(cleanup)
        return proc.pid

    def add_cycle(self) -> dict:
        tid = self.new_task_id()
        state = self.rng.choice(sorted(config.STATE_ROLE))
        pid = self.spawn_process()
        store.insert_task(self.conn, tid, f"цикл {tid}", state,
                          f"task/{tid.lower()}", config.DEFAULT_TARGET, 5.0)
        store.insert_lease(self.conn, tid, f"sess-{self.rng.randrange(10**9)}",
                           pid, self.host, store.now())
        return {"tid": tid, "pid": pid, "state": state}

    def cycle_line(self, text: str, cycle: dict, where: str) -> str:
        """Строка перечня, называющая цикл: id задачи, pid, состояние,
        `stop <id>`, `auto <id>` и время старта (год) на одной строке."""
        tid = cycle["tid"]
        lines = [ln for ln in text.splitlines() if tid in ln]
        self.assertTrue(lines, self.msg(f"{where}: цикл {cycle} не назван:\n{text}"))
        needles = (str(cycle["pid"]), cycle["state"], f"stop {tid}", f"auto {tid}")
        for ln in lines:
            rest = ln.replace(tid, "").replace(str(cycle["pid"]), "")
            if (all(n in ln for n in needles)
                    and any(y in rest for y in cycle["years"])):
                return ln
        self.fail(self.msg(
            f"{where}: нет строки цикла {cycle} с id задачи, pid, временем "
            f"старта, состоянием и командами stop/auto:\n{text}"))

    def assert_silent_or_marked(self, text: str, cycle: dict, where: str) -> None:
        if cycle["tid"] in text:
            self.assertIn(BORDERLINE, text, self.msg(
                f"{where}: цикл {cycle}, стартовавший после сдвига, назван "
                f"без пометки «{BORDERLINE}»:\n{text}"))


class PinUpdateSandbox(CyclesMixin, RealGitSandbox):
    """Настоящий git с bare `origin`; `pin-update <target>` сдвигает пин."""

    def setUp(self):
        super().setUp()
        self.init_cycles()
        self.add_synced_origin()
        self.old_sha = self.git("rev-parse", "HEAD").strip()
        (self.root / "next.txt").write_text("новый код пульта\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "новый main")
        self.target = self.git("rev-parse", "HEAD").strip()
        self.git("push", "-q", "origin", config.MAIN_BRANCH)
        self.git("reset", "-q", "--hard", self.old_sha)
        store.insert_canary_run(
            self.conn, "20260101T000000Z", "t", "01AAA", steps=1,
            cost_usd=0.1, review_iterations=0, escalations=0,
            outcome="killed", expected_escalation=None,
            actual_escalation=False, marker_mismatch=False,
            main_sha=self.target, verdict="green")
        self.ci_hook = None
        green = ci.MainLineStatus(ci.MAIN_GREEN, self.target, [], [], "",
                                  "CI main зелёный")

        def main_line_status(*args, **kwargs):
            if self.ci_hook is not None:
                hook, self.ci_hook = self.ci_hook, None
                hook()
            return green

        patcher = mock.patch.object(ci, "main_line_status", main_line_status)
        patcher.start()
        self.addCleanup(patcher.stop)

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def run_pin_update(self) -> tuple:
        """(вывод stdout+stderr, текст журнала, записанного командой)."""
        before = self.conn.execute("SELECT MAX(id) FROM steps").fetchone()[0] or 0
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            pin.cmd_pin_update(self.target)
        rows = self.conn.execute(
            "SELECT action, detail FROM steps WHERE id > ? ORDER BY id",
            (before,)).fetchall()
        journal = "\n".join(f"{r['action']}\n{r['detail'] or ''}" for r in rows)
        return self.strip_shas(out.getvalue() + err.getvalue()), self.strip_shas(journal)

    def strip_shas(self, text: str) -> str:
        for sha in (self.old_sha, self.target):
            text = text.replace(sha, "<sha>").replace(sha[:7], "<sha>")
        return text

    def late_cycles_on_first_leases_read(self, spawn) -> dict:
        """Обёртка `store.all_leases`: на первом чтении после того, как HEAD
        встал на целевой sha, зовёт `spawn()` (заводит циклы), затем отдаёт
        настоящий ответ. Возвращает словарь, куда `spawn` кладёт итог."""
        late = {}
        real_all_leases = store.all_leases

        def all_leases(conn):
            if not late and self.head() == self.target:
                late.update(spawn())
            return real_all_leases(conn)

        patcher = mock.patch.object(store, "all_leases", all_leases)
        patcher.start()
        self.addCleanup(patcher.stop)
        return late


class DoctorSandbox(CyclesMixin, TmpRootTest):
    """Схема БД во временном корне; проверка `doctor.check_stale_cycles`."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.init_cycles()

    def journal_pin(self) -> float:
        """Запись «pin обновлён»; момент пина — её метка, секунды эпохи."""
        store.journal(self.conn, config.PIN_UPDATE_JOURNAL_TASK_ID, "operator",
                      PIN_ACTION, "pin обновлён: aaaaaaa -> bbbbbbb")
        row = self.conn.execute(
            "SELECT ts FROM steps WHERE task_id=? AND action=? "
            "ORDER BY id DESC LIMIT 1",
            (config.PIN_UPDATE_JOURNAL_TASK_ID, PIN_ACTION)).fetchone()
        return datetime.strptime(row["ts"], "%Y-%m-%d %H:%M:%SZ").replace(
            tzinfo=timezone.utc).timestamp()

    def stale_check(self):
        check = doctor.check_stale_cycles(store.db())
        return check, f"{check.name}: {check.detail}"


class PinUpdateStartPrecisionTest(PinUpdateSandbox):
    """AC-1..AC-4 на выводе и журнале `pin-update`."""

    @unittest.skipUnless(PROC_AVAILABLE, "точный источник /proc есть только на Linux")
    def test_ac1_cycle_started_after_shift_is_not_named_with_proc(self):
        """Циклы стартуют через 0,25–0,6 с после сдвига пина, `/proc` доступна.

        Процессы запускаются на первом чтении `store.all_leases` после того,
        как HEAD встал на целевой sha, с паузой больше 0,1 с. Ни один из
        них не назван ни в выводе, ни в журнале `pin-update` — ни с
        пометкой, ни без неё.

        Ловит мутацию: на Linux время старта по-прежнему берётся из
        `ps -o lstart=` (или из `/proc` с целосекундным `btime`) — старт
        выходит раньше настоящего почти на 2 с (до 1 с), и поздний цикл
        попадает в перечень «старым» либо «пограничным» с пометкой.
        """
        def spawn():
            time.sleep(self.rng.uniform(0.25, 0.6))
            return {"cycles": [self.add_cycle()
                               for _ in range(self.rng.randint(1, 2))]}

        late = self.late_cycles_on_first_leases_read(spawn)

        output, journal = self.run_pin_update()

        self.assertTrue(late, self.msg(
            "store.all_leases не читался после сдвига пина — сценарий не разыгран"))
        self.assertEqual(self.head(), self.target, self.msg("пин не сдвинут"))
        for cycle in late["cycles"]:
            for where, text in (("вывод pin-update", output),
                                ("журнал pin-update", journal)):
                self.assertNotIn(cycle["tid"], text, self.msg(
                    f"{where}: назван цикл {cycle}, стартовавший после "
                    f"сдвига пина:\n{text}"))

    def test_ac2_ps_answer_straddling_shift_is_named_with_mark(self):
        """Ответ `ps` на целую секунду W раньше сдвига, а W + 2 с — позже.

        Сверка CI отпускает команду сразу за границей секунды W, так что
        сдвиг пина лежит в (W, W + 2]. Каждый цикл назван в выводе и в
        журнале строкой с id задачи, pid, временем старта, состоянием и
        командами `stop`/`auto`, а перечень несёт пометку «время старта не
        различимо от сдвига».

        Ловит мутацию: отбор сравнивает голый ответ `ps` с моментом сдвига
        и называет цикл «старым» без пометки; либо пограничный цикл
        выпадает из перечня как «новый»; либо строка пограничного цикла
        теряет состояние задачи или команду `stop <id>`.
        """
        cycles = [self.add_cycle() for _ in range(self.rng.randint(1, 3))]
        bound = {}

        def ci_hook():
            whole = math.floor(time.time()) + 1
            sleep_until(whole + 0.05)
            bound["W"] = whole
            for c in cycles:
                self.ps.answers[c["pid"]] = lstart_text(whole)
                c["years"] = years_of(whole)

        self.ci_hook = ci_hook

        with self.ps.active():
            output, journal = self.run_pin_update()
        finished = time.time()

        self.assertIn("W", bound, self.msg("сверка CI не вызвана — сценарий не разыгран"))
        self.assertLess(finished - bound["W"], 1.9, self.msg(
            "команда шла дольше 1,9 с после сверки CI — момент сдвига мог "
            "уйти за ответ ps + 2 с, сценарий не разыгран"))
        self.assertEqual(self.head(), self.target, self.msg("пин не сдвинут"))
        for where, text in (("вывод pin-update", output),
                            ("журнал pin-update", journal)):
            for c in cycles:
                line = self.cycle_line(text, c, where)
                self.assertNotIn(UNDETERMINED, line, self.msg(
                    f"{where}: ответ ps разборчив, а названо «{UNDETERMINED}»:\n{text}"))
            self.assertIn(BORDERLINE, text, self.msg(
                f"{where}: нет пометки «{BORDERLINE}»:\n{text}"))

    def test_ac3_ps_two_seconds_early_after_shift_is_not_named_silently(self):
        """Цикл стартует после сдвига, `ps` отдаёт его старт на 2 с раньше.

        Процессы запускаются на первом чтении `store.all_leases` после
        сдвига, сразу за границей целой секунды W; ответ `ps` для них — W −
        2 с, то есть на 2 с раньше настоящего старта и раньше момента
        сдвига. Цикл либо не назван ни в выводе, ни в журнале, либо назван
        вместе с пометкой «время старта не различимо от сдвига».

        Ловит мутацию: отбор доверяет голому ответу `ps` (`lstart <
        pin_moment` — значит старый) — цикл, загрузивший уже новый код,
        назван работающим на старом без всякой пометки.
        """
        def spawn():
            time.sleep(self.rng.uniform(0.0, 0.4))
            whole = math.floor(time.time()) + 1
            sleep_until(whole)
            cycles = [self.add_cycle() for _ in range(self.rng.randint(1, 2))]
            for c in cycles:
                self.ps.answers[c["pid"]] = lstart_text(whole - 2)
            return {"cycles": cycles}

        late = self.late_cycles_on_first_leases_read(spawn)

        with self.ps.active():
            output, journal = self.run_pin_update()

        self.assertTrue(late, self.msg(
            "store.all_leases не читался после сдвига пина — сценарий не разыгран"))
        for cycle in late["cycles"]:
            for where, text in (("вывод pin-update", output),
                                ("журнал pin-update", journal)):
                self.assert_silent_or_marked(text, cycle, where)

    def test_ac4_cycle_whose_whole_interval_precedes_shift_is_named_plainly(self):
        """Ответ `ps` на 3 с – час раньше начала команды.

        Весь интервал старта [ответ, ответ + 2 с) раньше сдвига: каждый
        цикл назван в выводе и журнале строкой с id задачи, pid, временем
        старта, состоянием и командами, пометки «время старта не различимо
        от сдвига» в перечне нет.

        Ловит мутацию: пометка ставится любому циклу, время которого взято
        из `ps` (интервал не сравнивается с моментом сдвига); либо интервал
        `ps` раздут в обе стороны и старый цикл стал «пограничным».
        """
        start = math.floor(time.time())
        cycles = [self.add_cycle() for _ in range(self.rng.randint(1, 3))]
        for c in cycles:
            answer = start - self.rng.randint(3, 3600)
            self.ps.answers[c["pid"]] = lstart_text(answer)
            c["years"] = years_of(answer)

        with self.ps.active():
            output, journal = self.run_pin_update()

        self.assertEqual(self.head(), self.target, self.msg("пин не сдвинут"))
        for where, text in (("вывод pin-update", output),
                            ("журнал pin-update", journal)):
            for c in cycles:
                line = self.cycle_line(text, c, where)
                self.assertNotIn(UNDETERMINED, line, self.msg(
                    f"{where}: ответ ps разборчив, а названо «{UNDETERMINED}»:\n{text}"))
            self.assertNotIn(BORDERLINE, text, self.msg(
                f"{where}: старый цикл помечен «{BORDERLINE}»:\n{text}"))

    def test_ac4_undetermined_start_is_marked_and_pin_still_moves(self):
        """Ни `/proc`, ни `ps` не дают времени старта (режим сбоя случайный).

        `ps` отвечает отказом запуска, ненулевым кодом, пустым ответом или
        мусором. Цикл назван с пометкой «не удалось определить»,
        `pin-update` завершается без отказа: HEAD на целевом sha, запись
        «pin обновлён» сделана.

        Ловит мутацию: неопределимое время старта превращено в интервал
        «−∞..+∞» и цикл называется «пограничным» или выпадает из перечня;
        либо сбой нового пути чтения времени не перехвачен и команда падает
        исключением уже после сдвига пина.
        """
        cycles = [self.add_cycle() for _ in range(self.rng.randint(1, 2))]
        mode = self.rng.choice(["raise", "rc1", "empty", "garbage"])
        print(f"режим сбоя: {mode}")
        for c in cycles:
            self.ps.answers[c["pid"]] = mode

        with self.ps.active():
            output, _journal = self.run_pin_update()

        self.assertEqual(self.head(), self.target, self.msg("пин не сдвинут"))
        rows = self.conn.execute(
            "SELECT 1 FROM steps WHERE task_id=? AND action=?",
            (config.PIN_UPDATE_JOURNAL_TASK_ID, PIN_ACTION)).fetchall()
        self.assertTrue(rows, self.msg("нет записи «pin обновлён»"))
        for c in cycles:
            lines = [ln for ln in output.splitlines() if c["tid"] in ln]
            self.assertTrue(lines, self.msg(
                f"цикл {c} с неопределимым временем выпал из перечня (режим "
                f"{mode}):\n{output}"))
            self.assertTrue(any(UNDETERMINED in ln for ln in lines), self.msg(
                f"у цикла {c} нет пометки «{UNDETERMINED}» (режим {mode}):\n{output}"))


class DoctorStartPrecisionTest(DoctorSandbox):
    """AC-1..AC-4 на предупреждении `doctor` «циклы на коде старше пина»."""

    @unittest.skipUnless(PROC_AVAILABLE, "точный источник /proc есть только на Linux")
    def test_ac1_doctor_does_not_name_cycle_started_after_pin_with_proc(self):
        """Циклы стартуют через 0,25–0,6 с после записи «pin обновлён».

        `/proc` доступна. Проверка `doctor` не называет ни одного из них.

        Ловит мутацию: на Linux время старта по-прежнему из `ps -o
        lstart=` (почти на 2 с раньше настоящего) — свежий цикл назван в
        предупреждении «старым» или «пограничным».
        """
        self.journal_pin()
        time.sleep(self.rng.uniform(0.25, 0.6))
        cycles = [self.add_cycle() for _ in range(self.rng.randint(1, 2))]

        _check, text = self.stale_check()

        for cycle in cycles:
            self.assertNotIn(cycle["tid"], text, self.msg(
                f"doctor назвал цикл {cycle}, стартовавший после пина:\n{text}"))

    def test_ac2_doctor_names_straddling_cycle_with_mark(self):
        """Ответ `ps` на 1 с раньше метки пина, ответ + 2 с — позже неё.

        Предупреждение «циклы на коде старше пина» называет каждый цикл
        строкой с id задачи, pid, временем старта, состоянием и командами
        `stop`/`auto` и несёт пометку «время старта не различимо от сдвига».

        Ловит мутацию: `doctor` классифицирует циклы иначе, чем `pin-update`
        (свой отбор без интервала) — пограничный цикл назван без пометки;
        либо он выпадает из предупреждения как «новый».
        """
        moment = self.journal_pin()
        cycles = [self.add_cycle() for _ in range(self.rng.randint(1, 3))]
        for c in cycles:
            self.ps.answers[c["pid"]] = lstart_text(moment - 1)
            c["years"] = years_of(moment - 1)

        with self.ps.active():
            check, text = self.stale_check()

        self.assertEqual(check.status, "warn", self.msg(f"нет предупреждения:\n{text}"))
        self.assertIn("старше пина", text, self.msg(text))
        for c in cycles:
            line = self.cycle_line(text, c, "doctor")
            self.assertNotIn(UNDETERMINED, line, self.msg(text))
        self.assertIn(BORDERLINE, text, self.msg(
            f"doctor: нет пометки «{BORDERLINE}»:\n{text}"))

    def test_ac3_doctor_ps_two_seconds_early_after_pin_is_not_named_silently(self):
        """Цикл стартует после записи пина, `ps` отдаёт старт на 2 с раньше.

        Процесс запускается сразу за первой границей целой секунды W после
        записи «pin обновлён»; ответ `ps` — W − 2 с, раньше метки пина.
        Цикл либо не назван в проверке `doctor`, либо назван с пометкой
        «время старта не различимо от сдвига».

        Ловит мутацию: `doctor` сравнивает голый ответ `ps` с меткой пина —
        свежий цикл назван «старым» без пометки.
        """
        self.journal_pin()
        time.sleep(self.rng.uniform(0.0, 0.4))
        whole = math.floor(time.time()) + 1
        sleep_until(whole)
        cycles = [self.add_cycle() for _ in range(self.rng.randint(1, 2))]
        for c in cycles:
            self.ps.answers[c["pid"]] = lstart_text(whole - 2)

        with self.ps.active():
            _check, text = self.stale_check()

        for cycle in cycles:
            self.assert_silent_or_marked(text, cycle, "doctor")

    def test_ac4_doctor_names_old_cycle_without_mark(self):
        """Ответ `ps` на 3 с – час раньше метки пина.

        Предупреждение называет каждый цикл полной строкой, пометки «время
        старта не различимо от сдвига» в нём нет.

        Ловит мутацию: `doctor` помечает пограничным любой цикл с временем
        из `ps`, не сравнивая конец интервала с меткой пина.
        """
        moment = self.journal_pin()
        cycles = [self.add_cycle() for _ in range(self.rng.randint(1, 3))]
        for c in cycles:
            answer = moment - self.rng.randint(3, 3600)
            self.ps.answers[c["pid"]] = lstart_text(answer)
            c["years"] = years_of(answer)

        with self.ps.active():
            check, text = self.stale_check()

        self.assertEqual(check.status, "warn", self.msg(f"нет предупреждения:\n{text}"))
        for c in cycles:
            line = self.cycle_line(text, c, "doctor")
            self.assertNotIn(UNDETERMINED, line, self.msg(text))
        self.assertNotIn(BORDERLINE, text, self.msg(
            f"doctor: старый цикл помечен «{BORDERLINE}»:\n{text}"))


if __name__ == "__main__":
    unittest.main()
