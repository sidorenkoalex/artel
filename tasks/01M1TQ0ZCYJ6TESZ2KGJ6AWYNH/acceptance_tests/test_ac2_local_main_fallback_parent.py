"""Приёмочный тест AC-2 задачи 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH: без `origin`
(сеть недоступна/`origin` не настроен/песочница) родитель первого
коммита артефактной ветки остаётся ГОЛОВА локального `main` — текущее
поведение, требование 1 его не меняет для этого случая.

Зелёный с рождения: без `origin` `artifact_branch.commit_files`
(`orchestrator/artifact_branch.py:118-119`) уже сегодня падает на
`gitcmd.branch_head_sha(config.MAIN_BRANCH)` как единственный
доступный источник родителя — именно то значение, которое требует этот
тест. Требование 1 добавляет ПРЕДПОЧТЕНИЕ origin, когда он доступен
(AC-1/AC-6, отдельный файл), но явно оставляет офлайн-фолбэк как есть
— этот тест фиксирует сохранение текущего поведения как планку, а не
описывает новый код (запись в журнал причины фолбэка — отдельный
критерий AC-7, отдельный файл, действительно красный до реализации).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import artifact_branch  # noqa: E402
from _sandbox import ArtifactBranchOriginSandbox  # noqa: E402

TASK = "01ACLOCALFALLBACK02"


class NoOriginFallsBackToLocalMainTest(ArtifactBranchOriginSandbox):

    def test_ac2_no_origin_falls_back_to_local_main_parent(self):
        """Песочница без `origin` вовсе (никогда не настраивался):
        родитель первого коммита новой артефактной ветки — sha головы
        локального `main`.

        Ловит мутацию: код при отсутствующем `origin` возвращает пустой
        родитель/падает вместо фолбэка на локальный `main` — коммит не
        создастся или получит родителем что-то иное, тест ловит
        сравнением sha с `local_main_head()`.
        """
        pin_head = self.local_main_head()

        sha = artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/SPEC.md": "спек"}, f"{TASK}: тест")

        self.assertTrue(sha, "коммит артефактной ветки не создан")
        self.assertEqual(self.commit_parent_sha(sha), pin_head)


if __name__ == "__main__":
    unittest.main()
