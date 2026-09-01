"""Приёмочный тест T094 — AC-2 (tasks/T094/SPEC.md, «Критерии приёмки»).

AC-2: «Функция-генератор идентификатора задачи возвращает валидный
ULID; вне тела этой функции в кодовой базе отсутствуют новые операции
парсинга/сортировки/предположений о длине формата id.»

Красен до реализации: сегодняшний `catalog.cmd_new` всё ещё выдаёт
`Tnnn` через литерал `:03d`, не ULID-генератор — оба теста ниже падают
на этом, каждый по своей грани критерия:

- `test_ac2_cmd_new_produces_a_valid_ulid_task_id` падает на регэкспе
  ULID: сегодняшний `catalog.cmd_new` всё ещё выдаёт `Tnnn`
  (`orchestrator/catalog.py`, `task_id = f"T{number:03d}"`), не ULID.
- `test_ac2_no_fixed_length_number_format_assumption_outside_legacy`
  падает на буквальном примере критерия («T%03d или аналог»): те же
  две строки `catalog.py` содержат литерал `:03d` — заменяются
  вызовом функции-генератора этой же задачей.

Второй тест — статический грep по исходникам `orchestrator/`/`scripts/`
(не тестам): единственное разрешённое исключение — `orchestrator/
store.py`, где живёт `task_number`/`TASK_ID` (SPEC, требование 6:
контур счётчика номеров и его legacy-парсинг заморожены как legacy,
не «новая операция» этой задачи). Файл функции-генератора отдельно не
исключается: валидный ULID-генератор по построению не содержит
трёхзначных числовых предположений формата `Tnnn`, поэтому не
совпадает с этим регэкспом — исключение ему не требуется.
"""
import re
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, config, gitcmd, workspace  # noqa: E402
from tests.sandbox import TmpRootTest, capture, fake_git  # noqa: E402

ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")

# Буквальный пример критерия: "T%03d или аналог" — фиксированная длина
# трёхзначного номера, любым из ходовых способов её выразить в Python.
LENGTH_ASSUMPTION_RE = re.compile(r"%03d|:03d|\\d\{3\}|zfill\(3\)")

# Легаси-зона требования 6 — единственное разрешённое исключение.
LEGACY_ALLOWLIST = {REPO_ROOT / "orchestrator" / "store.py"}

SCANNED_DIRS = (REPO_ROOT / "orchestrator", REPO_ROOT / "scripts")


class Ac2UlidGeneratorTest(TmpRootTest):
    """`cmd_new` не о git/worktree-механике здесь (та же граница, что у
    `tests/test_advance_guard.py::AdvanceGuardTest`): `templates/`
    копируется в песочницу, `gitcmd.git` подменён лёгкой `fake_git`
    (git-идентичность без реального репозитория), `workspace.ensure`
    подменён напрямую на `self.root` — без этого `cmd_new` уходит в
    `SystemExit` на «not a git repository» ещё до того, как успевает
    вернуть id, который и проверяет этот критерий."""

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")

        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        wt_patcher = mock.patch.object(
            workspace, "ensure", lambda task_id, branch: (self.root, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)

        capture(catalog.cmd_init)

    def test_ac2_cmd_new_produces_a_valid_ulid_task_id(self):
        task_id = catalog.cmd_new("Проверка формата id")

        self.assertRegex(
            task_id, ULID_RE,
            f"cmd_new вернул {task_id!r} — не валидный ULID (требование 2)")


class Ac2NoNewLengthAssumptionsTest(unittest.TestCase):

    def test_ac2_no_fixed_length_number_format_assumption_outside_legacy(self):
        hits = []
        for scan_dir in SCANNED_DIRS:
            if not scan_dir.is_dir():
                continue
            for path in sorted(scan_dir.glob("*.py")):
                if path in LEGACY_ALLOWLIST:
                    continue
                text = path.read_text(encoding="utf-8")
                for lineno, line in enumerate(text.splitlines(), start=1):
                    if LENGTH_ASSUMPTION_RE.search(line):
                        hits.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: "
                                   f"{line.strip()}")

        self.assertEqual(
            hits, [],
            f"формат-предположение о длине id (T%03d или аналог) вне "
            f"легаси-зоны store.py (требование 6) — вне тела "
            f"функции-генератора (AC-2): {hits}")


if __name__ == "__main__":
    unittest.main()
