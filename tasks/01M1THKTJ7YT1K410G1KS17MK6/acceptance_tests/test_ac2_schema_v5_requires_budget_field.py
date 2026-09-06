"""Приёмочные тесты 01M1THKTJ7YT1K410G1KS17MK6 — AC-2 (`scripts/guard.py`:
`SUPPORTED_SCHEMA_VERSION` поднят до 5; новая проверка отказывает SPEC
(`type: spec`) с `schema_version >= 5` без поля `budget_usd` или со
значением, которое не разбирается как число; SPEC с `schema_version < 5`
этой проверкой не затрагивается).

Чёрный ящик над `scripts.guard.check_content` — та же фикстура
`_sandbox.spec_text`, что и остальные тесты этой планки.

Красен до реализации: `scripts.guard.SUPPORTED_SCHEMA_VERSION` сегодня
равен 4 — SPEC с `schema_version: 5` уже отказывается ДРУГИМ, более
ранним правилом («schema_version новее поддерживаемой»), так что даже
`test_ac2_supported_schema_version_is_5` красен раньше, чем дело доходит
до самого поля `budget_usd`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import guard  # noqa: E402
from _sandbox import check_spec  # noqa: E402


class SupportedSchemaVersionTest(unittest.TestCase):
    """`SUPPORTED_SCHEMA_VERSION` — ровно 5, не любое число выше 4.

    Ловит мутацию: версия поднята до 6 или дальше «с запасом» — тогда
    SPEC со `schema_version: 5` (реальная задача этой версии, ещё не
    существующая на момент планки) не считался бы новее поддерживаемой,
    но и не был бы РОВНО тем значением, которое называет AC-2.
    """

    def test_ac2_supported_schema_version_is_5(self):
        self.assertEqual(guard.SUPPORTED_SCHEMA_VERSION, 5)


class SchemaV5RequiresBudgetFieldTest(unittest.TestCase):
    """SPEC `schema_version: 5` без `budget_usd` — отказ; со значением,
    которое не разбирается как число, — тоже отказ; корректное значение
    — без этого класса ошибок.

    Ловит мутацию: проверка присутствия поля забыта (только «разбирается
    как число», пропуская случай отсутствия поля вовсе) — тогда
    `test_ac2_v5_without_budget_field_is_refused` не найдёт ни одной
    ошибки, упомянувшей `budget_usd`, и упадёт.
    """

    def test_ac2_v5_without_budget_field_is_refused(self):
        errors = check_spec(schema_version=5, budget=None)

        self.assertTrue(errors, "SPEC v5 без budget_usd обязан быть отказан")
        self.assertTrue(
            any("budget_usd" in e for e in errors),
            f"ни одна ошибка не называет budget_usd: {errors!r}")

    def test_ac2_v5_with_unparseable_budget_is_refused(self):
        errors = check_spec(schema_version=5, budget="дорого")

        self.assertTrue(errors, "SPEC v5 с нечисловым budget_usd обязан "
                                "быть отказан")
        self.assertTrue(
            any("budget_usd" in e for e in errors),
            f"ни одна ошибка не называет budget_usd: {errors!r}")

    def test_ac2_v5_with_valid_budget_is_not_refused_by_this_rule(self):
        """Контрольный случай (проверяет чувствительность двух тестов
        выше): корректное число не должно тянуть за собой ошибку про
        отсутствие/неразборчивость `budget_usd` — иначе первые два теста
        были бы красны при ЛЮБОЙ реализации, не только при отсутствии
        кода задачи."""
        errors = check_spec(schema_version=5, budget=25)

        self.assertFalse(
            any("budget_usd" in e for e in errors),
            f"budget_usd: 25 — корректное значение, но получена ошибка "
            f"про это поле: {errors!r}")


class SchemaBelowV5IsUnaffectedTest(unittest.TestCase):
    """SPEC `schema_version < 5` без `budget_usd` — версия-гейтинг тем же
    приёмом, что уже несут `requires_ac_markup`/`requires_zones`: старый
    беклог не ловится задним числом.

    Ловит мутацию: новое правило написано без версии-гейтинга (проверяет
    поле у любого SPEC независимо от `schema_version`) — тогда SPEC
    `schema_version: 4` без `budget_usd`, валидный до этой задачи,
    внезапно получит ошибку про отсутствующее поле.
    """

    def test_ac2_v4_without_budget_field_is_not_refused_by_this_rule(self):
        errors = check_spec(schema_version=4, budget=None)

        self.assertFalse(
            any("budget_usd" in e for e in errors),
            f"SPEC schema_version 4 не обязан нести budget_usd — "
            f"получена ошибка: {errors!r}")


if __name__ == "__main__":
    unittest.main()
