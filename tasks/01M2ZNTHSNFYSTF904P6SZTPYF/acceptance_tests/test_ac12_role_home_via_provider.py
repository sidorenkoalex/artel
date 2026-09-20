"""AC-12: дом роли — развёртывание при `init` и сверка развёрнутого слоя
идут по `home_reference()` провайдера; для `claude` — тот же каталог
референса и то же имя развёрнутого каталога, что до задачи.

Красен до реализации: `home_reference()` некому отдать — реестра
провайдеров ещё нет; сама сверка развёрнутого слоя с референсом работает
и сегодня, её тест стережёт неизменность поведения.
"""
import inspect
import unittest

from orchestrator import catalog, config, doctor
from _providers import home_reference_parts, provider
from tests.sandbox import TmpRootTest

REFERENCE_PATH_PART = "docs/reference/role-home"
DEPLOYED_DIR_NAME = ".claude"
CURATED = "# Курируемый слой роли\n"
DEPLOYED_OTHER = "# правка Оператора поверх референса\n"


class RoleHomeViaProviderTest(TmpRootTest):
    """Временный корень пульта: свой референс дома роли и свой
    развёрнутый слой."""

    def seed_reference(self, text: str = CURATED):
        """Референс дома роли в временном корне — там же, где его держит
        репозиторий."""
        reference = (config.ROOT / "docs" / "reference" / "role-home"
                     / "claude")
        reference.mkdir(parents=True, exist_ok=True)
        (reference / "CLAUDE.md").write_text(text, encoding="utf-8")
        (reference / "settings.json").write_text("{}\n", encoding="utf-8")
        return reference

    def provider_reference(self):
        return home_reference_parts(provider().home_reference())

    def test_ac12_home_reference_names_todays_reference_and_deployed_dir(self):
        """Провайдер называет каталог референса внутри
        `docs/reference/role-home` и имя развёрнутого каталога
        `.claude`.

        Ловит мутацию: имя развёрнутого каталога отдано без ведущей
        точки (`claude`, как в самом репозитории) или референс указан на
        уже развёрнутый слой `.artel/home` — холодный старт разворачивает
        дом роли не туда, а CLI шага не находит своих настроек.
        """
        self.seed_reference()

        reference, name = self.provider_reference()

        self.assertIsNotNone(reference, "провайдер не назвал референс")
        self.assertIn(REFERENCE_PATH_PART, reference.as_posix())
        self.assertEqual(name, DEPLOYED_DIR_NAME)

    def test_ac12_init_deploys_exactly_the_provider_reference(self):
        """`init` разворачивает дом роли: каталог с именем от провайдера
        существует, а файлы референса лежат в нём побайтово теми же.

        Ловит мутацию: развёртывание берёт каталог мимо провайдера
        (собственный литерал пути) или копирует не то дерево — холодный
        старт оставляет роль без курируемого слоя, а расхождение
        всплывает только на шаге.
        """
        reference = self.seed_reference()

        self.capture(catalog.cmd_init)

        _, name = self.provider_reference()
        self.assertTrue((config.ROLE_HOME / name).is_dir(),
                        f"каталог {name} в {config.ROLE_HOME} не развёрнут")
        deployed = {p.name: p.read_bytes()
                    for p in config.ROLE_HOME.rglob("*") if p.is_file()}
        originals = [p for p in reference.rglob("*") if p.is_file()]
        self.assertTrue(originals, "референс дома роли пуст")
        for original in originals:
            with self.subTest(file=original.name):
                self.assertEqual(deployed.get(original.name),
                                 original.read_bytes())

    def test_ac12_init_asks_the_provider_for_the_reference(self):
        """Развёртывание в `orchestrator/catalog.py` обращается к
        `home_reference()`, а не несёт путь референса своим литералом.

        Ловит мутацию: `home_reference()` реализован, но `init`
        по-прежнему знает путь сам — второй провайдер получит чужой дом
        роли, и никакой отказ об этом не скажет.
        """
        source = inspect.getsource(catalog).lower()

        self.assertIn("home_reference", source)
        self.assertIn("provider", source,
                      "orchestrator/catalog.py не обращается к провайдеру "
                      "за домом роли")

    def test_ac12_role_home_check_compares_with_the_provider_reference(self):
        """Сверка развёрнутого слоя: файл развёрнутого слоя отличается от
        референса — предупреждение с именем файла; сама сверка берёт
        референс у провайдера.

        Ловит мутацию: сверка осталась на собственном литерале пути
        референса — на другом провайдере она сравнивала бы развёрнутый
        слой с чужим эталоном и молчала бы о настоящем расхождении.
        """
        self.seed_reference()
        config.ROLE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        (config.ROLE_CONFIG_DIR / "CLAUDE.md").write_text(
            DEPLOYED_OTHER, encoding="utf-8")

        check = doctor.check_role_home_reference()

        self.assertEqual(check.status, "warn", check.detail)
        self.assertIn("CLAUDE.md", check.detail)
        self.assertIn("provider",
                      inspect.getsource(doctor.check_role_home_reference).lower(),
                      "сверка дома роли не спрашивает референс у провайдера")


if __name__ == "__main__":
    unittest.main()
