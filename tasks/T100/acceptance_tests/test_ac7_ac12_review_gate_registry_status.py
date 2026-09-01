"""Приёмочные тесты T100 — машинный гейт `review -> acceptance` (через
`verifying`) по статусам записей реестра замечаний (tasks/T100/SPEC.md,
AC-7..AC-12).

Чёрный ящик над `orchestrator.fsm.cmd_advance` — песочница
`tests.test_invariants.FsmTest` (git и `gh` заглушены, БД и артефакты во
временном каталоге), тем же приёмом, что `tasks/T079/acceptance_tests/
test_ac4_review_to_verifying.py`. Сегодня (до T079) `review -> approved`
шёл напрямую в `acceptance`; после T079 — в `verifying` (проверка CI),
`acceptance` наступает позже. SPEC этой задачи называет проверяемую точку
буквально: «код в orchestrator/fsm_advance.py::review() (ветка status ==
"approved"), до перехода в verifying» (требование 5) — поэтому здесь
проверяется тот же самый переход `review -> verifying`, а не литеральное
состояние `acceptance`.

`scripts.guard.SUPPORTED_SCHEMA_VERSION` подменяется на 3 на время каждого
теста этого файла. Без подмены REVIEW.md со `schema_version: 3` отклонялся
бы guard'ом ещё ДО гейта требования 5 как «версия схемы новее
поддерживаемой» (требование 6 этой же задачи, сегодня SUPPORTED_SCHEMA_
VERSION == 2) — переход бы не происходил по совершенно другой причине,
пряча отсутствие самого гейта. Подмена изолирует именно предмет этого
файла (требование 5) от требования 6 и от структурных проверок раздела
(требования 1, 7 — AC-1..AC-6, отдельный файл test_ac1_ac6_guard_registry_
structure.py, здесь не переисполняется). Формат записи реестра — та же
markdown-таблица, тем же обоснованием, что в test_ac1_ac6_guard_registry_
structure.py.

Красен до реализации: AC-7, AC-8, AC-9, AC-10 (test_ac7_*, test_ac8_*,
test_ac9_*, test_ac10_*) падают, потому что `orchestrator/fsm_advance.py::
review()` сегодня вообще не читает раздел «Реестр замечаний» — ветка
`status == "approved"` только гоняет `acceptance.run` и без единой
проверки статусов записей переводит задачу в `verifying`. Как только
разработчик добавит гейт требования 5, эти тесты позеленеют без
изменения фикстур.

Зелёный с рождения: AC-11 (реестр закрыт — все записи `accepted`, либо
записей нет вовсе) уже сегодня, без всякого гейта, доходит до
`verifying` — тест фиксирует, что будущий гейт требования 5 не имеет
права ложно блокировать закрытый реестр. AC-12 (REVIEW.md со
`schema_version` ниже 3 — registry-проверки требования 5 на него не
распространяются, SPEC требование 6) — это тот же самый переход, что уже
проверяет `tasks/T079/acceptance_tests/test_ac4_review_to_verifying.py`
для REVIEW.md текущего формата, T100 его не трогает вовсе.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from tests.test_invariants import FsmTest  # noqa: E402
from orchestrator import fsm, store  # noqa: E402
from scripts import guard  # noqa: E402

REGISTRY_REVIEW = """---
task: {task}
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 3
---

# REVIEW: гейт реестра замечаний

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


def registry_row(record_id: str, status: str) -> str:
    return (f"| {record_id} | {status} | scripts/guard.py:120 | "
            f"замечание ревью | approved проходит без валидации "
            f"реестра | закрыть запись {record_id} |")


