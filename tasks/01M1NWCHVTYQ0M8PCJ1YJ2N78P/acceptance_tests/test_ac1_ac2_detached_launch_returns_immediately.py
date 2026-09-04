"""AC-1/AC-2: `auto`/`run` без `--attach` возвращают управление сразу,
напечатав pid отвязанного процесса, путь лога цикла и подсказку
`artel.py log <id>`, а сам цикл продолжает исполняться в отвязанном
процессе после возврата команды.

Красен до реализации: сегодня `run`/`auto` не отвязываются — вызывающая
команда блокируется, пока не отработает (или не встанет буксовать) сам
цикл; на задаче `in_dev` без готового PLAN.md это далеко за пределами
разумного таймаута теста (`AUTO_STALL_STEPS_LIMIT` повторов при живом
подставном `claude`), поэтому `run_cli` ловит это как `timed_out=True`,
а не зависает.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DetachedCycleSandbox  # noqa: E402

# Заведомо больше, чем разумный бюджет на «вернуться сразу» (доли секунды
# — секунда с запасом на планировщик ОС), и заведомо меньше времени сна
# подставного `claude` — так тест ловит именно «вернулась мгновенно, а
# не потому что шаг уже успел закончиться».
RETURN_BUDGET_SEC = 3.0
CLAUDE_SLEEP_SEC = 8


class Ac1Ac2DetachedLaunchReturnsImmediatelyTest(DetachedCycleSandbox):

    def setUp(self):
        super().setUp()
        self.enter_in_dev()
        self.set_claude_sleep(CLAUDE_SLEEP_SEC)

    def test_ac1_auto_returns_immediately_with_pid_log_hint(self):
        """`auto <id>` без `--attach`: команда возвращается почти сразу,
        не дожидаясь ни одного реального шага (подставной `claude` спит
        {CLAUDE_SLEEP_SEC}с — вызывающая команда обязана вернуться на
        порядок быстрее), напечатав pid ДРУГОГО, всё ещё живого процесса,
        путь `.artel/logs/<id>-auto-<n>.log` и подсказку
        `artel.py log <id>`.

        Ловит мутацию: `--attach` стал поведением по умолчанию (флаг
        detach убрали/инвертировали) — тест покраснеет на `timed_out`
        или на `elapsed >= RETURN_BUDGET_SEC`, поскольку вызывающая
        команда снова дождётся полного шага агента.
        """
        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "auto", self.TASK, timeout=RETURN_BUDGET_SEC + 2)

        self.assertFalse(
            timed_out,
            f"[{self.TASK}] auto без --attach не вернула управление за "
            f"{RETURN_BUDGET_SEC + 2}с — цикл не отвязан от вызывающей "
            f"команды:\n{out}")
        self.assertEqual(rc, 0, f"auto завершилась ненулевым кодом: {out}")
        self.assertLess(
            elapsed, RETURN_BUDGET_SEC,
            f"auto вернулась только через {elapsed:.2f}с (бюджет "
            f"{RETURN_BUDGET_SEC}с, подставной шаг длится "
            f"{CLAUDE_SLEEP_SEC}с) — управление не вернулось сразу:\n{out}")

        pid = self.extract_pid(out)
        self.track_pid(pid)
        self.assertIsNotNone(
            pid, f"вывод не назвал pid отвязанного процесса: {out!r}")
        self.assertNotEqual(
            pid, launcher_pid,
            "напечатанный pid совпал с pid короткоживущей вызывающей "
            "команды — это не pid ОТВЯЗАННОГО процесса")

        self.assertRegex(
            out, re.compile(rf"{re.escape(self.TASK)}-auto-\d+\.log"),
            f"вывод не назвал путь .artel/logs/{self.TASK}-auto-<n>.log "
            f"(SPEC AC-1/AC-3, требование 1): {out!r}")
        self.assertIn(
            f"artel.py log {self.TASK}", out,
            f"вывод не назвал подсказку «наблюдать: artel.py log "
            f"{self.TASK}»: {out!r}")

        self.assertTrue(
            self.is_alive(pid),
            f"процесс pid={pid}, напечатанный как «отвязанный», не найден "
            f"живым сразу после возврата вызывающей команды — либо это "
            f"был не тот процесс, либо цикл уже успел (неправдоподобно "
            f"быстро) завершиться")

    def test_ac2_run_returns_immediately_with_pid_log_hint(self):
        """`run <id>` без `--attach`: та же форма возврата, что у `auto`
        (AC-2) — pid отвязанного процесса, путь СОБСТВЕННОГО лога цикла
        (SPEC не фиксирует его точное имя, в отличие от `auto`) и та же
        подсказка `artel.py log <id>`.

        Ловит мутацию: `run` забыли завести в тот же путь отвязки, что и
        `auto` (реализовали detach только для одной из двух команд) —
        тест покраснеет на `timed_out`/`elapsed`, поскольку `run` при
        этом продолжит блокироваться до конца подставного шага.
        """
        out, rc, elapsed, launcher_pid, timed_out = self.run_cli(
            "run", self.TASK, timeout=RETURN_BUDGET_SEC + 2)

        self.assertFalse(
            timed_out,
            f"[{self.TASK}] run без --attach не вернула управление за "
            f"{RETURN_BUDGET_SEC + 2}с:\n{out}")
        self.assertEqual(rc, 0, f"run завершилась ненулевым кодом: {out}")
        self.assertLess(
            elapsed, RETURN_BUDGET_SEC,
            f"run вернулась только через {elapsed:.2f}с (бюджет "
            f"{RETURN_BUDGET_SEC}с): {out}")

        pid = self.extract_pid(out)
        self.track_pid(pid)
        self.assertIsNotNone(
            pid, f"вывод не назвал pid отвязанного процесса: {out!r}")
        self.assertNotEqual(pid, launcher_pid)

        log_path = self.extract_log_path(out)
        self.assertIsNotNone(
            log_path,
            f"вывод не назвал путь СОБСТВЕННОГО лога цикла run под "
            f".artel/logs/: {out!r}")
        self.assertTrue(
            Path(log_path).exists(),
            f"названный лог {log_path} не существует на диске")
        self.assertIn(f"artel.py log {self.TASK}", out)

        self.assertTrue(self.is_alive(pid))


if __name__ == "__main__":
    unittest.main()
