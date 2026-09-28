"""AC-1 — 01M3KE8ZJXFARS6KC441PCDCQV: три новые записи каталога моделей.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. `models.yaml` (приложением к PLAN) несёт три новые записи: в
разделе `claude` — `claude-opus-5-5` с ценами 4.00 / 20.00 / 5.00 / 0.20,
`min_cli_version: 2.1.280`, `status: supported`; в разделе `codex` —
`gpt-6-sol` с ценами 2.00 / 10.00 / 2.50 / 0.20, `min_cli_version:
0.156.1`, `status: experimental` и `gpt-6-luna` с ценами
0.10 / 0.50 / 0.125 / 0.01, `min_cli_version: 0.157.0`, `status:
experimental`.

Предмет критерия — каталог ВЕТКИ (`models.yaml` рабочей копии,
прочитанный `models.load_catalog`): редакция 2 планки по ANSWER-1,
вопрос 1, вариант (а) — прежняя редакция мерила ТУ ЖЕ тройку записей
разницей «база сравнения -> каталог после приложения PLAN», и коммит
`ae3370c5`, внёсший каталог в main вперёд задачи, сделал это измерение
неисполнимым (подробнее — докстринг `_catalog.py`). Проверяемое свойство
то же: три записи есть, каждая в своём разделе, с ценами, наименьшими
версиями клиента и статусами сверенной таблицы.

Красен до реализации: пока каталог не правлен, ни одной из трёх записей
в `models.yaml` нет — `_catalog.record()` отказывает «в каталоге ветки
нет записи claude-opus-5-5», и каждый тест этого файла падает на
отсутствии предмета проверки.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _catalog  # noqa: E402


class NewCatalogRecordsTest(unittest.TestCase):
    """Три записи, которых каталог до правки не нёс, — в каталоге ветки,
    с числами сверенной таблицы."""

    def test_ac1_catalog_carries_three_new_records(self):
        """Каталог ветки несёт `claude-opus-5-5`, `gpt-6-sol` и
        `gpt-6-luna`, каждую — в своём разделе провайдера.

        Ловит мутацию: разработчик добавил записи не в тот раздел —
        `gpt-6-sol` под `claude:` (обе модели в таблице требования 1
        стоят рядом, и раздел легко перепутать): `CatalogModel.provider`
        разойдётся с ожидаемым, и провайдером модели станет `claude`,
        то есть шаг на ней пошёл бы чужим CLI.
        """
        catalog = _catalog.catalog().catalog

        for model_id, want in sorted(_catalog.NEW_RECORDS.items()):
            with self.subTest(model=model_id):
                self.assertNotIn(
                    model_id, _catalog.PREVIOUS_PRICES,
                    f"{model_id} стоит в снимке каталога ДО правки — "
                    f"запись не новая, и AC-1 о ней не про добавление")
                entry = _catalog.record(self, model_id)
                self.assertEqual(want["provider"], entry.provider)
                self.assertIn(
                    model_id,
                    catalog.providers[want["provider"]].models,
                    f"{model_id} не стоит в разделе {want['provider']}")

    def test_ac1_new_records_carry_the_verified_prices(self):
        """Четыре цены каждой новой записи равны сверенной таблице
        требования 1 (вход / выход / запись в кэш / чтение из кэша).

        Ловит мутацию: запись `claude-opus-5-5` заведена копией соседней
        `claude-opus-5` (5.00 / 25.00 / 6.25 / 0.50) с одной лишь правкой
        идентификатора — ровно так была заведена `claude-fable-5-1`,
        пометка «ЦЕНЫ НЕ СВЕРЕНЫ» в файле про это и говорит. Шаг на такой
        записи тарифицировался бы на четверть дороже факта, а
        `assertAlmostEqual` по виду `input` покраснеет на 5.0 против 4.0.
        """
        for model_id, want in sorted(_catalog.NEW_RECORDS.items()):
            _catalog.assert_prices(self, model_id, want["prices"])

    def test_ac1_new_records_carry_the_minimum_cli_and_status(self):
        """Наименьшая версия клиента и статус новых записей — те, что
        названы критерием: 2.1.280/supported, 0.156.1/experimental,
        0.157.0/experimental.

        Ловит мутацию: `min_cli_version` новой записи оставлен минимумом
        раздела (1.0.0 у `claude`, 0.155.1 у `codex`) — предполётная
        сверка шага (`stack.model_cli_verdict`) пропустила бы запуск на
        клиенте, который эту модель не знает: ровно инцидент 19.09,
        «unrecognized_model» за три попытки и ноль токенов.
        """
        for model_id, want in sorted(_catalog.NEW_RECORDS.items()):
            entry = _catalog.record(self, model_id)
            with self.subTest(model=model_id):
                self.assertEqual(
                    _catalog.models.version_tuple(want["min_cli_version"],
                                                  model_id),
                    entry.min_cli_version)
                self.assertEqual(want["status"], entry.status)


if __name__ == "__main__":
    unittest.main()
