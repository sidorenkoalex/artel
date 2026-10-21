"""Команда `canary live`: показ реестра живого прогона канарейки и снятие зависшего `--drop <run_stamp> "<основание>"`.

Группа: долгоживущий
Красен до реализации: подкоманды `canary live` нет — `artel.py canary live …` уходит в разбор прогона канарейки и отказывает «нужен параметр --k»: реестр не показывается, ничего не снимается, строки журнала `operator` нет, справка подкоманду не называет.

Связка, которую держит файл: «публичный вход `artel.main()` с argv `canary
live …` — каталог реестра под корнем песочницы — журнал пульта». Песочница
— `tests.sandbox.InitializedTmpRootTest`: пути `config` во временном
каталоге, БД со схемой. Каталог реестра —
`config.ROOT/.artel/config.CANARY_LIVE_DIRNAME`; запись —
`<run_stamp>-<pid>.json` (поля записи части А плюс подложенные вручную
`parent_pid` и шаблон), метка — `<run_stamp>.lock` с pid текстом. Живой
процесс прогона — дочерний процесс-сон (он же проверяет, что сигнала не
было), мёртвый — pid завершённого и дождавшегося процесса. Время старта
процесса в записи — `doctor.process_start_time` того же pid; возраст записи
— поле `started_at`, возраст метки — время правки (`os.utime`). Ожидания по
часам нет.

Формат длительностей SPEC не задаёт: возраст и остаток ищутся в выводе в
любом из естественных видов (часы с дробью, часы и минуты, минуты,
секунды, `Ч:ММ[:СС]`), моменты-даты из текста перед этим вырезаются.

Значения `run_stamp`, pid родителя, шаблон, набор, основания и возрасты
порождаются от зерна; зерно печатается и входит в текст каждого провала.
"""
import contextlib
import io
import json
import os
import random
import re
import subprocess
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from orchestrator import artel, canary, config, doctor, store
from tests.sandbox import InitializedTmpRootTest

STAMP_FORMAT = "%Y%m%dT%H%M%SZ"
EMPTY = "живых прогонов канарейки нет"
NOTHING_TO_DROP = ("снимать нечего; дождись итога или используй "
                   "--during-canary у конкретной команды")
ROLE_REFUSAL = "команда недоступна процессу роли"
OLD_PARSER_REFUSAL = "нужен параметр --k"
ISO_MOMENT = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?"
                        r"(?:Z|[+-]\d{2}:?\d{2})?")


def durations(text: str) -> list:
    """Длительности (в секундах), записанные в тексте в любом естественном виде."""
    text = ISO_MOMENT.sub(" ", text)
    found = []

    def num(value: str) -> float:
        return float(value.replace(",", "."))

    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(?:ч|h)(?:[^\w]|$)"
                         r"(?:\s*(\d+)\s*(?:мин|м|m)(?:[^\w]|$))?", text):
        found.append(num(m.group(1)) * 3600 + (int(m.group(2)) * 60 if m.group(2) else 0))
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(?:мин|m\b)", text):
        found.append(num(m.group(1)) * 60)
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(?:с|сек|s)(?:[^\w]|$)", text):
        found.append(num(m.group(1)))
    for m in re.finditer(r"(?:(\d+) days?, )?(?<![\d:])(\d{1,3}):(\d{2})(?::(\d{2}))?(?![\d:])",
                         text):
        days = int(m.group(1) or 0)
        found.append(days * 86400 + int(m.group(2)) * 3600 + int(m.group(3)) * 60
                     + int(m.group(4) or 0))
    return found


