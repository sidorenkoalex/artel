"""Юнит-тесты уборки хвостов поделённого родителя на гейте SPEC
(01M3EM7EFQ4X4CAYMNG35P9D7Y, требования 1-3, 7).

Git настоящий (`tests.sandbox.RealGitSandbox`): предмет проверки — что
именно ответит git на `worktree remove`/`branch -d` и что после этого
останется в списке локальных веток; заглушкой `gitcmd.git` это не
изобразить.

Топология родителя повторяет два висящих родителя из «Контекста» SPEC:
кодовая ветка заведена `workspace.ensure` (то же первое действие шага
разработчика) и собственных коммитов не получила — работа шла в
артефактной ветке пульта, — то есть формально влита в main.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (artifact_branch, config, fsm, gitcmd,  # noqa: E402
                          store, workspace)
from tests.sandbox import RealGitSandbox, capture  # noqa: E402

PARENT = "T953DIVIDEDPARENT"
PARENT_TITLE = "Родитель, поделённый на гейте SPEC"
PARENT_BRANCH = "task/t953dividedparent-delenie"
# Вымышленный путь, не пересекающийся ни с одним модулем пульта: сверка
# путей SPEC с `zones:` на входе approve (`guard.spec_unclassified_paths`)
# обязана пройти, иначе деление до уборки не доходит вовсе.
ZONE = "orchestrator/t953_zone.py"

SPEC_TEXT = f"""---
task: {PARENT}
type: spec
author_role: analyst
status: ready
schema_version: 1
budget_usd: 15
zones: {ZONE}
---

# SPEC: {PARENT_TITLE}

## Контекст
Фикстура юнит-теста уборки при делении — короткий безобидный текст.

## Требования
1. Первое требование фикстуры.

## Критерии приёмки
AC-1. Первый критерий фикстуры.

## Деление

### Первая часть фикстуры

Зоны: {ZONE}
Порядок: первая, без зависимостей

Текст ТЗ первой части.

### Вторая часть фикстуры

Зоны: {ZONE}
Порядок: после части 1

Текст ТЗ второй части.

