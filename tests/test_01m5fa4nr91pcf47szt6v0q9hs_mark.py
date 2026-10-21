"""Реестр живого прогона канарейки: метка `<run_stamp>.lock` без записи — живость, уборка и неприкосновенность метки рядом с живой записью.

Группа: долгоживущий
Красен до реализации: `canary.live_run_note` читает только записи реестра — метка без записи с живым pid или свежая нечитаемая метка не держат окно (причины нет), а метка с мёртвым pid и старая нечитаемая метка остаются в каталоге без строки журнала.

Связка, которую держит файл: «каталог реестра под корнем песочницы —
`canary.live_run_note`/`canary.live_runs` — журнал пульта». Песочница —
`tests.sandbox.InitializedTmpRootTest`: пути `config` во временном
каталоге, БД со схемой. Каталог реестра —
`config.ROOT/.artel/config.CANARY_LIVE_DIRNAME`; запись —
`<run_stamp>-<pid>.json`, метка — `<run_stamp>.lock` с pid текстом.
Живой pid — дочерний процесс-сон (снимается в уборке теста), мёртвый —
pid уже завершённого и дождавшегося дочернего процесса. Время правки метки
задаётся `os.utime`; ожидания по часам нет.

Значения `run_stamp`, возрасты меток и тексты нечитаемых меток порождаются
от зерна; зерно печатается и входит в текст каждого провала.
"""
import json
import os
import random
import subprocess
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from orchestrator import canary, config, doctor, store
from tests.sandbox import InitializedTmpRootTest

STAMP_FORMAT = "%Y%m%dT%H%M%SZ"
ABSENT = "(запись реестра отсутствует)"


