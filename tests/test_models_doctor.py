"""Юнит-тесты проверок `doctor` по каталогу моделей и локальному слою и
шаблона слоя, который кладут `init` и `doctor --fix` (SPEC
01M3009Y9AGGY6ZCFA7H1HJ1TD, требования 7, 11; AC-7, AC-9, AC-14, AC-15).

Шаблон локального слоя общая песочница `tests/sandbox.py` кладёт в
`setUp` (иначе любой её путь до шага роли отказывал бы «ярус не
разрешён»), поэтому сценарий «файла НЕТ» тесты получают, удалив его —
это и есть состояние свежего пульта.
"""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, doctor, models  # noqa: E402
from tests.sandbox import TmpDirTest, TmpRootTest  # noqa: E402
from tests.test_models import (CATALOG_TEMPLATE, FULL_PRICES,  # noqa: E402
                               LOCAL_TEMPLATE)

AGENT_ROLES_YAML = """\
roles:
  developer:
    executor: agent
    token_slot: artel-developer
    skills: [conventions-core]
    model_tier: strong
  reviewer:
    executor: agent
    token_slot: artel-reviewer
    skills: [conventions-core]
    model_tier: {reviewer_tier}
  test_author:
    executor: agent
    token_slot: artel-test-author
    skills: [conventions-core]
    model_tier: strong
token_fallback: artel-token
"""


