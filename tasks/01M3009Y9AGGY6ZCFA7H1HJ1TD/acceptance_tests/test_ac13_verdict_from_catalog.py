"""AC-13: вердикт совместимости провайдера сверяет установленную версию
CLI с минимумом версии CLI МОДЕЛИ ИЗ КАТАЛОГА; таблица совместимости и
предупреждение «модель не в таблице совместимости» удалены из
`orchestrator/stack.py`, а модель вне каталога — отказ, не
предупреждение.

Красен до реализации: фикстура падает на отсутствующем `models.yaml`
(каталог создаёт эта задача), а `stack.MODEL_MIN_CLI_VERSION` и
`stack.MODEL_NOT_IN_TABLE_WARNING` всё ещё на месте — вердикт читает
таблицу, и модель вне её даёт `warn` и запуск как есть.
"""
import unittest
from unittest import mock

import _models
from _sandbox import CatalogSandbox
from orchestrator import providers, stack

MISSING_MODEL = "claude-modeli-kotoroy-net-v-kataloge"


class VerdictFromCatalogTest(CatalogSandbox):
    """Каталог во временном корне; установленная версия CLI — подменена."""

    def setUp(self):
        super().setUp()
        self.write_catalog()
        self.provider = providers.PROVIDERS["claude"]

    def verdict(self, installed: tuple, model: str):
        with mock.patch.object(stack, "installed_cli_version",
                               return_value=installed):
            return self.provider.model_verdict(model)

    def test_ac13_verdict_compares_installed_cli_with_the_catalog_minimum(self):
        """Версия CLI ниже минимума модели из каталога — `fail`; равная
        минимуму — `ok`.

        Ловит мутацию: сверка идёт с минимумом самого CLI
        (`providers/claude.py::CLI_MINIMUM`, 1.0.0) вместо минимума
        модели — CLI 2.1.250 на модели, требующей 2.1.251, проходит
        предполёт, и возвращается инцидент 19.09 («API Error 400» за три
        попытки по 120 с).
        """
        below = (2, 1, 250)
        exact = (2, 1, 251)
        self.assertEqual(_models.FABLE_MIN_CLI, stack.version_text(exact))

        self.assertEqual(self.verdict(below, _models.FABLE).status, "fail")
        self.assertEqual(self.verdict(exact, _models.FABLE).status, "ok")

    def test_ac13_model_missing_from_the_catalog_is_refused_not_warned(self):
        """Модель, которой нет в каталоге, даёт отказ (`fail`), а не
        предупреждение.

        Ловит мутацию: ветка «модели нет в таблице» переехала из
        `stack.py` в каталог как есть — неизвестная модель по-прежнему
        `warn` и запуск как есть, то есть шаг стартует на модели, о
        которой пульт ничего не знает.
        """
        self.assertEqual(self.verdict((9, 9, 9), MISSING_MODEL).status, "fail")

    def test_ac13_compatibility_table_and_its_warning_are_removed(self):
        """В `orchestrator/stack.py` больше нет ни таблицы совместимости,
        ни текста предупреждения о модели вне её.

        Ловит мутацию: таблица оставлена «на совместимость» и продолжает
        читаться где-то ещё — источников минимума версии CLI снова два, и
        они разъезжаются молча (ровно то, ради чего каталог и заведён).
        """
        self.assertFalse(hasattr(stack, "MODEL_MIN_CLI_VERSION"))
        self.assertFalse(hasattr(stack, "MODEL_NOT_IN_TABLE_WARNING"))

        source = (_models.REPO_ROOT / "orchestrator" / "stack.py").read_text(
            encoding="utf-8")
        self.assertNotIn("не в таблице совместимости", source)


if __name__ == "__main__":
    unittest.main()
