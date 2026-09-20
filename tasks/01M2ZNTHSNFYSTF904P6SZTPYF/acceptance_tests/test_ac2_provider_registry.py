"""AC-2: реестр провайдеров и регистрация имени `claude`.

Красен до реализации: пакета `orchestrator/providers/` ещё нет — импорт
`orchestrator.providers` падает `ModuleNotFoundError`.
"""
import unittest

import _providers


class ProviderRegistryTest(unittest.TestCase):
    """Реестр — словарь уровня модуля `orchestrator/providers/__init__.py`."""

    def test_ac2_registry_is_a_dict_carrying_the_claude_name(self):
        """В `__init__.py` пакета есть словарь-реестр, и в нём
        зарегистрировано имя `claude`.

        Ловит мутацию: реестр сделан функцией-свитчем (`if name ==
        "claude": ...`) вместо словаря — словаря с этим ключом на уровне
        модуля нет, регистрация второго провайдера снова требует правки
        кода ветвления, а не записи в реестр.
        """
        attr, registry = _providers.registry_entry()
        self.assertIsInstance(registry, dict)
        self.assertIn(_providers.CLAUDE, registry,
                      f"{attr} — реестр без имени '{_providers.CLAUDE}'")

    def test_ac2_claude_name_resolves_to_the_claude_module(self):
        """Запрос по имени `claude` отдаёт реализацию, объявленную в
        `orchestrator/providers/claude.py`, и она несёт методы
        интерфейса.

        Ловит мутацию: под именем `claude` зарегистрирован сам базовый
        интерфейс из `base.py` (заглушка, до которой не дошли руки) —
        модуль реализации не совпадает, шаг роли пошёл бы на абстрактных
        методах.
        """
        value = _providers.entry()

        self.assertEqual(_providers.implementation_module(value),
                         _providers.CLAUDE_MODULE)
        self.assertEqual(
            _providers.missing_interface_methods(_providers.provider()), [])


if __name__ == "__main__":
    unittest.main()