class _LayersTest(TmpDirTest):
    """Каталог, локальный слой и карта исполнителей временными файлами."""

    def setUp(self):
        super().setUp()
        self.use_catalog(CATALOG_TEMPLATE.format(
            prices=FULL_PRICES, status=models.STATUS_SUPPORTED))
        self.use_local(LOCAL_TEMPLATE)
        self.use_roles(AGENT_ROLES_YAML.format(reviewer_tier="strong"))

    def patch(self, attr: str, value) -> None:
        patcher = mock.patch.object(config, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def use_catalog(self, text: str) -> None:
        path = self.tdir / "models.yaml"
        path.write_text(text, encoding="utf-8")
        self.patch("MODELS", path)

    def use_local(self, text: str) -> None:
        path = self.tdir / "local-models.yaml"
        path.write_text(text, encoding="utf-8")
        self.patch("MODELS_LOCAL", path)

    def use_roles(self, text: str) -> None:
        path = self.tdir / "roles.yaml"
        path.write_text(text, encoding="utf-8")
        self.patch("ROLES", path)


class CatalogCheckTest(_LayersTest):
    """AC-14, первая проверка: «каталог моделей»."""

    def test_ok_lists_the_models_of_the_catalog(self):
        """Ловит мутацию: проверка зелёная всегда (каталог не читается
        вовсе) — `doctor` молчал бы о сломанном каталоге до первого
        отказа шага."""
        check = doctor.check_models_catalog()

        self.assertEqual(check.status, "ok", check.detail)
        self.assertIn("model-alfa", check.detail)

    def test_unparsed_catalog_fails_by_name(self):
        """Ловит мутацию: отказ разбора ловится как исключение и роняет
        весь `doctor` либо превращается в `warn` — прогон зеленел бы при
        каталоге, по которому не запускается ни один шаг."""
        self.use_catalog("providers:\n  - claude\n")

        check = doctor.check_models_catalog()

        self.assertEqual(check.status, "fail", check.detail)

    def test_tier_model_missing_from_the_catalog_fails(self):
        """Ловит мутацию: проверка каталога смотрит только на сам файл и
        не сверяется с ярусами — модель, на которую указывает ярус, но
        которой нет в каталоге, осталась бы незамеченной до шага."""
        self.use_local("tiers:\n  strong: model-net-v-kataloge\n")

        check = doctor.check_models_catalog()

        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn("model-net-v-kataloge", check.detail)


class LocalCheckTest(_LayersTest):
    """AC-14, вторая проверка: «локальный слой»."""

    def test_ok_lists_the_chain_of_every_agent_role(self):
        """Ловит мутацию: проверка смотрит только на существование файла
        и не разрешает ярусы ролей — слой с половиной ярусов зеленел бы,
        а шаг роли всё равно бы не стартовал."""
        check = doctor.check_models_local()

        self.assertEqual(check.status, "ok", check.detail)
        for role in ("developer", "reviewer", "test_author"):
            self.assertIn(role, check.detail)

    def test_missing_file_fails_and_names_the_fix(self):
        """Ловит мутацию: отсутствие слоя — `warn` или молчание, либо
        текст не называет команду починки: Оператор свежего пульта не
        узнал бы, что делать."""
        self.patch("MODELS_LOCAL", self.tdir / "net-takogo-fayla.yaml")

        check = doctor.check_models_local()

        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn(models.LOCAL_FIX_HINT, check.detail)

    def test_role_with_an_unresolvable_tier_fails(self):
        """Ловит мутацию: ярус роли вне перечня (или без модели в слое)
        не проверяется — красной строки `doctor` не было бы, и отказ
        всплыл бы только на `run` (AC-7)."""
        self.use_roles(AGENT_ROLES_YAML.format(reviewer_tier="turbo"))

        check = doctor.check_models_local()

        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn("reviewer", check.detail)

    def test_experimental_without_allowance_fails(self):
        """Ловит мутацию: статус `experimental` виден только `run`, но не
        `doctor` — пульт узнавал бы о неразрешённой модели в момент
        шага."""
        self.use_catalog(CATALOG_TEMPLATE.format(
            prices=FULL_PRICES, status=models.STATUS_EXPERIMENTAL))

        check = doctor.check_models_local()

        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn(models.STATUS_EXPERIMENTAL, check.detail)

    def test_both_checks_are_wired_into_all_checks(self):
        """Ловит мутацию: проверки написаны, но не подключены к
        `all_checks` — `doctor` молчал бы о слоях (тот же приём, что
        `tests/test_doctor.py::test_all_checks_wires_in_check_pin_unpushed`)."""
        import inspect

        source = inspect.getsource(doctor.all_checks)

        self.assertIn("check_models_catalog", source)
        self.assertIn("check_models_local", source)


class RoleProvidersChainTest(_LayersTest):
    """AC-15: строка `doctor` о провайдерах несёт цепочку целиком."""

    def test_line_prints_role_tier_model_provider(self):
        """Ловит мутацию: строка осталась парой «роль → провайдер» — по
        ней не видно, на какой модели реально пойдёт роль."""
        check = doctor.check_role_providers()

        self.assertEqual(check.status, "ok", check.detail)
        self.assertIn("developer → strong → model-alfa → claude", check.detail)

    def test_unresolved_chain_makes_the_line_red(self):
        """Ловит мутацию: неразрешимая цепочка печатается зелёной
        строкой с прочерком — `doctor` утверждал бы, что с ролями всё в
        порядке (AC-7)."""
        self.use_roles(AGENT_ROLES_YAML.format(reviewer_tier="turbo"))

        check = doctor.check_role_providers()

        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn("reviewer", check.detail)


class LocalTemplateTest(TmpRootTest):
    """AC-9: шаблон кладут `init` и `doctor --fix`; существующий файл не
    трогают."""

    def setUp(self):
        super().setUp()
        # Состояние свежего пульта: песочница кладёт шаблон в `setUp`
        # (см. докстринг модуля), а предмет этих тестов — его появление.
        config.MODELS_LOCAL.unlink()

    def test_init_puts_the_template_when_the_file_is_absent(self):
        """Ловит мутацию: `init` не кладёт слой — свежий пульт проходит
        `init` и не может запустить ни одного шага роли."""
        self.capture(catalog.cmd_init)

        self.assertTrue(config.MODELS_LOCAL.is_file())
        self.assertEqual(config.MODELS_LOCAL.read_text(encoding="utf-8"),
                         models.local_template_text())

    def test_doctor_fix_puts_the_template_when_the_file_is_absent(self):
        """Ловит мутацию: `doctor --fix` чинит всё, кроме локального слоя
        — Оператору пришлось бы писать файл руками по образцу."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            doctor.fix_models_local()

        self.assertTrue(config.MODELS_LOCAL.is_file())
        self.assertIn(str(config.MODELS_LOCAL), buf.getvalue())

    def test_existing_file_is_not_overwritten_by_either_command(self):
        """Ловит мутацию: шаблон кладётся безусловно — выбор моделей
        Оператора затирался бы каждым `init`/`doctor --fix`."""
        own = "tiers:\n  strong: claude-sonnet-5\n"
        config.MODELS_LOCAL.write_text(own, encoding="utf-8")

        self.capture(catalog.cmd_init)
        with redirect_stdout(io.StringIO()):
            doctor.fix_models_local()

        self.assertEqual(config.MODELS_LOCAL.read_text(encoding="utf-8"), own)

    def test_doctor_fix_is_wired_into_cmd_doctor(self):
        """Ловит мутацию: уборка написана, но `doctor --fix` её не зовёт
        — шаблон не появлялся бы ни при одном вызове команды."""
        import inspect

        self.assertIn("fix_models_local",
                      inspect.getsource(doctor.cmd_doctor))


if __name__ == "__main__":
    unittest.main()
