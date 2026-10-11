"""AC-3 (tasks/T080/SPEC.md): макет содержит борд задач — канбан-
раскладку, где колонки соответствуют состояниям конечного автомата
задачи (FSM), а не произвольным человеческим статусам.

Красен до реализации: HTML-файлов ещё нет (см. AC-1) — доски искать
негде. Как только появится макет, тест ищет группу из ≥4 разных «веток»
одного контейнера, каждая подписанная каноническим именем состояния FSM
(`orchestrator/fsm.py` / `orchestrator/config.py` — spec_writing,
spec_gate, tests_writing, in_dev, review, acceptance, merge_gate,
escalated, done, killed; НЕ включает `paused` — это флаг, не состояние
FSM, см. `_html_utils.CANONICAL_FSM_STATES`). Такая структурная проверка
(а не просто «слово где-то встречается в тексте») отличает настоящий
канбан от случайного упоминания состояния в карточке или логе.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import unittest  # noqa: E402

import _html_utils as h  # noqa: E402


class BoardColumnsAreFsmStatesTest(unittest.TestCase):

    def test_ac3_board_has_at_least_four_columns_named_after_fsm_states(self):
        files = h.html_files()
        if not files:
            self.fail(
                "в tasks/T080/ нет HTML-файлов макета — проверять AC-3 "
                "не на чем (см. AC-1)")
        found_per_file = {}
        for path in files:
            root = h.parse(path.read_text(encoding="utf-8"))
            labels = h.find_fsm_board(root)
            if labels:
                found_per_file[path.name] = labels
        self.assertTrue(
            found_per_file,
            "не найден борд задач: ни в одном HTML-файле нет группы из "
            "≥4 колонок одного контейнера, каждая подписанная "
            "каноническим именем состояния FSM "
            f"({sorted(h.CANONICAL_FSM_STATES)}) — либо колонки борда "
            "названы человеческими статусами вместо состояний FSM, "
            "либо доски нет вовсе (AC-3)")


if __name__ == "__main__":
    unittest.main()
