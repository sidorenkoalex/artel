"""AC-4 (tasks/01M1QHQ277PQQA894X97RVEX9Y/SPEC.md): «Ассерт на текст
адреса в `tests/test_branch_freshness_gate.py` (проверка «remote — url
записи target'а, не хардкод origin пульта») переписан под новый адрес и
продолжает проверять то же самое, не ослаблен.»

Красен до реализации: `TargetSourcedRemoteTest.
test_pull_freshness_fetches_target_url_not_pult_origin` (`tests/
test_branch_freshness_gate.py:561-599`) сегодня всё ещё сверяет
буквальный `"https://example.invalid/acme-target.git"` — `assertNotIn
("example.invalid", src)` падает на исходном тексте метода.
"""
import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# Импорт МОДУЛЯ, не класса: `from ... import TargetSourcedRemoteTest`
# связал бы имя класса в пространстве имён ЭТОГО файла, и `unittest
# discover` подобрал бы его как ЕЩЁ ОДИН тестовый класс для сборки —
# повторный, шумный прогон настоящей песочницы TargetSourcedRemoteTest
# (с реальным `catalog.cmd_new`) при каждом прогоне этой планки.
from tests import test_branch_freshness_gate  # noqa: E402

_METHOD = "test_pull_freshness_fetches_target_url_not_pult_origin"


class BranchFreshnessAssertRewrittenTest(unittest.TestCase):

    def test_ac4_assert_still_checks_url_record_not_hardcoded_origin(self):
        """Метод `test_pull_freshness_fetches_target_url_not_pult_origin`
        обязан: (а) не содержать больше DNS-адрес `example.invalid`,
        (б) продолжать проверять ровно то же самое — что remote фетча
        это `url` записи target'а (не хардкод `"origin"`) и что ветка
        фетча это `base` записи (не `config.MAIN_BRANCH`).

        Ловит мутацию: разработчик заменил адрес фикстуры, но заодно
        убрал/ослабил один из четырёх ассертов метода (например, снял
        `assertNotIn("origin", ...)` — регрессия к хардкоду origin,
        именно тот класс дефекта, который AC-10 задачи
        01M1NBWPKNBXP9ZXXQDJM7AXPJ уже один раз закрывала) — исходный
        текст метода читается напрямую и каждый из четырёх ассертов
        проверяется по отдельности, не общим «тест всё ещё существует».
        """
        cls = test_branch_freshness_gate.TargetSourcedRemoteTest
        method = getattr(cls, _METHOD, None)
        self.assertIsNotNone(
            method, f"{_METHOD} обязан остаться в TargetSourcedRemoteTest")
        src = inspect.getsource(method)

        self.assertNotIn("example.invalid", src,
                         "AC-3: DNS-адрес фикстуры обязан быть заменён")
        self.assertIn('assertNotIn("origin"', src,
                      "AC-4: проверка «remote — не хардкод origin» обязана "
                      "остаться")
        self.assertIn('assertIn("trunk"', src,
                      "AC-4: проверка ветки фетча (base записи target'а) "
                      "обязана остаться")
        self.assertIn("assertNotIn(config.MAIN_BRANCH", src,
                      "AC-4: проверка «MAIN_BRANCH — не эта ветка» обязана "
                      "остаться")

        class_src = inspect.getsource(cls)
        self.assertNotIn("example.invalid", class_src,
                         "AC-3: TARGETS_YAML класса тоже обязан обновиться")
        self.assertTrue(
            "file://" in class_src or "127.0.0.1" in class_src,
            "AC-3: новый адрес обязан быть заведомо локальным")


if __name__ == "__main__":
    unittest.main()
