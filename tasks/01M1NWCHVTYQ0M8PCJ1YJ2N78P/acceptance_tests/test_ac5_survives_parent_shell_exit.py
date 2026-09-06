"""AC-5: завершение процесса-родителя (промежуточной оболочки),
запустившего отвязанный цикл, не останавливает сам цикл — он продолжает
шаги задачи после того, как породившая его оболочка уже завершилась.

Красен до реализации: сегодня `auto <id>` — прямой потомок оболочки, не
отвязанный собственной сессией ОС; сама оболочка не может «уже
завершиться раньше цикла» (см. AC-1/AC-2) — коммуникация с shell'ом либо
идёт полным временем цикла (`communicate` не вернётся до конца
подставного шага), либо, если бы шаг где-то оборвал наследуемый терминал,
процесс агента получил бы SIGHUP/оборвался вместе с ним. Тест ловит
именно первое: `shell_returncode`/`elapsed` укажут, что оболочка ждала
цикл целиком, а не наоборот.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DetachedCycleSandbox  # noqa: E402

CLAUDE_SLEEP_SEC = 6


class Ac5SurvivesParentShellExitTest(DetachedCycleSandbox):

    def setUp(self):
        super().setUp()
        self.enter_in_dev()
        self.set_claude_sleep(CLAUDE_SLEEP_SEC)

    def test_ac5_cycle_outlives_the_intermediate_shell_that_launched_it(self):
        """Запускает `auto <id>` (без `--attach`) не напрямую, а через
        промежуточную оболочку (`sh -c "python3 .../artel.py auto <id>"`,
        тот же приём запуска, что называет SPEC), дожидается, пока сама
        оболочка полностью завершится, и только ПОСЛЕ этого проверяет:
        (1) pid, напечатанный командой, всё ещё жив; (2) цикл реально
        продолжает делать шаги ПОСЛЕ смерти оболочки — журнал задачи
        получает запись о завершении подставного шага уже после того, как
        `shell_proc` вернул код возврата.

        Ловит мутацию: детач сделан БЕЗ отвязки от сессии/группы процессов
        (`subprocess.Popen(...)` без `start_new_session=True`/эквивалента)
        — тогда завершение промежуточной оболочки посылает SIGHUP всей её
        группе процессов, и отвязанный процесс либо гибнет вместе с ней
        (тест упадёт на `is_alive`), либо переживает саму оболочку, но
        никогда не дописывает «agent run finished» (упадёт на ожидании
        журнала).
        """
        shell_proc = self.spawn_via_shell("auto", self.TASK)
        try:
            out, _ = shell_proc.communicate(timeout=CLAUDE_SLEEP_SEC + 5)
        except subprocess.TimeoutExpired:
            shell_proc.kill()
            out, _ = shell_proc.communicate()
            self.fail(
                f"промежуточная оболочка не завершилась за "
                f"{CLAUDE_SLEEP_SEC + 5}с — команда всё ещё не отвязана "
                f"(AC-1/AC-2), оболочка ждёт цикл целиком:\n{out}")

        self.assertEqual(
            shell_proc.returncode, 0,
            f"промежуточная оболочка не завершилась штатно:\n{out}")

        pid = self.extract_pid(out)
        self.track_pid(pid)
        self.assertIsNotNone(
            pid, f"вывод не назвал pid отвязанного процесса: {out!r}")

        self.assertTrue(
            self.is_alive(pid),
            f"процесс pid={pid} мёртв сразу после того, как завершилась "
            f"породившая его оболочка — цикл не пережил родителя")

        def step_finished():
            return any(r["action"] == "agent run finished"
                      for r in self.journal())

        finished = self.wait_until(
            step_finished, timeout=CLAUDE_SLEEP_SEC + 5)
        self.assertTrue(
            finished,
            f"цикл не дописал завершение подставного шага в журнал уже "
            f"ПОСЛЕ смерти породившей его оболочки — работа не "
            f"продолжилась независимо от родителя:\n{self.journal_text()}")


if __name__ == "__main__":
    unittest.main()
