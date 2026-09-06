"""Приёмочный тест AC-7 задачи 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH: песочница без
`origin` — в журнал задачи (`store.journal`) добавлена запись с
причиной вида «артефактная ветка от локального main: <причина>»
(требование 1/AC-2, тестовый пункт 4б).

Красен до реализации: `artifact_branch.commit_files`
(`orchestrator/artifact_branch.py`) сегодня НЕ пишет ни одной записи в
`store.journal` вовсе — модуль даже не импортирует `store`. Журнал
задачи `TASK` после вызова остаётся пуст, тест ждёт запись с текстом
причины — несовпадение (пустой список против непустого) красит тест
до появления кода журналирования.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import artifact_branch, store  # noqa: E402
from _sandbox import ArtifactBranchOriginSandbox  # noqa: E402

TASK = "01ACJOURNALREASON03"
REASON_PREFIX = "артефактная ветка от локального main:"


class JournalRecordsFallbackReasonTest(ArtifactBranchOriginSandbox):

    def test_ac7_journal_contains_local_main_fallback_reason(self):
        """Песочница без `origin`: после первого коммита артефактной
        ветки задачи `TASK` журнал задачи (`store.task_steps`) содержит
        запись, чей `detail` начинается с «артефактная ветка от
        локального main:» и несёт непустую причину после двоеточия.

        Ловит мутацию: фолбэк на локальный `main` работает (коммит
        создаётся), но запись в журнал не пишется, либо пишется без
        текста причины (пустая строка после «:») — тест ловит и
        отсутствие записи, и пустую причину.
        """
        sha = artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/SPEC.md": "спек"}, f"{TASK}: тест")
        self.assertTrue(sha, "коммит артефактной ветки не создан")

        steps = store.task_steps(store.db(), TASK)
        matching = [s for s in steps
                   if (s["detail"] or "").startswith(REASON_PREFIX)]

        self.assertTrue(matching,
                        f"в журнале задачи {TASK} нет записи с причиной "
                        f"вида {REASON_PREFIX!r}")
        reason = matching[0]["detail"][len(REASON_PREFIX):].strip()
        self.assertTrue(reason, "причина фолбэка не должна быть пустой")


if __name__ == "__main__":
    unittest.main()
