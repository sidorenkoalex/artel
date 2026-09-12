"""Приёмочный тест AC-7 задачи 01M290PP4KBTG1KYS1PWKQJH6T — `watch
--exit-on <класс>[,<класс>...]` завершает процесс кодом 0 сразу после
первой напечатанной строки любого из перечисленных классов, не дожидаясь
следующего опроса `--interval`; `--once` — синоним `--exit-on` с
классами по умолчанию; без обоих флагов поведение прежнее.

Красен до реализации: у `cmd_watch` сегодня нет ни `--exit-on`, ни
`--once` — оба флага молча игнорируются `_parse_args` (не входят в
разбираемый набор аргументов), цикл ведёт себя как обычно и не
завершается по факту печати строки — во всех тестах, ожидающих
`SystemExit`/мёртвый поток после печати маркера, `_join(timeout=…)`
застанет поток ЖИВЫМ, `assertFalse(thread.is_alive())` внутри `_join`
покраснеет.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import WatchTestCase  # noqa: E402


class ExitOnFiltersByListedClassTest(WatchTestCase):

    def test_ac7_exit_on_ignores_lines_outside_the_listed_classes(self):
        """`--events steps,refusals --exit-on refusals`: строка класса
        `steps` печатается, но НЕ завершает процесс; следующая за ней
        строка класса `refusals` завершает его кодом 0.

        Ловит мутацию: `--exit-on` завершает по ПЕРВОЙ напечатанной
        строке ЛЮБОГО класса, не только перечисленных (`refusals`) —
        тогда поток завершился бы уже на строке `steps`, и
        `assertTrue(is_alive())` сразу после неё упадёт.
        """
        conn = store.db()
        self._insert_task("E701")

        self._start(["--tasks", "E701", "--events", "steps,refusals",
                    "--exit-on", "refusals", "--interval", "0.3"])
        self._settle()

        store.journal(conn, "E701", "runner", "agent run started",
                     "маркер-steps-не-завершает")
        self._wait_until(
            lambda: "маркер-steps-не-завершает" in self._stream.getvalue())
        self.assertTrue(self._thread.is_alive(),
                        "watch завершился на строке класса, не входящего "
                        "в --exit-on")

        store.journal(conn, "E701", "fsm",
                     f"{store.REFUSAL_ACTION_PREFIX}: причина",
                     "маркер-refusals-завершает")
        self._join(timeout=3.0)
        self.assertIn("маркер-refusals-завершает", self._stream.getvalue())
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class ExitOnDoesNotWaitForNextIntervalTest(WatchTestCase):

    def test_ac7_exit_on_terminates_without_an_extra_full_interval_wait(self):
        """`--interval 3` (намеренно крупный): маркер класса `refusals`
        заводится СРАЗУ после старта — обнаруживается ПЕРВЫМ же опросом
        (~t=3с, т.к. `known_step_id` снят стартовым снимком раньше записи).
        Правильная реализация завершается СРАЗУ на этом опросе; ожидание
        `_join(timeout=4.5)` укладывается в это время с запасом, но НЕ
        укладывается в удвоенный интервал (~6с), которым обернулась бы
        реализация, добавляющая ещё один `time.sleep(interval)` перед
        проверкой `--exit-on`.

        Ловит мутацию: `--exit-on` проверяется только В НАЧАЛЕ следующей
        итерации ПОСЛЕ печати (то есть после ещё одного полного
        `time.sleep(interval)`) — реальное завершение сдвинется к ~t=6с,
        `_join(timeout=4.5)` не застанет поток мёртвым, `assertFalse` в
        `_join` покраснеет.
        """
        conn = store.db()
        self._insert_task("E704")

        self._start(["--tasks", "E704", "--exit-on", "refusals",
                    "--interval", "3"])
        self._settle()

        store.journal(conn, "E704", "fsm",
                     f"{store.REFUSAL_ACTION_PREFIX}: причина",
                     "маркер-без-лишнего-ожидания")
        self._join(timeout=4.5)
        self.assertIn("маркер-без-лишнего-ожидания",
                      self._stream.getvalue())
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class OnceIsExitOnWithDefaultClassesTest(WatchTestCase):

    def test_ac7_once_exits_after_first_line_of_any_default_class(self):
        """`--once` без `--events` — завершается кодом 0 сразу после
        первой строки класса по умолчанию (`_DEFAULT_EVENTS`, здесь —
        `steps`, класс `agent run started`).

        Ловит мутацию: `--once` игнорируется (тот же прежний
        бесконечный цикл) — поток остаётся жив дольше `_join(timeout=2.0)`,
        `assertFalse(thread.is_alive())` внутри `_join` покраснеет.
        """
        conn = store.db()
        self._insert_task("E702")

        self._start(["--tasks", "E702", "--once", "--interval", "0.3"])
        self._settle()

        store.journal(conn, "E702", "runner", "agent run started",
                     "маркер-once-завершает")
        self._join(timeout=2.0)
        self.assertIn("маркер-once-завершает", self._stream.getvalue())
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class WithoutExitOnBehaviorUnchangedTest(WatchTestCase):

    def test_ac7_without_exit_on_or_once_a_printed_line_does_not_terminate(self):
        """Без `--exit-on`/`--once` печать строки НЕ завершает процесс —
        поведение как до этой задачи (бесконечный поток до `--until`/
        истощения выборки).

        Ловит мутацию: реализация `--exit-on`/`--once` случайно меняет
        поведение ПО УМОЛЧАНИЮ (завершает по первой строке, даже когда ни
        один из флагов не передан) — поток умер бы раньше явного перевода
        задачи в терминальное состояние, `assertTrue(is_alive())` покраснеет.
        """
        conn = store.db()
        self._insert_task("E703")

        self._start(["--tasks", "E703", "--interval", "1"])
        self._settle()

        store.journal(conn, "E703", "runner", "agent run started",
                     "маркер-обычный-режим")
        self._wait_until(
            lambda: "маркер-обычный-режим" in self._stream.getvalue())
        self.assertTrue(self._thread.is_alive(),
                        "watch завершился по факту печати строки без "
                        "--exit-on/--once")

        self._set_state("E703", "killed", "in_dev")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


if __name__ == "__main__":
    unittest.main()
