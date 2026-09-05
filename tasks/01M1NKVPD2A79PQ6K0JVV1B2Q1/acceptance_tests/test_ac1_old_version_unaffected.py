"""Приёмочные тесты 01M1NKVPD2A79PQ6K0JVV1B2Q1 — AC-1, часть про обратную
совместимость («version-gated — старые SPEC не ломаются»).

Отдельный файл от `test_ac1_guard_requires_zones_field.py`: та часть AC-1
красна до реализации (guard ещё не требует `zones` вовсе), эта — зелена
уже сегодня и обязана остаться зелёной ПОСЛЕ реализации (регрессионная
защита), поэтому несёт свой собственный маркер красноты, а не общий с
остальными сценариями AC-1 (skills/test-authoring.md — маркер красноты
даётся ПО ФАЙЛУ; смешивать в одном файле «красное сегодня» и «зелёное
сегодня и всегда» без противоречия маркеру нельзя).

Зелёный с рождения: SPEC текущей поддерживаемой версии (3 — та же
версия, что несёт SPEC.md самой этой задачи) без поля `zones:` уже
сегодня проходит `guard.check_content` без единой ошибки (проверено
прогоном: `check(version=3, zones=None)` -> `[]`) — версия-гейтинг AC-1
защищает именно этот случай, и он не должен ломаться НИ строкой этой
задачи. Тест — защита от регрессии («слишком жадная» реализация начинает
требовать `zones` у версии 3 задним числом), не проверка новой логики.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import check  # noqa: E402

CURRENT_SUPPORTED_VERSION = 3  # SPEC.md этой самой задачи, schema_version: 3


class OldVersionStaysUnaffectedTest(unittest.TestCase):
    """SPEC текущей поддерживаемой версии (3) без поля `zones:` остаётся
    валидным: AC-1 требует version-gating «старые SPEC не ломаются».

    Ловит мутацию: проверка обязательности `zones` реализована без
    версии-гейтинга (например `if "zones" not in meta` безусловно, без
    сравнения `schema_version`) — эта фикстура (версия 3, без zones)
    начнёт отказываться, хотя AC-1 явно требует обратной совместимости.
    """

    def test_ac1_version_3_without_zones_is_still_accepted(self):
        errors = check(version=CURRENT_SUPPORTED_VERSION, zones=None)

        self.assertEqual(
            errors, [],
            f"guard отклонил SPEC schema_version {CURRENT_SUPPORTED_VERSION} "
            f"(текущая поддерживаемая версия ДО этой задачи) без поля "
            f"zones — version-gating AC-1 не должен затрагивать старые "
            f"SPEC: {errors}")


if __name__ == "__main__":
    unittest.main()
