"""AC-4 (tasks/T089/SPEC.md): артефакты уже закрытых задач в
`tasks/*/acceptance_tests/` не отредактированы; оставшиеся в них копии
дублей перечислены в артефактах T089 как известный остаток.

Два независимых утверждения критерия — оба проверены:
1. Файлы с оставшимися копиями (в acceptance_tests/ ЗАКРЫТЫХ задач,
   т.е. без локальной git-ветки `task/t<id>-...` — см. докстринг
   `test_ac3_open_tasks_dedup.py`) не входят в дифф этой ветки против
   `main`: правка T089 их не касалась.
2. Каждый такой файл (или его task-id) упомянут текстом хотя бы в одном
   из `tasks/T089/*.md` — «перечислены … как известный остаток» читается
   буквально: остаток назван где-то в артефактах T089, не обязательно в
   заранее заданном месте/формате (SPEC этого не специфицирует).

Красен до реализации: на момент написания этого теста ни `PLAN.md`, ни
`REVIEW.md` T089 ещё не существуют (SPEC.md, единственный сегодняшний
артефакт задачи, остатка не перечисляет — он и не должен, т.к. пишется
раньше, чем разработчик найдёт копии) — часть 2 падает уже сейчас на
всех найденных копиях (T028, T029, T034, T040, T041, T044, T045, T048,
T053, T060, T062, T074 — момент написания теста).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _repo_scan import (acceptance_test_dirs, changed_files, open_task_ids,  # noqa: E402
                        repo_root, resolve_base_ref, scan_definitions,
                        task_id_of)


class ClosedTaskRemainderTest(unittest.TestCase):

    def _remainder(self, root):
        open_ids = open_task_ids(root)
        remainder = []
        for d in acceptance_test_dirs(root):
            tid = task_id_of(d)
            if tid in open_ids:
                continue
            for path, name in scan_definitions(sorted(d.glob("*.py"))):
                remainder.append((tid, str(path.relative_to(root)), name))
        return remainder

    def test_ac4_closed_task_files_with_remainder_are_untouched(self):
        root = repo_root()
        remainder = self._remainder(root)
        base_ref = resolve_base_ref(root)
        changed = set(changed_files(root, base_ref))

        edited = sorted({rel for _, rel, _ in remainder if rel in changed})

        self.assertEqual(
            edited, [],
            "артефакты уже закрытых задач отредактированы вопреки AC-4: "
            f"{edited}")

    def test_ac4_remainder_listed_in_t089_artifacts(self):
        root = repo_root()
        remainder = self._remainder(root)
        if not remainder:
            self.skipTest("нет остатка дублей в закрытых задачах — "
                          "перечислять нечего")

        t089_docs = sorted((root / "tasks" / "T089").glob("*.md"))
        combined = "\n".join(
            p.read_text(encoding="utf-8") for p in t089_docs)

        unmentioned = sorted({
            rel for tid, rel, _ in remainder
            if tid not in combined and rel not in combined
        })

        self.assertEqual(
            unmentioned, [],
            "остаток дублей не упомянут ни в одном из "
            f"{[str(p.relative_to(root)) for p in t089_docs]}: "
            f"{unmentioned}")


if __name__ == "__main__":
    unittest.main()
