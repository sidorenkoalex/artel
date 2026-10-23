"""`kill <id> [--yes] [--reason "<текст>"]`: причина ликвидации в детали
перехода `state -> killed` и через неё в строке «Итог:» RETRO.

Группа: долгоживущий
Красен до реализации: диспетчер `kill` не разбирает `--reason`, `cleanup.cmd_kill` не принимает `reason` и возвращает `None`, деталь перехода всегда «kill switch», подсказки «причина не записана» нет, справка не называет флаг. Методы AC-4, AC-5, AC-14, AC-15 зелены и до реализации — они держат прежнее поведение отказа живому циклу и терминальной задачи, которое реализация обязана не сломать.

Сквозные сценарии держат связку «командная строка `artel.main` —
`cleanup.cmd_kill` — журнал БД — `retro.build_killed`» в настоящей
git-песочнице `TmpRepoTest` (та же, что у `tests/test_kill_cleanup.py`):
задача заводится `new`, kill идёт без подмен уборки. Живой цикл —
lease на pid отдельного дочернего процесса-заглушки этого host со свежим
heartbeat на состоянии `in_dev` (роль `developer`): так отказ живому
циклу срабатывает настоящим путём, а ошибочный kill не снимет сигналом
сам процесс тестов.
"""
import contextlib
import io
import os
import random
import socket
import subprocess
import sys
import unittest
from unittest import mock

from orchestrator import artel, cleanup, config, retro, runner, store
from tests.test_kill_cleanup import TmpRepoTest

KILLED_ACTION = "state -> killed"
HINT_PREFIX = "причина не записана"
EMPTY_REFUSAL = "kill: --reason требует непустую причину"
FLAG_REFUSAL = "kill: --reason требует причину следующим аргументом, а не флаг"


def hint_line(arg: str) -> str:
    return (f"причина не записана — в следующий раз: artel.py kill {arg} "
            f'--reason "<текст>"')


