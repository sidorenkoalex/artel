"""AC-4 — 01M3KE8ZJXFARS6KC441PCDCQV: литерал состава каталога в
`tests/test_models.py` приведён к новому составу и остался поимённым.

Источник — SPEC.md, «Критерии приёмки»:

AC-4. Перечень моделей в `tests/test_models.py` — по разделу `claude`, по
разделу `codex` и общий — равен новому составу каталога из требования 3;
сверка остаётся поимённой (сравнение с перечнем имён), не счётчиком и не
проверкой вхождения.

Проверяется ПОВЕДЕНИЕМ набора, а не формой его исходника: планка
подставляет `tests/test_models.py` три каталога подряд и смотрит, как
модуль на них отвечает.

- каталог ВЕТКИ — модуль обязан быть зелёным: литерал равен новому
  составу;
- тот же каталог, где ОДНА модель переименована (состав той же длины) —
  модуль обязан покраснеть: сверка счётчиком («моделей столько же») это
  пропустила бы;
- тот же каталог с ЛИШНЕЙ моделью — модуль обязан покраснеть: сверка
  вхождением («каждая ожидаемая есть») это пропустила бы.

Имя метода-сверки здесь не зашито: гоняется весь модуль. Литерал состава
— единственное в нём, что вообще реагирует на подмену состава каталога,
а переименование метода разработчиком не обязано ронять планку.

Редакция 2 планки по ANSWER-1, вопрос 1, вариант (а): подставляемый
каталог берётся из рабочей копии ветки, а не собирается применением
приложения PLAN к базе сравнения (докстринг `_catalog.py`). Три прогона,
их порядок и требуемые исходы — прежние.

Красен до реализации: литерал состава `tests/test_models.py` называет
старый состав со снятой `gpt-5.5` и без трёх новых моделей — на каталоге
ветки модуль красен, и первые два теста файла падают.
"""
import importlib
import io
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _catalog  # noqa: E402

from orchestrator import config  # noqa: E402

#: Имя модели, которой в каталоге нет и не будет: подмена состава обязана
#: опираться на заведомо невозможное имя, а не на «пока отсутствующее».
FIXTURE_EXTRA = "model-kotoroy-v-kataloge-ne-byvaet"

#: Запись лишней модели, дописываемая в первый раздел каталога. Форма — в
#: пределах `orchestrator/yamlmini.py`: вложенные блочные отображения.
EXTRA_RECORD = f"""\
      {FIXTURE_EXTRA}:
        min_cli_version: 1.0.0
        status: supported
        list_price_usd_per_mtok:
          input: 1.0
          output: 2.0
          cache_write: 3.0
          cache_read: 0.5
        price_date: {_catalog.PRICE_DATE}
"""

RENAMED_FROM = "claude-opus-5-5"
RENAMED_TO = "claude-opus-5-pereimenovannaya"


def _run_test_models(catalog_path: Path):
    """Прогон ВСЕГО модуля `tests/test_models.py` на каталоге
    `catalog_path`. Возвращает `unittest.TestResult`."""
    module = importlib.import_module("tests.test_models")
    suite = unittest.TestLoader().loadTestsFromModule(module)
    runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)
    with mock.patch.object(config, "MODELS", catalog_path):
        return runner.run(suite)


class CompositionLiteralTest(unittest.TestCase):

    def setUp(self):
        self.subject = _catalog.catalog()

    def write(self, name: str, text: str) -> Path:
        path = self.subject.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_ac4_branch_catalog_has_the_declared_composition(self):
        """Состав каталога ветки — тот, к которому требование 3
        обязывает привести литерал: четыре модели в разделе `claude`,
        шесть в разделе `codex`.

        Ловит мутацию: правка сняла `gpt-5.5`, но новую `gpt-6-luna`
        завела под тем же ключом, что `gpt-6-sol` (одна запись перетёрла
        другую — разбор отображения молча берёт последнюю): в разделе
        останется пять моделей, и сверка перечня покраснеет.
        """
        for section, expected in sorted(_catalog.NEW_COMPOSITION.items()):
            with self.subTest(section=section):
                self.assertEqual(
                    expected,
                    sorted(self.subject.catalog.providers[section].models))
        self.assertEqual(
            sorted(sum(_catalog.NEW_COMPOSITION.values(), [])),
            sorted(self.subject.catalog.models))

    def test_ac4_test_models_is_green_on_the_branch_catalog(self):
        """`tests/test_models.py` на каталоге ветки — зелёный: литерал
        состава равен новому составу.

        Ловит мутацию: литерал в разделе `codex` приведён к новому
        составу, а ОБЩИЙ перечень ниже оставлен прежним (в нём две
        строки, и вторую легко пропустить) — модуль покраснеет на
        сравнении общего перечня, хотя состав по разделам сойдётся.
        """
        result = _run_test_models(self.subject.path)

        self.assertTrue(
            result.wasSuccessful(),
            "tests/test_models.py красен на каталоге ветки: " + "; ".join(
                f"{case}: {trace.strip().splitlines()[-1]}"
                for case, trace in result.failures + result.errors))

    def test_ac4_renaming_one_model_turns_test_models_red(self):
        """Каталог, где одна модель переименована, а число моделей то же,
        `tests/test_models.py` обязан завернуть.

        Ловит мутацию: сверка состава ослаблена до счётчика («моделей
        столько же») либо до длины перечня — подмена одной модели другой
        прошла бы молча, а каталог решает, на чём вообще идут роли.
        """
        pattern = re.compile(rf"^(\s+){re.escape(RENAMED_FROM)}:",
                             re.MULTILINE)
        self.assertRegex(
            self.subject.text, pattern,
            f"в каталоге ветки нет записи {RENAMED_FROM} — подменять "
            f"нечего (см. AC-1)")
        renamed = pattern.sub(rf"\g<1>{RENAMED_TO}:", self.subject.text,
                              count=1)

        result = _run_test_models(self.write("models.renamed.yaml", renamed))

        self.assertFalse(
            result.wasSuccessful(),
            f"tests/test_models.py зелен на каталоге, где {RENAMED_FROM} "
            f"переименована в {RENAMED_TO} — состав сверяется не поимённо")

    def test_ac4_an_extra_model_turns_test_models_red(self):
        """Каталог с лишней моделью сверх нового состава
        `tests/test_models.py` обязан завернуть.

        Ловит мутацию: сверка состава ослаблена до вхождения
        (`assertIn`/`issubset` — «каждая ожидаемая модель в каталоге
        есть») — модель, добавленная мимо решения Оператора, прошла бы
        незамеченной, и ярус мог бы указать на неё.
        """
        anchor = "    models:\n"
        self.assertIn(anchor, self.subject.text,
                      "в каталоге ветки нет раздела моделей")
        extended = self.subject.text.replace(anchor, anchor + EXTRA_RECORD,
                                             1)

        result = _run_test_models(self.write("models.extended.yaml", extended))

        self.assertFalse(
            result.wasSuccessful(),
            f"tests/test_models.py зелен на каталоге с лишней моделью "
            f"{FIXTURE_EXTRA} — состав сверяется вхождением, не перечнем")


if __name__ == "__main__":
    unittest.main()
