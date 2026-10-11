"""Приёмочные тесты T083 — AC-4 (SPEC.md, «Критерии приёмки»):

Поведение боевого кода (`orchestrator/`, `scripts/`) не изменено — правки
задачи ограничены `tests/`.

Зелёный с рождения: на момент написания этих приёмочных тестов дифф ветки
задачи против `main` (`git diff --name-only $(git merge-base main HEAD)
HEAD`) касается только `tasks/T083/{SPEC.md,TZ.md}` — `orchestrator/` и
`scripts/` не тронуты. Это ожидаемо: разработчик ещё не приступал. Тест
проверяет РЕГРЕССИЮ на будущее — любой коммит разработчика, который
затронет `orchestrator/` или `scripts/`, должен покрасить именно этот
тест, а не остаться незамеченным («Не входит» SPEC: «Правки orchestrator/
и scripts/ — граница ТЗ строго tests/»).

Механическая проверка списком путей, не семантика диффа — в отличие от
`tasks/T037/acceptance_tests/test_manual_criteria.py` AC-6 («в диффе нет
изменённых ассертов») критерий здесь не требует понимания смысла правки,
только то, В КАКИХ ДИРЕКТОРИЯХ она лежит — это укладывается в unittest
без ручной сверки ревьювером.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402


class ProdCodeUntouchedSinceMainTest(unittest.TestCase):
    """AC-4."""

    def test_ac4_orchestrator_and_scripts_have_no_diff_against_main(self):
        base = subprocess.run(
            ["git", "merge-base", config.MAIN_BRANCH, "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()

        diff = subprocess.run(
            ["git", "diff", "--name-only", base, "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        changed = [line for line in diff.stdout.splitlines() if line.strip()]

        offenders = [f for f in changed
                    if f.startswith("orchestrator/") or f.startswith("scripts/")]

        self.assertEqual(
            offenders, [],
            "боевой код изменён вне границы ТЗ «строго tests/» (AC-4): "
            f"{offenders}")


if __name__ == "__main__":
    unittest.main()
