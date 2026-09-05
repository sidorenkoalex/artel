"""AC-13 (tasks/01M1PNBSHR2PMFECMP7C204MF1/SPEC.md): «Тест подтверждает:
агентный шаг роли стартует в новой группе процессов — pgid дочернего
процесса не равен pgid пульта.»

В отличие от AC-1 (`test_ac1_spawn_agent_new_process_group.py`, вызывает
`runner.spawn_agent` напрямую) — здесь агентный шаг заводится ЦЕЛИКОМ,
через настоящий `runner.run_agent_once` (lease/бюджет/git-идентичность/
чекпоинт заглушены — не предмет этой задачи, см. `_sandbox.
AgentStepSandbox`), одним реальным вызовом `role_cmd`, подменённым на
скрипт-пробу. Это ловит регрессию на СТЫКЕ («spawn_agent сам по себе
заводит группу, но `run_agent_once` эту группу почему-то не долетает до
реального шага роли» — например, если фикс AC-1 положат в другую, не
исполняемую в этом пути функцию), которую низкоуровневый AC-1 не видит.

Красен до реализации: `run_agent_once` сегодня зовёт `spawn_agent` без
выставления новой сессии — тот же класс красноты, что у AC-1, но
пойманный на уровне целого шага, а не примитива.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AgentStepSandbox, wait_for  # noqa: E402


class AgentStepPgidTest(AgentStepSandbox):

    def test_ac13_agent_step_child_pgid_differs_from_pult_pgid(self):
        """Полный шаг роли (`run_agent_once`) с `role_cmd`, подменённым на
        скрипт, пишущий собственный pgid в файл — сравнивается с pgid
        этого тестового процесса (роль «пульта» в терминах AC-13).

        Ловит мутацию: если развязка AC-1 (новая сессия) сделана в
        `spawn_agent`, но вызов внутри `run_agent_once` обходит её (другой
        путь спавна, kwarg перекрыт значением по умолчанию выше по стеку
        и т. п.) — записанный потомком pgid совпадёт с pgid пульта, и
        `assertNotEqual` покраснеет, хотя изолированный тест AC-1 остался
        бы зелёным.
        """
        pult_pgid = os.getpgid(0)

        outcome, _, _ = self.run_step(self.pgid_probe_cmd())

        self.assertEqual(outcome, "ok", "шаг-проба не завершился успешно")
        probe = self.probe_path("pgid.txt")
        self.assertTrue(wait_for(probe.exists, timeout=2.0),
                        "скрипт-проба не записал свой pgid")
        child_pgid = int(probe.read_text(encoding="utf-8").strip())
        self.assertNotEqual(child_pgid, pult_pgid,
                            "pgid агентного шага совпал с pgid пульта — "
                            "шаг не запущен в новой группе процессов")


if __name__ == "__main__":
    unittest.main()
