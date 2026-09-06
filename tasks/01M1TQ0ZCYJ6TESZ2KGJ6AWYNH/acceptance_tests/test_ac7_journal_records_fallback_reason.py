"""Приёмочный тест AC-7 задачи 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH: `origin`
настроен, но недостижим (fetch падает) — в журнал задачи
(`store.journal`) добавлена запись с причиной вида «артефактная ветка
от локального main: <причина>» (требование 1/AC-2, тестовый пункт 4б).

Решение Оператора по возврату 06.09 (CI красный на `tests/
test_branch_freshness_gate.py::TargetSourcedRemoteTest`): запись в
журнал пишется, только когда remote `origin` СУЩЕСТВУЕТ, а сам `fetch`
не удался — песочница вовсе БЕЗ `origin` (как было в этом файле до
правки) молча остаётся на локальном `main`, без записи (тот же случай,
что `test_ac2_local_main_fallback_parent.py`, где запись не
проверяется). Без этого разделения ЛЮБОЙ вызов `commit_files` первым
коммитом в репозитории без `origin` (в т.ч. лёгкие тестовые песочницы
`fake_git`, где `git remote` тоже пуст) писал бы в журнал — включая
`cmd_new` в `tests/test_branch_freshness_gate.py`, что и красило CI.
"""
import shutil
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
        """`origin` заведён (`add_origin`), но его bare-репозиторий
        уничтожен ДО коммита — `git fetch origin main` обязан упасть.
        После первого коммита артефактной ветки задачи `TASK` журнал
        задачи (`store.task_steps`) содержит запись, чей `detail`
        начинается с «артефактная ветка от локального main:» и несёт
        непустую причину после двоеточия.

        Ловит мутацию: фолбэк на локальный `main` работает (коммит
        создаётся), но запись в журнал не пишется, либо пишется без
        текста причины (пустая строка после «:») — тест ловит и
        отсутствие записи, и пустую причину.
        """
        self.add_origin()
        shutil.rmtree(self.bare, ignore_errors=True)

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
