"""`pin-update <sha> [--wait-ci]`: ожидание CI головы main командой пульта
и отказы диспетчера на неверной форме команды.

Группа: долгоживущий
Красен до реализации: диспетчер `pin-update` берёт `rest[0]` как sha и не знает `--wait-ci` — на первом незелёном опросе команда отказывает без ожидания (AC-1..AC-5), без аргументов падает `IndexError`, а `--wait-ci`/`--wait` без формы отказа уходят в `fetch` (AC-8, AC-9). Методы AC-6 и AC-7 зелены и до реализации — они держат прежнее поведение без флага и порядок «канарейка раньше CI», которое реализация обязана не сломать.

Сквозные сценарии держат связку «командная строка `artel.main` —
`pin.cmd_pin_update` — настоящий git песочницы с bare `origin` — журнал
БД» (`SyncedOriginConnSandbox`, тот же приём, что у `tests/test_pin.py`):
целевой sha — коммит, уже лежащий в `origin`, на который главная копия
песочницы ещё не сдвинута; «пин сдвинут» — HEAD главной копии стал этим
sha. Подменены цвет CI (`ci.main_line_status`), возраст зелёного прогона
канарейки (`canary.merges_since_last_green_run`), константы ожидания и
часы модуля `pin` — едиными подменёнными часами: `sleep(x)` продвигает
подменённое время на `x`, `monotonic()` возвращает текущее подменённое
время; сеть и реальное ожидание не участвуют. Периоды и потолки берутся
случайно при каждом запуске, зерно печатается и входит в текст провала.
"""
import contextlib
import io
import os
import random
import re
import sys
import time as real_time
import unittest
from unittest import mock

from orchestrator import artel, canary, ci, config, pin, store
from tests.sandbox import SyncedOriginConnSandbox

USAGE = "artel.py pin-update <sha> [--wait-ci]"
NO_SHA_REFUSAL = f"pin-update: нужен полный sha main артели — {USAGE}"
WAIT_LINE_RE = re.compile(r"\[pin-update\] .*\(ожидание \d+ сек\)")


class FakeClock:
    """Единые подменённые часы модуля `pin`: `sleep(x)` продвигает время на
    `x` и запоминает аргумент, `monotonic()` возвращает текущее время.
    Прочие атрибуты `time` читаются из настоящего модуля."""

    def __init__(self, start: int):
        self.now = float(start)
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def monotonic(self):
        return self.now

    def __getattr__(self, name):
        return getattr(real_time, name)


