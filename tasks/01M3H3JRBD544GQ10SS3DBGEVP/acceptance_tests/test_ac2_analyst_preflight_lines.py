"""AC-2 — 01M3H3JRBD544GQ10SS3DBGEVP: строки предполёта роли analyst.

Источник — SPEC.md, «Критерии приёмки»:

AC-2. Для analyst в выводе doctor присутствуют те же строки предполёта,
что для остальных ролей: токен либо вход провайдера, дом роли, цепочка
роли в `role-providers` и `models-local`; при провайдере Codex это строки
входа по подписке и дома роли Codex, при провайдере Claude — прежние
строки Claude.

Оба варианта провайдера ставятся картой исполнителей под тестом, а не
сегодняшним состоянием `roles.yaml` пульта: критерий говорит про ОБА, и
тест, читающий нынешнее поле роли, проверял бы ровно один — тот, который
у Оператора стоит в день прогона.

Красен до реализации: analyst не входит в перечень ролей `doctor`, поэтому
ни одной зависимой от роли строки для него не печатается — ни строки
входа, ни дома роли, ни цепочки.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import doctor, models, providers  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402

from _analyst import ANALYST, DoctorLinesSandbox, roles_with  # noqa: E402

#: Строка сверки развёрнутого дома роли — у каждого провайдера своя
#: (склейка `provider_preflight_checks` схлопнула бы их под общим именем).
CLAUDE_HOME_LINE = "role-home-reference"
CODEX_HOME_LINE = "codex-role-home"
#: Строка секрета Claude — «чем шаг авторизуется» у провайдера по умолчанию.
CLAUDE_TOKEN_LINE = "token"


class AnalystPreflightLinesTest(DoctorLinesSandbox):
    """Зависимые от роли строки `doctor` для analyst на обоих провайдерах."""

    def role_named(self, checks: list) -> list:
        """Проверки, чей текст называет роль analyst."""
        return [check for check in checks if ANALYST in check.detail]

    def assert_chains_name_the_analyst(self, provider_name: str) -> None:
        """Цепочка роли analyst стоит и в строке `role-providers` (с
        именем её провайдера), и в строке `models-local`."""
        resolved = models.resolve_role(ANALYST)
        chain = f"{ANALYST} → {resolved.tier} → {resolved.model}"

        role_providers = doctor.check_role_providers()
        models_local = doctor.check_models_local()

        self.assertEqual(role_providers.status, "ok", role_providers.detail)
        self.assertIn(f"{chain} → {provider_name}", role_providers.detail)
        self.assertEqual(models_local.status, "ok", models_local.detail)
        self.assertIn(chain, models_local.detail)

    def test_ac2_analyst_on_codex_gets_the_subscription_login_and_codex_home(self):
        """Карта держит analyst на `codex`: предполёт печатает строку
        подписочного входа, названную ролью, строку дома роли Codex и
        цепочку роли в обеих строках моделей.

        Ловит мутацию: перечень ролей предполёта расширен, а склейка
        провайдерских проверок по-прежнему опрашивает провайдера ОДНОЙ
        роли (или провайдера по умолчанию вместо провайдера роли) —
        analyst на Codex получает зелёные строки Claude, а невыполненный
        вход ChatGPT не всплывает нигде: шаг уходит платной попыткой в
        неавторизованный CLI.
        """
        self.use_roles(roles_with(ANALYST, provider=codex_provider.CLI_NAME))

        grouped = self.grouped_provider_lines()

        auth = self.role_named(grouped.get(doctor.CODEX_AUTH_CHECK, []))
        self.assertEqual(len(auth), 1, sorted(grouped))
        self.assertEqual(auth[0].status, "ok", auth[0].detail)
        self.assertIn(CODEX_HOME_LINE, grouped, sorted(grouped))
        self.assert_chains_name_the_analyst(codex_provider.CLI_NAME)

    def test_ac2_analyst_on_claude_gets_the_previous_claude_lines(self):
        """Карта держит analyst на провайдере по умолчанию: предполёт
        печатает прежнюю строку секрета Claude, названную ролью, и строку
        дома роли Claude, а ни одной строки Codex не появляется.

        Ловит мутацию: строки провайдера подставлены жёстко под Codex
        («analyst же пробная роль на Codex») — пульт, где analyst остался
        на Claude, начинает платить подпроцессом `codex login status` и
        краснеть на инструменте, которого у него нет; либо строка секрета
        перестала называть роль, и склейка схлопывает её в одну на все
        роли, прячя отсутствие токена у analyst.
        """
        self.use_roles(roles_with(ANALYST,
                                  provider=providers.DEFAULT_PROVIDER))

        grouped = self.grouped_provider_lines()

        token = self.role_named(grouped.get(CLAUDE_TOKEN_LINE, []))
        self.assertEqual(len(token), 1, sorted(grouped))
        self.assertEqual(token[0].status, "ok", token[0].detail)
        self.assertIn(CLAUDE_HOME_LINE, grouped, sorted(grouped))
        self.assertNotIn(doctor.CODEX_AUTH_CHECK, grouped, sorted(grouped))
        self.assertNotIn(CODEX_HOME_LINE, grouped, sorted(grouped))
        self.assert_chains_name_the_analyst(providers.DEFAULT_PROVIDER)


if __name__ == "__main__":
    unittest.main()
