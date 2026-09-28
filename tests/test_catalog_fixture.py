"""Каталог моделей сценария — фикстура песочницы, а не боевой
`models.yaml` репозитория (SPEC 01M3KE8ZJXFARS6KC441PCDCQV, требование 4;
REVIEW.md итерации 1, R1-F1).

Класс дефекта тот же, что у фикстуры карты исполнителей (SPEC
01M3HP7RQEY0SBYNKQ902QD2CZ, `tests/test_roles_map_fixture.py`): состав
каталога — крутилка Оператора (28.09 он добавил три записи и снял одну), и
тест, читавший боевой каталог ради одного лишь идентификатора модели,
краснел от такой правки мимо своего предмета.

Здесь — сторож самого механизма: `tests/sandbox.py::TmpRootTest.
use_catalog_fixture` адресует `config.MODELS` на каталог-фикстуру ТОЛЬКО
на время сценария, который его позвал. Без этого сторожа отказ механизма
молчалив: `config.MODELS` процессно не подменяется (и не должен —
боевой каталог остаётся предметом `tests/test_models.py::CatalogTest`),
поэтому сценарий, потерявший подмену, просто возвращается к боевому
каталогу, где моделей фикстуры нет, и проходит вырожденно —
`tests/test_providers_codex.py::StepCostTest` и `tests/
test_token_rate_divergence.py::ChargeStepJournalTest` остаются зелёными,
теряя свой предмет (проверено ревью нейтрализацией метода в ноль).

Вторая половина того же свойства — возврат: каталог сценария не течёт в
соседние тесты прогона, иначе с `CatalogTest` снялась бы сверка боевого
состава по порядку прогона, а не по своему предмету.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, models  # noqa: E402
from tests.sandbox import (FIXTURE_CODEX_MODEL,  # noqa: E402
                           FIXTURE_OTHER_MODEL, FIXTURE_TIER_MODEL,
                           TmpRootTest)

REPO_ROOT = Path(__file__).resolve().parent.parent
LIVE_MODELS_PATH = REPO_ROOT / "models.yaml"

#: Состав каталога-фикстуры: модель яруса (её требует разрешение цепочки
#: роли) плюс две модели, которых в боевом каталоге нет по построению.
FIXTURE_COMPOSITION = sorted({FIXTURE_TIER_MODEL, FIXTURE_OTHER_MODEL,
                              FIXTURE_CODEX_MODEL})

#: Модели, ради которых фикстура и заводилась: сценарию нужна «какая-нибудь
#: другая модель каталога» и «какая-нибудь модель раздела `codex`».
#: Боевого каталога они не касаются — на этом и стоит проверка ниже.
FIXTURE_ONLY_MODELS = (FIXTURE_OTHER_MODEL, FIXTURE_CODEX_MODEL)


class CatalogFixtureSourceTest(TmpRootTest):
    """Требование 4: источник каталога сценария — литерал песочницы."""

    def test_the_scenario_catalog_is_the_fixture_not_the_live_file(self):
        """После `use_catalog_fixture()` разбор пульта (`models.
        load_catalog`) отдаёт состав фикстуры, а `config.MODELS` адресует
        файл песочницы, а не `models.yaml` репозитория.

        Ловит мутацию: патч уходит мимо `config.MODELS` (на другой атрибут
        или на свою копию пути) либо файл ложится туда, откуда каталог не
        читается, — сценарий молча читает боевой `models.yaml`, модели
        фикстуры в нём не разрешаются, и переведённые на неё классы
        (`tests/test_providers_codex.py::StepCostTest`, `tests/
        test_token_rate_divergence.py::ChargeStepJournalTest`) проходят
        вырожденно: «неполная разбивка -> UNCHARGED» перестаёт отличаться
        от «модель не разрешилась -> UNCHARGED».
        """
        live = sorted(models.load_catalog(LIVE_MODELS_PATH).models)

        path = self.use_catalog_fixture()
        catalog = models.load_catalog()

        self.assertEqual(Path(config.MODELS), path)
        self.assertNotEqual(Path(config.MODELS), LIVE_MODELS_PATH)
        self.assertEqual(sorted(catalog.models), FIXTURE_COMPOSITION)
        # Контроль вырожденности: состав фикстуры и боевой состав
        # различимы — иначе равенство выше выполнялось бы и без подмены.
        self.assertNotEqual(sorted(catalog.models), live)
        self.assertEqual(models.catalog_model(FIXTURE_CODEX_MODEL).provider,
                         "codex")
        self.assertEqual(models.catalog_model(FIXTURE_OTHER_MODEL).provider,
                         "claude")

    def test_the_models_the_translated_scenarios_name_live_only_in_the_fixture(self):
        """Модели, ради которых фикстура заведена, есть в ней и
        отсутствуют в боевом каталоге.

        Ловит мутацию: фикстура переписана на идентификаторы боевого
        каталога («так ближе к правде») — сценарий, потерявший подмену,
        продолжает разрешать свои модели из `models.yaml`, проверка
        соседнего метода зеленеет при любой поломке механизма, и
        связанность с крутилкой Оператора возвращается незаметно.
        """
        live = models.load_catalog(LIVE_MODELS_PATH)

        self.use_catalog_fixture()
        fixture = models.load_catalog()

        # Без subTest: провал внутри него pytest печатает строкой
        # `SUBFAILED`, мимо разбора красноты по `FAILED`/`ERROR`
        # (тот же довод, что в `tests/test_roles_map_fixture.py`).
        for model_id in FIXTURE_ONLY_MODELS:
            self.assertIn(model_id, fixture.models,
                          f"{model_id}: модель фикстуры пропала из неё")
            self.assertNotIn(model_id, live.models,
                             f"{model_id}: идентификатор фикстуры совпал с "
                             f"боевым каталогом — подмена перестала быть "
                             f"наблюдаемой")


class _CatalogFixtureSandbox(TmpRootTest):
    """Песочница, которая зовёт фикстуру каталога, — её гоняет руками
    `SandboxCatalogRestoreTest` ниже, а не сборщик pytest (поэтому имя
    сценарного метода не начинается с `test_`).

    `seen` — что сценарий увидел ВНУТРИ себя: контроль вырожденности,
    без него «каталог не утёк» выполнялось бы и тогда, когда сценарий
    каталог вовсе не менял."""

    seen = None

    def scenario(self):
        self.use_catalog_fixture()
        type(self).seen = (Path(config.MODELS),
                           sorted(models.load_catalog().models))


class SandboxCatalogRestoreTest(unittest.TestCase):
    """Требование 4, вторая половина: каталог сценария остаётся у
    сценария, а каталог ПРОЦЕССА остаётся боевым."""

    def process_catalog(self) -> tuple:
        return Path(config.MODELS), sorted(models.load_catalog().models)

    def test_the_scenario_catalog_does_not_leak_into_the_process(self):
        """Сценарий, позвавший `use_catalog_fixture()`, возвращает
        `config.MODELS` и состав каталога процесса на место.

        Ловит мутацию: патч ставится без `addCleanup` (или снятие уходит
        в `tearDown`, до которого сценарий с ошибкой не доходит) —
        каталог-фикстура течёт в соседние тесты прогона, и `tests/
        test_models.py::CatalogTest` сверяет литерал состава с тремя
        моделями песочницы вместо боевого каталога: правка `models.yaml`
        мимо литерала проходит зелёным по порядку прогона.
        """
        before = self.process_catalog()

        result = unittest.TestResult()
        _CatalogFixtureSandbox("scenario").run(result)

        self.assertEqual(result.errors + result.failures, [],
                         result.errors + result.failures)
        # Контроль вырожденности: сценарий каталог действительно уводил.
        self.assertNotEqual(_CatalogFixtureSandbox.seen, before)
        self.assertEqual(self.process_catalog(), before)

    def test_the_process_catalog_of_the_run_is_the_live_file(self):
        """Без явного вызова фикстуры каталог прогона — боевой
        `models.yaml` репозитория: `config.MODELS` песочница процессно НЕ
        подменяет (в отличие от `config.ROLES`/`config.MODELS_LOCAL`).

        Ловит мутацию: `MODELS` добавлен в `ALL_CONFIG_ATTRS` или уведён
        на фикстуру на весь процесс «для единообразия» — боевой каталог
        перестаёт быть предметом `tests/test_models.py::CatalogTest`, и
        сверка состава поимённо («каталог решает, на чём вообще идут
        роли») снимается целиком.
        """
        self.assertEqual(Path(config.MODELS), LIVE_MODELS_PATH)
        self.assertNotIn(FIXTURE_OTHER_MODEL, models.load_catalog().models)


if __name__ == "__main__":
    unittest.main()