class CanaryLiveCommandTest(InitializedTmpRootTest):
    """Каталог реестра песочницы, живые и мёртвые pid настоящих дочерних процессов."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used = set()
        self.children = []

    # ------------------------------------------------------------ фикстуры

    def msg(self, text) -> str:
        return f"зерно: {self.seed}; {text}"

    def registry(self) -> Path:
        path = Path(config.ROOT) / ".artel" / config.CANARY_LIVE_DIRNAME
        path.mkdir(parents=True, exist_ok=True)
        return path

    def stamp(self) -> str:
        while True:
            moment = datetime(2031, 1, 1, tzinfo=timezone.utc) + timedelta(
                seconds=self.rng.randrange(300 * 24 * 3600))
            text = moment.strftime(STAMP_FORMAT)
            if text not in self.used:
                self.used.add(text)
                return text

    def token(self, n: int = 8) -> str:
        return "".join(self.rng.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(n))

    def live(self) -> subprocess.Popen:
        proc = subprocess.Popen([sys.executable, "-c",
                                 "import time; time.sleep(600)"])
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        return proc

    @staticmethod
    def dead_pid() -> int:
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        return proc.pid

    def put_mark(self, stamp: str, pid, age: float = 5.0) -> Path:
        mark = self.registry() / f"{stamp}.lock"
        mark.write_text(f"{pid}\n", encoding="utf-8")
        moment = time.time() - age
        os.utime(mark, (moment, moment))
        return mark

    def put_record(self, stamp: str, pid: int, *, tasks: int = 1, age: float = 600.0,
                   start_known: bool = True, **extra) -> Path:
        started = doctor.process_start_time(pid) if start_known else None
        if start_known:
            self.assertIsNotNone(started, self.msg(f"время старта pid {pid} не определилось"))
        payload = {
            "pid": pid,
            "process_start": None if started is None else started.isoformat(),
            "run_stamp": stamp, "sha": f"{self.rng.randrange(16 ** 40):040x}",
            "set_name": config.CANARY_DEFAULT_SET,
            "started_at": (datetime.now(timezone.utc)
                           - timedelta(seconds=age)).isoformat(),
            "tasks": tasks}
        payload.update(extra)
        record = self.registry() / f"{stamp}-{pid}.json"
        record.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return record

    def cli(self, *argv: str) -> tuple:
        """(код выхода, stdout+stderr) `artel.main()` с argv Оператора."""
        out = io.StringIO()
        code = 0
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                artel.main()
            except SystemExit as exc:
                if isinstance(exc.code, str):
                    out.write(f"\n{exc.code}")
                    code = 1
                else:
                    code = exc.code or 0
        return code, out.getvalue()

    def rows(self) -> list:
        return [dict(r) for r in store.all_steps(store.db())]

    def swept(self, rows=None) -> list:
        rows = self.rows() if rows is None else rows
        return [r for r in rows if r["action"] == canary.LIVE_RUN_SWEPT_ACTION]

    def operator_rows(self, rows=None) -> list:
        rows = self.rows() if rows is None else rows
        return [r for r in rows if r["actor"] == "operator"]

    def reason(self) -> str:
        return f"основание {self.token()} {self.rng.randrange(10 ** 6)}"

    def assert_duration(self, out: str, expected: float, tolerance: float, what: str):
        found = durations(out)
        self.assertTrue(any(abs(value - expected) <= tolerance for value in found),
                        self.msg(f"{what} ≈ {expected:.0f} с (±{tolerance:.0f}) нет в "
                                 f"выводе; длительности {found}:\n{out}"))

    # -------------------------------------------------------------- AC-7

    def record_age(self, tasks: int) -> float:
        """Возраст записи (доля часа ≥ 0.5) и остаток, не совпадающий по времени суток с началом."""
        timeout = canary.CANARY_DRIVE_TIMEOUT_SEC
        ages = [m * 60 for m in (*range(95, 116, 5), *range(155, 176, 5))]
        self.rng.shuffle(ages)
        now = datetime.now(timezone.utc)
        for age in ages:
            rest = (timeout * tasks + 3600 - age) % 86400
            start = now - timedelta(seconds=age)
            clocks = [start.hour * 3600 + start.minute * 60]
            local = start.astimezone()
            clocks.append(local.hour * 3600 + local.minute * 60)
            if all(min(abs(rest - c), 86400 - abs(rest - c)) > 2 * 3600 for c in clocks):
                return float(age)
        return float(ages[0])

    def test_ac7_shows_record_mark_and_empty_registry(self):
        """`canary live` без аргументов: по записи, по метке без записи и на пустом реестре.

        Запись живого процесса с `tasks` = N (случайное), подложенными
        `parent_pid` и шаблоном: в выводе `run_stamp`, pid, `parent_pid`,
        шаблон, sha7, набор, время начала (сам текст `started_at` либо его
        дата и `ЧЧ:ММ` в UTC или местном времени), возраст и остаток
        `CANARY_DRIVE_TIMEOUT_SEC` × N + 1 ч − возраст (допуск полчаса; доля
        часа возраста выбрана так, что и отбрасывание дробной части, и
        округление укладываются в допуск). Метка без записи с живым pid: её
        `run_stamp`, pid и возраст по времени правки. Каталога нет и каталог
        пуст: «живых прогонов канарейки нет». Код выхода — 0.

        Ловит мутацию: остаток считается без `+ 1 ч` или без умножения на
        число задач (расхождение на час и больше), либо метки без записи в
        показе нет, либо `parent_pid`/шаблон записи не выводятся.
        """
        for where in ("каталога нет", "каталог пуст"):
            with self.subTest(реестр=where):
                if where == "каталог пуст":
                    self.registry()
                code, out = self.cli("canary", "live")
                self.assertEqual(code, 0, self.msg(out))
                self.assertIn(EMPTY, out, self.msg(out))

        tasks = self.rng.randint(1, 4)
        age = self.record_age(tasks)
        proc = self.live()
        stamp = self.stamp()
        parent = self.rng.randrange(2, 99999)
        template = f"shablon-{self.token(6)}"
        set_name = f"nabor-{self.token(5)}"
        record = self.put_record(stamp, proc.pid, tasks=tasks, age=age,
                                 parent_pid=parent, template=template,
                                 templates=[template], set_name=set_name)
        mark = self.put_mark(stamp, proc.pid)
        entry = json.loads(record.read_text(encoding="utf-8"))
        code, out = self.cli("canary", "live")
        self.assertEqual(code, 0, self.msg(out))
        for label, value in (("run_stamp", stamp), ("pid", str(proc.pid)),
                             ("parent_pid", str(parent)), ("шаблон", template),
                             ("sha7", entry["sha"][:7]), ("набор", set_name)):
            self.assertIn(value, out, self.msg(f"{label} нет в выводе:\n{out}"))
        start = datetime.fromisoformat(entry["started_at"])
        spellings = [entry["started_at"]]
        for moment in (start, start.astimezone()):
            spellings.append((moment.strftime("%Y-%m-%d"), moment.strftime("%H:%M")))
        self.assertTrue(
            entry["started_at"] in out or any(isinstance(s, tuple) and s[0] in out
                                              and s[1] in out for s in spellings),
            self.msg(f"время начала {entry['started_at']} нет в выводе:\n{out}"))
        self.assert_duration(out, age, 3600, "возраст записи")
        remaining = canary.CANARY_DRIVE_TIMEOUT_SEC * tasks + 3600 - age
        self.assert_duration(out, remaining, 1800, "остаток до потолка")
        record.unlink()
        mark.unlink()

        other = self.live()
        mark_stamp = self.stamp()
        mark_age = self.rng.uniform(1.6, 5.4) * 3600
        mark = self.put_mark(mark_stamp, other.pid, mark_age)
        code, out = self.cli("canary", "live")
        self.assertEqual(code, 0, self.msg(out))
        self.assertIn(mark_stamp, out, self.msg(out))
        self.assertIn(str(other.pid), out, self.msg(out))
        self.assertNotIn(EMPTY, out, self.msg(out))
        self.assert_duration(out, mark_age, 3600, "возраст метки")
        self.assertTrue(mark.exists(), self.msg("показ убрал живую метку"))

    # -------------------------------------------------------------- AC-8

    def test_ac8_show_sweeps_dead_record_and_dead_mark(self):
        """`canary live` при мёртвой записи (с её меткой), метке без записи с мёртвым pid и одной живой записи.

        Наблюдение: файлы мёртвых убраны, в журнале пульта на каждую — новая
        строка `LIVE_RUN_SWEPT_ACTION`; их `run_stamp` в выводе нет; живая
        запись показана и осталась.

        Ловит мутацию: показ читает каталог в обход уборки чтения реестра —
        мёртвая запись или мёртвая метка показаны как живые и остаются на
        диске без строки журнала.
        """
        dead_stamp, mark_stamp, live_stamp = self.stamp(), self.stamp(), self.stamp()
        dead = self.dead_pid()
        dead_record = self.put_record(dead_stamp, dead, start_known=False)
        dead_record_mark = self.put_mark(dead_stamp, dead)
        dead_mark = self.put_mark(mark_stamp, self.dead_pid())
        proc = self.live()
        live_record = self.put_record(live_stamp, proc.pid)
        before = len(self.swept())
        code, out = self.cli("canary", "live")
        self.assertEqual(code, 0, self.msg(out))
        for path in (dead_record, dead_record_mark, dead_mark):
            self.assertFalse(path.exists(), self.msg(f"{path.name} не убран:\n{out}"))
        self.assertGreaterEqual(len(self.swept()) - before, 2, self.msg(self.swept()))
        self.assertNotIn(dead_stamp, out, self.msg(out))
        self.assertNotIn(mark_stamp, out, self.msg(out))
        self.assertIn(live_stamp, out, self.msg(out))
        self.assertTrue(live_record.exists(), self.msg("живая запись убрана"))

    # -------------------------------------------------------------- AC-9

    def drop(self, stamp: str, reason: str) -> tuple:
        return self.cli("canary", "live", "--drop", stamp, reason)

    def test_ac9_drop_removes_each_droppable_case_without_signal(self):
        """`--drop` снимает (а) запись старше `CANARY_DRIVE_TIMEOUT_SEC`, (б) запись без времени старта, (в) метку без записи, а также две такие записи одного `run_stamp`.

        Во всех случаях процесс прогона жив и после снятия (сигнала не
        получил), файлы снятого исчезли; метка `run_stamp`, рядом с которой
        не осталось записей, снята. Код выхода — 0.

        Ловит мутацию: снимается только первая из записей `run_stamp`
        (вторая остаётся), либо метка остаётся после снятия последней
        записи, либо случай (б)/(в) отказывает как «прогон жив».
        """
        timeout = canary.CANARY_DRIVE_TIMEOUT_SEC
        for case in ("а", "б", "в", "а+б"):
            with self.subTest(случай=case):
                stamp = self.stamp()
                procs, records = [], []
                if "а" in case:
                    procs.append(self.live())
                    records.append(self.put_record(
                        stamp, procs[-1].pid, tasks=3,
                        age=timeout + self.rng.uniform(600, 3000)))
                if "б" in case:
                    procs.append(self.live())
                    records.append(self.put_record(stamp, procs[-1].pid,
                                                   start_known=False))
                if case == "в":
                    procs.append(self.live())
                mark = self.put_mark(stamp, procs[0].pid)
                code, out = self.drop(stamp, self.reason())
                self.assertEqual(code, 0, self.msg(f"{case}: {out}"))
                for record in records:
                    self.assertFalse(record.exists(), self.msg(f"{case}: {record.name}\n{out}"))
                self.assertFalse(mark.exists(), self.msg(f"{case}: метка осталась\n{out}"))
                for proc in procs:
                    self.assertIsNone(proc.poll(), self.msg(f"{case}: процесс получил сигнал"))

    def test_ac9_drop_keeps_fresh_record_and_mark(self):
        """У `run_stamp` старая запись (старше `CANARY_DRIVE_TIMEOUT_SEC`) и свежая запись живого процесса с определённым временем старта, метка — его.

        Наблюдение: снята только старая запись; свежая запись и метка на
        месте, оба процесса живы.

        Ловит мутацию: `--drop` снимает все записи `run_stamp` разом или
        снимает метку по одному `run_stamp`, не глядя на оставшуюся запись.
        """
        stamp = self.stamp()
        old, fresh = self.live(), self.live()
        old_record = self.put_record(stamp, old.pid, tasks=3,
                                     age=canary.CANARY_DRIVE_TIMEOUT_SEC + 900)
        fresh_record = self.put_record(stamp, fresh.pid, age=300)
        mark = self.put_mark(stamp, fresh.pid)
        code, out = self.drop(stamp, self.reason())
        self.assertEqual(code, 0, self.msg(out))
        self.assertFalse(old_record.exists(), self.msg(out))
        self.assertTrue(fresh_record.exists(), self.msg(f"свежая запись снята:\n{out}"))
        self.assertTrue(mark.exists(), self.msg(f"метка снята при оставшейся записи:\n{out}"))
        self.assertIsNone(old.poll(), self.msg("процесс получил сигнал"))
        self.assertIsNone(fresh.poll(), self.msg("процесс получил сигнал"))

    # ------------------------------------------------------------- AC-10

    def test_ac10_drop_journals_operator_line_with_files_and_reason(self):
        """Успешный `--drop` метки без записи и старой записи при живом процессе прогона.

        Наблюдение: в журнале пульта новая строка без задачи от `operator`,
        действие — не `LIVE_RUN_SWEPT_ACTION`; деталь несёт имена удалённых
        файлов и основание; и деталь, и вывод несут «процесс <pid> жив —
        прогон продолжается без защиты окна».

        Ловит мутацию: снятие пишется прежней строкой уборки от
        `orchestrator` (или не пишется), либо деталь без основания или без
        имён файлов, либо предупреждение о живом процессе не выводится.
        """
        for case in ("метка", "запись"):
            with self.subTest(случай=case):
                stamp = self.stamp()
                proc = self.live()
                removed = []
                if case == "запись":
                    removed.append(self.put_record(
                        stamp, proc.pid, tasks=2,
                        age=canary.CANARY_DRIVE_TIMEOUT_SEC + 600))
                removed.append(self.put_mark(stamp, proc.pid))
                reason = self.reason()
                before = len(self.rows())
                code, out = self.drop(stamp, reason)
                self.assertEqual(code, 0, self.msg(out))
                fresh = self.operator_rows(self.rows()[before:])
                self.assertEqual(len(fresh), 1, self.msg(f"{fresh}\n{out}"))
                row = fresh[0]
                self.assertFalse(row["task_id"], self.msg(row))
                self.assertTrue(row["action"], self.msg(row))
                self.assertNotEqual(row["action"], canary.LIVE_RUN_SWEPT_ACTION,
                                    self.msg(row))
                detail = row["detail"] or ""
                warning = f"процесс {proc.pid} жив — прогон продолжается без защиты окна"
                for part in (*[p.name for p in removed], reason, warning):
                    self.assertIn(part, detail, self.msg(f"{part!r} нет в детали: {row}"))
                self.assertIn(warning, out, self.msg(out))

    # ------------------------------------------------------------- AC-11

    def test_ac11_drop_refuses_fresh_live_record(self):
        """`--drop` для свежей записи живого процесса с определённым временем старта.

        Наблюдение: ненулевой код, текст «canary live: прогон <run_stamp> жив
        (pid <pid>, возраст <ч>) — снимать нечего; дождись итога или используй
        --during-canary у конкретной команды»; запись и метка на месте,
        строки журнала `operator` нет, процесс жив.

        Ловит мутацию: строгий вариант не соблюдён — свежая живая запись
        снимается по требованию Оператора, окно канарейки молча открывается.
        """
        stamp = self.stamp()
        proc = self.live()
        record = self.put_record(stamp, proc.pid, age=self.rng.uniform(60, 3 * 3600))
        mark = self.put_mark(stamp, proc.pid)
        before = len(self.rows())
        code, out = self.drop(stamp, self.reason())
        self.assertNotEqual(code, 0, self.msg(out))
        head = f"canary live: прогон {stamp} жив (pid {proc.pid}, возраст "
        self.assertIn(head, out, self.msg(out))
        tail = out.split(head, 1)[1]
        self.assertIn(f") — {NOTHING_TO_DROP}", tail, self.msg(out))
        self.assertTrue(record.exists(), self.msg(out))
        self.assertTrue(mark.exists(), self.msg(out))
        self.assertEqual(self.operator_rows(self.rows()[before:]), [], self.msg(out))
        self.assertIsNone(proc.poll(), self.msg("процесс получил сигнал"))

    # ------------------------------------------------------------- AC-12

    def test_ac12_bad_stamp_refused_before_registry_read(self):
        """`--drop` с `run_stamp` не по шаблону `^\\d{8}T\\d{6}Z$` (короче, длиннее, без `Z`, с путём, строчными).

        В каталоге реестра — мёртвая запись и её метка: любое чтение
        реестра убрало бы их со строкой журнала. Наблюдение: ненулевой код,
        оба файла на месте, строк уборки и строк `operator` нет.

        Ловит мутацию: проверка шаблона стоит после уборки чтения реестра
        (мёртвая запись убрана), либо шаблон проверяется поиском вместо
        полного совпадения (`../<stamp>` проходит).
        """
        valid = self.stamp()
        dead = self.dead_pid()
        record = self.put_record(valid, dead, start_known=False)
        mark = self.put_mark(valid, dead)
        bad = [valid[:-1], valid[:8] + valid[9:], valid + "0", valid.lower(),
               f"../{valid}", f"{valid}/..", valid.replace("T", "-"),
               valid[1:], self.token(6)]
        for stamp in bad:
            with self.subTest(run_stamp=stamp):
                before = len(self.rows())
                code, out = self.drop(stamp, self.reason())
                self.assertNotEqual(code, 0, self.msg(out))
                self.assertNotIn(OLD_PARSER_REFUSAL, out, self.msg(out))
                self.assertTrue(record.exists(), self.msg(f"реестр прочитан:\n{out}"))
                self.assertTrue(mark.exists(), self.msg(f"реестр прочитан:\n{out}"))
                self.assertEqual(self.rows()[before:], [], self.msg(out))

    # ------------------------------------------------------------- AC-13

    def test_ac13_malformed_arguments_refused(self):
        """`canary live` с `--drop` без `run_stamp`, без основания, с пустым и пробельным основанием и с лишними аргументами.

        В реестре — метка без записи с живым pid, которую `--drop` снял бы.
        Наблюдение: ненулевой код, отказ не прежнего разбора прогона, метка
        на месте, строки `operator` нет.

        Ловит мутацию: пустое основание принимается (снятие без
        основания), либо лишний аргумент молча отбрасывается и команда
        исполняется.
        """
        stamp = self.stamp()
        proc = self.live()
        mark = self.put_mark(stamp, proc.pid)
        reason = self.reason()
        variants = [
            ("--drop без run_stamp", ["--drop"]),
            ("без основания", ["--drop", stamp]),
            ("пустое основание", ["--drop", stamp, ""]),
            ("пробельное основание", ["--drop", stamp, "  "]),
            ("лишний аргумент показа", [self.token(5)]),
            ("лишний аргумент --drop", ["--drop", stamp, reason, self.token(5)]),
        ]
        for name, tail in variants:
            with self.subTest(вариант=name):
                before = len(self.rows())
                code, out = self.cli("canary", "live", *tail)
                self.assertNotEqual(code, 0, self.msg(f"{name}: {out}"))
                self.assertNotIn(OLD_PARSER_REFUSAL, out, self.msg(out))
                self.assertTrue(mark.exists(), self.msg(f"{name}: метка снята\n{out}"))
                self.assertEqual(self.operator_rows(self.rows()[before:]), [],
                                 self.msg(out))

    # ------------------------------------------------------------- AC-14

    def test_ac14_absent_stamp_reports_and_exits_zero(self):
        """`--drop` по `run_stamp`, которого в реестре нет, и по `run_stamp`, у которого была только мёртвая запись.

        Наблюдение: вывод «canary live: в реестре нет <run_stamp>», код 0,
        строки `operator` нет; во втором случае мёртвая запись и её метка
        убраны и в журнале новая строка `LIVE_RUN_SWEPT_ACTION`. Чужая живая
        метка остаётся.

        Ловит мутацию: отсутствие `run_stamp` — отказ с ненулевым кодом,
        либо `--drop` по мёртвой записи пишет строку `operator`, а не
        прежнюю строку уборки.
        """
        keeper = self.put_mark(self.stamp(), self.live().pid)
        for case in ("нет вовсе", "только мёртвая запись"):
            with self.subTest(случай=case):
                stamp = self.stamp()
                files = []
                if case != "нет вовсе":
                    dead = self.dead_pid()
                    files = [self.put_record(stamp, dead, start_known=False),
                             self.put_mark(stamp, dead)]
                before = len(self.rows())
                code, out = self.drop(stamp, self.reason())
                fresh = self.rows()[before:]
                self.assertEqual(code, 0, self.msg(out))
                self.assertIn(f"canary live: в реестре нет {stamp}", out, self.msg(out))
                self.assertEqual(self.operator_rows(fresh), [], self.msg(fresh))
                for path in files:
                    self.assertFalse(path.exists(), self.msg(f"{path.name} осталась"))
                if files:
                    self.assertTrue(self.swept(fresh), self.msg(fresh))
                self.assertTrue(keeper.exists(), self.msg("чужая живая метка убрана"))

    # ------------------------------------------------------------- AC-15

    def test_ac15_role_refused_and_help_names_subcommand(self):
        """Под ролью (`ARTEL_ROLE` в окружении) `canary live` и `canary live --drop …` отказывают; справка `artel.py --help` называет `canary live`.

        Наблюдение под ролью: ненулевой код, «canary live: команда
        недоступна процессу роли», снимаемая метка на месте, строки
        `operator` нет.

        Ловит мутацию: подкоманда внесена в разрешённые роли (показ или
        `--drop` исполняется под ролью), либо строка справки не дописана.
        """
        stamp = self.stamp()
        mark = self.put_mark(stamp, self.live().pid)
        with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "developer"}):
            for tail in ([], ["--drop", stamp, self.reason()]):
                with self.subTest(форма=tail[:1] or "показ"):
                    before = len(self.rows())
                    code, out = self.cli("canary", "live", *tail)
                    self.assertNotEqual(code, 0, self.msg(out))
                    self.assertIn("canary live", out, self.msg(out))
                    self.assertIn(ROLE_REFUSAL, out, self.msg(out))
                    self.assertTrue(mark.exists(), self.msg(out))
                    self.assertEqual(self.operator_rows(self.rows()[before:]), [],
                                     self.msg(out))
        code, out = self.cli("--help")
        self.assertIn("canary live", out, self.msg(out))


if __name__ == "__main__":
    unittest.main()
