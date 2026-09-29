"""AC-15: PLAN несёт unified-диф к `skills/test-authoring.md` (раздел о
долгоживущем файле: признаки требований 2-6, прогон в выгрузке и правила
отказа, запрет пропусков, образец теста пульта в песочнице с веткой
документов во временном каталоге), применимый `git apply --check` к
чистому дереву.

PLAN.md читается ТОЛЬКО из артефактной ветки (`gitcmd.show` +
`artifact_branch.branch_name`): в среде прогона планки пультом на диске
лежит один `acceptance_tests/`. Чистое дерево — `skills/test-authoring.md`
на базе ветки задачи (`gitcmd.diff_base` — точка расхождения с `origin`),
выписанный во временный каталог; уже применённый диф принимается в
обратную сторону.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё не создан (его пишет developer) — `gitcmd.show` по артефактной ветке возвращает пустоту, все три теста падают на «PLAN.md найден».

Валидация: стаб — синтетический PLAN с настоящим дифом к скилу, снятым
`git diff` с временной правки файла, подставленный подменой `plan_text`;
`git apply --check` исполнялся по-настоящему: все три теста зелёные, диф
с испорченным числом строк хунка или строкой контекста — красный.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import REPO_ROOT  # noqa: E402
from orchestrator import artifact_branch, gitcmd  # noqa: E402

TASK_ID = "01M3P0SQQM453G9DP3NVDVGC49"
TARGET_FILE = "skills/test-authoring.md"

_DIFF_BLOCK = re.compile(r"```(?:diff|patch)\n(diff --git .*?)\n```", re.DOTALL)

# Опорные части раздела — по содержанию, без учёта пробелов и регистра.
REQUIRED = {
    "якорь временного каталога": ("self.tdir", "self.root"),
    "tempfile как якорь": ("tempfile",),
    "признак diff_base/merge-base": ("diff_base", "merge-base"),
    "git с каталогом копии": ("cwd=", "-C"),
    "прогон в выгрузке": ("выгрузк",),
    "запрет пропусков": ("пропуск",),
    "skipTest среди форм пропуска": ("skiptest",),
    "песочница tests/sandbox.py": ("tests/sandbox.py", "tests.sandbox"),
    "ветка документов через artifact_branch": ("artifact_branch",),
}


def plan_text() -> str | None:
    text, _reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                f"tasks/{TASK_ID}/PLAN.md")
    return text or None


def skill_diffs(plan: str) -> list[str]:
    return [m.group(1) + "\n" for m in _DIFF_BLOCK.finditer(plan)
            if f"a/{TARGET_FILE}" in m.group(1).splitlines()[0]]


def added_lines(diff: str) -> str:
    return "\n".join(line[1:] for line in diff.splitlines()
                     if line.startswith("+") and not line.startswith("+++"))


def flat(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


class PlanSkillDiffTest(unittest.TestCase):

    def setUp(self):
        self.plan = plan_text()
        self.assertIsNotNone(
            self.plan, f"PLAN.md задачи не найден в артефактной ветке "
                       f"{artifact_branch.branch_name(TASK_ID)} (AC-15)")
        self.diffs = skill_diffs(self.plan)

    def test_ac15_diff_applies_to_clean_tree(self):
        """Каждый ```diff-блок по `skills/test-authoring.md` проходит
        `git apply --check` на файле базы ветки задачи (или уже применён —
        тогда накладывается обратной стороной).

        Ловит мутацию: диф собран руками — число строк в хедере хунка или
        строки контекста не совпадают с файлом базы (класс T046/T047) —
        `git apply --check` отвечает ненулевым кодом в обе стороны.
        """
        self.assertTrue(self.diffs, f"в PLAN нет ```diff-блока по {TARGET_FILE}")
        base = gitcmd.diff_base("HEAD", repo=REPO_ROOT)
        self.assertTrue(base, "база ветки задачи не вычислена")
        shown = subprocess.run(["git", "show", f"{base}:{TARGET_FILE}"],
                               cwd=REPO_ROOT, capture_output=True)
        self.assertEqual(shown.returncode, 0, shown.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / TARGET_FILE
            target.parent.mkdir(parents=True)
            target.write_bytes(shown.stdout)
            for diff in self.diffs:
                direct = subprocess.run(["git", "apply", "--check", "-"],
                                        cwd=tmp, input=diff, text=True,
                                        capture_output=True)
                if direct.returncode == 0:
                    continue
                reverse = subprocess.run(
                    ["git", "apply", "--check", "--reverse", "-"], cwd=tmp,
                    input=diff, text=True, capture_output=True)
                self.assertEqual(
                    reverse.returncode, 0,
                    f"диф не накладывается ни прямо, ни обратно:\n"
                    f"{direct.stderr}\n{reverse.stderr}")

    def test_ac15_diff_covers_signs_export_skips_and_sample(self):
        """Добавленные дифом строки называют якоря временного каталога
        (`self.tdir`/`self.root`, `tempfile`), признак `diff_base`/
        `merge-base`, git с `cwd=`/`-C` копии, прогон в выгрузке, запрет
        пропусков (`skipTest`), и несут образец теста пульта: класс,
        унаследованный от песочницы `tests.sandbox`, с веткой документов
        через `artifact_branch`.

        Ловит мутацию: приложен диф, правящий только список признаков, без
        прогона в выгрузке и образца — test_author не узнает, как писать
        допустимый тест пульта; первая же недостающая часть краснеет.
        """
        self.assertTrue(self.diffs, f"в PLAN нет ```diff-блока по {TARGET_FILE}")
        added = "\n".join(added_lines(d) for d in self.diffs)
        squeezed = flat(added)
        for what, variants in REQUIRED.items():
            with self.subTest(part=what):
                self.assertTrue(any(flat(v) in squeezed for v in variants),
                                f"в добавленных строках нет: {what} {variants}")
        self.assertRegex(added, r"class\s+\w+\(\w*Sandbox\w*\)",
                         "нет образца: класса-наследника песочницы")

    def test_ac15_plan_confirms_git_apply_check(self):
        """Вне самого дифа PLAN подтверждает прогон `git apply --check`.

        Ловит мутацию: диф приложен без подтверждения прогона — в тексте
        PLAN за вычетом дифов упоминания `git apply --check` нет.
        """
        prose = self.plan
        for diff in self.diffs:
            prose = prose.replace(diff.rstrip("\n"), "")
        self.assertIn("git apply --check", prose)


if __name__ == "__main__":
    unittest.main()
