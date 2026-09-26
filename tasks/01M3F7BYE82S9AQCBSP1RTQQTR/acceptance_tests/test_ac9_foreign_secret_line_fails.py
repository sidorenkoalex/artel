"""AC-9 — 01M3F7BYE82S9AQCBSP1RTQQTR: строка `foreign-provider-secrets`
даёт fail на чужом секрете в собранном окружении шага и ok в штатном
случае.

Источник — SPEC.md, «Критерии приёмки»:

AC-9. Строка foreign-provider-secrets в doctor даёт fail, когда в
собранном окружении шага оказался секрет чужого провайдера (проверяется
подменой сборки окружения), и ok в штатном случае; тест покрывает оба
исхода.

«Подмена сборки окружения» — буквально из критерия: `runner.role_env`
отдаёт заранее заданный словарь. Чтобы планка не зависела от того, каким
именно вызовом проверка добывает окружение шага, сценарий провала
воспроизводится ОБОИМИ каналами сразу: и ambient-переменной Оператора
(общий белый список манифеста копирует её в шаг), и подменённой сборкой.
Штатный случай — зеркально: ambient пуст и подменённая сборка чиста.

Роль на `codex` в `roles.yaml` не заведена (и заводить её задача не
должна), поэтому провайдер ролей подменяется `roles.provider`.

Красен до реализации: сегодня строка отвечает `warn` («сужение списка по
провайдеру — отдельная задача линии») — `assertEqual("fail", …)` падает
на этом `warn`.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import config, doctor, providers, roles  # noqa: E402
from orchestrator import runner  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

SECRET_VALUE = "znachenie-tokena-operatora"


class ForeignSecretLineFailsTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        self.foreign = providers.get("claude").secret_env_names()
        self.assertTrue(self.foreign, "у провайдера claude нет ни одного "
                                      "имени секрета — сверять нечего")
        # Ambient гасится УДАЛЕНИЕМ: «переменной нет» и «переменная есть и
        # пуста» — разные состояния для белого списка манифеста.
        ambient = mock.patch.dict(os.environ, {})
        ambient.start()
        self.addCleanup(ambient.stop)
        for name in self.foreign:
            os.environ.pop(name, None)
        # Все agent-роли идут на `codex`: секрет Claude для них — чужой.
        provider_patch = mock.patch.object(roles, "provider",
                                           lambda role: "codex")
        provider_patch.start()
        self.addCleanup(provider_patch.stop)

    def check_with_step_env(self, env: dict):
        """Строка `foreign-provider-secrets` при окружении шага `env`."""
        with mock.patch.object(runner, "role_env",
                               lambda role=None, task_id=None: dict(env)):
            return doctor.check_foreign_provider_secrets()

    def test_ac9_a_foreign_secret_in_the_assembled_step_env_is_a_failure(self):
        """Собранное окружение шага роли на `codex` несёт токен подписки
        Claude — строка `foreign-provider-secrets` отвечает `fail`,
        называет переменную по ИМЕНИ и не печатает её значения.

        Ловит мутацию: строка оставлена предупреждением («сузили
        окружение — и хватит»), и состояние, которое пульт теперь умеет
        чинить, продолжает молча проезжать мимо `doctor`: код выхода
        прогона нулевой, Оператор ничего не чинит.
        """
        step_env = {name: SECRET_VALUE for name in self.foreign}
        step_env["CODEX_HOME"] = str(config.ROLE_HOME / ".codex")

        with mock.patch.dict(os.environ, {name: SECRET_VALUE
                                          for name in self.foreign}):
            check = self.check_with_step_env(step_env)

        self.assertEqual(doctor.FOREIGN_SECRETS_CHECK, check.name)
        self.assertEqual(
            "fail", check.status,
            f"чужой секрет в собранном окружении шага обязан быть отказом "
            f"(AC-9); строка ответила: {check.status} — {check.detail}")
        self.assertTrue(
            any(name in check.detail for name in self.foreign),
            f"отказ не называет переменную по имени: {check.detail}")
        self.assertNotIn(SECRET_VALUE, check.detail,
                         "значение секрета напечатано в строке doctor")

    def test_ac9_a_clean_step_env_keeps_the_line_green(self):
        """В собранном окружении шага чужих секретов нет (ambient пуст,
        сборка чиста) — строка отвечает `ok`.

        Ловит мутацию: ужесточение написано так, что строка краснеет от
        самого факта «роль идёт на чужом провайдере» (по ambient-
        переменной или по белому списку, а не по СОБРАННОМУ окружению), —
        `doctor` пульта, где утечки уже нет, остаётся красным навсегда, и
        отказ перестаёт что-либо значить.
        """
        check = self.check_with_step_env(
            {"CODEX_HOME": str(config.ROLE_HOME / ".codex")})

        self.assertEqual(
            "ok", check.status,
            f"штатный случай обязан быть зелёным (AC-9): {check.detail}")


if __name__ == "__main__":
    unittest.main()