class MarkWithoutRecordTest(InitializedTmpRootTest):
    """Каталог реестра песочницы, живые и мёртвые pid настоящих дочерних процессов."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used = set()

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

    def put_mark(self, stamp: str, text: str, age: float) -> Path:
        mark = self.registry() / f"{stamp}.lock"
        mark.write_text(text, encoding="utf-8")
        moment = time.time() - age
        os.utime(mark, (moment, moment))
        return mark

    def put_record(self, stamp: str, pid: int, *, tasks: int = 1,
                   age: float = 60.0) -> Path:
        started = doctor.process_start_time(pid)
        record = self.registry() / f"{stamp}-{pid}.json"
        record.write_text(json.dumps({
            "pid": pid,
            "process_start": None if started is None else started.isoformat(),
            "run_stamp": stamp, "sha": f"{self.rng.randrange(16 ** 40):040x}",
            "set_name": config.CANARY_DEFAULT_SET,
            "started_at": (datetime.now(timezone.utc)
                           - timedelta(seconds=age)).isoformat(),
            "tasks": tasks}), encoding="utf-8")
        return record

    def swept_rows(self) -> list:
        return [dict(r) for r in store.all_steps(store.db())
                if r["action"] == canary.LIVE_RUN_SWEPT_ACTION]

    def nonnumeric(self) -> str:
        letters = "abcdefxyzабв?-"
        return "".join(self.rng.choice(letters)
                       for _ in range(self.rng.randint(1, 6)))

    # ------------------------------------------------------- AC-2 и AC-3

    def check_unreadable(self, text: str, ctx: str) -> None:
        stamp = self.stamp()
        young = self.rng.uniform(0, 50)
        mark = self.put_mark(stamp, text, young)
        before = len(self.swept_rows())
        note = canary.live_run_note()
        self.assertIsNotNone(note, self.msg(f"{ctx}: метка {young:.0f} с — не живой прогон"))
        self.assertTrue(mark.exists(), self.msg(f"{ctx}: свежая метка убрана"))
        self.assertEqual(len(self.swept_rows()), before, self.msg(ctx))

        old = self.rng.uniform(70, 30 * 24 * 3600)
        moment = time.time() - old
        os.utime(mark, (moment, moment))
        self.assertIsNone(canary.live_run_note(),
                          self.msg(f"{ctx}: старая метка ({old:.0f} с) держит окно"))
        self.assertFalse(mark.exists(), self.msg(f"{ctx}: старая метка осталась"))
        self.assertEqual(len(self.swept_rows()), before + 1,
                         self.msg(f"{ctx}: {self.swept_rows()}"))

    def test_ac2_empty_mark_alive_while_young_swept_when_old(self):
        """Пустая метка без записи: моложе 60 с — живой прогон, старше 60 с — убрана строкой журнала.

        Сценарий: метка без содержимого (и метка из одних пробелов и
        перевода строки) с временем правки моложе 60 с — `live_run_note`
        называет прогон, метка на месте, строк уборки нет; то же время
        правки отодвинуто за 60 с — причины нет, метки нет, в журнале
        пульта ровно одна новая строка `LIVE_RUN_SWEPT_ACTION`.

        Ловит мутацию: пустая метка читается как мёртвый pid и убирается
        сразу, без порога 60 с (свежая метка пропадает, окно не держится),
        либо уборка старой метки не пишет строку журнала.
        """
        for text in ("", self.rng.choice((" ", "\n", " \n"))):
            with self.subTest(текст=repr(text)):
                self.check_unreadable(text, f"метка {text!r}")

    def test_ac3_nonnumeric_mark_alive_while_young_swept_when_old(self):
        """Непустая нечисловая метка без записи (`abc` и случайные тексты): моложе 60 с — жива, старше — убрана строкой журнала.

        Ловит мутацию: `int()` метки падает и метка выбрасывается как
        мёртвая без сверки возраста — свежая нечисловая метка убрана и
        окно не держится; либо нечисловая старая метка остаётся навсегда.
        """
        for text in ("abc", self.nonnumeric(), f"{self.nonnumeric()}\n"):
            with self.subTest(текст=repr(text)):
                self.check_unreadable(text, f"метка {text!r}")

    # -------------------------------------------------------------- AC-4

    def test_ac4_mark_with_dead_pid_swept_with_journal_line(self):
        """Метка без записи с pid завершённого процесса — даже свежая по времени правки — убрана.

        Наблюдение: `live_run_note` причины не даёт, файла метки нет, в
        журнале пульта новая строка `LIVE_RUN_SWEPT_ACTION`.

        Ловит мутацию: живость метки решает только время правки (свежая
        метка мёртвого процесса держит окно и остаётся), либо мёртвая метка
        убирается без строки журнала.
        """
        for age in (self.rng.uniform(0, 50), self.rng.uniform(70, 10 ** 5)):
            with self.subTest(возраст=int(age)):
                stamp = self.stamp()
                mark = self.put_mark(stamp, f"{self.dead_pid()}\n", age)
                before = len(self.swept_rows())
                self.assertIsNone(canary.live_run_note(), self.msg(stamp))
                self.assertFalse(mark.exists(), self.msg(f"метка {stamp} осталась"))
                self.assertEqual(len(self.swept_rows()), before + 1,
                                 self.msg(self.swept_rows()))

    # -------------------------------------------------------------- AC-6

    def test_ac6_mark_beside_live_record_untouched_and_not_in_live_runs(self):
        """Живая запись прогона S и метка S, которую новая логика сочла бы мёртвой; рядом — метка T без записи с живым pid.

        Наблюдение: после `live_run_note` метка S на месте (содержимое и
        время правки те же), строк уборки нет, причина — прежняя «идёт
        канарейка S на <sha7>» без пометки об отсутствии записи;
        `live_runs()` отдаёт ровно одну запись — прогона S с pid записи — и
        не возвращает метку T.

        Ловит мутацию: метки сверяются без оглядки на оставшиеся записи —
        метка S с мёртвым pid (или старая нечитаемая) рядом с живой записью
        убирается; либо `live_runs` начинает возвращать метки без записи.
        """
        for mark_text, age in ((f"{self.dead_pid()}\n", 10.0),
                               (self.rng.choice(("", "abc")), 3600.0)):
            with self.subTest(метка=repr(mark_text)):
                stamp, other = self.stamp(), self.stamp()
                pid = self.live_pid()
                record = self.put_record(stamp, pid)
                mark = self.put_mark(stamp, mark_text, age)
                other_mark = self.put_mark(other, f"{self.live_pid()}\n", 5.0)
                shot = (mark.read_bytes(), mark.stat().st_mtime_ns)
                before = len(self.swept_rows())
                note = canary.live_run_note()
                sha = json.loads(record.read_text(encoding="utf-8"))["sha"]
                self.assertTrue(mark.exists(), self.msg("метка рядом с живой записью убрана"))
                self.assertEqual((mark.read_bytes(), mark.stat().st_mtime_ns), shot,
                                 self.msg("метка рядом с живой записью тронута"))
                self.assertEqual(len(self.swept_rows()), before,
                                 self.msg(self.swept_rows()))
                self.assertEqual(note, f"идёт канарейка {stamp} на {sha[:7]}",
                                 self.msg(note))
                runs = canary.live_runs()
                self.assertEqual([(r.get("run_stamp"), r.get("pid")) for r in runs],
                                 [(stamp, pid)], self.msg(runs))
                self.assertTrue(other_mark.exists(), self.msg("метка T убрана"))
                record.unlink()
                mark.unlink()
                other_mark.unlink()


if __name__ == "__main__":
    unittest.main()
