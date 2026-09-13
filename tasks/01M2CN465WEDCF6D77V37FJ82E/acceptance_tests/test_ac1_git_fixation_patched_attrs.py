"""AC-1 — 01M2CN465WEDCF6D77V37FJ82E: `_GitFixationTmpRootTest.
PATCHED_ATTRS` несёт `WORKTREES` и `BACKUP_MARKER`.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. `tests/test_git_fixation.py:159` — `_GitFixationTmpRootTest.
PATCHED_ATTRS` содержит `WORKTREES` и `BACKUP_MARKER`.

Красен до реализации: сегодня `_GitFixationTmpRootTest.PATCHED_ATTRS` =
`("ROOT", "DB", "TASKS", "LOGS", "PROJECTS", "ROLE_HOME",
"ROLE_CONFIG_DIR", "TARGETS")` (SPEC «Контекст», регрессия коммита
d692f2a6) — ни "WORKTREES", ни "BACKUP_MARKER" в кортеже нет, оба
`assertIn` ниже падают.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tests.test_git_fixation import _GitFixationTmpRootTest  # noqa: E402


class GitFixationPatchedAttrsTest(unittest.TestCase):
    """Требование 1 SPEC: песочница мультитаргета этого файла обязана
    патчить пути `config.WORKTREES`/`config.BACKUP_MARKER`, как и
    остальные семь путей `config`, которые она уже патчит — иначе
    `RealPultGitTest` (настоящий git, `tests/test_git_fixation.py:724`)
    пишет worktree и маркер бэкапа на настоящий корень пульта."""

    def test_ac1_patched_attrs_include_worktrees(self):
        """Кортеж `PATCHED_ATTRS` включает `"WORKTREES"`.

        Ловит мутацию: строку `"WORKTREES"` не добавили в кортеж (или
        добавили с опечаткой) — `assertIn` не находит элемент и красит
        тест.
        """
        self.assertIn("WORKTREES", _GitFixationTmpRootTest.PATCHED_ATTRS)

    def test_ac1_patched_attrs_include_backup_marker(self):
        """Кортеж `PATCHED_ATTRS` включает `"BACKUP_MARKER"`.

        Ловит мутацию: правку ограничили одним `"WORKTREES"` и забыли
        `"BACKUP_MARKER"` — второй `assertIn` красит тест независимо от
        первого (оба атрибута из AC-1 проверяются отдельно, чтобы
        частичный фикс не проходил планку).
        """
        self.assertIn("BACKUP_MARKER", _GitFixationTmpRootTest.PATCHED_ATTRS)


if __name__ == "__main__":
    unittest.main()
