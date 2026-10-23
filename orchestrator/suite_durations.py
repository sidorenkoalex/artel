"""Время каждого теста полного прогона по отметкам времени строк хода (SPEC
01M5MJFSYW6MH0WD05CY8V75TX): разбор отметок `durations`, поток чтения лога
прогона `Reader`, файл времени рядом с логом и блок «самые медленные»
отчёта `suite-run`.

Сводку `--durations` pytest печатает только в конце, и оборванный по
пределу прогон до неё не доходит; строки хода `-vv` («[gwN] [ NN%] PASSED
<id>») идут по ходу прогона, и время их появления в логе — время теста.
"""
import re
import threading
import time
from pathlib import Path
from typing import NamedTuple

from . import suite_run

# Строка рабочих xdist: «2 workers [2 items]», «1 worker [1 item]» — отсчёт
# первой строки хода каждого процесса.
_WORKERS = re.compile(r"^\d+ workers? \[\d+ items?\]")
_WORKER = re.compile(r"^\[(gw\d+)\] ")
_FAILING = ("FAILED", "ERROR")

# Чтение прироста лога — не реже раза в 0,5 с (требование 1).
POLL_SEC = 0.25
# Ожидание остановки потока после конца прогона (требование 3).
JOIN_SEC = 2.0

SLOWEST_TESTS = 30
SLOWEST_FILES = 15


class Record(NamedTuple):
    node: str
    worker: str
    outcome: str
    seconds: float


class _Tracker:
    """Разбор отметок по одной полной строке: `feed` отдаёт запись строки
    хода (время — от прошлой строки хода своего процесса) или `None`."""

    def __init__(self, start: float):
        self.origin = start
        self.last: dict[str, float] = {}
        self.in_report = False

    def feed(self, at: float, line: str) -> Record | None:
        if self.in_report:
            return None
        if suite_run._REPORT_SECTION.match(line):
            self.in_report = True
            return None
        if not self.last and _WORKERS.match(line):
            self.origin = at
            return None
        worker = _WORKER.match(line)
        match = suite_run._PROGRESS.match(line)
        if worker is None or match is None or not match.group("n1"):
            return None
        name = worker.group(1)
        seconds = at - self.last.get(name, self.origin)
        self.last[name] = at
        return Record(match.group("n1").strip(), name, match.group("s1"),
                      seconds)


def _worse(old: str, new: str) -> str:
    return old if old in _FAILING else new


def durations(marks: list, start: float) -> list[Record]:
    """Записи (id узла, процесс, исход, секунды) по отметкам `marks` — парам
    (время появления, полная строка без перевода строки) в порядке
    появления; `start` — начало прогона. Одна запись на (id, процесс) в
    порядке первого появления: повтор id прибавляет время, исход — худший
    (как в `suite_run._progress`)."""
    tracker = _Tracker(start)
    merged: dict[tuple, Record] = {}
    for at, line in marks:
        record = tracker.feed(at, line)
        if record is None:
            continue
        key = (record.node, record.worker)
        old = merged.get(key)
        if old is not None:
            record = old._replace(outcome=_worse(old.outcome, record.outcome),
                                  seconds=old.seconds + record.seconds)
        merged[key] = record
    return list(merged.values())


def path_for(log: Path) -> Path:
    """Файл времени рядом с логом: `<имя лога без .log>.durations.tsv` — не
    под шаблонами номеров логов `*.log` (`suite_run._new_log`,
    `agent_log.new_agent_log`)."""
    log = Path(log)
    stem = log.name[:-len(".log")] if log.name.endswith(".log") else log.name
    return log.with_name(f"{stem}.durations.tsv")


class Reader:
    """Фоновый поток: читает прирост лога `log`, пишет строку файла времени
    на каждую строку хода по мере появления. Время строки — момент чтения,
    в котором появились её первые байты, а не её `\\n`: xdist дописывает
    перевод строки только со следующим событием набора. Лог открыт только
    на чтение; сбой потока прогон не трогает — поток просто кончается."""

    def __init__(self, log: Path, start: float):
        self.log = Path(log)
        self.tracker = _Tracker(start)
        self.stopping = threading.Event()
        self.pending = b""
        self.pending_at = 0.0
        self.thread = threading.Thread(target=self._loop, daemon=True,
                                       name="suite-durations")

    def start(self) -> "Reader":
        self.thread.start()
        return self

    def stop(self) -> None:
        """Остановка после конца прогона: поток дочитывает остаток лога, его
        ждут не дольше `JOIN_SEC`."""
        self.stopping.set()
        self.thread.join(JOIN_SEC)

    def _loop(self) -> None:
        try:
            with open(path_for(self.log), "w", encoding="utf-8") as out, \
                    open(self.log, "rb") as src:
                while not self.stopping.wait(POLL_SEC):
                    self._read(src, out)
                self._read(src, out)
                # Процесс pytest уже завершён — хвост без `\n` дописать
                # некому, он полная строка.
                if self.pending:
                    self._emit(self.pending_at, self.pending, out)
                    self.pending = b""
        except Exception:  # noqa: BLE001 — файл времени не условие прогона
            return

    def _read(self, src, out) -> None:
        chunk = src.read()
        if not chunk:
            return
        now = time.monotonic()
        if not self.pending:
            self.pending_at = now
        self.pending += chunk
        while b"\n" in self.pending:
            line, _, self.pending = self.pending.partition(b"\n")
            self._emit(self.pending_at, line, out)
            # Всё после первого `\n` пришло этим чтением.
            self.pending_at = now

    def _emit(self, at: float, raw: bytes, out) -> None:
        line = raw.decode("utf-8", errors="replace").rstrip("\r")
        record = self.tracker.feed(at, line)
        if record is None:
            return
        out.write(f"{record.node}\t{record.worker}\t{record.outcome}\t"
                  f"{record.seconds:.3f}\n")
        out.flush()


def _read_file(path: Path) -> dict[str, float]:
    """id узла -> секунды по файлу времени: строки одного id суммируются."""
    tests: dict[str, float] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return tests
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        try:
            seconds = float(parts[3])
        except ValueError:
            continue
        tests[parts[0]] = tests.get(parts[0], 0.0) + seconds
    return tests


def _top(items: dict[str, float], limit: int) -> list[str]:
    ranked = sorted(items.items(), key=lambda item: (-item[1], item[0]))
    return [f"  {seconds:.2f} с  {name}" for name, seconds in ranked[:limit]]


def slowest_block(log: Path) -> str:
    """Блок «самые медленные» отчёта `suite-run` по файлу времени лога
    `log`; файла нет или в нём нет строк — пустая строка (требование 5)."""
    tests = _read_file(path_for(log))
    if not tests:
        return ""
    files: dict[str, float] = {}
    for node, seconds in tests.items():
        file = node.split("::", 1)[0]
        files[file] = files.get(file, 0.0) + seconds
    lines = [f"самые медленные тесты ({min(len(tests), SLOWEST_TESTS)} из "
             f"{len(tests)}):", *_top(tests, SLOWEST_TESTS),
             f"самые медленные файлы ({min(len(files), SLOWEST_FILES)} из "
             f"{len(files)}):", *_top(files, SLOWEST_FILES)]
    return "\n".join(lines)
