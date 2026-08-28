"""AC-1, AC-2 (tasks/T058/SPEC.md): агентный шаг роли не исполняет хуки
project-слоя репозитория; контрольная пара доказывает, что канарейка
вообще способна сработать (иначе AC-1 «зелёный» ничего не значит).

`runner.run_agent_once` — единственное место, строящее реальный `cmd`/
`cwd`/`env` шага (orchestrator/runner.py:481; `spawn_agent` — заявленная
самим модулем точка мокинга, см. его докстринг: «отдельная от
subprocess.Popen точка мокинга cli-вызова агента»). Тест не переизобретает
эти аргументы и не фиксирует конкретный механизм изоляции (SPEC,
требование 1: «settings-source-флаг, переменная окружения или иное
средство ... выбирается на этапе PLAN») — он перехватывает РЕАЛЬНО
построенные `cmd`/`cwd`/`env` (мок только `spawn_agent`, чтобы
`run_agent_once` не пытался читать stdout несуществующего процесса —
`FileNotFoundError` уходит в уже существующую ветку «claude CLI не
найден», без побочных эффектов) и прогоняет их через настоящий
установленный `claude` CLI (`_hookcanary.canary_fired`, см. её докстринг
— офлайн, без сети и оплаты). Какой бы механизм PLAN ни выбрал: если он
реально исключает project-слой из построенных аргументов — канарейка не
сработает; сегодня (до реализации T058) она срабатывает, и AC-1
закономерно красный — это ожидаемо для приёмочного теста, написанного
до кода (skills/test-authoring.md).

AC-2 — контрольная пара к AC-1 (дословно из SPEC: «подтверждает, что
тест различает "хук не сработал вообще" от "хук изолирован именно у
роли"»): та же канарейка, тот же способ прогона, но в «операторском
окружении (главная копия)» — `config.ROOT` с обычным (не курируемым
ролью) окружением и без изоляции project-слоя — обязана сработать.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import catalog, config, runner, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture, fake_git  # noqa: E402

from _hookcanary import canary_fired, write_canary_hook  # noqa: E402

TASK_ID = "T900"
SYNTHETIC_TARGET = "__t058_hook_canary__"


class RoleHookIsolationTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), TASK_ID, "Канарейка project-хука",
                          "in_dev", f"task/{TASK_ID.lower()}-x",
                          SYNTHETIC_TARGET, 25.0)

    def _capture_role_invocation(self) -> dict:
        """Реальные `cmd`/`cwd`/`env`, которые `run_agent_once` передал бы
        `spawn_agent` для шага роли developer — без запуска настоящего
        процесса (перехват на границе, заявленной самим `spawn_agent`)."""
        captured = {}

        def fake_spawn(cmd, **kwargs):
            captured["cmd"] = list(cmd)
            captured["cwd"] = kwargs.get("cwd")
            captured["env"] = kwargs.get("env")
            raise FileNotFoundError()

        with mock.patch.object(runner, "spawn_agent", fake_spawn), \
             mock.patch.object(runner.gitcmd, "git", fake_git), \
             mock.patch.object(runner.keychain, "token", lambda slot: None):
            runner.run_agent_once(store.db(), TASK_ID, "developer",
                                  "тестовый промпт канарейки", 1)
        self.assertIn("cmd", captured,
                      "spawn_agent не был вызван — run_agent_once не дошёл "
                      "до построения аргументов шага")
        return captured

    def test_ac1_role_invocation_does_not_execute_project_hook_canary(self):
        captured = self._capture_role_invocation()
        write_canary_hook(Path(captured["cwd"]))

        fired = canary_fired(captured["cmd"], captured["cwd"], captured["env"])

        self.assertFalse(
            fired,
            "канарейка project-слоя сработала в окружении роли — "
            "PreToolUse/иные хуки project-конфига не изолированы "
            "(SPEC T058 AC-1)")

    def test_ac2_same_canary_fires_in_operator_environment(self):
        write_canary_hook(self.root)

        fired = canary_fired(["claude", "-p"], self.root, dict(os.environ))

        self.assertTrue(
            fired,
            "контрольная канарейка НЕ сработала даже в операторском "
            "окружении (главная копия) — тест не различает 'хук не "
            "сработал вообще' от 'хук изолирован именно у роли' "
            "(SPEC T058 AC-2)")


if __name__ == "__main__":
    unittest.main()
