"""AC-1 (tasks/01M27JPEGCGMDDRX5A98QWJW0Z/SPEC.md): `config.PROTECTED_PATHS`
несёт все пять существующих путей и все пять добавленных этой задачей.

Красен до реализации: сегодня (`orchestrator/config.py:509`)
`PROTECTED_PATHS` несёт только пять исходных путей (`gates.yaml`,
`roles.yaml`, `.github/`, `templates/`, `skills/`) — пяти добавленных
(`docs/invariants.md`, `tests/test_invariants.py`, `docs/adr/`,
`CLAUDE.md`, `targets.yaml`) в кортеже ещё нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402


class ProtectedPathsListTest(unittest.TestCase):

    def test_ac1_protected_paths_has_all_ten_paths(self):
        """`config.PROTECTED_PATHS`, как множество, равно ровно пяти
        исходным и пяти добавленным этой задачей путям — не больше, не
        меньше.

        Ловит мутацию: один из пяти новых путей не добавлен (например,
        опечатка `target.yaml` вместо `targets.yaml`) либо один из пяти
        существующих путей случайно потерян при правке кортежа
        (`assertEqual` множеств ловит расхождение в обе стороны, не
        только «чего-то не хватает»).
        """
        expected = {
            "gates.yaml", "roles.yaml", ".github/", "templates/", "skills/",
            "docs/invariants.md", "tests/test_invariants.py", "docs/adr/",
            "CLAUDE.md", "targets.yaml",
        }
        self.assertEqual(set(config.PROTECTED_PATHS), expected)


if __name__ == "__main__":
    unittest.main()
