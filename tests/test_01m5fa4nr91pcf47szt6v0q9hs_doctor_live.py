"""Проверка `doctor` `canary-live`: живые прогоны канарейки по реестру, предупреждение о зависших и мёртвых, уборка под `doctor --fix`.

Группа: долгоживущий
Красен до реализации: среди строк `doctor.all_checks` нет строки `canary-live`, а `doctor --fix` реестр не убирает — мёртвая запись и метка с мёртвым pid остаются без строки журнала.

Связка, которую держит файл: «каталог реестра под корнем песочницы —
`doctor.all_checks`/`doctor.cmd_doctor(fix=True)` — журнал пульта».
Песочница — `tests.sandbox.InitializedTmpRootTest` (пути `config` во
временном каталоге, БД со схемой), строки `doctor` — публичный
`doctor.all_checks(conn)`, строка ищется по имени `canary-live`. Каталог
реестра — `config.ROOT/.artel/config.CANARY_LIVE_DIRNAME`; запись —
`<run_stamp>-<pid>.json` с полями записи прогона, метка — `<run_stamp>.lock`
с pid текстом. Живой pid — дочерний процесс-сон, мёртвый — pid
завершённого и дождавшегося процесса. Возраст записи — поле `started_at`,
возраст метки — время правки (`os.utime`); потолок
`canary.CANARY_DRIVE_TIMEOUT_SEC` читается из модуля, не литералом.

Формат возраста «<ч>» SPEC не уточняет: возраст ищется в тексте строки в
любом из естественных видов (часы с дробью, часы и минуты, минуты,
секунды).

Значения `run_stamp`, sha, возрасты порождаются от зерна; зерно печатается
и входит в текст каждого провала.
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

from orchestrator import canary, config, doctor, store
from tests.sandbox import InitializedTmpRootTest

STAMP_FORMAT = "%Y%m%dT%H%M%SZ"
CHECK = "canary-live"
EMPTY = "живых прогонов канарейки нет"
ABSENT = "запись реестра отсутствует"


NETWORK_GIT = {"clone", "fetch", "push", "pull", "ls-remote"}


def _local_command(argv) -> bool:
    """Локальный процесс песочницы: `ps`, интерпретатор Python, git без сети."""
    if not isinstance(argv, (list, tuple)) or not argv:
        return False
    words = [os.fsdecode(a) for a in argv]
    name = Path(words[0]).name
    if name == "git":
        return not NETWORK_GIT & set(words[1:])
    return name == "ps" or name.startswith("python") or words[0] == sys.executable


def hours_found(text: str) -> list:
    """Длительности (в секундах), записанные в тексте в любом естественном виде."""
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
    return found


class DoctorCanaryLiveTest(InitializedTmpRootTest):
    """Каталог реестра песочницы, живые и мёртвые pid настоящих дочерних процессов."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used = set()
        # Без сети и без настоящих ролей: прочие проверки `doctor` зовут CLI
        # роли (живой смок), `gh` и сетевой git — им отвечает отказ запуска.
        real_run, real_popen = subprocess.run, subprocess.Popen

        def run(argv, *args, **kwargs):
            if _local_command(argv):
                return real_run(argv, *args, **kwargs)
            empty = b"" if not (kwargs.get("text") or kwargs.get("encoding")
                                or kwargs.get("universal_newlines")) else ""
            return subprocess.CompletedProcess(argv, 127, empty, empty)

        def popen(argv, *args, **kwargs):
            if _local_command(argv):
                return real_popen(argv, *args, **kwargs)
            raise FileNotFoundError(f"песочница: внешний процесс {argv!r} не запускается")

        for name, fake in (("run", run), ("Popen", popen)):
            patcher = mock.patch.object(subprocess, name, fake)
            patcher.start()
            self.addCleanup(patcher.stop)

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

    def live_pid(self) -> int:
        proc = subprocess.Popen([sys.executable, "-c",
                                 "import time; time.sleep(600)"])
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        return proc.pid

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
                   start_known: bool = True) -> tuple:
        started = doctor.process_start_time(pid) if start_known else None
        sha = f"{self.rng.randrange(16 ** 40):040x}"
        record = self.registry() / f"{stamp}-{pid}.json"
        record.write_text(json.dumps({
            "pid": pid,
            "process_start": None if started is None else started.isoformat(),
            "run_stamp": stamp, "sha": sha, "set_name": config.CANARY_DEFAULT_SET,
            "started_at": (datetime.now(timezone.utc)
                           - timedelta(seconds=age)).isoformat(),
            "tasks": tasks}), encoding="utf-8")
        return record, sha

    def check(self):
        checks = doctor.all_checks(store.db())
        found = [c for c in checks if c.name == CHECK]
        self.assertEqual(len(found), 1, self.msg(
            f"строк {CHECK}: {len(found)}\n"
            + "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in checks)))
        return found[0]

    def rows(self) -> list:
        return [dict(r) for r in store.all_steps(store.db())]

    def assert_age(self, text: str, age: float, what: str) -> None:
        found = hours_found(text)
        self.assertTrue(any(abs(v - age) <= 3600 for v in found),
                        self.msg(f"{what}: возраст ≈ {age:.0f} с нет в {text!r} ({found})"))

    # ------------------------------------------------------------- AC-16

    def test_ac16_ok_lines_for_empty_registry_live_record_and_mark(self):
        """Строка `canary-live`: пустой реестр, живая запись, метка без записи с живым pid.

        Наблюдение: пустой реестр (каталога нет и каталог пуст) — `ok`
        «живых прогонов канарейки нет»; живая запись моложе потолка — `ok`
        с «<run_stamp> на <sha7>, pid <pid>, возраст <ч>»; метка без записи
        с живым pid — `ok`, в строке её `run_stamp`, пометка «запись
        реестра отсутствует» и возраст по времени правки. Файлы на месте,
        журнал не растёт.

        Ловит мутацию: проверка не видит меток без записи (метка с живым
        pid даёт «живых прогонов нет»), либо в строке живой записи нет pid
        или sha7, либо проверка не подключена к `all_checks`.
        """
        for where in ("каталога нет", "каталог пуст"):
            with self.subTest(реестр=where):
                if where == "каталог пуст":
                    self.registry()
                check = self.check()
                self.assertEqual(check.status, "ok", self.msg(check))
                self.assertIn(EMPTY, check.detail, self.msg(check))

        timeout = canary.CANARY_DRIVE_TIMEOUT_SEC
        stamp = self.stamp()
        pid = self.live_pid()
        age = self.rng.uniform(0.2, 0.9) * timeout
        record, sha = self.put_record(stamp, pid, age=age)
        before = len(self.rows())
        check = self.check()
        self.assertEqual(check.status, "ok", self.msg(check))
        head = f"{stamp} на {sha[:7]}, pid {pid}, возраст "
        self.assertIn(head, check.detail, self.msg(check))
        self.assert_age(check.detail.split(head, 1)[1], age, "запись")
        self.assertTrue(record.exists(), self.msg(check))
        record.unlink()

        mark_stamp = self.stamp()
        mark_pid = self.live_pid()
        mark_age = self.rng.uniform(0.2, 0.9) * timeout
        mark = self.put_mark(mark_stamp, mark_pid, mark_age)
        check = self.check()
        self.assertEqual(check.status, "ok", self.msg(check))
        self.assertIn(mark_stamp, check.detail, self.msg(check))
        self.assertIn(ABSENT, check.detail, self.msg(check))
        self.assertNotIn(EMPTY, check.detail, self.msg(check))
        self.assert_age(check.detail.split(mark_stamp, 1)[1], mark_age, "метка")
        self.assertTrue(mark.exists(), self.msg(check))
        self.assertEqual(len(self.rows()), before, self.msg(self.rows()[before:]))

    # ------------------------------------------------------------- AC-17

    def test_ac17_warn_with_drop_hint_for_overdue_record_and_mark(self):
        """Запись живого процесса старше `CANARY_DRIVE_TIMEOUT_SEC` (но моложе потолка) и метка без записи с живым pid старше того же порога по времени правки.

        Наблюдение: строка `canary-live` — `warn` с подсказкой
        `canary live --drop <run_stamp> "<основание>"` этого `run_stamp`;
        файл на месте.

        Ловит мутацию: предупреждение срабатывает только на потолке
        записи (`CANARY_DRIVE_TIMEOUT_SEC` × задачи + 1 ч), а не на
        `CANARY_DRIVE_TIMEOUT_SEC`, либо возраст метки по времени правки не
        сверяется вовсе.
        """
        timeout = canary.CANARY_DRIVE_TIMEOUT_SEC
        for case in ("запись", "метка"):
            with self.subTest(случай=case):
                stamp = self.stamp()
                pid = self.live_pid()
                if case == "запись":
                    path, _sha = self.put_record(
                        stamp, pid, tasks=3,
                        age=timeout + self.rng.uniform(600, timeout))
                else:
                    path = self.put_mark(stamp, pid,
                                         timeout + self.rng.uniform(600, timeout))
                check = self.check()
                self.assertEqual(check.status, "warn", self.msg(check))
                self.assertIn(f'canary live --drop {stamp} "<основание>"', check.detail,
                              self.msg(check))
                self.assertTrue(path.exists(), self.msg(check))
                path.unlink()

    # ------------------------------------------------------------- AC-18

    def test_ac18_dead_entries_warn_without_fix_and_swept_with_fix(self):
        """Мёртвая запись (с её меткой) и метка без записи с мёртвым pid: `doctor` без `--fix`, затем `doctor --fix`.

        Наблюдение без `--fix`: строка `canary-live` — `warn` с подсказкой
        `doctor --fix` или `canary live --drop`; все файлы на месте, журнал
        не вырос. Под `doctor.cmd_doctor(fix=True)`: файлы убраны, в журнале
        пульта новые строки `LIVE_RUN_SWEPT_ACTION`.

        Ловит мутацию: проверка `doctor` убирает мёртвое сама (через
        прежнее чтение реестра с уборкой) — без `--fix` файлы пропадают и
        журнал растёт; либо `--fix` реестр не чинит.
        """
        dead = self.dead_pid()
        record_stamp, mark_stamp = self.stamp(), self.stamp()
        record, _sha = self.put_record(record_stamp, dead, start_known=False)
        files = [record, self.put_mark(record_stamp, dead),
                 self.put_mark(mark_stamp, self.dead_pid())]
        before = len(self.rows())
        check = self.check()
        self.assertEqual(check.status, "warn", self.msg(check))
        self.assertTrue("doctor --fix" in check.detail
                        or "canary live --drop" in check.detail, self.msg(check))
        for path in files:
            self.assertTrue(path.exists(), self.msg(f"{path.name} убран без --fix"))
        self.assertEqual(self.rows()[before:], [], self.msg(self.rows()[before:]))

        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.suppress(SystemExit):
            doctor.cmd_doctor(fix=True)
        for path in files:
            self.assertFalse(path.exists(), self.msg(f"{path.name} не убран:\n{out.getvalue()}"))
        swept = [r for r in self.rows()[before:]
                 if r["action"] == canary.LIVE_RUN_SWEPT_ACTION]
        self.assertGreaterEqual(len(swept), 2, self.msg(swept))


if __name__ == "__main__":
    unittest.main()
