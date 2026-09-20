"""AC-3: `roles.provider(role)` — поле `provider:` роли, дефолт `claude`.

Красен до реализации: `orchestrator/roles.py` не несёт функции
`provider` — обращение к ней падает `AttributeError`.
"""
import unittest
from unittest import mock

from orchestrator import config, roles
from tests.sandbox import TmpDirTest

FIELD_PROVIDER = "codex-planki"

ROLES_YAML = """roles:
  alfa:
    executor: agent
    token_slot: artel-alfa
    skills: [conventions-core]
    provider: {provider}
  beta:
    executor: agent
    token_slot: artel-beta
    skills: [conventions-core]

token_fallback: artel-token
""".format(provider=FIELD_PROVIDER)


class RolesProviderTest(TmpDirTest):
    """Карта исполнителей — временный `roles.yaml`: сам файл репозитория
    эта задача не меняет, а дефолт обязан работать на роли без поля."""

    def setUp(self):
        super().setUp()
        path = self.tdir / "roles-under-test.yaml"
        path.write_text(ROLES_YAML, encoding="utf-8")
        patcher = mock.patch.object(config, "ROLES", path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ac3_field_value_is_returned_for_a_role_that_has_it(self):
        """Роль с полем `provider:` отдаёт значение поля дословно.

        Ловит мутацию: функция возвращает дефолт всегда (поле не
        читается вовсе) — роль на другом CLI молча ушла бы на `claude`.
        """
        self.assertEqual(roles.provider("alfa"), FIELD_PROVIDER)

    def test_ac3_role_without_the_field_defaults_to_claude(self):
        """Роль без поля `provider:` отдаёт `claude`.

        Ловит мутацию: отсутствие поля оформлено отказом (`RolesError`)
        или `None`, как у `roles.model` — сегодняшний `roles.yaml` без
        поля `provider:` останавливал бы каждый шаг.
        """
        self.assertEqual(roles.provider("beta"), "claude")


if __name__ == "__main__":
    unittest.main()
