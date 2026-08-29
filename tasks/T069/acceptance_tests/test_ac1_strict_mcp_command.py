"""AC-1 (tasks/T069/SPEC.md): команда запуска шага роли содержит строгий
MCP-режим; в шаге роли недоступен ни один MCP-сервер из `.mcp.json`
рабочего каталога.

`runner.run_agent_once` — единственное место, строящее реальный `cmd`
шага (orchestrator/runner.py, `spawn_agent(["claude", "-p", ...])`,
SPEC T069 «Материалы»). Тест не переизобретает этот `cmd` — он
перехватывает РЕАЛЬНО построенные аргументы (мок только `spawn_agent`,
тем же приёмом, что и `tasks/T058/acceptance_tests/
test_ac1_ac2_role_hook_isolation.py::_capture_role_invocation`:
`spawn_agent` — заявленная самим модулем `runner.py` точка мокинга
cli-вызова агента, `FileNotFoundError` уходит в уже существующую ветку
«claude CLI не найден», без побочных эффектов) и сверяет его с флагом,
подтверждённым `claude --help` установленного пина CLI
(`config.CLI_VERSION_PIN`, требование 1 SPEC — «точную комбинацию
флагов сверить с claude --help»):

    --strict-mcp-config   Only use MCP servers from --mcp-config,
                           ignoring all other MCP configurations

(проверено вручную этой же связкой на установленной в этом окружении
версии `claude`, `config.CLI_VERSION_PIN` на момент написания теста).
Курируемого списка MCP-серверов у пульта сейчас нет (SPEC, требование
1: «целевое состояние: ноль MCP-серверов в шаге роли») — поэтому
одного `--strict-mcp-config` без `--mcp-config` достаточно для «ноль
MCP-серверов»: `--strict-mcp-config` ограничивает резолвинг ИСКЛЮЧИТЕЛЬНО
серверами из `--mcp-config`, а без него список пуст.

Сегодня (до реализации T069) `run_agent_once` не передаёт
`--strict-mcp-config` вообще — тест закономерно красный, это ожидаемо
для приёмочного теста, написанного до кода (skills/test-authoring.md).

Живая дискриминирующая проверка («канарейка в .mcp.json рабочего
каталога реально не достижима шагом») исследована отдельно (см. PLAN.md
T069, «Подход», если он это фиксирует) и НЕ включена сюда: экспериментально
подтверждено (несколько прогонов настоящего `claude -p` с временным
`HOME`/без токена, `--debug-file`, канарейкой-сервером в `.mcp.json`
рабочего каталога), что в headless `-p`-режиме СВЕЖИЙ, ранее не
подтверждённый project-scope MCP-сервер вообще не подключается ни с
флагом, ни без него — интерактивное подтверждение (`⏸ Pending
approval`, `claude mcp list`) недостижимо в headless-режиме структурно,
поэтому дифференцирующий сигнал «подключился/не подключился» в этом
режиме не наблюдается ни в каком варианте (не специфичен для флага) —
живой прогон не различает «изолировано» от «vector never fires
headless anyway» и был бы имитацией дискриминирующей проверки, а не ей
самой. Офлайн-сборка cmd (этот файл) — единственный источник фактуры,
которую можно наблюдать детерминированно и бесплатно; расхождение
фактического поведения флага с документированным в `--help`, если
обнаружится на другой версии CLI, фиксируется в артефакте задачи, а не
подгоняется под тест (SPEC, требование 1, последнее предложение).

Красен до реализации: `test_ac1_role_command_uses_strict_mcp_config` —
`run_agent_once` сегодня не добавляет `--strict-mcp-config` в `cmd`
(проверено прогоном перед написанием этого докстринга).
Зелёный с рождения: `test_ac1_no_curated_mcp_config_means_zero_servers`
— курируемого `--mcp-config` у пульта нет уже сегодня (SPEC,
требование 1, «сейчас нет»); тест фиксирует это, не реализацию T069, и
обязан остаться зелёным и после неё — регресс здесь означает, что
кто-то приделал `--mcp-config` без ADR (принцип целостности, ADR-0002).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, runner, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture, fake_git  # noqa: E402

TASK_ID = "T901"
SYNTHETIC_TARGET = "__t069_strict_mcp__"


class StrictMcpCommandTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), TASK_ID, "Строгий MCP-режим шага",
                          "in_dev", f"task/{TASK_ID.lower()}-x",
                          SYNTHETIC_TARGET, 25.0)

    def _capture_role_cmd(self) -> list:
        captured = {}

        def fake_spawn(cmd, **kwargs):
            captured["cmd"] = list(cmd)
            raise FileNotFoundError()

        with mock.patch.object(runner, "spawn_agent", fake_spawn), \
             mock.patch.object(runner.gitcmd, "git", fake_git), \
             mock.patch.object(runner.keychain, "token", lambda slot: None):
            runner.run_agent_once(store.db(), TASK_ID, "developer",
                                  "тестовый промпт MCP-изоляции", 1)
        self.assertIn("cmd", captured,
                      "spawn_agent не был вызван — run_agent_once не дошёл "
                      "до построения аргументов шага")
        return captured["cmd"]

    def test_ac1_role_command_uses_strict_mcp_config(self):
        cmd = self._capture_role_cmd()

        self.assertIn(
            "--strict-mcp-config", cmd,
            "команда запуска шага роли не содержит --strict-mcp-config — "
            "MCP-конфиг рабочего каталога (`.mcp.json`) не ограничен "
            "стороной пульта (SPEC T069 AC-1)")

    def test_ac1_no_curated_mcp_config_means_zero_servers(self):
        """Курируемого списка MCP-серверов у пульта сейчас нет (SPEC,
        требование 1) — `--mcp-config` в команде отсутствует, а значит
        `--strict-mcp-config` резолвит пустой список серверов (целевое
        состояние: ноль MCP-серверов в шаге роли)."""
        cmd = self._capture_role_cmd()

        self.assertNotIn(
            "--mcp-config", cmd,
            "команда шага роли передаёт --mcp-config, хотя курируемого "
            "списка MCP-серверов у пульта сейчас нет — при наличии "
            "--strict-mcp-config без --mcp-config список серверов пуст "
            "(SPEC T069, требование 1); если курируемый список появился, "
            "этот тест и AC-1 нужно пересмотреть вместе, а не в обход")


if __name__ == "__main__":
    unittest.main()
