"""AC-1/AC-2 задачи 01M2DTT96FS25SHXP0HDTWARQH: `orchestrator.roles`
несёт функцию `model(role) -> str | None` — значение поля `model` роли
из `roles.yaml`, `None` — если поле не задано; `RolesError` (тем же
приёмом, что `skills()`) — если поле присутствует, но не является
непустой строкой.

Красен до реализации: `orchestrator.roles` пока не несёт атрибута
`model` вовсе — `roles.model("developer")` падает `AttributeError`, а не
проверяемым ассертом; реализация задачи ещё не внесена.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, roles  # noqa: E402


class RolesModelTest(unittest.TestCase):
    """Тот же приём песочницы, что `tests/test_yaml_parsing.py::RolesTest`:
    временный `roles.yaml`, `config.ROLES` подменён на него."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "roles.yaml"
        patcher = mock.patch.object(config, "ROLES", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, text: str) -> None:
        self.path.write_text(text, encoding="utf-8")

    def test_ac1_model_returns_the_configured_identifier(self):
        """Роль `developer` несёт `model: claude-opus-5` — `roles.model`
        возвращает именно эту строку, не булево наличие поля и не имя
        роли.

        Ловит мутацию: `model()` путает поле (например, читает `skills`
        или `token_slot`), либо возвращает `True`/имя роли вместо
        значения поля.
        """
        self.write("roles:\n  developer:\n    skills: [a]\n"
                   "    model: claude-opus-5\n")

        self.assertEqual(roles.model("developer"), "claude-opus-5")

    def test_ac1_model_returns_none_when_the_field_is_absent(self):
        """Роль описана и читаема, но без поля `model` — `roles.model`
        возвращает `None`, не бросает и не подставляет строку-заглушку.

        Ловит мутацию: `model()` бросает `RolesError` на отсутствии поля
        (как `skills()` на отсутствии `skills`) вместо возврата `None` —
        AC-1 явно требует именно `None` для этого случая, в отличие от
        `skills()`.
        """
        self.write("roles:\n  developer:\n    skills: [a]\n")

        self.assertIsNone(roles.model("developer"))

    def test_ac2_non_string_value_raises_roles_error(self):
        """`model:` роли `developer` задан числом, а не идентификатором
        CLI — тем же приёмом, что `skills()` на неверном формате, это
        `RolesError`.

        Ловит мутацию: `model()` пропускает нестроковое значение молча
        (например, `str(5)`, приводя тип, вместо отказа).
        """
        self.write("roles:\n  developer:\n    skills: [a]\n    model: 5\n")

        with self.assertRaises(roles.RolesError):
            roles.model("developer")

    def test_ac2_empty_string_value_raises_roles_error(self):
        """`model: ""` — синтаксически строка, но пустая: AC-2 требует тот
        же отказ, что и у нестрокового значения, а не пропуск как валидной
        строки.

        Ловит мутацию: проверка ограничивается `isinstance(value, str)`
        без проверки `bool(value)` — пустая строка проходит как модель.
        """
        self.write('roles:\n  developer:\n    skills: [a]\n    model: ""\n')

        with self.assertRaises(roles.RolesError):
            roles.model("developer")


if __name__ == "__main__":
    unittest.main()
