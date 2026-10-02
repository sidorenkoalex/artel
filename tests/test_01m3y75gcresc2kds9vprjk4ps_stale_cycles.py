"""`pin-update` и `doctor` называют живые циклы `auto`/`run`, чей процесс
стартовал раньше сдвига пина и поэтому исполняет прежний код пульта.

Группа: долгоживущий

Критерии приёмки, которые покрывает файл:

AC-1. После успешного `pin-update` цикл с lease этой машины и живым pid,
чей процесс стартовал раньше сдвига, назван в выводе и в журнале. Указаны
id задачи, pid, время старта, состояние задачи и команды `stop <id>` и
`auto <id>`.

AC-2. Цикл под наблюдением (есть строка `observed_runs` для его task_id и
pid) получает команду `auto <id> --client <client> --chat <chat>` со
значениями из связанной строки `observations`. Цикл без наблюдения
получает `auto <id>` без этих аргументов.

AC-3. Цикл, чей процесс стартовал после сдвига пина, в перечне
`pin-update` не назван.

AC-4. Lease с мёртвым pid в перечне `pin-update` не назван.

AC-5. Если время старта процесса определить не удалось, цикл назван с
пометкой «не удалось определить», а `pin-update` завершается успешно:
пин сдвинут, запись «pin обновлён» сделана.

AC-6. `pin-update` не шлёт сигналов процессам циклов: ни
`os.kill`/`os.killpg`, ни `liveness.terminate_process_group` не
вызываются.

AC-7. `doctor` выдаёт предупреждение «циклы на коде старше пина» с тем же
перечнем, что в AC-1, когда живой цикл этой машины стартовал раньше
последней записи «pin обновлён». Если такого цикла нет, предупреждения
нет.

Устройство сценариев. «Цикл» — настоящий дочерний процесс Python (спит,
пока тест его не снимет) и строка `leases` с его pid и именем этой
машины; время старта у него настоящее, из таблицы процессов ОС. `pin-
update` идёт в настоящем git-репозитории песочницы с bare `origin` и
зелёным прогоном канарейки на целевом sha, то есть сдвиг пина успешен.
Время старта у `ps` и метки журнала — с точностью до секунды, поэтому
между стартом процесса и моментом пина тест выдерживает паузу больше
секунды (`GAP_SEC`): иначе «раньше»/«позже» в пределах одной секунды
неразличимы и тест стал бы зависеть от удачи.

AC-3 требует процесс, который жив в момент составления перечня, но
стартовал ПОСЛЕ сдвига. Его заводит обёртка `store.all_leases` — SPEC
(«Контекст») называет её источником живых циклов: на первом её вызове
после того, как HEAD уже стоит на целевом sha, обёртка выдерживает паузу,
запускает процесс и заводит его lease, затем отдаёт настоящий ответ.
Тест проверяет, что обёртка сработала, — иначе сценарий AC-3 не
разыгран бы вовсе.

AC-6: проверка живости `os.kill(pid, 0)` сигнала не шлёт (это сверка
адресуемости, тот же приём `liveness`, на который ссылается SPEC
«Материалы» для отбора живых lease), поэтому запрещён `os.kill` с
ненулевым сигналом, любой `os.killpg` и `liveness.terminate_process_group`.
Подмены их не исполняют — ни один процесс сигнала не получит, даже если
реализация его пошлёт.

AC-5: время старта ломается подменой `subprocess`: каждая команда, кроме
git (без него `pin-update` не сдвинет пин), случайным образом отвечает
отказом запуска, ненулевым кодом, пустым ответом или мусором. Так
покрываются все три случая требования 4 («ошибка вызова, пустой или
неразборчивый ответ»), не завися от того, какой системной утилитой
реализация читает таблицу процессов.

AC-7: проверка ищется среди `doctor.all_checks` по содержанию — проверка
со статусом `warn`, чей текст называет «старше пина» (SPEC не фиксирует
имя проверки, только текст предупреждения). Внешние команды `doctor`
(CLI ролей, git, сеть) не исполняются: исполняются только утилиты
сведений о процессах (`ps`, `sysctl`, `lsof`), прочее отвечает отказом
запуска — тот же приём, что у `tests/test_doctor.py`.

Идентификаторы задач, состояния, число циклов, клиенты и чаты
наблюдений — случайные при каждом запуске; зерно печатается и входит в
текст каждого провала.

Красен до реализации: `pin-update` печатает и журналирует только «pin
обновлён: <old> -> <new>», о живых циклах не сообщает, а проверки
`doctor` «циклы на коде старше пина» нет — ни id задачи, ни команд
`stop`/`auto`, ни пометки «не удалось определить» в выводе нет.
"""
import os
import random
import socket
import subprocess
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from orchestrator import config, doctor, liveness, pin, store
from tests.sandbox import RealGitSandbox, TmpRootTest, _dead_pid

