"""AC-16: команда `models` печатает таблицу (провайдер, модель, статус,
минимум CLI, прейскурант, действующий тариф и его источник, роли по
ярусам) и ничего не записывает — ни файлов, ни состояния.

Красен до реализации: сценарий падает на отсутствующем `models.yaml`
(каталог создаёт эта задача), а самой команды `models` в диспетчере
`orchestrator/artel.py` нет — вызов вышел бы с «Неизвестная команда
models».
"""
import sys
import unittest
from unittest import mock

import _models
from _sandbox import CatalogSandbox
from orchestrator import artel
from tests.sandbox import capture

ROLE = "developer"
OVERRIDE_PRICES = {"input": 4.0, "output": 20.0,
                   "cache_write": 5.5, "cache_read": 0.4}
CALIBRATED_AT = "2026-09-20"
SOURCE = "kalibrovka-po-zhurnalu"

# Слова столбцов — из формулировки самого критерия.
COLUMN_WORDS = ("провайдер", "модель", "статус", "cli", "прейскурант",
                "тариф", "источник", "ярус")


def _tree(root) -> dict:
    """Снимок дерева: путь -> содержимое файла (каталоги — пустым
    значением)."""
    snapshot = {}
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        snapshot[rel] = path.read_bytes() if path.is_file() else None
    return snapshot


class ModelsCommandTest(CatalogSandbox):
    """Каталог, локальный слой с переопределением и ярусы ролей во
    временном корне пульта."""

    def setUp(self):
        super().setUp()
        self.write_catalog()
        self.strong_model, self.second_model = _models.two_supported_models()
        self.tiers = {"strong": self.strong_model,
                      "standard": self.second_model,
                      "cheap": self.second_model}
        override = (self.strong_model, OVERRIDE_PRICES, CALIBRATED_AT, SOURCE)
        self.texts = _models.local_texts(self.tiers, override=override)
        self.role_tiers = {role: "strong" for role in _models.agent_roles()}
        self.set_roles_tiers(self.role_tiers)

    def run_models(self) -> str:
        """Вывод `artel.py models` — через диспетчер команд, не мимо него
        (SPEC требование 12: команда живёт в `orchestrator/artel.py`)."""
        with mock.patch.object(sys, "argv", ["artel.py", "models"]):
            return capture(artel.main)

    def printed(self) -> str:
        """Вывод команды на первой форме записи локального слоя, которую
        разбор принял."""
        def attempt(text):
            self.write_local(text)
            out = self.run_models()
            assert SOURCE in out, (
                f"источник действующего тарифа не напечатан:\n{out}")
            return out

        return _models.first_success(self.texts, attempt)

    def test_ac16_table_carries_every_column_of_the_criterion(self):
        """В выводе есть все столбцы критерия: провайдер, модель, статус,
        минимум CLI, прейскурант, действующий тариф и его источник, роли
        по ярусам.

        Ловит мутацию: команда печатает голый дамп каталога (модель и
        цены) — Оператор не видит ни действующего тарифа, ни его
        источника, ни того, какие роли поедут на этой модели, то есть
        ровно того, ради чего «только чтение»-команда и заведена.
        """
        out = self.printed()
        lowered = out.lower()

        for word in COLUMN_WORDS:
            with self.subTest(column=word):
                self.assertIn(word, lowered, f"нет столбца «{word}»:\n{out}")

    def test_ac16_table_carries_models_versions_rates_and_roles(self):
        """Содержимое таблицы: три модели каталога с их статусами и
        минимумами CLI, прейскурант, действующий тариф переопределения с
        источником и роли по ярусам.

        Ловит мутацию: действующий тариф печатается прейскурантом
        каталога (переопределение локального слоя команда не применяет) —
        таблица показывает не те деньги, по которым реально считается
        шаг.
        """
        out = self.printed()
        entries = _models.model_entries(_models.catalog_document())

        for model, (_path, entry) in entries.items():
            with self.subTest(model=model):
                self.assertIn(model, out)
                versions = [v for v in entry.values()
                            if isinstance(v, str) and _models.VERSION_RE.match(v)]
                self.assertTrue(any(v in out for v in versions),
                                f"нет минимума CLI {model}: {versions}")
                statuses = [v for v in entry.values() if v in _models.STATUSES]
                self.assertTrue(any(s in out for s in statuses),
                                f"нет статуса {model}: {statuses}")

        list_price = entries[self.strong_model][1][_models.PRICE_KEY]
        self.assertIn(str(list_price["cache_write"]), out,
                      "прейскурант каталога не напечатан")
        self.assertIn(str(OVERRIDE_PRICES["cache_write"]), out,
                      "действующий тариф переопределения не напечатан")
        self.assertIn(SOURCE, out)
        for role, tier in self.role_tiers.items():
            with self.subTest(role=role):
                self.assertIn(role, out)
                self.assertIn(tier, out)

    def test_ac16_command_writes_nothing(self):
        """После команды дерево пульта байт в байт прежнее: ни нового
        файла, ни изменённого.

        Ловит мутацию: команда попутно чинит отсутствующий локальный слой
        (кладёт шаблон, как `doctor --fix`) или заводит состояние
        (`store.db()` создаёт БД) — читающая команда перестаёт быть
        безопасной, а вызов из чужого каталога заводит там пульт-призрак.
        """
        self.write_local(self.texts[0])
        before = _tree(self.root)

        self.run_models()

        self.assertEqual(_tree(self.root), before)


if __name__ == "__main__":
    unittest.main()
