"""Критерии `canary runs`, проверка которых называет закрытые имена `orchestrator.canary` (AC-1, AC-12).

Группа: разовый
Красен до реализации: подкоманды `canary runs` нет — `artel.py canary runs` уходит в разбор прогона канарейки и отказывает «нужен параметр --k», заголовков прогонов в выводе нет.

Почему разовый: AC-1 требует текста причины отказа «тем же текстом, что
`canary._acceptance_summary(…)`», AC-12 — подмены `canary._live_dir`; правило
долгоживущих файлов `tests/` запрещает закрытые имена, поэтому эти два
критерия держит планка задачи, а остальные — долгоживущий файл
`tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py`.

Песочница — `tests.sandbox.InitializedTmpRootTest`; строки прогонов —
прямой `INSERT` в `canary_runs` песочницы. Ожидаемые строки собираются по
формату требования 4 SPEC; значения порождаются от зерна, зерно печатается
и входит в текст провала.
"""
import contextlib
import io
import random
import re
import socket
import string
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from orchestrator import artel, canary, config, store
from tests.sandbox import InitializedTmpRootTest

STAMP_FORMAT = "%Y%m%dT%H%M%SZ"
CREATED_FORMAT = "%Y-%m-%d %H:%M:%SZ"
HEADER_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z  ")
COLUMNS = ("run_stamp", "title", "task_id", "steps", "cost_usd",
           "review_iterations", "escalations", "outcome",
           "expected_escalation", "actual_escalation", "marker_mismatch",
           "created_at", "main_sha", "verdict", "set_name", "models_summary",
           "acceptance_route", "autogate_refusal", "escalation_roles")


def text(value) -> str:
    return "—" if value is None else str(value)


def money(value) -> str:
    return "—" if value is None else f"{value:.2f}"


def header_line(stamp: str, rows: list) -> str:
    first = rows[0]
    sha = "—" if first["main_sha"] is None else first["main_sha"][:8]
    green = sum(1 for r in rows if r["verdict"] == "green")
    total = sum(r["cost_usd"] or 0 for r in rows)
    return (f"{stamp}  набор={text(first['set_name'])}  sha={sha}  "
            f"задач={len(rows)}  зелёных={green}  ${total:.2f}")


def task_line(row: dict) -> str:
    line = (f"  {row['title']}  {row['task_id']}  вердикт={text(row['verdict'])}"
            f"  исход={text(row['outcome'])}  ${money(row['cost_usd'])}"
            f"  шагов={text(row['steps'])}"
            f"  ревью-итераций={text(row['review_iterations'])}"
            f"  эскалаций={text(row['escalations'])}")
    if row["escalation_roles"]:
        line += f" (роли: {row['escalation_roles']})"
    if row["marker_mismatch"] == 1:
        line += "  [расхождение маркера]"
    return line


