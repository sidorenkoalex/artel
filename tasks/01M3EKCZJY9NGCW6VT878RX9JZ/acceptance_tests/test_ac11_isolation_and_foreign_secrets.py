"""AC-11: обе строки `doctor` про секреты знают новое правило — смок
изоляции Codex краснеет на любом имени ключа OpenAI в собранном
окружении шага, а строка чужих секретов больше не называет
`OPENAI_API_KEY` шагу роли на Claude.

Красен до реализации: `doctor.codex_isolation_smoke` сверяет песочницу,
сеть, одиннадцать функций и `HOME`/`CODEX_HOME`, но про имена ключей в
окружении не знает вовсе — окружение с `CODEX_API_KEY` для неё зелёное;
`check_foreign_provider_secrets` продолжает называть `OPENAI_API_KEY`,
потому что тот стоит и в `stack.ROLE_ENV_ALLOWLIST`, и в
`CodexProvider.secret_env_names()`.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from orchestrator import config, doctor, keychain, providers  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

AMBIENT_VALUE = "kluch-operatora-znachenie"


class CodexIsolationSmokeTest(TmpRootTest):
    """Смок изоляции шага Codex — требование 5."""

    def setUp(self):
        super().setUp()
        _util.drop_ambient(self, *_util.CLAUDE_SECRETS,
                           *_util.FORBIDDEN_ENV_NAMES, "CODEX_HOME")
        _util.patch(self, keychain, "token", lambda slot: "tok-podpiski")
        _util.stub_tool_path(self)
        self.provider_class = type(providers.get("codex"))

    def smoke_with_env(self, extra: dict):
        """Смок на провайдере, окружение которого несёт `extra` поверх
        правильного дома роли: сверяется РЕАЛЬНО собранная команда шага и
        подменённое окружение, как это делает сам смок."""
        deployed = config.ROLE_HOME / ".codex"

        def leaky(inner_self, role=None, task_id=None):
            env = {"HOME": str(config.ROLE_HOME),
                   "CODEX_HOME": str(deployed)}
            env.update(extra)
            return env

        with mock.patch.object(self.provider_class, "environment", leaky):
            return doctor.codex_isolation_smoke("developer")

    def test_ac11_any_openai_key_name_in_the_codex_step_env_is_a_named_failure(self):
        """Любая из `OPENAI_API_KEY`, `CODEX_API_KEY`, `CODEX_ACCESS_TOKEN`
        в собранном окружении шага Codex — `fail` смока, называющий
        переменную по имени; окружение без них остаётся зелёным.

        Ловит мутацию: проверка написана на одно имя (`OPENAI_API_KEY` —
        то, которое убрали из белого списка), а `CODEX_API_KEY`/
        `CODEX_ACCESS_TOKEN` не смотрит. Живая проверка 22.09 показала,
        что `codex exec` читает именно `CODEX_API_KEY`, — то есть
        незамеченным остался бы ровно тот канал, которым ключ и
        подействовал бы на шаг.
        """
        clean = self.smoke_with_env({})
        self.assertNotEqual(clean.status, "fail", clean.detail)

        for name in _util.FORBIDDEN_ENV_NAMES:
            with self.subTest(name=name):
                check = self.smoke_with_env({name: AMBIENT_VALUE})

                self.assertEqual(check.status, "fail", check.detail)
                self.assertIn(name, check.detail)
                self.assertNotIn(AMBIENT_VALUE, check.detail)

    def test_ac11_foreign_secrets_line_never_names_the_openai_key_for_a_claude_step(self):
        """Строка `foreign-provider-secrets` для шага роли на Claude не
        называет `OPENAI_API_KEY` ни при каком его ambient-значении.

        Ловит мутацию: ключ убран из белого списка, но остался в
        `CodexProvider.secret_env_names()` — проверка чужих секретов
        перебирает имена секретов ДРУГИХ провайдеров, и жёлтая строка про
        утечку продолжала бы гореть на пульте, где утечки уже нет: `doctor`
        просит Оператора чинить то, что починено.
        """
        for value in (AMBIENT_VALUE, ""):
            with self.subTest(ambient=repr(value)):
                with mock.patch.dict(os.environ, {"OPENAI_API_KEY": value}):
                    check = doctor.check_foreign_provider_secrets()

                self.assertNotIn("OPENAI_API_KEY", check.detail)
                if value:
                    self.assertNotIn(value, check.detail)


if __name__ == "__main__":
    unittest.main()
