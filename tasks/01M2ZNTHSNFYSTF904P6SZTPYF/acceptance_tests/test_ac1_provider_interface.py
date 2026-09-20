"""AC-1: базовый интерфейс провайдера исполнителя роли.

Красен до реализации: пакета `orchestrator/providers/` ещё нет — импорт
`orchestrator.providers.base` падает `ModuleNotFoundError`.
"""
import inspect
import unittest

import _providers


def _interface_candidates():
    """Классы, объявленные в `orchestrator/providers/base.py`."""
    module = _providers.base_module()
    return [value for value in vars(module).values()
            if inspect.isclass(value) and value.__module__ == module.__name__]


class ProviderInterfaceTest(unittest.TestCase):
    """Состав интерфейса читается из самого модуля: имя класса критерий
    не называет, названы только методы."""

    def test_ac1_base_declares_all_six_interface_methods(self):
        """В `base.py` есть класс интерфейса, несущий все шесть методов
        критерия: `command`, `environment`, `home_reference`,
        `preflight`, `cli_tool`, `model_verdict`.

        Ловит мутацию: интерфейс объявлен наполовину — вердикт модели
        (`model_verdict`) или инструмент манифеста (`cli_tool`) оставлены
        в `stack.py` и в базу не вынесены: ни один класс `base.py` не
        несёт полного набора, тест называет недостающие методы.
        """
        candidates = _interface_candidates()
        self.assertTrue(candidates,
                        "в orchestrator/providers/base.py нет ни одного "
                        "объявленного класса")
        gaps = {cls.__name__: _providers.missing_interface_methods(cls)
                for cls in candidates}
        complete = [name for name, missing in gaps.items() if not missing]
        self.assertTrue(complete,
                        f"ни один класс base.py не объявляет полный "
                        f"интерфейс; недостающие методы по классам: {gaps}")

    def test_ac1_interface_methods_carry_the_named_parameters(self):
        """У методов интерфейса — параметры, названные критерием:
        `command(model)`, `environment(role, task_id)`, `preflight(role)`,
        `model_verdict(model)`.

        Ловит мутацию: `environment` объявлена без `task_id` (метка
        задачи в окружении роли собирается где-то ещё) либо `command`
        объявлена без `model` — сигнатура интерфейса разошлась с
        критерием, а подмена реализации на другого провайдера перестала
        быть возможной без правки вызывающих.
        """
        candidates = [cls for cls in _interface_candidates()
                      if not _providers.missing_interface_methods(cls)]
        self.assertTrue(candidates, "класс интерфейса не найден (см. "
                                    "test_ac1_base_declares_all_six_"
                                    "interface_methods)")
        cls = candidates[0]
        for method, required in sorted(_providers.INTERFACE_METHODS.items()):
            with self.subTest(method=method):
                params = list(inspect.signature(
                    getattr(cls, method)).parameters)
                for name in required:
                    self.assertIn(name, params,
                                  f"{cls.__name__}.{method}{tuple(params)}: "
                                  f"нет параметра {name!r}")


if __name__ == "__main__":
    unittest.main()
