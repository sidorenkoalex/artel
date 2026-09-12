"""AC-1 (tasks/01M2ARQMTYRNPR5HRXAPCBAXNY/SPEC.md): когда `behind > 0`, но
ВСЕ файлы диффа main от точки расхождения (`merge-base(branch, base)`) до
`base` документные по `scripts.ci_push_class.is_doc_path` И не
пересекаются с файлами диффа ветки от той же точки расхождения до
`branch` — `pull.evaluate` возвращает `Fresh` (подтяжка не выполняется).

Красен до реализации: `pull.evaluate` сегодня не сравнивает дифф main с
диффом ветки вовсе — при `behind > 0` она безусловно идёт в `git merge`
(`grep -n "is_doc_path" orchestrator/pull.py` пуст).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import PullFreshnessSandbox  # noqa: E402
from orchestrator import pull  # noqa: E402


class DocOnlyNonOverlappingMainAdvanceIsFreshTest(PullFreshnessSandbox):

    def test_ac1_doc_only_non_overlapping_main_diff_is_fresh(self):
        """main продвигается ДВУМЯ документными коммитами (`docs/backlog.md`,
        `docs/other.md`), ни один из этих путей не пересекается с
        собственным диффом ветки задачи (`orchestrator/ac1_marker.py`) —
        `pull.evaluate` обязан признать ветку свежей и не выполнять
        подтяжку, несмотря на `behind > 0`.

        Ловит мутацию: `evaluate` проверяет документность только
        ПОСЛЕДНЕГО коммита main (или вовсе не собирает полный список
        файлов диффа от точки расхождения) — увидев второй документный
        коммит отдельно, счёл бы его недокументным изменением или
        деградировал бы к прежнему безусловному `Pulled`;
        `assertEqual(outcome, Fresh())` поймает любой другой исход."""
        self.branch_off_main()
        self.commit_on_branch({"orchestrator/ac1_marker.py": "# маркер ветки\n"},
                              f"{self.TASK}: правка ветки")
        self.add_main_commit({"docs/backlog.md": "строка копилки 1\n"},
                             "оператор: копилка — строка 1")
        self.add_main_commit({"docs/other.md": "строка копилки 2\n"},
                             "оператор: копилка — строка 2")

        outcome = self.evaluate()

        self.assertEqual(outcome, pull.Fresh())


if __name__ == "__main__":
    unittest.main()
