"""AC-1: сборщик упоминаний путей в `scripts/guard.py`.

Красен до реализации: сборщика требования 1 в `scripts/guard.py` ещё нет — единственная сегодняшняя функция сбора путей `_zone_paths` знает только `orchestrator/*.py`/`scripts/*.py` (`ZONE_PATH`, scripts/guard.py:1130) и не возвращает каталог `tests/`, так что ни одна функция модуля контракту AC-1 не удовлетворяет.

`config.ROOT` здесь НЕ подменяется: существование путей сверяется с
реальным деревом пульта, где `orchestrator/catalog.py` и `tests/` есть, а
`orchestrator/nosuch.py` нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from scripts import guard  # noqa: E402

EXISTING_FILE = "orchestrator/catalog.py"
EXISTING_DIR = "tests/"
MISSING_FILE = "orchestrator/nosuch.py"

PROBE_TEXT = (f"Правится {EXISTING_FILE}, тесты кладутся в {EXISTING_DIR}, "
              f"а {MISSING_FILE} эта задача только создаст.")


class PathCollectorTest(unittest.TestCase):

    def test_ac1_collector_keeps_existing_paths_and_drops_missing(self):
        """Текст называет существующий файл, существующий каталог с
        завершающим слэшем и несуществующий путь — сборщик возвращает
        первые два и не возвращает третий.

        Сборщик ищется по контракту (`_util.collectors_matching`), а не
        по имени: SPEC имени не называет.

        Ловит мутацию: фильтр «остаются только существующие в
        репозитории» снят (или сверяется не с `config.ROOT`) —
        `orchestrator/nosuch.py` попадёт в результат, и ни один кандидат
        не пройдёт `must_not_have`; ровно так же ловится потеря
        кандидата-каталога `tests/` (регулярка без ветки «`каталог/` с
        завершающим слэшем»).
        """
        matching = _util.collectors_matching(
            PROBE_TEXT,
            must_have={EXISTING_FILE, EXISTING_DIR},
            must_not_have={MISSING_FILE})

        self.assertTrue(
            matching,
            "в scripts/guard.py нет функции от одного текстового "
            "аргумента, возвращающей {%s, %s} и не возвращающей %s; "
            "найдено: %r" % (EXISTING_FILE, EXISTING_DIR, MISSING_FILE,
                             _util.collector_results(PROBE_TEXT)))

    def test_ac1_backticked_path_is_counted_as_the_plain_one(self):
        """Файл в обратных кавычках и тот же файл в обычном тексте дают
        один и тот же результат сборщика.

        Ловит мутацию: кандидат берётся вместе с обрамляющей кавычкой
        (например, регулярка допускает символ `` ` `` в имени) либо,
        наоборот, разбор привязан к обратным кавычкам и голый текст не
        разбирает — множества двух текстов разойдутся.
        """
        plain = f"Правится {EXISTING_FILE} по месту."
        quoted = f"Правится `{EXISTING_FILE}` по месту."

        names = _util.collectors_matching(
            PROBE_TEXT,
            must_have={EXISTING_FILE, EXISTING_DIR},
            must_not_have={MISSING_FILE})
        self.assertTrue(names, "сборщик не найден — см. тест выше")

        for name in names:
            with self.subTest(collector=name):
                collector = getattr(guard, name)
                self.assertEqual(set(collector(plain)), set(collector(quoted)),
                                 "обратные кавычки меняют результат сборщика")
                self.assertIn(EXISTING_FILE, set(collector(quoted)))


if __name__ == "__main__":
    unittest.main()