GAP_SEC = 1.5
ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
UNDETERMINED = "не удалось определить"
PROCESS_INFO_TOOLS = ("ps", "sysctl", "lsof")
REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen
REAL_KILL = os.kill


class _CyclesMixin:
    """Общая часть сценариев: случайность, циклы-процессы, lease, задачи."""

    def init_cycles(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.host = socket.gethostname()
        self.used_ids = set()

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

        def _cleanup():
            proc.kill()
            proc.wait(timeout=10)

        self.addCleanup(_cleanup)
        return proc.pid

    def add_cycle(self, pid: int = None, state: str = None) -> dict:
        """Задача в случайном состоянии и lease этой машины с pid цикла."""
        tid = self.new_task_id()
        state = state or self.rng.choice(sorted(config.STATE_ROLE))
        pid = self.spawn_process() if pid is None else pid
        store.insert_task(self.conn, tid, f"цикл {tid}", state,
                          f"task/{tid.lower()}", config.DEFAULT_TARGET, 5.0)
        store.insert_lease(self.conn, tid, f"sess-{self.rng.randrange(10**9)}",
                           pid, self.host, store.now())
        return {"tid": tid, "pid": pid, "state": state}

    def observe(self, cycle: dict, pid: int = None) -> tuple:
        """Наблюдение задачи цикла и строка `observed_runs` с данным pid."""
        client = f"client{self.rng.randrange(10**6)}"
        chat = f"chat{self.rng.randrange(10**6)}"
        obs = store.register_observation(
            self.conn, config.DEFAULT_TARGET, client, chat,
            f"sess-{self.rng.randrange(10**9)}", [cycle["tid"]])
        store.record_observed_run(self.conn, obs, cycle["tid"],
                                  cycle["pid"] if pid is None else pid,
                                  f"log-{self.rng.randrange(10**6)}.log")
        return client, chat

    def assert_cycle_named(self, text: str, cycle: dict, where: str) -> None:
        """AC-1: id задачи, pid, время старта, состояние, `stop`/`auto`."""
        tid = cycle["tid"]
        for needle in (tid, str(cycle["pid"]), cycle["state"],
                       f"stop {tid}", f"auto {tid}"):
            self.assertIn(needle, text, self.msg(
                f"{where}: цикл {cycle} не назван полностью — нет «{needle}»:\n{text}"))
        self.assertNotIn(UNDETERMINED, text, self.msg(
            f"{where}: время старта живого процесса определимо, а названо "
            f"«{UNDETERMINED}»:\n{text}"))
        years = {str(datetime.now().year), str(datetime.now(timezone.utc).year)}
        self.assertTrue(any(y in text for y in years), self.msg(
            f"{where}: нет времени старта процесса (год {years}):\n{text}"))

    def assert_auto_plain(self, text: str, tid: str, where: str) -> None:
        """AC-2: каждая команда `auto <id>` — без `--client`/`--chat`."""
        needle = f"auto {tid}"
        start = text.find(needle)
        self.assertNotEqual(start, -1, self.msg(f"{where}: нет «{needle}»:\n{text}"))
        while start != -1:
            tail = text[start + len(needle):].split("\n", 1)[0]
            self.assertNotIn("--client", tail, self.msg(
                f"{where}: цикл без наблюдения получил аргументы наблюдения: "
                f"«{needle}{tail}»"))
            self.assertNotIn("--chat", tail, self.msg(
                f"{where}: цикл без наблюдения получил аргументы наблюдения: "
                f"«{needle}{tail}»"))
            start = text.find(needle, start + 1)


class _PinUpdateSandbox(_CyclesMixin, RealGitSandbox):
    """Настоящий git с bare `origin`; целевой sha — коммит впереди HEAD,
    уже известный локально, с зелёным прогоном канарейки на нём:
    `pin-update <target>` сдвигает пин успешно."""

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

    def last_step_id(self) -> int:
        row = self.conn.execute("SELECT MAX(id) FROM steps").fetchone()
        return row[0] or 0

    def run_pin_update(self) -> tuple:
        """(вывод stdout+stderr, текст журнала, записанного командой)."""
        before = self.last_step_id()
        out, err = _Buffer(), _Buffer()
        with mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            pin.cmd_pin_update(self.target)
        rows = self.conn.execute(
            "SELECT action, detail FROM steps WHERE id > ? ORDER BY id",
            (before,)).fetchall()
        journal = "\n".join(f"{r['action']}\n{r['detail'] or ''}" for r in rows)
        return self.strip_shas(out.text + err.text), self.strip_shas(journal)

    def strip_shas(self, text: str) -> str:
        """sha в тексте могут случайно нести цифры года — убираются."""
        for sha in (self.old_sha, self.target):
            text = text.replace(sha, "<sha>").replace(sha[:7], "<sha>")
        return text

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()


class _Buffer:
    def __init__(self):
        self.parts = []

    def write(self, s):
        self.parts.append(s)
        return len(s)

    def flush(self):
        pass

    @property
    def text(self) -> str:
        return "".join(self.parts)


class PinUpdateNamesStaleCyclesTest(_PinUpdateSandbox):
    """AC-1/AC-2: перечень живых циклов, стартовавших до сдвига пина."""

    def test_ac1_cycles_started_before_shift_are_named_in_output_and_journal(self):
        """Несколько живых циклов этой машины стартовали до `pin-update`.

        После успешного сдвига пина каждый назван и в выводе команды, и в
        журнале: id задачи, pid, время старта процесса, текущее состояние
        задачи, команды `stop <id>` и `auto <id>`.

        Ловит мутацию: перечень печатается, но в журнал не пишется (или
        наоборот) — запись «pin обновлён» и соседние записи не называют
        id задачи и pid; либо строка цикла теряет состояние задачи или
        команду `stop <id>`; либо время старта не определяется и
        подставляется «не удалось определить» для живого процесса.
        """
        cycles = [self.add_cycle() for _ in range(self.rng.randint(1, 3))]
        time.sleep(GAP_SEC)

        output, journal = self.run_pin_update()

        self.assertEqual(self.head(), self.target, self.msg("пин не сдвинут"))
        for cycle in cycles:
            self.assert_cycle_named(output, cycle, "вывод pin-update")
            self.assert_cycle_named(journal, cycle, "журнал pin-update")

    def test_ac2_observed_cycle_gets_client_and_chat_unobserved_does_not(self):
        """Два живых цикла до сдвига: один под наблюдением, другой без.

        У наблюдаемого (строка `observed_runs` с его task_id и pid) команда
        `auto <id> --client <client> --chat <chat>` со значениями из его
        строки `observations`. У второго тоже есть строка `observed_runs`
        по его задаче, но с pid прежнего запуска, — он считается не под
        наблюдением и получает `auto <id>` без аргументов.

        Ловит мутацию: признак наблюдения сверяется только по task_id без
        pid — цикл, у задачи которого наблюдался прежний запуск, получает
        `--client/--chat` старого наблюдения; либо аргументы наблюдения не
        добавляются вовсе и наблюдаемый цикл получает голый `auto <id>`.
        """
        observed = self.add_cycle()
        plain = self.add_cycle()
        client, chat = self.observe(observed)
        stale_client, stale_chat = self.observe(plain, pid=_dead_pid())
        time.sleep(GAP_SEC)

        output, journal = self.run_pin_update()

        expected = f"auto {observed['tid']} --client {client} --chat {chat}"
        for where, text in (("вывод pin-update", output),
                            ("журнал pin-update", journal)):
            self.assertIn(expected, text, self.msg(
                f"{where}: нет команды «{expected}»:\n{text}"))
            self.assert_auto_plain(text, plain["tid"], where)
            self.assertNotIn(stale_client, text, self.msg(
                f"{where}: клиент наблюдения прежнего запуска приписан живому "
                f"циклу:\n{text}"))
            self.assertNotIn(stale_chat, text, self.msg(
                f"{where}: чат наблюдения прежнего запуска приписан живому "
                f"циклу:\n{text}"))


class PinUpdateSelectionTest(_PinUpdateSandbox):
    """AC-3/AC-4: в перечень не попадают циклы новее пина и мёртвые lease."""

    def test_ac3_cycle_started_after_shift_is_not_named(self):
        """Цикл, стартовавший до сдвига, и цикл, стартовавший после.

        Второй процесс запускается и получает lease уже после того, как
        HEAD встал на целевой sha (на первом чтении `store.all_leases`
        после сдвига, с паузой больше секунды). В перечне назван только
        первый.

        Ловит мутацию: время старта процесса не сравнивается с моментом
        сдвига (в перечень идёт любой живой lease этой машины) либо
        сравнение перевёрнуто — процесс, загрузивший уже новый код,
        назван как работающий на старом.
        """
        early = self.add_cycle()
        time.sleep(GAP_SEC)
        late = {}
        real_all_leases = store.all_leases

        def all_leases_with_late_cycle(conn):
            if not late and self.head() == self.target:
                time.sleep(GAP_SEC)
                late.update(self.add_cycle())
            return real_all_leases(conn)

        with mock.patch.object(store, "all_leases", all_leases_with_late_cycle):
            output, journal = self.run_pin_update()

        self.assertTrue(late, self.msg(
            "store.all_leases не читался после сдвига пина — сценарий "
            "«цикл стартовал после сдвига» не разыгран"))
        self.assert_cycle_named(output, early, "вывод pin-update")
        for where, text in (("вывод pin-update", output),
                            ("журнал pin-update", journal)):
            self.assertNotIn(late["tid"], text, self.msg(
                f"{where}: назван цикл {late}, стартовавший после сдвига "
                f"пина:\n{text}"))

    def test_ac4_lease_with_dead_pid_is_not_named(self):
        """Lease этой машины с мёртвым pid рядом с живым циклом.

        Живой цикл назван, задача мёртвого lease — нет.

        Ловит мутацию: живость pid не проверяется (в перечень идёт любой
        lease этой машины) — мёртвый pid получает предложение `stop`/
        `auto`, хотя цикла уже нет.
        """
        alive = self.add_cycle()
        dead = [self.add_cycle(pid=_dead_pid())
                for _ in range(self.rng.randint(1, 2))]
        time.sleep(GAP_SEC)

        output, journal = self.run_pin_update()

        self.assert_cycle_named(output, alive, "вывод pin-update")
        for cycle in dead:
            for where, text in (("вывод pin-update", output),
                                ("журнал pin-update", journal)):
                self.assertNotIn(cycle["tid"], text, self.msg(
                    f"{where}: назван lease с мёртвым pid {cycle}:\n{text}"))


class PinUpdateRobustnessTest(_PinUpdateSandbox):
    """AC-5/AC-6: отказ определить время старта и отсутствие сигналов."""

    def test_ac5_undetermined_start_time_is_marked_and_pin_still_moves(self):
        """Время старта процесса определить нельзя.

        Каждая внешняя команда, кроме git, отвечает одним из сбоев (выбор
        случайный по зерну): отказ запуска, ненулевой код, пустой ответ,
        мусор. Цикл всё равно назван с пометкой «не удалось определить»,
        `pin-update` завершается без отказа, HEAD на целевом sha, запись
        «pin обновлён» сделана.

        Ловит мутацию: сбой чтения времени старта не перехвачен — команда
        падает исключением или `sys.exit` уже после сдвига пина, без
        записи «pin обновлён»; либо цикл с неопределённым временем молча
        выпадает из перечня (сравнение с моментом сдвига на `None` даёт
        «не раньше»).
        """
        cycle = self.add_cycle()
        time.sleep(GAP_SEC)
        mode = self.rng.choice(["raise", "rc1", "empty", "garbage"])
        print(f"режим сбоя: {mode}")

        def is_git(cmd) -> bool:
            argv = [cmd] if isinstance(cmd, (str, bytes)) else list(cmd)
            return bool(argv) and Path(str(argv[0]).split()[0]).name == "git"

        def broken_run(cmd, *args, **kwargs):
            if is_git(cmd):
                return REAL_RUN(cmd, *args, **kwargs)
            if mode == "raise":
                raise FileNotFoundError("песочница: сведения о процессе недоступны")
            text = bool(kwargs.get("text") or kwargs.get("universal_newlines")
                        or kwargs.get("encoding"))
            body = {"rc1": "", "empty": "", "garbage": "??? не время ???\n"}[mode]
            code = 1 if mode == "rc1" else 0
            out = body if text else body.encode()
            if kwargs.get("check") and code:
                raise subprocess.CalledProcessError(code, cmd, out, out)
            return subprocess.CompletedProcess(cmd, code, out, out)

        def broken_popen(cmd, *args, **kwargs):
            if is_git(cmd):
                return REAL_POPEN(cmd, *args, **kwargs)
            raise FileNotFoundError("песочница: сведения о процессе недоступны")

        with mock.patch.object(subprocess, "run", broken_run), \
                mock.patch.object(subprocess, "Popen", broken_popen):
            output, journal = self.run_pin_update()

        self.assertEqual(self.head(), self.target, self.msg("пин не сдвинут"))
        rows = self.conn.execute(
            "SELECT 1 FROM steps WHERE task_id=? AND action=?",
            (config.PIN_UPDATE_JOURNAL_TASK_ID, "pin обновлён")).fetchall()
        self.assertTrue(rows, self.msg("нет записи «pin обновлён»"))
        self.assertIn(cycle["tid"], output, self.msg(
            f"цикл с неопределённым временем старта выпал из перечня:\n{output}"))
        self.assertIn(UNDETERMINED, output, self.msg(
            f"нет пометки «{UNDETERMINED}» (режим {mode}):\n{output}"))

    def test_ac6_pin_update_sends_no_signals_to_cycles(self):
        """Живые циклы до сдвига, `pin-update` со шпионами сигналов.

        Ни `os.kill` с ненулевым сигналом, ни `os.killpg`, ни
        `liveness.terminate_process_group` не вызваны; циклы по-прежнему
        названы (перечень есть, команда не ушла по пути «тихо ничего не
        сделать»), процессы циклов живы.

        Ловит мутацию: `pin-update` «помогает» Оператору и сам гасит
        устаревший цикл — `liveness.terminate_process_group(pgid)` или
        `os.kill(pid, SIGTERM)` по pid из lease.
        """
        cycles = [self.add_cycle() for _ in range(self.rng.randint(1, 2))]
        time.sleep(GAP_SEC)
        signals = []

        def spy_kill(pid, sig):
            if sig == 0:
                return REAL_KILL(pid, sig)
            signals.append(("os.kill", pid, sig))

        def spy_killpg(pgid, sig):
            signals.append(("os.killpg", pgid, sig))

        def spy_terminate(*args, **kwargs):
            signals.append(("liveness.terminate_process_group", args, kwargs))

        with mock.patch.object(os, "kill", spy_kill), \
                mock.patch.object(os, "killpg", spy_killpg), \
                mock.patch.object(liveness, "terminate_process_group", spy_terminate):
            output, _journal = self.run_pin_update()

        self.assertEqual(signals, [], self.msg(f"pin-update слал сигналы: {signals}"))
        for cycle in cycles:
            self.assertIn(cycle["tid"], output, self.msg(
                f"цикл {cycle} не назван:\n{output}"))
            REAL_KILL(cycle["pid"], 0)


class _DoctorSandbox(_CyclesMixin, TmpRootTest):
    """Песочница `doctor.all_checks`: схема БД, дом во временном каталоге,
    внешние команды кроме утилит сведений о процессах не исполняются."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.init_cycles()
        home = self.root / "dom"
        home.mkdir()
        patcher = mock.patch.object(Path, "home", lambda *a, **k: home)
        patcher.start()
        self.addCleanup(patcher.stop)

    def journal_pin(self) -> None:
        store.journal(self.conn, config.PIN_UPDATE_JOURNAL_TASK_ID, "operator",
                      "pin обновлён", "pin обновлён: aaaaaaa -> bbbbbbb")

    def stale_warnings(self) -> list:
        def allowed(cmd) -> bool:
            argv = [cmd] if isinstance(cmd, (str, bytes)) else list(cmd)
            return bool(argv) and Path(str(argv[0]).split()[0]).name in PROCESS_INFO_TOOLS

        def run(cmd, *args, **kwargs):
            if allowed(cmd):
                return REAL_RUN(cmd, *args, **kwargs)
            raise FileNotFoundError("песочница: внешний процесс не запускается")

        def popen(cmd, *args, **kwargs):
            if allowed(cmd):
                return REAL_POPEN(cmd, *args, **kwargs)
            raise FileNotFoundError("песочница: внешний процесс не запускается")

        with mock.patch.object(subprocess, "run", run), \
                mock.patch.object(subprocess, "Popen", popen):
            checks = doctor.all_checks(store.db())
        return [c for c in checks if c.status == "warn"
                and "старше пина" in f"{c.name} {c.detail}".lower()]


class DoctorStaleCyclesTest(_DoctorSandbox):
    """AC-7: предупреждение `doctor` «циклы на коде старше пина»."""

    def test_ac7_doctor_warns_about_cycle_older_than_last_pin_record(self):
        """Две записи «pin обновлён»; цикл A стартовал между ними, B — после.

        Момент пина — ПОСЛЕДНЯЯ запись журнала: A старше её и назван в
        предупреждении тем же перечнем, что у `pin-update` (id задачи,
        pid, время старта, состояние, `stop`/`auto`), B новее и не назван.

        Ловит мутацию: момент пина берётся из первой (самой старой)
        записи «pin обновлён» — A оказывается «после пина» и
        предупреждения нет; либо предупреждение называет все живые
        циклы, включая B, стартовавший уже после последнего пина.
        """
        self.journal_pin()
        time.sleep(GAP_SEC)
        older = self.add_cycle()
        time.sleep(GAP_SEC)
        self.journal_pin()
        time.sleep(GAP_SEC)
        newer = self.add_cycle()

        warnings = self.stale_warnings()

        text = "\n".join(f"{c.name}: {c.detail}" for c in warnings)
        self.assertTrue(warnings, self.msg(
            "нет предупреждения «циклы на коде старше пина»"))
        self.assert_cycle_named(text, older, "doctor")
        self.assertNotIn(newer["tid"], text, self.msg(
            f"doctor назвал цикл {newer}, стартовавший после пина:\n{text}"))

    def test_ac7_doctor_is_silent_without_cycles_older_than_pin(self):
        """Живые циклы есть, но все стартовали после последней записи пина.

        Плюс lease с мёртвым pid. Предупреждения «циклы на коде старше
        пина» нет вовсе.

        Ловит мутацию: проверка выдаёт `warn` всегда, даже с пустым
        перечнем; либо сравнение момента старта с моментом пина
        перевёрнуто и предупреждение называет свежие циклы.
        """
        self.journal_pin()
        time.sleep(GAP_SEC)
        for _ in range(self.rng.randint(1, 2)):
            self.add_cycle()
        self.add_cycle(pid=_dead_pid())

        warnings = self.stale_warnings()

        self.assertEqual(warnings, [], self.msg(
            f"предупреждение без циклов старше пина: {warnings}"))


if __name__ == "__main__":
    unittest.main()
