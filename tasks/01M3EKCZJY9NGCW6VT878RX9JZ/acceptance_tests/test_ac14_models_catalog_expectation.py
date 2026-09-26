"""AC-14: тест каталога моделей в `tests/test_models.py` зелёный на
ФАКТИЧЕСКОМ каталоге — три модели Claude и пять OpenAI, у каждой статус
из перечня и непустая дата цены.

Красен до реализации: `tests/test_models.py` сегодня ждёт ровно три
модели Claude (`sorted(catalog.models) == ["claude-fable-5-1",
"claude-opus-5", "claude-sonnet-5"]`) и утверждает `model.provider ==
"claude"` для каждой записи каталога, а каталог после мержа приложения
`models.yaml` части 1 несёт восемь моделей в двух разделах — это и есть
тот красный 1 из 37 на пине, который задача обязана закрыть (второй тест
файла).

Первый тест файла ЗЕЛЁН и до реализации — сознательно: он закрепляет
фактическое состояние каталога, которое требование 8 запрещает менять
(правка `models.yaml` в задачу не входит, критерий приводит к каталогу
ОЖИДАНИЕ теста, а не наоборот). Без него ослабление ожидания в
`tests/test_models.py` до «моделей больше нуля» прошло бы оба гейта.
"""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import models  # noqa: E402

CLAUDE_MODELS = 3
OPENAI_MODELS = 5


class CatalogExpectationTest(unittest.TestCase):
    """Ожидание каталога — требование 8."""

    def test_ac14_the_catalog_carries_three_claude_and_five_openai_models(self):
        """Фактический каталог `models.yaml` разбирается и несёт ровно три
        модели Claude и ровно пять моделей OpenAI; у КАЖДОЙ статус из
        перечня `models.STATUSES` и непустая дата цены, а провайдер записи
        совпадает с провайдером её раздела.

        Ловит мутацию: ожидание в `tests/test_models.py` подогнали под
        каталог ослаблением — вместо перечня моделей сверяется только
        «моделей больше нуля», и пропавшая модель, запись без статуса или
        без даты прейскуранта перестают краснеть (требование 8: имя теста
        менять можно, строгость — нет). Этот тест фиксирует само свойство
        каталога независимо от того, как его сверяет набор `tests/`.
        """
        catalog = models.load_catalog()

        counts = {name: len(section.models)
                  for name, section in catalog.providers.items()}
        self.assertEqual(counts.get("claude"), CLAUDE_MODELS, counts)
        self.assertEqual(counts.get("codex"), OPENAI_MODELS, counts)
        self.assertEqual(len(catalog.models),
                         CLAUDE_MODELS + OPENAI_MODELS, sorted(catalog.models))

        for name, section in sorted(catalog.providers.items()):
            for model_id in sorted(section.models):
                model = catalog.models[model_id]
                with self.subTest(model=model_id):
                    self.assertEqual(model.provider, name)
                    self.assertIn(model.status, models.STATUSES)
                    self.assertTrue(model.price_date, model_id)

    def test_ac14_the_models_test_module_of_the_repository_is_green(self):
        """Набор `tests/test_models.py` рабочей копии проходит целиком на
        фактическом каталоге — ровно тот прогон, который на пине красен
        одним тестом из 37.

        Ловит мутацию: ожидание каталога поправили в одном месте, а
        второе (сверка `model.provider == "claude"` по ВСЕМ записям
        каталога того же теста) оставили — планка, проверяющая только
        свойство каталога, такую половинчатую правку пропустила бы, и
        ветка не получила бы зелёной планки на `merge_gate`. Имя теста в
        модуле при этом не фиксируется (требование 8 разрешает его
        менять): прогоняется весь модуль.
        """
        import tests.test_models as module

        suite = unittest.TestLoader().loadTestsFromModule(module)
        result = unittest.TextTestRunner(stream=io.StringIO(),
                                         verbosity=0).run(suite)

        self.assertGreater(result.testsRun, 0, "модуль не собрал тестов")
        self.assertEqual(
            [str(item[0]) for item in result.failures + result.errors], [])


if __name__ == "__main__":
    unittest.main()
