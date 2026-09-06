"""Задача 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH — критерии о том, что явно НЕ
меняется этой задачей: AC-3 (внешний target — без отдельного кода),
AC-4 (повторный коммит в уже существующую артефактную ветку) и AC-8
(регрессия существующих тестов).

# AC-3: skip — сам SPEC формулирует критерий как констатацию
существующей архитектуры («артефактная ветка любого target коммитится
в config.ROOT»), явно НЕ как отдельный тестируемый критерий («а не как
новый критерий с отдельным тестом», раздел «Критерии приёмки» AC-3;
то же в разделе «Не входит»/ANSWER-1). Родитель для внешнего target
выбирается ТЕМ ЖЕ кодом, что и в AC-1/AC-2 — уже покрыт тестами
`test_ac1_ac6_first_commit_parent_from_origin.py`/
`test_ac2_local_main_fallback_parent.py`, дублирующий тест здесь не
добавляет нового сигнала.

# AC-8: ci — критерий про существующие `tests/test_artifact_branch*.py`
и `tests/test_catalog*.py`, остающиеся зелёными в CI кодовой ветки:
регрессия существующего набора — забота автогейта зелёного CI
(orchestrator/fsm_autogate.py), не отдельного acceptance-теста
(`tests/test_artifact_branch*.py` на момент написания планки не
существует вовсе — глобу нечего ловить; `tests/test_catalog_status_
log.py`/`tests/test_catalog_new_race.py` гоняет полный прогон `tests/`
в CI на каждый пуш кодовой ветки).

Зелёный с рождения (AC-4): повторный коммит в артефактную ветку, уже
существующую (`gitcmd.branch_head_sha(branch)` возвращает непустое
значение), сегодня уже берёт родителя из ГОЛОВЫ ЭТОЙ ветки
(`orchestrator/artifact_branch.py:118`, короткое замыкание `or` до
любого обращения к main/origin) — origin-фетч требования 1 применяется
только когда ветки ЕЩЁ нет; этот путь код не трогает, тест лишь
фиксирует сохранение текущего поведения как планку.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import artifact_branch  # noqa: E402
from _sandbox import ArtifactBranchOriginSandbox  # noqa: E402

TASK = "01ACREPEATCOMMIT04"


class RepeatCommitParentUnchangedTest(ArtifactBranchOriginSandbox):

    def test_ac4_repeat_commit_parent_is_existing_branch_head(self):
        """Артефактная ветка задачи `TASK` уже существует (первый
        коммит сделан офлайн, без `origin`); затем появляется `origin`
        и уходит вперёд ещё на один коммит. Второй коммит в ту же
        ветку обязан взять родителем ГОЛОВУ ВЕТКИ (первый коммит), а не
        свежую голову origin/main — поведение с `parent` при повторных
        коммитах требование 1 не меняет.

        Ловит мутацию: код требования 1 применяется БЕЗУСЛОВНО (всегда
        предпочитает origin/main, даже когда `branch_head_sha(branch)`
        уже непусто) — второй коммит получит родителем свежую голову
        origin/main вместо головы собственной ветки, тест ловит это
        сравнением sha родителя.
        """
        first_sha = artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/SPEC.md": "спек v1"}, f"{TASK}: v1")
        self.assertTrue(first_sha, "первый коммит артефактной ветки не создан")

        self.add_origin()
        self.advance_origin_main(
            {"tasks/01ACREPEATCOMMIT_OTHER/marker.txt": "чужой origin-коммит\n"})

        second_sha = artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/SPEC.md": "спек v2"}, f"{TASK}: v2")

        self.assertTrue(second_sha, "второй коммит артефактной ветки не создан")
        self.assertEqual(self.commit_parent_sha(second_sha), first_sha)


if __name__ == "__main__":
    unittest.main()
