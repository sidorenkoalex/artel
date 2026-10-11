"""AC-6 (tasks/T080/SPEC.md): макет содержит очередь гейтов Оператора с
записями для spec_gate и merge_gate, у каждой записи — кнопки approve и
reject.

Красен до реализации: HTML-файлов ещё нет (см. AC-1) — очередь гейтов
искать негде. Как только появится макет, тест по отдельности ищет для
`spec_gate` и для `merge_gate` (имена — буквально из `gates.yaml:12-24`
и `orchestrator/fsm.py`, не `review_gate`, которого в коде нет) самый
маленький узел документа, в котором ЭТО имя гейта соседствует с обеими
метками approve и reject.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import unittest  # noqa: E402

import _html_utils as h  # noqa: E402

APPROVE_RE = re.compile(r"\bapprove\b|одобрить|утвердить", re.I)
REJECT_RE = re.compile(r"\breject\b|отклонить|отказать", re.I)

GATE_NAMES = ("spec_gate", "merge_gate")


def _gate_entry_predicate(gate_name):
    gate_re = re.compile(re.escape(gate_name), re.I)

    def predicate(text):
        return bool(
            gate_re.search(text)
            and APPROVE_RE.search(text)
            and REJECT_RE.search(text))
    return predicate


class GatesQueueApproveRejectTest(unittest.TestCase):

    def test_ac6_spec_gate_and_merge_gate_entries_have_approve_reject(self):
        files = h.html_files()
        if not files:
            self.fail(
                "в tasks/T080/ нет HTML-файлов макета — проверять AC-6 "
                "не на чем (см. AC-1)")
        missing = []
        for gate_name in GATE_NAMES:
            predicate = _gate_entry_predicate(gate_name)
            found = False
            for path in files:
                root = h.parse(path.read_text(encoding="utf-8"))
                node = h.smallest_matching(root, predicate)
                if node is not None:
                    found = True
                    break
            if not found:
                missing.append(gate_name)
        self.assertFalse(
            missing,
            "в очереди гейтов не найдена запись(и) с кнопками approve и "
            f"reject рядом с именем гейта: {missing} (AC-6 — очередь "
            "гейтов Оператора должна показывать spec_gate и merge_gate, "
            "у каждого — approve/reject)")


if __name__ == "__main__":
    unittest.main()
