"""AC-9: `init` и `doctor --fix` кладут шаблон локального слоя, если файла
нет (все ярусы на `claude-opus-5`, раздел переопределений пуст), и не
трогают уже существующий файл.

Красен до реализации: фикстура падает на отсутствующем `models.yaml`
(каталог создаёт эта задача), а `init`/`doctor --fix` о локальном слое
всё равно не знают — `.artel/models.yaml` после них не появляется.
"""
import unittest
from unittest import mock

import _models
from _sandbox import CatalogSandbox, ModelsDoctorSandbox
from orchestrator import catalog, doctor, gitcmd, yamlmini
from tests.sandbox import capture, fake_git

# Содержимое, которое ни одна из команд не вправе переписать.
OPERATOR_LOCAL = ("tiers:\n  strong: claude-fable-5-1\n"
                  "  standard: claude-sonnet-5\n  cheap: claude-sonnet-5\n")


class _TemplateAssertions:

    def assert_template(self) -> None:
        """Шаблон на месте: все ярусы на `claude-opus-5`, переопределений
        нет."""
        self.assertTrue(self.local_path.is_file(),
                        f"шаблон локального слоя не положен: {self.local_path}")
        doc = yamlmini.mapping(self.local_path.read_text(encoding="utf-8"))

        tiers = _models.section(doc, "tiers")
        self.assertIsInstance(tiers, dict, f"раздела tiers: нет: {doc}")
        self.assertEqual(sorted(tiers), sorted(_models.TIERS))
        for tier, model in tiers.items():
            self.assertEqual(model, _models.OPUS, f"ярус {tier}")

        overrides = _models.section(doc, "overrides")
        self.assertIn(overrides, (None, {}),
                      f"раздел переопределений не пуст: {overrides!r}")


class InitPlacesTemplateTest(_TemplateAssertions, CatalogSandbox):
    """`init` во временном корне пульта."""

    def setUp(self):
        super().setUp()
        self.write_catalog()

    def init(self) -> None:
        with mock.patch.object(gitcmd, "git", fake_git):
            capture(catalog.cmd_init)

    def test_ac9_init_places_the_template_when_the_file_is_missing(self):
        """`init` на пульте без `.artel/models.yaml` кладёт шаблон: три
        яруса на `claude-opus-5`, раздел переопределений пуст.

        Ловит мутацию: шаблон кладётся с пустым `tiers:` (или с ярусами,
        указывающими на разные модели «по вкусу кода») — свежий пульт
        либо не разрешает ни одного яруса, либо молча назначает ролям не
        ту модель, которую называет SPEC.
        """
        self.init()

        self.assert_template()

    def test_ac9_init_does_not_overwrite_an_existing_local_layer(self):
        """Существующий `.artel/models.yaml` `init` не перезаписывает и не
        меняет.

        Ловит мутацию: шаблон пишется безусловно (`write_text` без
        проверки существования) — `init`, который Оператор зовёт и на
        живом пульте (холодный старт, восстановление), затирал бы его
        калибровку тарифов и выбор моделей по ярусам.
        """
        self.write_local(OPERATOR_LOCAL)

        self.init()

        self.assertEqual(self.local_path.read_text(encoding="utf-8"),
                         OPERATOR_LOCAL)


class DoctorFixPlacesTemplateTest(_TemplateAssertions, ModelsDoctorSandbox):
    """`doctor --fix` в окружении `tests/test_doctor.py`."""

    def setUp(self):
        super().setUp()
        self.write_catalog()

    def doctor_fix(self) -> None:
        with mock.patch.object(doctor, "all_checks", lambda conn: []), \
                mock.patch.object(doctor.gitcmd, "list_branches",
                                  lambda prefix="": []), \
                mock.patch.object(doctor.gitcmd, "git", fake_git):
            capture(lambda: doctor.cmd_doctor(fix=True))

    def test_ac9_doctor_fix_places_the_template_when_the_file_is_missing(self):
        """`doctor --fix` на пульте без локального слоя кладёт тот же
        шаблон, что и `init`.

        Ловит мутацию: шаблон кладёт только `init` — пульт, заведённый до
        этой задачи (`init` там уже прошёл), остаётся без локального слоя
        навсегда, а `doctor` только краснеет, ничего не чиня.
        """
        self.local_path.unlink(missing_ok=True)

        self.doctor_fix()

        self.assert_template()

    def test_ac9_doctor_fix_does_not_overwrite_an_existing_local_layer(self):
        """Существующий файл `doctor --fix` не перезаписывает.

        Ловит мутацию: починка трактует «файл не такой, как шаблон» как
        повод привести его к шаблону — `doctor --fix`, который Оператор
        зовёт для уборки веток и хуков, попутно сбрасывал бы ярусы на
        дефолт.
        """
        self.write_local(OPERATOR_LOCAL)

        self.doctor_fix()

        self.assertEqual(self.local_path.read_text(encoding="utf-8"),
                         OPERATOR_LOCAL)


if __name__ == "__main__":
    unittest.main()
