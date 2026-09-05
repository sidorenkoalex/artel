"""Приёмочные тесты 01M1NKVPD2A79PQ6K0JVV1B2Q1 — AC-4 (в
`orchestrator/config.py` объявлен именованный список общих зон:
`orchestrator/config.py`, `docs/codebase-map.md`, `tests/`, `roles.yaml`).

Тест ниже проверяет ровно ДЕКЛАРАЦИЮ — существование именованного
контейнера с этими четырьмя путями буквально (та часть AC-4, которую эта
задача, часть 1 нарезки SPEC, реализует и может проверить сама). Вторая
половина AC-4 — «пересечение по путям из этого списка не считается
конфликтом зон ни на одной из проверок ниже» — говорит о проверках
занятости (часть 2, AC-5..AC-10) и сверки диффа (часть 3, AC-11..AC-13),
которых в коде ЭТОЙ задачи нет (`test_scope_markers.py` в этом же
каталоге, пометки AC-5..AC-15); та часть проверяется тестами частей 2/3
(сверка диффа — уже задача 01M1P9QCHPHSCEA6TK13PV85SP, её AC-6: «...не
считается нарушением по AC-1» читает тот же список).

Тест не привязан к конкретному имени константы (SPEC не называет имя
буквально — только состав списка) — ищет ЛЮБОЙ контейнер `orchestrator/
config.py`, несущий все четыре пути, тем же способом, каким `PROTECTED_
PATHS` уже хранит другой такой список (`orchestrator/config.py`,
кортеж строк).

Красен до реализации: `orchestrator/config.py` сегодня не содержит ни
одного контейнера со всеми четырьмя путями (проверено перебором
`vars(config)` — единственное совпадающее по формату `PROTECTED_PATHS`
несёт другой набор путей: `gates.yaml`, `roles.yaml`, `.github/`,
`templates/`, `skills/` — из общего списка зон он делит только
`roles.yaml`) — assertion ниже покраснеет, пока разработчик не заведёт
новый список.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

EXPECTED_COMMON_ZONES = {"orchestrator/config.py", "docs/codebase-map.md",
                         "tests/", "roles.yaml"}


class CommonZonesNamedListExistsTest(unittest.TestCase):
    """`orchestrator/config.py` несёт именованный список/кортеж/множество,
    членами которого являются буквально все четыре ожидаемых пути общих
    зон (AC-4).

    Ловит мутацию: список заведён с опечаткой в одном из путей (например
    `test/` вместо `tests/`), с неполным набором (пропущен `roles.yaml`),
    либо общий список вовсе не заведён отдельно, а нужные пути молча
    вписаны прямо в код проверок частей 2/3 — ни то, ни другое не даёт
    контейнера, для которого `EXPECTED_COMMON_ZONES <= set(value)`.
    """

    def test_ac4_config_declares_a_container_with_all_common_zone_paths(self):
        matches = []
        for name in dir(config):
            if name.startswith("_"):
                continue
            value = getattr(config, name)
            if isinstance(value, (list, tuple, set, frozenset)):
                if EXPECTED_COMMON_ZONES <= set(value):
                    matches.append(name)

        self.assertTrue(
            matches,
            f"orchestrator/config.py не несёт ни одного именованного "
            f"контейнера со всеми путями общих зон {sorted(EXPECTED_COMMON_ZONES)} "
            f"(AC-4)")


if __name__ == "__main__":
    unittest.main()
