"""AC-7 — 01M3F7BYE82S9AQCBSP1RTQQTR: `runner.role_env` не отдаёт шагу
секреты ЧУЖИХ провайдеров.

Источник — SPEC.md, «Критерии приёмки»:

AC-7. orchestrator/runner.py::role_env отдаёт окружение шага без имён
секретов ЧУЖИХ провайдеров реестра: имя, объявленное `secret_env_names`
другого провайдера, в результат не попадает, даже если задано в окружении
Оператора и разрешено общим белым списком манифеста.

Роль на `codex` в `roles.yaml` сегодня не заведена ни одна (и заводить её
задача не должна — «Не входит»), поэтому провайдер роли подменяется
`roles.provider`: предмет критерия — сборка окружения, а не содержимое
карты исполнителей. Обе предпосылки критерия («задано в окружении
Оператора», «разрешено общим белым списком») проверяются явно, а не
предполагаются: белый список читается из `stack.ROLE_ENV_ALLOWLIST`, а не
из списка имён, переписанного в планку.

Песочница — общая `tests/sandbox.py::TmpRootTest` (пути `config` во
временном каталоге, `stack.check_stack` уже подменён ею): своей копии
планка не заводит.

Красен до реализации: `role_env` сегодня кладёт в окружение шага весь
белый список манифеста целиком, без учёта провайдера роли, — токен
подписки Claude остаётся в окружении шага на Codex, и `assertNotIn`
падает на первом же имени.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import keychain, providers, roles, runner, stack  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

#: Синтетический секрет «второго провайдера» — имя, которого нет ни у
#: одного CLI: сегодняшний набор `CodexProvider.secret_env_names()` пуст,
#: и обратная сторона симметрии иначе проверялась бы пустотой.
SYNTHETIC_SECRET = "ARTEL_TEST_CODEX_SECRET"
SECRET_VALUE = "znachenie-sekreta-operatora"


class RoleEnvDropsForeignSecretsTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        for patcher in (
                mock.patch.object(keychain, "token", lambda slot: "tok-slot"),
                # Резолв инструментов манифеста — заглушкой: предмет AC-7 —
                # ИМЕНА переменных в собранном окружении, а не наличие
                # чужого CLI на машине прогона планки.
                mock.patch.object(runner.shutil, "which",
                                  lambda name: f"/artel-test-bin/{name}")):
            patcher.start()
            self.addCleanup(patcher.stop)

    def step_env(self, provider_name: str, ambient: dict) -> dict:
        """Окружение шага роли, идущей на провайдере `provider_name`, при
        заданных ambient-переменных Оператора."""
        with mock.patch.object(roles, "provider", lambda role: provider_name), \
                mock.patch.dict(os.environ, ambient):
            return runner.role_env("developer", _util.TASK_ID)

    def test_ac7_claude_subscription_token_does_not_reach_a_codex_step(self):
        """Окружение шага роли на `codex`, собранное при заданных
        ambient-переменных секрета Claude, не несёт ни одного имени из
        `ClaudeProvider.secret_env_names()` — при том, что оба имени
        стоят в общем белом списке манифеста и заданы Оператором.

        Ловит мутацию: сужение написано по накладке провайдера (шаг
        перестаёт получать токен ТОЛЬКО когда его кладёт сам провайдер),
        а общий белый список по-прежнему копирует ambient-переменную
        Оператора в каждый шаг — токен подписки уезжает в чужой CLI ровно
        тем каналом, ради которого требование 4 и написано.
        """
        claude_secrets = providers.get("claude").secret_env_names()
        self.assertTrue(claude_secrets, "у провайдера claude нет ни одного "
                                        "имени секрета — сверять нечего")
        for name in claude_secrets:
            self.assertIn(name, stack.ROLE_ENV_ALLOWLIST,
                          f"{name} вне белого списка манифеста — "
                          f"предпосылка AC-7 не воспроизведена")

        env = self.step_env("codex", {name: SECRET_VALUE
                                      for name in claude_secrets})

        self.assertIn("CODEX_HOME", env,
                      "собрано окружение не шага на codex — проверять "
                      "нечего: " + repr(sorted(env)))
        for name in claude_secrets:
            self.assertNotIn(
                name, env,
                f"{name} — секрет ЧУЖОГО провайдера для шага на codex, "
                f"а он в окружении шага (AC-7)")

    def test_ac7_the_symmetry_holds_for_a_secret_of_the_second_provider(self):
        """Обратная сторона: имя, объявленное секретом провайдера
        `codex` и стоящее в белом списке, не попадает в окружение шага
        роли на `claude`, — а собственный секрет провайдера роли в
        окружении остаётся.

        Ловит мутацию: фильтр вычитает имена секретов ВСЕХ провайдеров
        реестра, включая своего, — шаг роли на Claude остаётся без токена
        подписки и падает «Not logged in»; либо фильтр написан литералом
        `CLAUDE_CODE_OAUTH_TOKEN` и знает ровно одну сторону, а второй
        провайдер со своим секретом (эта подмена) проходит мимо него.
        """
        codex_class = type(providers.get("codex"))
        own = providers.get("claude").secret_env_names()[0]
        ambient = {SYNTHETIC_SECRET: SECRET_VALUE, own: "tok-ambient"}

        with mock.patch.object(codex_class, "secret_env_names",
                               lambda inner: (SYNTHETIC_SECRET,)), \
                mock.patch.dict(stack.ROLE_ENV_ALLOWLIST,
                                {SYNTHETIC_SECRET: "секрет теста"}):
            env = self.step_env("claude", ambient)

        self.assertNotIn(
            SYNTHETIC_SECRET, env,
            f"{SYNTHETIC_SECRET} объявлен секретом провайдера codex и всё "
            f"же попал в окружение шага роли на claude (AC-7)")
        self.assertEqual(
            "tok-ambient", env.get(own),
            f"собственный секрет провайдера роли ({own}) обязан остаться в "
            f"окружении шага: сужение идёт по ЧУЖИМ именам")


if __name__ == "__main__":
    unittest.main()
