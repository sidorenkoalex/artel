"""Приёмочные тесты 01M1NKVPD2A79PQ6K0JVV1B2Q1 — AC-1 (frontmatter SPEC
несёт поле `zones:`; `guard.py` требует поле для SPEC новой версии схемы,
version-gated — старые SPEC не ломаются).

Два сценария: (1) новая версия без `zones:` — guard отказывает и НАЗЫВАЕТ
поле по имени, не общей фразой; (2) новая версия С заполненным `zones:`
— принимается без единой ошибки. Обратная совместимость (старая версия
без `zones:` по-прежнему принимается) — отдельный файл
`test_ac1_old_version_unaffected.py`, зелёный уже сегодня (маркер
красноты этого файла не годится ему). `_sandbox.py` объясняет, почему
тесты сверяют текст сообщения («zones» по имени), а не просто факт
непустого списка ошибок, и почему выбрана версия 4 при том, что SPEC не
называет число буквально.

Красен до реализации: `scripts/guard.py` сегодня не знает поля `zones`
вовсе (проверено `grep -n zones -r scripts/guard.py` — совпадений нет,
кроме несвязанного `_zone_paths`/`ZONE_PATH`, см. докстринг `_sandbox.py`)
и `SUPPORTED_SCHEMA_VERSION = 3` — сценарий (1) сегодня уже возвращает
непустой список ошибок, но по ДРУГОЙ причине («schema_version 4 новее
поддерживаемой 3»), которая не называет «zones»; сценарий (2) сегодня
отказывает по ТОЙ ЖЕ причине («новее поддерживаемой»), хотя сам список
зон валиден. Оба покраснеют на assertion, специфичном для этой задачи,
до того, как разработчик поднимет `SUPPORTED_SCHEMA_VERSION` до 4 и
добавит требование `zones` для version >= 4.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import NEW_ZONES_VERSION, check  # noqa: E402


class NewVersionRequiresZonesFieldTest(unittest.TestCase):
    """SPEC версии `NEW_ZONES_VERSION` без поля `zones:` — guard отказывает,
    и сообщение отказа называет поле `zones` по имени.

    Ловит мутацию: разработчик поднимает `SUPPORTED_SCHEMA_VERSION` до
    новой версии (делая её вообще поддерживаемой), но забывает добавить
    отдельную проверку обязательности `zones` для этой версии — список
    ошибок станет пустым (версия больше не «слишком новая», а поле никто
    не требует), assertion на непустоту и на упоминание «zones» оба
    покраснеют. Отдельно ловит и «версия поддерживается, поле требуется,
    но отказ сформулирован общей фразой без имени поля» — assertIn на
    «zones» покраснеет даже при непустом списке ошибок.
    """

    def test_ac1_missing_zones_is_refused_and_named(self):
        errors = check(version=NEW_ZONES_VERSION, zones=None)

        self.assertTrue(
            errors,
            f"guard принял SPEC schema_version {NEW_ZONES_VERSION} без "
            f"поля zones — ожидался отказ (AC-1)")
        combined = " ".join(errors)
        self.assertIn(
            "zones", combined,
            f"отказ guard'а для SPEC schema_version {NEW_ZONES_VERSION} "
            f"без поля zones не называет поле 'zones' по имени (AC-1): "
            f"{errors}")


class NewVersionWithZonesIsAcceptedTest(unittest.TestCase):
    """SPEC новой версии С заполненным полем `zones:` проходит guard без
    единой ошибки — отказ снимается именно заполнением поля, не чем-то
    посторонним.

    Ловит мутацию: guard продолжает отказывать любой SPEC новой версии
    независимо от наличия `zones` (например порог версии поднят, но
    собственно чтение/проверку значения `zones` разработчик не подключил
    к условию, либо оставил старое безусловное «версия не поддерживается»)
    — список ошибок останется непустым даже с заполненным полем.
    """

    def test_ac1_new_version_with_zones_present_passes(self):
        errors = check(version=NEW_ZONES_VERSION, zones="orchestrator/store.py")

        self.assertEqual(
            errors, [],
            f"guard отклонил SPEC schema_version {NEW_ZONES_VERSION} с "
            f"заполненным полем zones (AC-1): {errors}")


if __name__ == "__main__":
    unittest.main()