class CanaryRunsPrivateNamesTest(InitializedTmpRootTest):
    """Три прогона в `canary_runs` песочницы."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used = set()
        self.moment = datetime(2030, 1, 1, tzinfo=timezone.utc)
        store.all_canary_runs(store.db())

    def msg(self, note) -> str:
        return f"зерно: {self.seed}; {note}"

    def token(self, n: int = 8) -> str:
        return "".join(self.rng.choice(string.ascii_lowercase) for _ in range(n))

    def stamp(self) -> str:
        while True:
            value = (datetime(2031, 1, 1, tzinfo=timezone.utc) + timedelta(
                seconds=self.rng.randrange(300 * 24 * 3600))).strftime(STAMP_FORMAT)
            if value not in self.used:
                self.used.add(value)
                return value

    def row(self, stamp: str, **fields) -> dict:
        self.moment += timedelta(seconds=self.rng.randrange(1, 600))
        values = {
            "run_stamp": stamp, "title": f"canary-{self.token()}",
            "task_id": "01" + self.token(24).upper(),
            "steps": self.rng.randrange(1, 30),
            "cost_usd": self.rng.randrange(1, 2000) / 100,
            "review_iterations": self.rng.randrange(0, 4),
            "escalations": self.rng.randrange(0, 3),
            "outcome": self.rng.choice(["merged", "escalated"]),
            "expected_escalation": None, "actual_escalation": 0,
            "marker_mismatch": 0,
            "created_at": self.moment.strftime(CREATED_FORMAT),
            "main_sha": f"{self.rng.randrange(16 ** 40):040x}",
            "verdict": "green", "set_name": config.CANARY_DEFAULT_SET,
            "models_summary": None, "acceptance_route": None,
            "autogate_refusal": None, "escalation_roles": "",
        }
        values.update(fields)
        return values

    def insert(self, *rows: dict) -> None:
        conn = store.db()
        for values in rows:
            conn.execute(
                f"INSERT INTO canary_runs ({', '.join(COLUMNS)}) "
                f"VALUES ({', '.join('?' for _ in COLUMNS)})",
                tuple(values[c] for c in COLUMNS))
        conn.commit()

    def cli(self, *argv: str) -> tuple:
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

    @staticmethod
    def lines(output: str) -> list:
        return [line.rstrip() for line in output.splitlines() if line.strip()]

    def three_runs(self) -> list:
        """Три прогона по две задачи с разными вердиктами, стоимостью и причиной отказа; строки по `id`."""
        old, mid, new = sorted(self.stamp() for _ in range(3))
        refusal = f"нет  метки\n{self.token()}   в  PLAN"
        rows = [
            self.row(old, verdict="green", acceptance_route="autogate",
                     autogate_refusal=refusal, cost_usd=1.25),
            self.row(old, verdict="red", outcome="escalated", cost_usd=2.5,
                     escalations=1, escalation_roles="developer"),
            self.row(mid, verdict="red", acceptance_route="manual",
                     autogate_refusal=f"ручная {self.token()}"),
            self.row(mid, verdict="red"),
            self.row(new, verdict="green"),
            self.row(new, verdict="green", acceptance_route="autogate",
                     autogate_refusal=f"красная планка {self.token()}"),
        ]
        self.insert(*rows)
        return rows

    def test_ac1_three_runs_headers_tasks_and_refusal_text(self):
        """Три прогона по две задачи: `canary runs` печатает заголовки от нового к старому, строки задач и причину отказа автогейта.

        Вывод без пустых строк совпадает построчно с ожидаемым: заголовок
        (сумма `cost_usd`, счёт зелёных), строки задач по требованию 4, под
        задачей с причиной отказа — текст
        `canary._acceptance_summary(route, refusal, False)` без ведущих
        пробелов с отступом в четыре пробела.

        Ловит мутацию: причина печатается сырым `autogate_refusal` (с
        переводом строки и двойными пробелами) или без различия маршрута
        `manual`/`autogate` — строка причины не совпадает; сумма или счёт
        зелёных по одной строке группы — заголовок не совпадает; прогоны от
        старого к новому — порядок строк вывода иной."""
        rows = self.three_runs()
        code, out = self.cli("canary", "runs")
        self.assertEqual(code, 0, self.msg(out))
        expected = []
        for stamp in sorted({r["run_stamp"] for r in rows}, reverse=True):
            group = [r for r in rows if r["run_stamp"] == stamp]
            expected.append(header_line(stamp, group))
            for r in group:
                expected.append(task_line(r))
                summary = canary._acceptance_summary(
                    r["acceptance_route"], r["autogate_refusal"], False).lstrip()
                if summary:
                    expected.append(f"    {summary}")
        self.assertEqual(self.lines(out), expected, self.msg(f"вывод:\n{out}"))

    def test_ac12_no_live_registry_no_network(self):
        """При `canary.live_runs`, `canary._live_dir`, `subprocess.Popen` и `socket.socket`, падающих при вызове, `canary runs` печатает прогоны.

        Ловит мутацию: команда помечает прогоны, ещё живые по реестру
        (`canary._live_dir`/`canary.live_runs`), или узнаёт sha через `git`
        (`subprocess`) — подмена вызвана, прогоны не напечатаны."""
        rows = self.three_runs()
        fakes = {name: mock.Mock(side_effect=AssertionError(f"{name} вызван"))
                 for name in ("live_runs", "_live_dir", "Popen", "socket")}
        with mock.patch.object(canary, "live_runs", fakes["live_runs"]), \
                mock.patch.object(canary, "_live_dir", fakes["_live_dir"]), \
                mock.patch.object(subprocess, "Popen", fakes["Popen"]), \
                mock.patch.object(socket, "socket", fakes["socket"]):
            code, out = self.cli("canary", "runs")
        self.assertEqual(code, 0, self.msg(out))
        headers = [line.split("  ", 1)[0] for line in self.lines(out)
                   if HEADER_RE.match(line)]
        self.assertEqual(headers, sorted({r["run_stamp"] for r in rows}, reverse=True),
                         self.msg(out))
        for name, fake in fakes.items():
            self.assertFalse(fake.called, self.msg(f"{name} вызван"))


if __name__ == "__main__":
    unittest.main()
