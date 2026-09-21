"""AC-6: `orchestrator/roles.py` отдаёт ярус agent-роли из поля
`model_tier` и принимает только `strong | standard | cheap`; поле `model`
у роли не читается пультом ни в одной точке кода.

Красен до реализации: функции, отдающей ярус, в `orchestrator/roles.py`
нет вовсе, а поле `model` читают и сам модуль (`roles.model`), и
`orchestrator/stack.py`, и `orchestrator/runner.py`.
"""
import unittest
from unittest import mock

import _models
from orchestrator import config, roles
from tests.sandbox import TmpDirTest

ROLE = "developer"


class RoleTierReaderTest(TmpDirTest):
    """Карта исполнителей — временный `roles.yaml`: сам файл репозитория
    эта задача не правит (требование 15 — приложение к PLAN), а ярусы в
    нём появятся только на мерже."""

    def set_roles(self, tier) -> None:
        path = self.tdir / "roles-under-test.yaml"
        path.write_text(_models.roles_yaml_with_tiers({ROLE: tier}),
                        encoding="utf-8")
        patcher = mock.patch.object(config, "ROLES", path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ac6_tier_of_an_agent_role_comes_from_the_model_tier_field(self):
        """Ярус роли читается из поля `model_tier:` и отдаётся дословно —
        каждое значение закрытого перечня.

        Ловит мутацию: значение поля подменяется дефолтом (`strong` для
        любой роли) — ярус `cheap`, выставленный Оператором дешёвой роли,
        молча уходил бы на дорогую модель, и цепочка «роль → ярус»
        существовала бы только на бумаге.
        """
        for tier in _models.TIERS:
            with self.subTest(tier=tier):
                path = self.tdir / f"roles-{tier}.yaml"
                path.write_text(_models.roles_yaml_with_tiers({ROLE: tier}),
                                encoding="utf-8")
                with mock.patch.object(config, "ROLES", path):
                    self.assertEqual(_models.role_tier(ROLE), tier)

    def test_ac6_tier_outside_the_closed_list_is_a_named_error(self):
        """Значение вне перечня `strong | standard | cheap` — именованная
        ошибка, называющая роль и значение.

        Ловит мутацию: значение поля принимается как есть (перечень
        нигде не сверяется) — опечатка `strогng` доезжает до разрешения
        цепочки и оборачивается отказом «ярус не назван в tiers:»
        локального слоя, то есть диагнозом не о той причине.
        """
        self.set_roles("stroong")

        with self.assertRaises(Exception) as ctx:  # noqa: PT027 — класс не назван SPEC
            _models.role_tier(ROLE)

        exc = ctx.exception
        self.assertNotEqual(
            type(exc).__module__, "builtins",
            f"отказ не именован — встроенное исключение "
            f"{type(exc).__name__}: {exc}")
        self.assertIn("stroong", str(exc))
        self.assertIn(ROLE, str(exc))


class ModelFieldIsNotReadTest(unittest.TestCase):
    """Статический разбор кода пульта — поле `model` роли больше не
    читается ни в одной точке."""

    def test_ac6_no_code_path_reads_the_model_field_of_a_role(self):
        """Ни один модуль `orchestrator/` не читает поле `model` записи
        роли (`roles.model(...)`, `.get("model")`, `["model"]`), и самой
        функции `roles.model` больше нет.

        Ловит мутацию: `model_tier` добавлен, а старое чтение `model`
        оставлено «на всякий случай» — после применения приложения к
        `roles.yaml` (поле удалено у всех четырёх ролей) это чтение
        отдаёт `None`, и шаг роли уходит на дефолт CLI мимо цепочки
        разрешения, вместо отказа.
        """
        self.assertFalse(
            hasattr(roles, "model"),
            "orchestrator/roles.py всё ещё несёт чтение поля model")

        found = _models.model_field_reads()

        self.assertEqual(found, [], "поле model роли читается:\n"
                         + "\n".join(found))


if __name__ == "__main__":
    unittest.main()
