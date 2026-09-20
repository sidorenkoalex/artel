"""AC-5: `role_cmd()` без параметров и argv шага, совпадающий с
зафиксированным до задачи списком.

Зелёный с рождения: argv шага собран до задачи и не меняется ею — тест
стережёт его через рефакторинг и покраснеет, если провайдер соберёт
команду иначе (задача объявляет любое отличие argv дефектом).
"""
import inspect
import shutil
import unittest
from pathlib import Path

from orchestrator import config, runner
from tests.sandbox import TmpRootTest

# Хвост argv шага роли, зафиксированный ДО задачи (`runner.role_cmd()` на
# 20.09): флаги в том же порядке, значение `--setting-sources` — от
# крутилки Оператора `config.AGENT_SETTING_SOURCES`, не литералом.
EXPECTED_TAIL = [
    "-p", "--permission-mode", "acceptEdits",
    "--output-format", "stream-json", "--verbose",
    "--allowedTools", "Bash(git:*),Bash(python3:*)",
    "--setting-sources", config.AGENT_SETTING_SOURCES,
    "--strict-mcp-config",
]


class RoleCmdArgvTest(TmpRootTest):
    """Песочница нужна ради подмены `stack.check_stack` и резолва
    инструментов манифеста, не ради файлов: `role_cmd()` — чистая сборка."""

    def test_ac5_role_cmd_takes_no_parameters(self):
        """Сигнатура `role_cmd()` — пустой список параметров.

        Ловит мутацию: провайдер роли протаскивается параметром
        (`role_cmd(provider)`) — все вызывающие обязаны знать провайдера,
        а офлайн-смок изоляции и `run_agent_once` расходятся в том, кого
        они спрашивают.
        """
        self.assertEqual(list(inspect.signature(runner.role_cmd).parameters),
                         [])

    def test_ac5_argv_matches_the_pre_task_expected_list(self):
        """Команда шага совпадает элемент в элемент: абсолютный путь
        инструмента, затем зафиксированный хвост флагов.

        Ловит мутацию: провайдер собрал команду заново и потерял или
        переставил флаг (`--strict-mcp-config`, `--verbose`,
        `--setting-sources`), либо вернул argv[0] литералом `claude`
        вместо абсолютного пути резолва манифеста.
        """
        argv = runner.role_cmd()

        self.assertEqual(argv[1:], EXPECTED_TAIL)
        self.assertEqual(argv[0], shutil.which("claude"))
        self.assertTrue(Path(argv[0]).is_absolute(), argv[0])
        self.assertEqual(Path(argv[0]).name, "claude")


if __name__ == "__main__":
    unittest.main()