## Не входит
- Всё остальное.
"""

GIT_REFUSAL = "fatal: фикстура T953 — git отказал в удалении ветки"


def failing_branch_delete(real_git):
    """Подмена `gitcmd.git`, в которой отказывает ТОЛЬКО удаление ветки —
    узко на `-d`/`-D`, а не на всю подкоманду `branch`: `git branch
    --merged` в том же проходе решает, влита ветка или нет, и его подмена
    подменила бы предмет соседнего требования, а не сбой уборки."""
    import subprocess

    def flaky(*args: str):
        if args and args[0] == "branch" and ("-d" in args or "-D" in args):
            return subprocess.CompletedProcess(args, 128, "", GIT_REFUSAL)
        return real_git(*args)

    return flaky


class DivisionParentCleanupTest(RealGitSandbox):
    """Родитель на `spec_gate` с секцией «## Деление», кодовой веткой и
    worktree; `approve` подтверждает гейт зафиксированным sha."""

    def setUp(self):
        super().setUp()
        # `workspace.ensure` для НОВОЙ ветки делает `git fetch origin
        # <MAIN_BRANCH>` (SPEC 01M297HFSKV3GVZJ9YF20FZEZE) и без
        # настоящего origin именованно отказывается заводить worktree.
        self.add_synced_origin()
        store.insert_task(store.db(), PARENT, PARENT_TITLE, "spec_writing",
                          PARENT_BRANCH, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        artifact_branch.commit_files(
            PARENT, {f"tasks/{PARENT}/SPEC.md": SPEC_TEXT},
            f"{PARENT}: SPEC готов")
        capture(fsm.cmd_advance, PARENT)
        wt_path, error = workspace.ensure(PARENT, PARENT_BRANCH)
        self.assertIsNone(error, f"worktree родителя не заведён: {error}")
        self.wt_path = wt_path
        self.sha = store.get_task(store.db(), PARENT)["fixed_sha"]

    # ------------------------------------------------------------ утилиты

    def branches(self) -> list[str]:
        return self.git("branch", "--format=%(refname:short)").split()

    def subtask_ids(self) -> list[str]:
        return sorted(row["id"] for row in store.all_tasks(store.db())
                      if row["parent_task_id"] == PARENT)

    def steps(self) -> list:
        return store.task_steps(store.db(), PARENT)

    def cleanup_notes(self) -> list[str]:
        return [r["detail"] or "" for r in self.steps()
                if r["action"] == "уборка"]

    def journal_text(self) -> str:
        return "\n".join(f"{r['action']} | {r['detail'] or ''}"
                         for r in self.steps())

    # ------------------------------------------------------------ сценарии

    def test_division_removes_parent_worktree_and_branch(self):
        """Требование 1: деление доводит родителя до `killed` «поделена
        на: …» и тем же переходом снимает его worktree и кодовую ветку.

        Ловит мутацию: вызов уборки из `_spawn_division_subtasks` убран
        (сегодняшнее поведение до задачи) или поставлен ДО
        `workspace.remove` — `git branch -d` откажет, пока ветку держит
        worktree, и ветка останется среди локальных.
        """
        capture(fsm.cmd_approve, PARENT, self.sha)

        self.assertEqual(2, len(self.subtask_ids()),
                         f"подзадачи не заведены: {self.subtask_ids()}")
        self.assertEqual("killed",
                         store.get_task(store.db(), PARENT)["state"])
        self.assertNotIn(PARENT_BRANCH, self.branches(),
                         f"кодовая ветка родителя осталась: "
                         f"{self.branches()}")
        self.assertFalse(self.wt_path.exists(),
                         f"каталог worktree родителя остался: {self.wt_path}")

    def test_division_cleanup_names_the_empty_branch_as_merged(self):
        """Требования 1, 5: запись «уборка» родителя перечисляет хвосты и
        называет пустую ветку влитой — она и есть тот исход, ради
        которого требование 4 сняло прежнее «оставлена: смержена».

        Ловит мутацию: уборка при делении сделана прямыми вызовами
        `workspace.remove`/`drop_task_branch` мимо `cleanup_killed_task`
        — диск и git приходят в порядок, а записи журнала нет; либо
        пустая ветка снимается как «неслитая» (флаг `-D` безусловно),
        и по журналу уже не отличить снятый указатель на историю main от
        снесённой несохранённой работы.
        """
        capture(fsm.cmd_approve, PARENT, self.sha)

        notes = self.cleanup_notes()
        self.assertEqual(1, len(notes),
                         f"записей «уборка» не ровно одна: "
                         f"{self.journal_text()}")
        self.assertIn(f"убран worktree {self.wt_path}", notes[0])
        self.assertIn(f"tasks/{PARENT}/", notes[0])
        self.assertIn(f"удалена влитая ветка {PARENT_BRANCH}", notes[0])

    def test_division_keeps_the_artifact_branch_of_the_parent(self):
        """Требование 3: артефактная ветка родителя и её SPEC.md с
        разделом «## Деление» переживают уборку нетронутыми — из этого
        раздела нарезаны части, и он остаётся историей деления.

        Ловит мутацию: уборка сделана полным путём kill
        (`cleanup._cmd_kill`) вместо `cleanup_killed_task` — по дороге
        публикуется снапшот закрытия и локальная артефактная ветка
        удаляется (`snapshot.publish_and_cleanup`).
        """
        artifact = artifact_branch.branch_name(PARENT)
        head_before = gitcmd.branch_head_sha(artifact)
        self.assertTrue(head_before, "предусловие: артефактная ветка есть")

        capture(fsm.cmd_approve, PARENT, self.sha)

        self.assertEqual(head_before, gitcmd.branch_head_sha(artifact),
                         "голова артефактной ветки родителя сдвинулась")
        text, _ = gitcmd.show(artifact, f"tasks/{PARENT}/SPEC.md")
        self.assertIn("## Деление", text or "")

    def test_cleanup_failure_does_not_cancel_the_division(self):
        """Требование 2: git отказал в удалении ветки — деление всё равно
        состоялось, а причина отказа осела в журнале родителя.

        Ловит мутацию: уборка вызвана без обработки сбоя — `approve`
        падает уже ПОСЛЕ заведения подзадач и перевода родителя в
        `killed`, то есть деление остаётся сделанным наполовину. Тот же
        ассерт ловит обратную мутацию — сбой проглочен молча, без
        причины в журнале.
        """
        real_git = gitcmd.git

        with mock.patch.object(gitcmd, "git", failing_branch_delete(real_git)):
            capture(fsm.cmd_approve, PARENT, self.sha)

        self.assertEqual(2, len(self.subtask_ids()),
                         f"сбой уборки отменил подзадачи: "
                         f"{self.subtask_ids()}")
        self.assertEqual("killed",
                         store.get_task(store.db(), PARENT)["state"])
        self.assertIn("поделена на:", self.journal_text())
        joined = " | ".join(self.cleanup_notes())
        self.assertIn(GIT_REFUSAL, joined,
                      f"запись «уборка» не называет причину отказа git: "
                      f"{joined!r}")
        self.assertIn(PARENT_BRANCH, joined)

    def test_cleanup_exception_is_journalled_not_raised(self):
        """Требование 2, вторая половина: даже НЕОЖИДАННОЕ исключение
        внутри уборки (не штатный отказ git, который `cleanup_killed_task`
        сам превращает в строку) не выходит наружу и оседает записью
        «уборка».

        Ловит мутацию: `try/except` вокруг `cleanup_killed_task` в
        `fsm._cleanup_divided_parent` снят или сужен до конкретного типа
        (например, только `OSError`) — `approve` падает наружу с
        заведёнными подзадачами и родителем в `killed`.
        """
        from orchestrator import cleanup

        boom = RuntimeError("уборка сломалась неожиданно")
        with mock.patch.object(cleanup, "cleanup_killed_task",
                               side_effect=boom):
            capture(fsm.cmd_approve, PARENT, self.sha)

        self.assertEqual(2, len(self.subtask_ids()))
        self.assertEqual("killed",
                         store.get_task(store.db(), PARENT)["state"])
        self.assertIn("уборка сломалась неожиданно",
                      " | ".join(self.cleanup_notes()))


if __name__ == "__main__":
    unittest.main()