class RegistryGateTest(FsmTest):
    """Общая песочница: REVIEW.md со schema_version: 3 в state == review,
    свежая итерация (reviewed_iter=0 < iteration=1)."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(guard, "SUPPORTED_SCHEMA_VERSION", 3)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.set_state("review", reviewed_iter=0)

    def write_registry_review(self, rows: list[str]) -> None:
        text = REGISTRY_REVIEW.format(task=self.TASK, rows="\n".join(rows))
        (self.tdir / "REVIEW.md").write_text(text, encoding="utf-8")

    def advance(self) -> str:
        return self.capture(fsm.cmd_advance, self.TASK)

    def journal_text(self) -> str:
        rows = store.db().execute(
            "SELECT detail FROM steps WHERE task_id=?", (self.TASK,)
        ).fetchall()
        return " ".join(r["detail"] or "" for r in rows)


class OpenRecordBlocksTransitionTest(RegistryGateTest):
    """AC-7: запись со статусом `open` отклоняет переход, отказ называет
    её id."""

    def test_ac7_open_record_blocks_transition_and_names_its_id(self):
        self.write_registry_review([registry_row("R1-F1", "open")])

        out = self.advance()

        self.assertNotEqual(
            self.state(), "verifying",
            "запись реестра со статусом open не должна пропускать "
            "review -> verifying (SPEC AC-7)")
        self.assertIn(
            "R1-F1", out + self.journal_text(),
            "отказ обязан называть id незакрытой записи (SPEC AC-7) — "
            "'R1-F1' не встречается ни в выводе, ни в журнале")


class FixedRecordAloneBlocksTransitionTest(RegistryGateTest):
    """AC-8: запись со статусом `fixed` без последующего перевода в
    `accepted` отклоняет переход — `fixed` сам по себе не закрывает
    замечание."""

    def test_ac8_fixed_without_accepted_blocks_transition(self):
        self.write_registry_review([registry_row("R1-F1", "fixed")])

        self.advance()

        self.assertNotEqual(
            self.state(), "verifying",
            "запись реестра со статусом fixed (без accepted) не "
            "должна пропускать review -> verifying (SPEC AC-8)")


class RejectedRecordAloneBlocksTransitionTest(RegistryGateTest):
    """AC-9: запись со статусом `rejected` без последующего перевода в
    `accepted` отклоняет переход — симметрия с AC-8 (ANSWER-1)."""

    def test_ac9_rejected_without_accepted_blocks_transition(self):
        self.write_registry_review([registry_row("R1-F1", "rejected")])

        self.advance()

        self.assertNotEqual(
            self.state(), "verifying",
            "запись реестра со статусом rejected (без accepted) не "
            "должна пропускать review -> verifying (SPEC AC-9)")


class NeedsWorkRecordBlocksTransitionTest(RegistryGateTest):
    """AC-10: запись со статусом `needs_work` отклоняет переход."""

    def test_ac10_needs_work_record_blocks_transition(self):
        self.write_registry_review([registry_row("R1-F1", "needs_work")])

        self.advance()

        self.assertNotEqual(
            self.state(), "verifying",
            "запись реестра со статусом needs_work не должна "
            "пропускать review -> verifying (SPEC AC-10)")


class ClosedRegistryAllowsTransitionTest(RegistryGateTest):
    """AC-11: переход проходит, если все записи реестра — `accepted`,
    либо записей в реестре нет вовсе (при прочих условиях перехода
    неизменных: approved, свежий вердикт, зелёные acceptance_tests —
    в этой песочнице acceptance_tests/ у задачи нет, `acceptance.run`
    тривиально зелёный)."""

    def test_ac11_all_accepted_records_allow_transition(self):
        self.write_registry_review([registry_row("R1-F1", "accepted")])

        self.advance()

        self.assertEqual(
            self.state(), "verifying",
            "реестр с единственной accepted-записью не пропустил "
            "review -> verifying (SPEC AC-11)")

    def test_ac11_empty_registry_allows_transition(self):
        self.write_registry_review([])

        self.advance()

        self.assertEqual(
            self.state(), "verifying",
            "реестр без единой записи не пропустил review -> "
            "verifying (SPEC AC-11)")


class LegacySchemaVersionUnaffectedTest(FsmTest):
    """AC-12: переход `review -> acceptance` для REVIEW.md со
    schema_version < 3 (или без поля) не подвергается проверкам AC-7..
    AC-11 — ведёт себя как до этой задачи."""

    def test_ac12_schema_version_1_transition_unaffected_by_registry_gate(self):
        self.write_review("approved", 1)
        self.set_state("review", reviewed_iter=0)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "verifying",
            "REVIEW.md со schema_version: 1 (прежний формат) обязан "
            "дойти до verifying так же, как до этой задачи (SPEC "
            "AC-12) — registry-гейт требования 5 на него не "
            "распространяется")

    def test_ac12_missing_schema_version_field_unaffected_by_registry_gate(self):
        text = ("---\n"
                f"task: {self.TASK}\n"
                "type: review\n"
                "author_role: reviewer\n"
                "status: approved\n"
                "iteration: 1\n"
                "---\n\n"
                "# REVIEW: без schema_version\n\n"
                "## Соответствие SPEC\n\n"
                "## Замечания\n\n"
                "## Вердикт\n"
                "approved\n\n"
                "## Проверено исполнением\n"
                "`python3 -m unittest discover -s tests` — зелёный.\n")
        (self.tdir / "REVIEW.md").write_text(text, encoding="utf-8")
        self.set_state("review", reviewed_iter=0)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "verifying",
            "REVIEW.md без поля schema_version обязан дойти до "
            "verifying так же, как до этой задачи (SPEC AC-12) — "
            "registry-гейт требования 5 на него не распространяется")


if __name__ == "__main__":
    unittest.main()
