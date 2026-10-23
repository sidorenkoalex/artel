"""Задача не трогает код записи `observations` и существующие тесты наблюдения.

Группа: разовый
Зелёный с рождения: критерий требует неизменности файлов относительно main — до правок задачи дифф ветки их не содержит; тест краснеет, только если реализация их тронет.

Пути задачи берутся помощником пульта `changed_paths()` (закоммиченный
дифф от базы ветки плюс неотслеживаемые файлы) — тем же правилом, что
гейт зон.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import changed_paths  # noqa: E402

UNTOUCHED = (
    "orchestrator/store.py",
    "tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py",
    "tests/test_observation_edges.py",
    "tests/test_observation_acceptance_return.py",
    "tests/test_cycle_hint.py",
)


class UntouchedFilesTest(unittest.TestCase):

    def test_ac7_store_and_existing_observation_tests_match_main(self):
        """Дифф ветки задачи не содержит `orchestrator/store.py` и четырёх тестов наблюдения.

        Код записи `last_seen_at`/`started_at`/`created_at` в `observations`
        живёт в `orchestrator/store.py`: файл не изменён — формат записи и
        её код прежние. Файлы `tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py`,
        `tests/test_observation_edges.py`,
        `tests/test_observation_acceptance_return.py`, `tests/test_cycle_hint.py`
        на ветке совпадают с main (их нет среди путей задачи).

        Ловит мутацию: разработчик меняет формат `last_seen_at` в
        `store.py` (например, `strftime` вместо `isoformat`) или правит
        существующий тест наблюдения под новый код — путь появляется в
        `changed_paths()`.
        """
        changed = set(changed_paths())
        for path in UNTOUCHED:
            with self.subTest(path=path):
                self.assertNotIn(path, changed, f"{path} изменён на ветке задачи")


if __name__ == "__main__":
    unittest.main()
