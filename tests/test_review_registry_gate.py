"""Юнит-тесты гейта «Реестр замечаний» в `orchestrator/fsm_advance.py::
review()` (SPEC T100, требование 5), дополняют чёрный ящик
`tasks/T100/acceptance_tests/test_ac7_ac12_review_gate_registry_status.py`
случаями, которых там нет: несколько незакрытых записей разом (все id
обязаны быть названы, не только первая) и молчание гейта, когда
`registry_records` пуст, но секция физически присутствует.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import fsm, store  # noqa: E402
from scripts import guard  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402

REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 3
---

# REVIEW: гейт реестра — юнит-тесты

## Соответствие SPEC

## Замечания

## Реестр замечаний
| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
{rows}

## Вердикт
approved

## Проверено исполнением
`python3 -m unittest discover -s tests` — зелёный.
"""


def row(record_id: str, status: str) -> str:
    return (f"| {record_id} | {status} | a.py:1 | суть | последствие | "
            f"решение {record_id} |")


class RegistryGateUnitTest(FsmTest):

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(guard, "SUPPORTED_SCHEMA_VERSION", 3)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.set_state("review", reviewed_iter=0)

    def write(self, rows: list[str]) -> None:
        (self.tdir / "REVIEW.md").write_text(
            REVIEW_MD.format(task=self.TASK, rows="\n".join(rows)),
            encoding="utf-8")

    def journal_text(self) -> str:
        rows = store.db().execute(
            "SELECT detail FROM steps WHERE task_id=?", (self.TASK,)
        ).fetchall()
        return " ".join(r["detail"] or "" for r in rows)


class AllUnresolvedIdsAreNamedTest(RegistryGateUnitTest):
    """Незакрытых записей несколько — отказ обязан назвать КАЖДУЮ, не
    только первую попавшуюся (иначе разработчик чинит по одной и снова
    натыкается на гейт)."""

    def test_every_unresolved_id_appears_in_the_refusal(self):
        self.write([row("R1-F1", "open"), row("R1-F2", "fixed"),
                   row("R1-F3", "accepted")])

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertNotEqual(self.state(), "acceptance")
        blob = out + self.journal_text()
        self.assertIn("R1-F1", blob)
        self.assertIn("R1-F2", blob)


class GateSilentWhenNoRecordsTest(RegistryGateUnitTest):
    """Секция «Реестр замечаний» физически на месте (шапка таблицы), но
    строк данных нет вовсе — гейт не имеет права требовать закрытия
    несуществующих записей (симметрично AC-11 из приёмочных тестов,
    здесь — через прямой вызов `guard.requires_registry`/
    `registry_records`, не только `cmd_advance`)."""

    def test_requires_registry_true_and_records_empty_does_not_block(self):
        self.write([])
        meta = {"schema_version": 3}

        self.assertTrue(guard.requires_registry(meta))
        self.assertEqual(
            guard.registry_records((self.tdir / "REVIEW.md").read_text()),
            [])

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "acceptance")


if __name__ == "__main__":
    unittest.main()
