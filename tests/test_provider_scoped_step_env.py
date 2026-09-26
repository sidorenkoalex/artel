"""Сужение окружения шага по провайдеру и строка `foreign-provider-secrets`
(SPEC 01M3F7BYE82S9AQCBSP1RTQQTR, требования 4-5).

Предмет — СОБРАННОЕ окружение шага (`runner.role_env`), а не накладка
провайдера: белый список манифеста (`stack.ROLE_ENV_ALLOWLIST`) общий на
пульт и копирует ambient-переменную Оператора в каждый шаг мимо
провайдера — тест, смотревший бы только накладку, оставался бы зелёным
ровно в том сценарии, ради которого требование 4 написано.

Обе стороны симметрии проверяются на РЕЕСТРЕ (`secret_env_names()`), а не
на литералах имён: со следующим провайдером список иначе придётся
дописывать в двух местах. Роль на `codex` в `roles.yaml` не заведена ни
одна (и заводить её задача не должна) — исполнитель шага подменяется
`roles.provider`.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (config, doctor, keychain, providers,  # noqa: E402
                          roles, runner, stack)
from tests.sandbox import TmpRootTest  # noqa: E402

#: Синтетический секрет «второго провайдера»: сегодняшний набор
#: `CodexProvider.secret_env_names()` пуст, и обратная сторона симметрии
#: иначе проверялась бы пустотой.
SYNTHETIC_SECRET = "ARTEL_TEST_CODEX_SECRET"
SECRET_VALUE = "znachenie-sekreta-operatora"


class _StepEnvSandbox(TmpRootTest):
    """Песочница обеих сторон: keychain не спрашивается по-настоящему,
    резолв инструментов манифеста заглушен (предмет — ИМЕНА переменных в
    собранном окружении, а не наличие чужого CLI на машине прогона), а
    ambient-секреты провайдеров сняты УДАЛЕНИЕМ: «переменной нет» и
    «переменная есть и пуста» — разные состояния для белого списка."""

    def setUp(self):
        super().setUp()
        for patcher in (
                mock.patch.object(keychain, "token", lambda slot: "tok-slot"),
                mock.patch.object(runner.shutil, "which",
                                  lambda name: f"/artel-test-bin/{name}")):
            patcher.start()
            self.addCleanup(patcher.stop)
        ambient = mock.patch.dict(os.environ, {})
        ambient.start()
        self.addCleanup(ambient.stop)
        for provider in providers.PROVIDERS.values():
            for name in provider.secret_env_names():
                os.environ.pop(name, None)

    def claude_secrets(self) -> tuple:
        return tuple(providers.get("claude").secret_env_names())

    def step_env(self, provider_name: str, ambient: dict) -> dict:
        """Окружение шага роли, идущей на провайдере `provider_name`, при
        заданных ambient-переменных Оператора."""
        with mock.patch.object(roles, "provider", lambda role: provider_name), \
                mock.patch.dict(os.environ, ambient):
            return runner.role_env("developer", "01TESTTASK")


class ForeignSecretsDroppedFromStepEnvTest(_StepEnvSandbox):
    """Требование 4: секрет ЧУЖОГО провайдера в окружение шага не попадает,
    собственный — остаётся."""

    def test_claude_subscription_token_does_not_reach_a_codex_step(self):
        """Окружение шага роли на `codex` не несёт ни одного имени из
        `ClaudeProvider.secret_env_names()` — при том, что оба имени стоят
        в общем белом списке манифеста и заданы Оператором.

        Ловит мутацию: сужение написано по накладке провайдера (шаг
        перестаёт получать токен только когда его кладёт сам провайдер), а
        общий белый список по-прежнему копирует ambient-переменную
        Оператора в каждый шаг — токен подписки уезжает в чужой CLI ровно
        тем каналом, ради которого требование 4 и написано.
        """
        foreign = self.claude_secrets()
        self.assertTrue(foreign, "у провайдера claude нет имён секрета")
        for name in foreign:
            self.assertIn(name, stack.ROLE_ENV_ALLOWLIST,
                          f"{name} вне белого списка — предпосылка не "
                          f"воспроизведена")

        env = self.step_env("codex", {name: SECRET_VALUE for name in foreign})

        self.assertIn("CODEX_HOME", env, sorted(env))
        for name in foreign:
            self.assertNotIn(name, env, name)
        self.assertNotIn(SECRET_VALUE, set(env.values()))

    def test_a_secret_of_the_second_provider_does_not_reach_a_claude_step(self):
        """Обратная сторона: имя, объявленное секретом провайдера `codex` и
        стоящее в белом списке, не попадает в окружение шага роли на
        `claude`, — а собственный секрет провайдера роли остаётся с
        ambient-значением Оператора.

        Ловит мутацию: фильтр вычитает имена секретов ВСЕХ провайдеров
        реестра, включая своего, — шаг роли на Claude остаётся без токена
        подписки и падает «Not logged in»; либо фильтр написан литералом
        `CLAUDE_CODE_OAUTH_TOKEN` и знает ровно одну сторону, а второй
        провайдер со своим секретом (эта подмена) проходит мимо него.
        """
        codex_class = type(providers.get("codex"))
        own = self.claude_secrets()[0]

        with mock.patch.object(codex_class, "secret_env_names",
                               lambda inner: (SYNTHETIC_SECRET,)), \
                mock.patch.dict(stack.ROLE_ENV_ALLOWLIST,
                                {SYNTHETIC_SECRET: "секрет теста"}):
            env = self.step_env("claude", {SYNTHETIC_SECRET: SECRET_VALUE,
                                           own: "tok-ambient"})

        self.assertNotIn(SYNTHETIC_SECRET, env, sorted(env))
        self.assertEqual("tok-ambient", env.get(own),
                         "собственный секрет провайдера роли обязан остаться")

    def test_todays_claude_step_env_is_not_narrowed_by_a_single_name(self):
        """Сегодняшний пульт: у провайдера `codex` имён секрета нет вовсе,
        значит у шага роли на `claude` вычитать нечего — набор чужих имён
        пуст.

        Ловит мутацию: сужение считает чужими все имена белого списка (или
        все имена секретов реестра), и шаг роли на Claude теряет токен
        подписки на КАЖДОМ пульте, а не только в синтетическом сценарии.
        """
        self.assertEqual(
            set(), runner.foreign_secret_env_names(providers.get("claude")))
        self.assertEqual(
            set(self.claude_secrets()),
            runner.foreign_secret_env_names(providers.get("codex")))


class ForeignSecretLineOnAssembledEnvTest(_StepEnvSandbox):
    """Требование 5: строка `foreign-provider-secrets` — отказ на чужом
    секрете в СОБРАННОМ окружении шага и `ok` в штатном случае."""

    def setUp(self):
        super().setUp()
        # Все agent-роли идут на `codex`: секрет Claude для них — чужой.
        patcher = mock.patch.object(roles, "provider", lambda role: "codex")
        patcher.start()
        self.addCleanup(patcher.stop)

    def check_with_step_env(self, env: dict):
        """Строка при окружении шага `env` — подменой самой сборки: строка
        обязана смотреть на собранное окружение, а не на ambient."""
        with mock.patch.object(runner, "role_env",
                               lambda role=None, task_id=None: dict(env)):
            return doctor.check_foreign_provider_secrets()

    def test_a_foreign_secret_in_the_assembled_step_env_is_a_failure(self):
        """Собранное окружение шага роли на `codex` несёт токен подписки
        Claude — строка отвечает `fail`, называет переменную по ИМЕНИ и не
        печатает её значения.

        Ловит мутацию: строка оставлена предупреждением («сузили окружение
        — и хватит»), и состояние, которое пульт теперь умеет чинить,
        продолжает молча проезжать мимо `doctor`: код выхода прогона
        нулевой, Оператор ничего не чинит.
        """
        foreign = self.claude_secrets()
        step_env = {name: SECRET_VALUE for name in foreign}
        step_env["CODEX_HOME"] = str(config.ROLE_HOME / ".codex")

        with mock.patch.dict(os.environ, {name: SECRET_VALUE
                                          for name in foreign}):
            check = self.check_with_step_env(step_env)

        self.assertEqual(doctor.FOREIGN_SECRETS_CHECK, check.name)
        self.assertEqual("fail", check.status, check.detail)
        self.assertTrue(any(name in check.detail for name in foreign),
                        check.detail)
        self.assertNotIn(SECRET_VALUE, check.detail)

    def test_a_clean_assembled_step_env_keeps_the_line_green(self):
        """Чужих секретов в собранном окружении шага нет — строка `ok`,
        даже когда ambient-переменная Оператора задана: сужение их уже
        вычло.

        Ловит мутацию: ужесточение написано так, что строка краснеет от
        самого факта «роль идёт на чужом провайдере» (по ambient или по
        белому списку, а не по СОБРАННОМУ окружению) — `doctor` пульта, где
        утечки уже нет, остаётся красным навсегда, и отказ перестаёт
        что-либо значить.
        """
        clean = {"CODEX_HOME": str(config.ROLE_HOME / ".codex")}

        with mock.patch.dict(os.environ, {name: SECRET_VALUE
                                          for name in self.claude_secrets()}):
            check = self.check_with_step_env(clean)

        self.assertEqual("ok", check.status, check.detail)

    def test_unassembled_step_env_is_a_warning_not_a_silent_pass(self):
        """Окружение шага не собралось (`OSError` резолва инструментов) —
        `warn` «сверка не проведена» с названной причиной.

        Ловит мутацию: отказ сборки трактуется как отсутствие утечки
        (`ok`) — пульт, где окружение шага вообще не собирается, читается
        Оператором как пульт без чужих секретов; либо как `fail` — тогда
        строка называет утечкой то, чего не проверяла.
        """
        def refuses(role=None, task_id=None):
            raise OSError("объявленный инструмент не найден в PATH: codex")

        with mock.patch.object(runner, "role_env", refuses):
            check = doctor.check_foreign_provider_secrets()

        self.assertEqual("warn", check.status, check.detail)
        self.assertIn("codex", check.detail)

    def test_the_line_reads_the_real_step_env_assembly(self):
        """Без подмен: строка зовёт настоящую сборку окружения шага, и на
        сегодняшнем коде она зелёная даже при заданном ambient-токене
        Claude — то есть сужение требования 4 и эта строка говорят об одном
        и том же окружении.

        Ловит мутацию: строка собирает окружение своей копией правила
        (ambient плюс накладка провайдера) вместо `runner.role_env` — копия
        разъедется с раннером на первой же правке сужения, и проверка
        начнёт отвечать про окружение, которого у шага нет.
        """
        with mock.patch.dict(os.environ, {name: SECRET_VALUE
                                          for name in self.claude_secrets()}):
            check = doctor.check_foreign_provider_secrets()

        self.assertEqual("ok", check.status, check.detail)


if __name__ == "__main__":
    unittest.main()
