"""AC-10: PLAN.md несёт приложение к `skills/test-authoring.md` о помощнике.

Раздел о помощнике пульта называет `_pult.py`, четыре функции и константы
и объявляет помощник единственным рекомендуемым способом; разделы
«Источник артефактов задачи — только артефактная ветка» и «База диффа
задачи — точка расхождения с `origin`» ссылаются на помощник; приложение
проходит `git apply --check` на чистом дереве.

PLAN.md читается из ссылки документов задачи (`gitcmd.show` по
`artifact_branch.branch_name`), скил — из HEAD кодовой ветки. Приложение,
уже наложенное в скил к моменту прогона (Оператор применил его отдельным
MR, ветка подтянула main), засчитывается обратной проверкой — тем же
правилом, что ворота мержа.

Валидация стабом: PLAN.md пишет разработчик, test_author его не создаёт —
тесты прогнаны с подменённым чтением PLAN.md (образец приложения,
снятый `git diff` правки скила) и позеленели; без подмены красны.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё нет — в ссылке документов читать нечего.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import artifact_branch, gitcmd  # noqa: E402
from scripts import guard  # noqa: E402

TASK_ID = "01M44EP4Q927DJXVX9YMMZ0B7V"
SKILL = "skills/test-authoring.md"
FUNCTIONS = ("artifact_text", "branch_diff", "changed_paths", "apply_check")
CONSTANTS = ("TASK_ID", "CODE_ROOT")
ARTIFACT_SOURCE_HEADING = "## Источник артефактов задачи — только артефактная ветка"
DIFF_BASE_HEADING = "## База диффа задачи — точка расхождения с `origin`"


def sections(text: str) -> dict[str, str]:
    """Заголовок `## …` -> тело раздела до следующего `## `."""
    found = {}
    matches = list(re.finditer(r"^## .*$", text, re.M))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        found[match.group(0).strip()] = text[match.end():end]
    return found


class SkillAppendixTest(unittest.TestCase):

    def setUp(self):
        plan, reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                   f"tasks/{TASK_ID}/PLAN.md")
        self.assertIsNotNone(plan, f"PLAN.md нет в ссылке документов: {reason}")
        appendices, _errors = guard.plan_appendices(plan)
        mine = [a for a in appendices if SKILL in a.paths]
        self.assertTrue(mine, f"в PLAN.md нет приложения к {SKILL}")
        self.diff = mine[0].diff
        base, reason = gitcmd.show("HEAD", SKILL)
        self.assertIsNotNone(base, f"{SKILL} не прочитан из HEAD: {reason}")
        self.tree = Path(tempfile.mkdtemp(prefix="plank-ac10-"))
        self.addCleanup(shutil.rmtree, self.tree, ignore_errors=True)
        (self.tree / "skills").mkdir()
        (self.tree / SKILL).write_text(base, encoding="utf-8")
        self.patch = self.tree / "appendix.diff"
        self.patch.write_text(self.diff, encoding="utf-8")

    def apply(self, *flags: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "apply", *flags, str(self.patch)],
                              cwd=self.tree, capture_output=True, text=True)

    def patched_skill(self) -> str:
        """Текст скила с приложением: наложено сейчас либо уже было в HEAD."""
        if self.apply("--check").returncode == 0:
            res = self.apply()
            self.assertEqual(res.returncode, 0, res.stderr)
        return (self.tree / SKILL).read_text(encoding="utf-8")

    def test_ac10_appendix_passes_git_apply_check_on_clean_tree(self):
        """Приложение проходит `git apply --check` на чистом дереве.

        Сценарий: скил из HEAD кодовой ветки во временном дереве;
        `git apply --check` приложения успешен (либо успешна обратная
        проверка — приложение уже наложено в HEAD).

        Ловит мутацию: хедер хунка приложения не совпадает с реальным
        диапазоном строк скила — `git apply --check` отказывает в обе
        стороны."""
        forward = self.apply("--check")
        backward = self.apply("--check", "--reverse")

        self.assertTrue(forward.returncode == 0 or backward.returncode == 0,
                        f"git apply --check: {forward.stderr}")

    def test_ac10_helper_section_names_file_functions_constants(self):
        """Раздел о помощнике называет `_pult.py`, четыре функции и константы.

        Сценарий: в скиле после приложения есть раздел `## …`, тело
        которого называет `_pult.py`, `artifact_text`, `branch_diff`,
        `changed_paths`, `apply_check`, `TASK_ID`, `CODE_ROOT` и объявляет
        помощник единственным рекомендуемым способом.

        Ловит мутацию: раздел описывает помощник без одной из функций
        (`apply_check` забыта) или без слов о единственном рекомендуемом
        способе — проверка называет пропуск."""
        text = self.patched_skill()
        helper_sections = {h: h + b for h, b in sections(text).items()
                           if "_pult.py" in h + b}
        self.assertTrue(helper_sections, "в скиле нет раздела о _pult.py")

        def gaps(whole: str) -> list[str]:
            lowered = whole.lower()
            return ([name for name in FUNCTIONS + CONSTANTS if name not in whole]
                    + [word for word in ("единствен", "рекоменд")
                       if word not in lowered])

        complete = [h for h, whole in helper_sections.items() if not gaps(whole)]
        self.assertTrue(complete, "ни один раздел о _pult.py не называет всё: "
                        + "; ".join(f"«{h}» без {gaps(w)}"
                                    for h, w in helper_sections.items()))

    def test_ac10_artifact_and_diff_base_sections_refer_to_helper(self):
        """Разделы об источнике артефактов и базе диффа ссылаются на помощник.

        Сценарий: в скиле после приложения разделы «Источник артефактов
        задачи — только артефактная ветка» и «База диффа задачи — точка
        расхождения с `origin`» есть и называют помощник (`_pult`,
        «помощник» или его функцию).

        Ловит мутацию: приложение добавляет раздел о помощнике, но не
        правит два прежних раздела — они по-прежнему учат
        `gitcmd.show`/`gitcmd.diff_base` без ссылки на помощник."""
        found = sections(self.patched_skill())
        markers = {
            ARTIFACT_SOURCE_HEADING: ("_pult", "помощник", "artifact_text"),
            DIFF_BASE_HEADING: ("_pult", "помощник", "changed_paths",
                                "branch_diff"),
        }
        for heading, words in markers.items():
            self.assertTrue(heading in found, f"раздела «{heading}» нет")
            body = found[heading].lower()
            self.assertTrue(any(w.lower() in body for w in words),
                            f"раздел «{heading}» не ссылается на помощник")


if __name__ == "__main__":
    unittest.main()