class KillReasonSandbox(TmpRepoTest):
    """Песочница сценариев `kill`: вызов через `artel.main` из окружения
    Оператора, снимки журнала и RETRO задачи."""

    def run_main(self, *args: str) -> tuple[str, SystemExit | None]:
        """`artel.py <args>` из окружения Оператора; (весь вывод вместе с
        текстом выхода, исключение выхода либо `None`)."""
        operator_env = {k: v for k, v in os.environ.items()
                        if k not in (config.ARTEL_ROLE_ENV, "HOME")}
        out, err = io.StringIO(), io.StringIO()
        exit_exc = None
        with mock.patch.dict(os.environ, operator_env, clear=True), \
                mock.patch.object(sys, "argv", ["artel.py", *args]), \
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

    def steps(self) -> list:
        return store.task_steps(store.db(), self.TASK)

    def killed_details(self) -> list[str]:
        return [s["detail"] for s in self.steps() if s["action"] == KILLED_ACTION]

    def last_killed_detail(self) -> str:
        details = self.killed_details()
        self.assertTrue(details, "перехода state -> killed в журнале нет")
        return details[-1]

    def retro_text(self) -> str:
        return retro.build_killed(store.db(), self.TASK)

    def itog_lines(self) -> list[str]:
        return [line for line in self.retro_text().splitlines()
                if line.startswith("Итог:")]

    def assert_single_itog(self, detail: str) -> None:
        self.assertEqual(self.itog_lines(),
                         [f"Итог: killed — причина: {detail}"])

    def seed_live_cycle(self):
        """Живой цикл: `in_dev` и lease на живой pid этого host со свежим
        heartbeat; строка lease — для сверки текста отказа."""
        holder = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(600)"])
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        conn = store.db()
        store.set_state(conn, self.TASK, "in_dev", "operator",
                        expected_state=self.task_row()["state"], detail="тест")
        store.insert_lease(conn, self.TASK, "cycle-session", holder.pid,
                           socket.gethostname(), store.now())
        return store.lease_row(conn, self.TASK)

    def live_cycle_refusal_text(self, row) -> str:
        role = runner.step_role(self.task_row())
        return (f"[{self.TASK}] цикл жив (pid {row['pid']}, шаг {role} с "
                f"{row['heartbeat_ts']}) — остановить цикл: artel.py stop "
                f"{self.TASK}; ликвидировать задачу (ветка и worktree будут "
                f"удалены): artel.py kill {self.TASK} --yes")

    def kill_directly(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            cleanup.cmd_kill(self.TASK)


class KillReasonDetailTest(KillReasonSandbox):
    """Причина `--reason` попадает в деталь перехода и в «Итог:» RETRO."""

    def test_ac1_reason_before_yes_lands_in_detail_and_retro(self):
        """`kill <id> --reason "дубль X" --yes` через `artel.main`.

        Деталь последней записи `state -> killed` — `kill switch: дубль X`,
        RETRO несёт строку «Итог: killed — причина: kill switch: дубль X».

        Ловит мутацию: диспетчер разбирает `--reason`, но `_cmd_kill` по-
        прежнему пишет постоянную деталь `kill switch` (параметр не дошёл до
        `set_state`) — деталь и строка «Итог:» без причины.
        """
        self.run_main("kill", self.TASK, "--reason", "дубль X", "--yes")

        self.assertEqual(self.task_row()["state"], "killed")
        self.assertEqual(self.last_killed_detail(), "kill switch: дубль X")
        self.assertIn("Итог: killed — причина: kill switch: дубль X",
                      self.retro_text().splitlines())

    def test_ac2_yes_before_reason_gives_the_same_result(self):
        """`kill <id> --yes --reason "дубль X"` — порядок флагов обратный.

        Результат тот же, что при `--reason` перед `--yes`.

        Ловит мутацию: значение причины берётся позиционно (`rest[2]` после
        `--reason` на фиксированном месте) — при `--yes` первым деталь
        становится `kill switch: --reason` либо причины нет вовсе.
        """
        self.run_main("kill", self.TASK, "--yes", "--reason", "дубль X")

        self.assertEqual(self.last_killed_detail(), "kill switch: дубль X")
        self.assertIn("Итог: killed — причина: kill switch: дубль X",
                      self.retro_text().splitlines())

    def test_ac10_newline_is_replaced_by_one_space(self):
        """Причина `"строка 1\\nстрока 2"`.

        Деталь — `kill switch: строка 1 строка 2`, строка «Итог:» в RETRO
        одна и несёт всю причину.

        Ловит мутацию: причина пишется в деталь без замены перевода строки
        — деталь содержит `\\n`, «Итог:» обрывается на «строка 1», а
        «строка 2» уходит отдельной строкой RETRO.
        """
        self.run_main("kill", self.TASK, "--reason", "строка 1\nстрока 2")

        self.assertEqual(self.last_killed_detail(),
                         "kill switch: строка 1 строка 2")
        self.assert_single_itog("kill switch: строка 1 строка 2")

    def test_ac11_crlf_is_replaced_by_exactly_one_space(self):
        """Причина `"строка 1\\r\\nстрока 2"`.

        Деталь — `kill switch: строка 1 строка 2` с ровно одним пробелом
        между словами, строка «Итог:» в RETRO одна.

        Ловит мутацию: `\\r` и `\\n` заменяются пробелом по отдельности —
        деталь `kill switch: строка 1  строка 2` с двумя пробелами.
        """
        self.run_main("kill", self.TASK, "--reason", "строка 1\r\nстрока 2")

        self.assertEqual(self.last_killed_detail(),
                         "kill switch: строка 1 строка 2")
        self.assert_single_itog("kill switch: строка 1 строка 2")

    def test_ac12_lone_cr_is_replaced_by_one_space(self):
        """Причина `"строка 1\\rстрока 2"`.

        Деталь — `kill switch: строка 1 строка 2`, строка «Итог:» в RETRO
        одна.

        Ловит мутацию: заменяется только `\\n` (`replace("\\n", " ")`) —
        одиночный `\\r` остаётся в детали, она не равна ожидаемой, а
        `splitlines` RETRO рвёт «Итог:» на две строки.
        """
        self.run_main("kill", self.TASK, "--reason", "строка 1\rстрока 2")

        self.assertEqual(self.last_killed_detail(),
                         "kill switch: строка 1 строка 2")
        self.assert_single_itog("kill switch: строка 1 строка 2")

    def test_ac13_edges_are_stripped(self):
        """Причина `"  дубль X \\n"` с пробелами и переводом строки по краям.

        Деталь — `kill switch: дубль X`.

        Ловит мутацию: края не обрезаются либо обрезаются до замены
        переводов строки (`strip` раньше `replace`) — деталь
        `kill switch:   дубль X  ` или `kill switch: дубль X ` с хвостовым
        пробелом.
        """
        self.run_main("kill", self.TASK, "--reason", "  дубль X \n")

        self.assertEqual(self.last_killed_detail(), "kill switch: дубль X")


class KillHintTest(KillReasonSandbox):
    """Подсказка «причина не записана» — только у `kill` из командной
    строки, записавшего переход без `--reason`."""

    def test_ac3_prefix_kill_without_reason_prints_hint_with_typed_prefix(self):
        """`kill <префикс>` без `--reason`: префикс id случайной длины.

        Деталь перехода — `kill switch` побайтно; в выводе строка подсказки
        с ровно введённым префиксом (не полным id) и буквальной заглушкой
        `"<текст>"`.

        Ловит мутацию: подсказка печатает разрешённый полный id вместо
        введённого аргумента (либо подставляет что-то вместо `"<текст>"`),
        или деталь без причины меняется (`kill switch: ` с двоеточием) —
        строка подсказки не та либо деталь не равна `kill switch`.
        """
        seed = random.randrange(2 ** 32)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        prefix = self.TASK[:rng.randrange(6, len(self.TASK))]
        self.assertNotEqual(prefix, self.TASK)

        out, _ = self.run_main("kill", prefix)

        self.assertEqual(self.task_row()["state"], "killed", f"зерно: {seed}")
        self.assertEqual(self.last_killed_detail(), "kill switch",
                         f"зерно: {seed}")
        self.assertIn(hint_line(prefix), out.splitlines(),
                      f"зерно: {seed}; вывод: {out}")
        self.assertNotIn(hint_line(self.TASK), out.splitlines(),
                         f"зерно: {seed}")

    def test_ac4_live_cycle_refusal_keeps_its_text_and_has_no_hint(self):
        """`kill <id>` без `--reason` и без `--yes` при живом цикле.

        Отказ `_refuse_live_cycle` с прежним текстом, подсказки нет.

        Ловит мутацию: диспетчер печатает подсказку при любом вызове без
        `--reason`, не глядя на возврат `cmd_kill` (или печатает её до
        вызова) — строка «причина не записана» в выводе отказа.
        """
        row = self.seed_live_cycle()

        out, exc = self.run_main("kill", self.TASK)

        self.assertIsNotNone(exc, "отказ живому циклу не случился")
        self.assertEqual(exc.code, self.live_cycle_refusal_text(row))
        self.assertNotIn(HINT_PREFIX, out)
        self.assertEqual(self.task_row()["state"], "in_dev")

    def test_ac5_terminal_task_kill_has_no_hint(self):
        """`kill <id>` без `--reason` для уже убитой задачи.

        Вывод «kill не требуется», подсказки нет.

        Ловит мутацию: `cmd_kill` возвращает `True` и для терминальной
        задачи (возврат не взят из флага `won`) — диспетчер печатает
        подсказку на повторном kill.
        """
        self.kill_directly()

        out, _ = self.run_main("kill", self.TASK)

        self.assertIn("kill не требуется", out)
        self.assertNotIn(HINT_PREFIX, out)

    def test_ac6_direct_cmd_kill_returns_true_without_hint(self):
        """Прямой `cleanup.cmd_kill(task_id)` без флагов, как из `canary.py`.

        Переход в `killed` записан, подсказки в выводе нет, возврат `True`.

        Ловит мутацию: подсказку печатает сам `cmd_kill`, а не диспетчер
        (вызовы канарейки её выводят), либо `cmd_kill` не возвращает
        результат `_cmd_kill` (возврат `None`).
        """
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            result = cleanup.cmd_kill(self.TASK)

        self.assertIs(result, True)
        self.assertEqual(self.task_row()["state"], "killed")
        self.assertIn(KILLED_ACTION, [s["action"] for s in self.steps()])
        self.assertNotIn(HINT_PREFIX, buf.getvalue())


class KillReasonRefusalTest(KillReasonSandbox):
    """Отказы по причине — до живого цикла, lease и журнала; причина при
    отказах и для терминальной задачи нигде не пишется."""

    def test_ac7_empty_or_blank_reason_is_refused_without_changes(self):
        """`kill <id> --reason ""` и `kill <id> --reason "   "`.

        Отказ «kill: --reason требует непустую причину»; состояние задачи
        прежнее, новых записей журнала задачи нет.

        Ловит мутацию: проверка пустоты без `strip` (`if not reason`) —
        пробельная причина проходит, задача убита с деталью
        `kill switch: ` либо `kill switch:    `.
        """
        for value in ("", "   "):
            with self.subTest(reason=repr(value)):
                state_before = self.task_row()["state"]
                steps_before = len(self.steps())

                out, exc = self.run_main("kill", self.TASK, "--reason", value)

                self.assertIsNotNone(exc, "отказа нет")
                self.assertIn(EMPTY_REFUSAL, out)
                self.assertEqual(self.task_row()["state"], state_before)
                self.assertEqual(len(self.steps()), steps_before)

    def test_ac8_empty_reason_is_refused_before_live_cycle_check(self):
        """`kill <id> --reason ""` при живом цикле без `--yes`.

        Отказ о пустой причине; записи журнала «kill отклонён: цикл жив»
        нет.

        Ловит мутацию: пустая причина проверяется после
        `_refuse_live_cycle` (например, внутри `_cmd_kill`) — первым
        срабатывает отказ живому циклу и пишет свою запись журнала.
        """
        self.seed_live_cycle()

        out, exc = self.run_main("kill", self.TASK, "--reason", "")

        self.assertIsNotNone(exc, "отказа нет")
        self.assertIn(EMPTY_REFUSAL, out)
        self.assertNotIn(cleanup.KILL_REFUSAL_JOURNAL_ACTION,
                         [s["action"] for s in self.steps()])

    def test_ac9_flag_as_reason_value_is_refused(self):
        """`kill <id> --reason --yes`: значением причины оказался флаг.

        Отказ «…следующим аргументом, а не флаг»; состояние прежнее, новых
        записей журнала нет, записи `state -> killed` нет, ни одна деталь
        не несёт `--yes` причиной.

        Ловит мутацию: значение `--reason` берётся без проверки на `--` —
        задача убита с деталью `kill switch: --yes`.
        """
        state_before = self.task_row()["state"]
        steps_before = len(self.steps())

        out, exc = self.run_main("kill", self.TASK, "--reason", "--yes")

        self.assertIsNotNone(exc, "отказа нет")
        self.assertIn(FLAG_REFUSAL, out)
        self.assertEqual(self.task_row()["state"], state_before)
        self.assertEqual(len(self.steps()), steps_before)
        self.assertEqual(self.killed_details(), [])
        self.assertFalse([s for s in self.steps()
                          if "kill switch: --yes" in (s["detail"] or "")])

    def test_ac14_terminal_task_does_not_record_the_reason(self):
        """`kill <id> --reason "дубль X"` для уже убитой задачи.

        Нового перехода `state -> killed` нет, вывод «kill не требуется»,
        текста `дубль X` нет ни в журнале задачи, ни в её RETRO.

        Ловит мутацию: причина журналится отдельной записью до проверки
        терминальности (например, «kill: причина») — `дубль X` в детали
        записи журнала.
        """
        self.kill_directly()
        killed_before = len(self.killed_details())

        out, _ = self.run_main("kill", self.TASK, "--reason", "дубль X")

        self.assertEqual(len(self.killed_details()), killed_before)
        self.assertIn("kill не требуется", out)
        self.assertFalse([s for s in self.steps()
                          if "дубль X" in (s["detail"] or "")])
        self.assertNotIn("дубль X", self.retro_text())

    def test_ac15_live_cycle_refusal_does_not_record_the_reason(self):
        """`kill <id> --reason "дубль X"` при живом цикле без `--yes`.

        Отказ `_refuse_live_cycle` с прежним текстом, перехода
        `state -> killed` нет, текста `дубль X` нет ни в одной записи
        журнала (в том числе «kill отклонён: цикл жив»), ни в RETRO.

        Ловит мутацию: причину дописывают в текст отказа живому циклу (и
        тем самым в его запись журнала) — текст отказа не равен прежнему,
        `дубль X` в детали записи «kill отклонён: цикл жив».
        """
        row = self.seed_live_cycle()

        _, exc = self.run_main("kill", self.TASK, "--reason", "дубль X")

        self.assertIsNotNone(exc, "отказ живому циклу не случился")
        self.assertEqual(exc.code, self.live_cycle_refusal_text(row))
        self.assertEqual(self.killed_details(), [])
        self.assertFalse([s for s in self.steps()
                          if "дубль X" in (s["detail"] or "")])
        self.assertNotIn("дубль X", self.retro_text())


class KillDispatchReasonTest(KillReasonSandbox):
    """Диспетчер `kill` с подменённым `cleanup.cmd_kill`: `reason=`
    передаётся только при флаге `--reason`."""

    def test_ac16_reason_kwarg_only_with_the_flag(self):
        """Три вызова диспетчера с подменённым `cleanup.cmd_kill`.

        `--reason "дубль X"` — вызов с `reason="дубль X"`; `kill <id>` и
        `kill <id> --yes` — прежний вызов без `reason`. Существующие тесты
        `KillDispatchYesFlagTest` (`tests/test_kill_live_cycle_refusal.py`)
        проходят.

        Ловит мутацию: диспетчер передаёт `reason=None` всегда (без
        образца `_approve_during_canary_kwargs`) — вызовы без флага не
        равны `cmd_kill(<id>, confirmed=…)`, существующие тесты красны.
        """
        cases = ((("--reason", "дубль X"),
                  mock.call(self.TASK, confirmed=False, reason="дубль X")),
                 ((), mock.call(self.TASK, confirmed=False)),
                 (("--yes",), mock.call(self.TASK, confirmed=True)))
        for flags, expected in cases:
            with self.subTest(flags=flags):
                with mock.patch.object(cleanup, "cmd_kill") as kill:
                    self.run_main("kill", self.TASK, *flags)
                self.assertEqual(kill.call_args_list, [expected])

        from tests import test_kill_live_cycle_refusal as existing
        suite = unittest.TestSuite(
            existing.KillDispatchYesFlagTest(name) for name in (
                "test_yes_flag_reaches_cmd_kill_as_confirmed_true",
                "test_missing_flag_reaches_cmd_kill_as_confirmed_false"))
        result = unittest.TestResult()
        suite.run(result)
        self.assertEqual((result.testsRun, result.failures, result.errors),
                         (2, [], []))


class KillHelpTest(unittest.TestCase):
    """Справка `artel.py` называет флаги `kill`."""

    def test_ac17_help_line_names_yes_and_reason_flags(self):
        """Строка перечня команд с `kill <id>` в справке `artel.py`.

        Строка называет `[--yes] [--reason "<текст>"]`.

        Ловит мутацию: флаг добавлен в диспетчер, а строка справки
        оставлена прежней (`kill <id> |`) — строки с флагами нет.
        """
        lines = [line for line in (artel.__doc__ or "").splitlines()
                 if "kill <id>" in line]
        self.assertTrue(lines, "строки kill <id> в справке нет")
        self.assertTrue(any('[--yes] [--reason "<текст>"]' in line
                            for line in lines), lines)


if __name__ == "__main__":
    unittest.main()