class PinUpdateWaitCiSandbox(SyncedOriginConnSandbox):
    """Песочница: главная копия на старом sha, в `origin` — целевой коммит
    поверх него; вызов `artel.main` из окружения Оператора."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        (self.root / "pin_target.txt").write_text(
            f"{self.seed}\n", encoding="utf-8")
        self.git("add", "pin_target.txt")
        self.git("commit", "-q", "-m", "целевой коммит main")
        self.target = self.git("rev-parse", "HEAD").strip()
        self.git("push", "-q", "origin", config.MAIN_BRANCH)
        self.git("reset", "-q", "--hard", "HEAD~1")
        self.old = self.head()
        self.assertNotEqual(self.old, self.target)
        # Remote-tracking ref — на старом sha: любой `git fetch origin main`
        # вернёт его на целевой, по нему видно, был ли `fetch`.
        self.tracking = f"refs/remotes/origin/{config.MAIN_BRANCH}"
        self.git("update-ref", self.tracking, self.old)
        self.clock = FakeClock(self.rng.randint(1_000, 1_000_000))
        self.polls = []
        self.heads_at_poll = []

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def ctx(self, text: str = "") -> str:
        return f"зерно: {self.seed}; {text}"

    def status(self, kind: str, note: str) -> ci.MainLineStatus:
        return ci.MainLineStatus(kind, self.target, [], [], "", note)

    def run_main(self, *args, kinds=(), poll=90, ceiling=3600,
                 canary_age=0):
        """`artel.py <args>` с подменами; `kinds` — цвета CI по опросам
        (последний повторяется). Возвращает (вывод с текстом выхода,
        исключение выхода либо `None`)."""
        kinds = list(kinds)

        def fake_status(sha, repo=None):
            self.heads_at_poll.append(self.head())
            self.polls.append(sha)
            kind = kinds[min(len(self.polls), len(kinds)) - 1]
            return self.status(kind, f"опрос {len(self.polls)}: {kind}")

        operator_env = {k: v for k, v in os.environ.items()
                        if k not in (config.ARTEL_ROLE_ENV, "HOME")}
        out, err = io.StringIO(), io.StringIO()
        exit_exc = None
        with mock.patch.dict(os.environ, operator_env, clear=True), \
                mock.patch.object(sys, "argv", ["artel.py", *args]), \
                mock.patch.object(pin, "time", self.clock, create=True), \
                mock.patch.object(ci, "main_line_status",
                                  side_effect=fake_status), \
                mock.patch.object(canary, "merges_since_last_green_run",
                                  return_value=canary_age), \
                mock.patch.object(config, "MERGE_GATE_CI_WAIT_POLL_SEC", poll), \
                mock.patch.object(config, "MERGE_GATE_CI_WAIT_CEILING_SEC",
                                  ceiling), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            try:
                artel.main()
            except SystemExit as exc:
                exit_exc = exc
        text = out.getvalue() + err.getvalue()
        if exit_exc is not None and isinstance(exit_exc.code, str):
            text += "\n" + exit_exc.code
        return text, exit_exc

    def refusal(self, exc) -> str:
        self.assertIsNotNone(exc, self.ctx("ожидался отказ команды"))
        self.assertIsInstance(exc.code, str, self.ctx(f"код выхода {exc.code!r}"))
        return exc.code

    def assert_no_fetch(self, text: str) -> None:
        self.assertEqual(self.git("rev-parse", self.tracking).strip(),
                         self.old, self.ctx(f"был git fetch; {text}"))


class WaitCiSuccessTest(PinUpdateWaitCiSandbox):

    def test_ac1_running_then_green_moves_pin_after_one_pause(self):
        """Первый опрос CI «идёт», второй «зелёный»: команда ждёт и сдвигает пин.

        Период опроса случайный: пауза обязана быть ровно одна и ровно с
        `MERGE_GATE_CI_WAIT_POLL_SEC`, пин — на целевом sha только после
        второго опроса, в выводе — строка «(ожидание … сек)».
        Ловит мутацию: `--wait-ci` не передан из диспетчера в
        `cmd_pin_update` (или ожидание не подключено) — на первом же
        опросе «идёт» команда отказывает «повтори, когда CI завершится»,
        пин остаётся на старом sha, паузы нет; либо пауза взята литералом
        90 вместо константы — аргумент `sleep` расходится с подменённым
        периодом."""
        poll = self.rng.randint(5, 300)
        text, exc = self.run_main("pin-update", self.target, "--wait-ci",
                                  kinds=[ci.MAIN_RUNNING, ci.MAIN_GREEN],
                                  poll=poll, ceiling=poll * 10)
        self.assertIsNone(exc, self.ctx(text))
        self.assertEqual(len(self.polls), 2, self.ctx(text))
        self.assertEqual(self.heads_at_poll[1], self.old,
                         self.ctx("пин сдвинут раньше второго опроса"))
        self.assertEqual(self.head(), self.target, self.ctx(text))
        self.assertEqual(self.clock.sleeps, [poll], self.ctx(text))
        self.assertRegex(text, WAIT_LINE_RE, self.ctx(text))

    def test_ac2_unknown_is_not_green_on_wait_path(self):
        """Первый опрос «неизвестно», второй «зелёный»: неизвестный цвет не зелёный.

        Опросов ровно два, пауза ровно одна; на втором опросе пин ещё на
        старом sha, после команды — на целевом (инвариант 19 на пути
        `--wait-ci`).
        Ловит мутацию: ожидание считает `MAIN_UNKNOWN` зелёным (условие
        `kind != MAIN_RUNNING` вместо `kind == MAIN_GREEN`) — пин
        сдвигается после первого опроса, второго опроса и паузы нет; либо
        `MAIN_UNKNOWN` отказывает сразу, как без флага — пин не сдвинут."""
        poll = self.rng.randint(5, 300)
        text, exc = self.run_main("pin-update", self.target, "--wait-ci",
                                  kinds=[ci.MAIN_UNKNOWN, ci.MAIN_GREEN],
                                  poll=poll, ceiling=poll * 10)
        self.assertIsNone(exc, self.ctx(text))
        self.assertEqual(len(self.polls), 2, self.ctx(text))
        self.assertEqual(len(self.clock.sleeps), 1, self.ctx(text))
        self.assertEqual(self.heads_at_poll[1], self.old,
                         self.ctx("пин сдвинут после опроса MAIN_UNKNOWN"))
        self.assertEqual(self.head(), self.target, self.ctx(text))


class WaitCiRefusalTest(PinUpdateWaitCiSandbox):

    def test_ac3_running_then_red_refuses_without_third_poll(self):
        """«Идёт», затем «красный»: отказ текстом красного CI, третьего опроса нет.

        Ловит мутацию: ожидание трактует `MAIN_RED` как незавершённый CI и
        продолжает опрос — появляется третий опрос (и вторая пауза), а
        отказ приходит по потолку, не текстом «сначала почини main»; либо
        текст красного отказа на пути ожидания сочинён заново и
        расходится с прежним."""
        poll = self.rng.randint(5, 300)
        text, exc = self.run_main("pin-update", self.target, "--wait-ci",
                                  kinds=[ci.MAIN_RUNNING, ci.MAIN_RED],
                                  poll=poll, ceiling=poll * 10)
        message = self.refusal(exc)
        self.assertEqual(
            message,
            f"pin-update: CI коммита {self.target[:8]} красный — опрос 2: "
            f"{ci.MAIN_RED}; пин не сдвинут, сначала почини main",
            self.ctx(text))
        self.assertEqual(len(self.polls), 2, self.ctx(text))
        self.assertEqual(self.head(), self.old, self.ctx(text))

    def test_ac4_ceiling_refusal_names_the_ceiling_constant(self):
        """CI «идёт» до потолка: отказ «потолок ожидания CI main истёк (N сек)», N — константа.

        Потолок случайный и НЕ кратен периоду, поэтому прошедшее время на
        отказе больше потолка: число в тексте обязано быть значением
        `MERGE_GATE_CI_WAIT_CEILING_SEC`, а не прошедшим временем; пин на
        месте.
        Ловит мутацию: в текст отказа подставлено прошедшее время
        (`int(monotonic() - start)`) вместо константы потолка — число в
        скобках больше потолка; либо потолок не проверяется и команда не
        отказывает вовсе (опрос до таймаута теста) — нет отказа с текстом
        потолка."""
        poll = self.rng.randint(5, 120)
        ceiling = poll * self.rng.randint(1, 6) + self.rng.randint(1, poll - 1)
        text, exc = self.run_main("pin-update", self.target, "--wait-ci",
                                  kinds=[ci.MAIN_RUNNING],
                                  poll=poll, ceiling=ceiling)
        message = self.refusal(exc)
        self.assertIn(f"потолок ожидания CI main истёк ({ceiling} сек)",
                      message, self.ctx(f"poll={poll}, ceiling={ceiling}; {text}"))
        self.assertEqual(self.head(), self.old, self.ctx(text))

    def test_ac5_ceiling_equal_to_period_refuses_after_second_poll(self):
        """Потолок равен периоду, CI всё время «идёт»: отказ после второго опроса.

        Пауза ровно одна, строка «(ожидание … сек)» напечатана дважды —
        на каждом опросе до проверки потолка.
        Ловит мутацию: потолок сверяется строгим `>` вместо `>=` —
        появляются третий опрос и вторая пауза; пауза ставится и после
        последнего незелёного опроса — пауз две; проверка потолка стоит
        до печати строки ожидания — строка напечатана один раз."""
        poll = self.rng.randint(5, 300)
        text, exc = self.run_main("pin-update", self.target, "--wait-ci",
                                  kinds=[ci.MAIN_RUNNING],
                                  poll=poll, ceiling=poll)
        message = self.refusal(exc)
        self.assertIn("потолок ожидания CI main истёк", message, self.ctx(text))
        self.assertEqual(len(self.polls), 2, self.ctx(text))
        self.assertEqual(len(self.clock.sleeps), 1, self.ctx(text))
        self.assertEqual(len(WAIT_LINE_RE.findall(text)), 2, self.ctx(text))
        self.assertEqual(self.head(), self.old, self.ctx(text))


class WithoutWaitCiTest(PinUpdateWaitCiSandbox):

    def test_ac6_without_flag_running_refuses_as_before(self):
        """Без `--wait-ci` и с CI «идёт» — прежний отказ, паузы нет.

        Ловит мутацию: ожидание включено всегда, а не только по флагу
        (`wait_ci` по умолчанию истинен или диспетчер передаёт `True`) —
        команда делает паузу и опрашивает CI снова вместо немедленного
        отказа «повтори, когда CI завершится»."""
        text, exc = self.run_main("pin-update", self.target,
                                  kinds=[ci.MAIN_RUNNING],
                                  poll=self.rng.randint(5, 300),
                                  ceiling=self.rng.randint(301, 4000))
        message = self.refusal(exc)
        self.assertEqual(
            message,
            f"pin-update: CI не подтверждён для {self.target[:8]} — опрос 1: "
            f"{ci.MAIN_RUNNING}; пин не сдвинут, повтори, когда CI завершится",
            self.ctx(text))
        self.assertEqual(self.clock.sleeps, [], self.ctx(text))
        self.assertEqual(self.head(), self.old, self.ctx(text))

    def test_ac7_canary_refusal_comes_before_any_ci_poll(self):
        """Нет зелёного прогона канарейки и `--wait-ci`: отказ канарейки без опроса CI.

        Подменённый возраст — «прогона нет» либо не моложе предела
        `CANARY_MAX_MERGES_SINCE_GREEN`.
        Ловит мутацию: ожидание CI поставлено до гейта канарейки — команда
        опрашивает `main_line_status` (и ждёт) прежде, чем отказать
        канарейкой."""
        for age in (None, config.CANARY_MAX_MERGES_SINCE_GREEN
                    + self.rng.randint(0, 5)):
            with self.subTest(age=age):
                self.polls.clear()
                self.clock.sleeps.clear()
                text, exc = self.run_main("pin-update", self.target,
                                          "--wait-ci", kinds=[ci.MAIN_RUNNING],
                                          canary_age=age)
                message = self.refusal(exc)
                self.assertIn("нет зелёного прогона канарейки", message,
                              self.ctx(text))
                self.assertEqual(self.polls, [], self.ctx(text))
                self.assertEqual(self.clock.sleeps, [], self.ctx(text))
                self.assertEqual(self.head(), self.old, self.ctx(text))


class DispatcherFormTest(PinUpdateWaitCiSandbox):

    def test_ac8_missing_sha_refuses_with_command_form(self):
        """`pin-update` без аргументов и `pin-update --wait-ci` — отказ с формой команды.

        Не исключение индекса; `fetch` не вызван, журнал не изменился.
        Ловит мутацию: диспетчер берёт `rest[0]` как sha без проверки —
        без аргументов падает `IndexError`, а `--wait-ci` уходит в
        `cmd_pin_update` как sha и вызывает `git fetch`."""
        for args in ((), ("--wait-ci",)):
            with self.subTest(args=args):
                before = store.journal_maxima(self.conn)
                text, exc = self.run_main("pin-update", *args,
                                          kinds=[ci.MAIN_GREEN])
                self.assertEqual(self.refusal(exc), NO_SHA_REFUSAL,
                                 self.ctx(text))
                self.assert_no_fetch(text)
                self.assertEqual(store.journal_maxima(self.conn), before,
                                 self.ctx(text))
                self.assertEqual(self.head(), self.old, self.ctx(text))

    def test_ac9_unknown_argument_refuses_with_its_name(self):
        """`pin-update <sha> --wait` и `<sha> --wait-ci --force` — отказ с именем аргумента.

        `fetch` не вызван, журнал не изменился.
        Ловит мутацию: неизвестные флаги молча отбрасываются (флаг
        ищется только по наличию `--wait-ci`) — команда идёт в `fetch` и
        дальше; либо отказ называет не тот аргумент."""
        cases = ((self.target, "--wait"), "--wait"), \
            ((self.target, "--wait-ci", "--force"), "--force")
        for args, bad in cases:
            with self.subTest(args=args):
                before = store.journal_maxima(self.conn)
                text, exc = self.run_main("pin-update", *args,
                                          kinds=[ci.MAIN_GREEN])
                self.assertEqual(
                    self.refusal(exc),
                    f"pin-update: неизвестный аргумент {bad} — {USAGE}",
                    self.ctx(text))
                self.assert_no_fetch(text)
                self.assertEqual(store.journal_maxima(self.conn), before,
                                 self.ctx(text))
                self.assertEqual(self.head(), self.old, self.ctx(text))


if __name__ == "__main__":
    unittest.main()
