"""AC-7 — 01M3FTQ16M3VVXPPFCC0BGA39V: перегенерированная карта в ветке
несёт секции всех модулей подпакетов, и прогон генератора на голове
ветки не оставляет изменений.

Источник — SPEC.md, «Критерии приёмки»:

AC-7. `docs/codebase-map.md` ветки содержит секции всех 34 модулей
подпакетов `orchestrator/doctor/`, `orchestrator/advance_gates/`,
`orchestrator/providers/`, и прогон `python3 scripts/codebase_map.py` на
голове ветки не оставляет изменений в рабочем дереве (условие зелёного
CI-джоба codebase-map).

«Не оставляет изменений» читается ровно так, как это условие
проверяет названный в критерии CI-джоб (`.github/workflows/ci.yml`, шаг
«закоммиченная карта не стухла»): расхождение по строке `built_at_sha`
джоб признаёт свежестью («карта свежа: содержимое совпадает, отличается
только built_at_sha»), потому что sha собственного коммита карта нести не
может; расхождение по любой другой строке и любой другой изменённый файл
— краснота. Иначе критерий был бы неисполним: перегенерация в ветке
всегда даёт файл со sha того коммита, ПОСЛЕ которого карту закоммитили.

Красен до реализации: карта ветки собрана нерекурсивным генератором и
секций модулей подпакетов не содержит вовсе —
`test_ac7_map_lists_every_subpackage_module` падает списком отсутствующих
секций. `test_ac7_regeneration_at_branch_head_leaves_tree_clean` зелёный
и сейчас (старый генератор воспроизводит старую карту) — он держит
условие CI-джоба, когда генератор и карта поедут одним коммитом.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from scripts import codebase_map  # noqa: E402

# Каталоги подпакетов названы критерием буквально; их состав читается с
# диска, а не списком имён: критерий говорит про ВСЕ модули этих
# каталогов, а их число (34 на 27.09) меняется вместе с деревом.
SUBPACKAGE_DIRS = ("orchestrator/doctor", "orchestrator/advance_gates",
                   "orchestrator/providers")
SPEC_SUBPACKAGE_MODULES = 34


class BranchMapListsSubpackagesTest(unittest.TestCase):

    def setUp(self):
        self.assertTrue(
            _util.MAP_PATH.is_file(),
            f"{_util.MAP_REL} обязан лежать в рабочей копии (AC-7)")
        self.map_text = _util.MAP_PATH.read_text(encoding="utf-8")
        self.expected = []
        for directory in SUBPACKAGE_DIRS:
            dir_path = _util.REPO_ROOT / directory
            self.assertTrue(dir_path.is_dir(),
                            f"{directory} обязан существовать в дереве (AC-7)")
            self.expected.extend(
                sorted(p.relative_to(_util.REPO_ROOT).as_posix()
                       for p in dir_path.rglob("*.py")
                       if "__pycache__" not in p.parts))

    def test_ac7_map_lists_every_subpackage_module(self):
        """Каждый `.py`-модуль трёх названных подпакетов имеет в
        закоммиченной карте ветки свою секцию `## <путь>`; их число не
        меньше 34 — замера SPEC на голове ветки.

        Ловит мутацию: генератор починен, а карта в ветке не
        перегенерирована (или перегенерирована до правки генератора) —
        секций подпакетов в файле не будет, и тест назовёт отсутствующие
        пути.
        """
        headers = set(_util.section_headers(self.map_text))
        missing = [rel for rel in self.expected if rel not in headers]
        self.assertEqual(
            [], missing,
            f"{_util.MAP_REL} обязан нести секцию каждого модуля подпакетов "
            f"{', '.join(SUBPACKAGE_DIRS)} (AC-7); нет секций: {missing}")
        self.assertGreaterEqual(
            len(self.expected), SPEC_SUBPACKAGE_MODULES,
            f"в подпакетах ожидалось не меньше {SPEC_SUBPACKAGE_MODULES} "
            f"модулей (замер SPEC на 27.09), найдено {len(self.expected)} — "
            f"проверь список каталогов подпакетов (AC-7)")

    def test_ac7_regeneration_at_branch_head_leaves_tree_clean(self):
        """Генератор ГОЛОВЫ ветки, запущенный процессом в отдельной
        рабочей копии той же головы, не меняет в ней ни одного файла,
        кроме строки `built_at_sha` самой карты — то самое условие, по
        которому CI-джоб codebase-map признаёт закоммиченную карту
        свежей (и генератор, и дерево берутся из одного checkout, как в
        самом джобе).

        Ловит мутацию: карта собрана руками/старым генератором и
        расходится с тем, что даёт генератор ветки (например, забыт один
        каталог подпакета или порядок секций отличается) — `git status`
        покажет изменённую карту, содержимое без `built_at_sha` не
        совпадёт, и тест покраснеет.
        """
        with _util.detached_worktree_at_head() as head_dir:
            committed = (head_dir / codebase_map.OUTPUT_PATH).read_text(
                encoding="utf-8")
            result = _util.run_generator(
                head_dir, script=head_dir / "scripts" / "codebase_map.py")
            self.assertEqual(
                0, result.returncode,
                f"генератор обязан отработать с кодом 0 (AC-7):\n"
                f"{result.stdout}\n{result.stderr}")
            status = _util.git("status", "--porcelain", cwd=head_dir).stdout
            regenerated = (head_dir / codebase_map.OUTPUT_PATH).read_text(
                encoding="utf-8")

        dirty = [line[3:] for line in status.splitlines() if line]
        self.assertEqual(
            [], [path for path in dirty if path != _util.MAP_REL],
            f"прогон генератора на голове ветки не должен менять ничего, "
            f"кроме {_util.MAP_REL} (AC-7); git status: {dirty}")
        self.assertEqual(
            _util.strip_built_at_sha(committed),
            _util.strip_built_at_sha(regenerated),
            f"закоммиченная {_util.MAP_REL} обязана совпадать с "
            f"перегенерированной вплоть до строки built_at_sha — условие "
            f"зелёного CI-джоба codebase-map (AC-7)")


if __name__ == "__main__":
    unittest.main()
