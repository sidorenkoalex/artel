"""AC-14, AC-15: раздел `codex` каталога моделей и вердикт совместимости
модели с установленным CLI.

`models.yaml` — защищённый путь: раздел приезжает приложением к PLAN,
которое пульт применяет на мерже, а планка гоняется до него — поэтому
каталог под тестом собирается из самого приложения (`_codex.
catalog_text_with_appendix`), а PLAN читается из артефактной ветки, не с
диска.

Красен до реализации: ни раздела `codex` в приложении PLAN, ни
`CodexProvider.model_verdict` ещё нет — разбор каталога отказывает на
незарегистрированном провайдере, а `providers.get("codex")` —
`UnknownProviderError`.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, models, providers, stack  # noqa: E402
from tests.sandbox import TmpDirTest  # noqa: E402

from _codex import (CLI_MINIMUM, CLI_MINIMUM_TEXT, CODEX_PRICES,  # noqa: E402
                    CODEX_PRICE_DATE, PROVIDER, STEP_MODEL,
                    catalog_text_with_appendix)

MODEL_OUTSIDE_CATALOG = "gpt-modeli-takoy-net"

#: Версии CLI сценария AC-15: у `codex` — выше и ниже минимума записи, у
#: `claude` — заведомо другое число, чтобы вердикт, спросивший не тот
#: инструмент, отличался от верного.
CODEX_FRESH = "0.156.0"
CODEX_STALE = "0.150.0"
CLAUDE_VERSION = "2.1.267"


class CatalogSectionTest(TmpDirTest):
    """Раздел `codex` каталога моделей — требование 8, AC-14."""

    def setUp(self):
        super().setUp()
        path = self.tdir / "models.yaml"
        path.write_text(catalog_text_with_appendix(), encoding="utf-8")
        patcher = mock.patch.object(config, "MODELS", path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ac14_codex_section_parses_with_five_models_and_the_answer_prices(self):
        """Раздел `codex` разбирается без ошибок: `cli: codex`,
        `min_cli_version` 0.155.1, `cost_from_cli: false`; в разделе ровно
        пять моделей ANSWER-1, у каждой `status: experimental`,
        `price_date: 2026-09-21`, четыре цены по таблице и `cache_write`,
        равный `input`.

        Ловит мутацию: `cost_from_cli` оставлен `true` копипастой раздела
        Claude — пульт ждал бы стоимость шага от CLI, который её не
        сообщает, и расход задачи считался бы по отсутствующему числу;
        либо `cache_write` заведён «как у Anthropic» (дороже входа), и
        каждая оценка шага на Codex завышается на записи кэша, которую
        OpenAI отдельно не тарифицирует.
        """
        catalog = models.load_catalog()

        section = catalog.providers[PROVIDER]
        self.assertEqual(section.cli, PROVIDER)
        self.assertEqual(tuple(section.min_cli_version), CLI_MINIMUM)
        self.assertIs(section.cost_from_cli, False)

        listed = sorted(model_id for model_id, entry in catalog.models.items()
                        if entry.provider == PROVIDER)
        self.assertEqual(listed, sorted(CODEX_PRICES))

        for model_id, prices in CODEX_PRICES.items():
            with self.subTest(model=model_id):
                entry = catalog.models[model_id]
                self.assertEqual(entry.status, "experimental")
                self.assertEqual(entry.price_date, CODEX_PRICE_DATE)
                self.assertEqual(tuple(entry.min_cli_version), CLI_MINIMUM)
                self.assertEqual(tuple(entry.list_price), prices)
                self.assertEqual(entry.list_price.cache_write,
                                 entry.list_price.input)


class ModelVerdictTest(TmpDirTest):
    """`CodexProvider.model_verdict` — требование 7, AC-15."""

    def setUp(self):
        super().setUp()
        path = self.tdir / "models.yaml"
        path.write_text(catalog_text_with_appendix(), encoding="utf-8")
        patcher = mock.patch.object(config, "MODELS", path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.asked = []

    def verdict(self, model: str, codex_version: str):
        """Вердикт при заданной версии установленного `codex`; `claude`
        при этом отвечает ЗАВЕДОМО другим числом — вердикт, спросивший не
        тот инструмент, разойдётся с ожидаемым."""
        def fake_run(args, **kwargs):
            name = Path(str(args[0])).name
            self.asked.append(name)
            text = codex_version if name == PROVIDER else CLAUDE_VERSION
            return subprocess.CompletedProcess(list(args), 0, f"{text}\n", "")

        with mock.patch.object(stack.subprocess, "run", side_effect=fake_run):
            return providers.get(PROVIDER).model_verdict(model)

    def test_ac15_verdict_reads_the_catalog_minimum_and_asks_codex_version(self):
        """Модель, которой нет в каталоге, — `fail`; модель каталога при
        версии CLI не ниже минимума записи — `ok`; при более старой
        версии — `fail` с общим текстом «модель роли не поддерживается
        CLI»; версия спрашивается у `codex`, не у `claude`.

        Ловит мутацию: `model_verdict` унаследован у Claude как есть и
        зовёт `stack.installed_cli_version()` — тот спрашивает
        `claude --version`, и модель Codex получает вердикт по версии
        чужого CLI: свежий Claude при древнем Codex даёт зелёный
        предполёт и провал попытки за деньги.
        """
        absent = self.verdict(MODEL_OUTSIDE_CATALOG, CODEX_FRESH)
        self.assertEqual(absent.status, "fail", absent.detail)
        self.assertIn(MODEL_OUTSIDE_CATALOG, absent.detail)

        self.asked.clear()
        fresh = self.verdict(STEP_MODEL, CODEX_FRESH)
        self.assertEqual(fresh.status, "ok", fresh.detail)
        self.assertIn(PROVIDER, self.asked, self.asked)
        self.assertNotIn("claude", self.asked, self.asked)

        stale = self.verdict(STEP_MODEL, CODEX_STALE)
        self.assertEqual(stale.status, "fail", stale.detail)
        self.assertIn(stack.MODEL_UNSUPPORTED_PREFIX, stale.detail)
        self.assertIn(CLI_MINIMUM_TEXT, stale.detail)


if __name__ == "__main__":
    unittest.main()
