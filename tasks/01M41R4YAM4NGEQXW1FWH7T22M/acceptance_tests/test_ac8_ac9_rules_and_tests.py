"""Факты задачи 01M41R4YAM4NGEQXW1FWH7T22M: приложение-диф к правилам ролей
в PLAN.md (AC-8) и тесты требований 1, 2, 4 в `tests/` кодовой ветки (AC-9).

Группа: разовый
Красен до реализации: PLAN.md задачи ещё не написан (его пишет developer) — диф к skills/test-authoring.md, skills/review-checklist.md, skills/coding-standards.md не найден; test_ac9 зелен, как только в ветке лежат долгоживущие файлы задачи (их добавляет эта же планка).

Свойства кода (команда `plank-run`, восстановление удалённых файлов, текст
миссии `role_prompt.docs_dir_note`) сторожат долгоживущие файлы задачи в
`tests/` (`tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`,
`tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py`) — AC-1…AC-7 и
часть AC-8 о миссии покрыты их методами `test_ac<n>_…`. Здесь — то, что
после мержа проверять не на чем: приложение к PLAN.md (из артефактной ветки
через `gitcmd.show`, не с диска) и состав тестов ветки относительно базы
`gitcmd.diff_base`.
"""
import ast
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from orchestrator import artifact_branch, config, gitcmd

TASK_ID = "01M41R4YAM4NGEQXW1FWH7T22M"
SKILLS = ("skills/test-authoring.md", "skills/review-checklist.md",
          "skills/coding-standards.md")
DIFF_BLOCK = re.compile(r"```diff\n(.*?)\n```", re.S)

# Слова, по которым добавленные строки правила называют `plank-run`
# единственным способом и с причиной запрещают копирование и удаление.
RULE_WORDS = (("plank-run", r"plank-run"),
              ("«единственный способ»", r"единствен"),
              ("запрет ручного копирования планки", r"копир"),
              ("запрет удаления каталогов рабочей копии", r"удал"),
              ("причина — случаи 03.10.2026", r"03\.10\.2026"))


def plan_text() -> str | None:
    text, _reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                f"tasks/{TASK_ID}/PLAN.md")
    return text


def file_sections(patch: str) -> dict:
    """{путь: секция `diff --git` этого файла} по всем ```diff-блокам."""
    sections = {}
    for chunk in re.split(r"(?m)^(?=diff --git )", patch):
        match = re.match(r"diff --git a/(\S+) b/(\S+)", chunk)
        if match:
            sections[match.group(2)] = chunk if chunk.endswith("\n") else chunk + "\n"
    return sections


def added_lines(section: str) -> str:
    return "\n".join(line[1:] for line in section.splitlines()
                     if line.startswith("+") and not line.startswith("+++"))


class PlanSkillsDiffTest(unittest.TestCase):

    def test_ac8_plan_diff_to_three_skills_applies_and_names_plank_run(self):
        """PLAN.md несёт применимый диф к трём файлам правил ролей.

        Сценарий: PLAN.md читается из артефактной ветки; из его ```diff-блоков
        берутся секции `skills/test-authoring.md`, `skills/review-checklist.md`,
        `skills/coding-standards.md`; файлы базы ветки (`gitcmd.diff_base`)
        выкладываются во временный каталог, и секции проходят `git apply
        --check` (либо `--reverse`, если Оператор уже применил их в базу);
        добавленные строки каждой секции называют `plank-run` единственным
        способом, запрещают ручное копирование планки и удаление каталогов
        рабочей копии и называют причину — случаи 03.10.2026.

        Ловит мутацию: диф приложен не ко всем трём файлам (например, без
        `skills/coding-standards.md`) — секции нет; заголовок хунка не
        совпадает с реальным диапазоном файла — `git apply --check` отказывает
        в обе стороны; правка правила называет `plank-run`, но без запрета
        копирования или без причины — в добавленных строках нет слова.
        """
        text = plan_text()
        self.assertIsNotNone(text, "PLAN.md нет в артефактной ветке задачи")
        sections = file_sections("\n".join(DIFF_BLOCK.findall(text)))
        base = gitcmd.diff_base("HEAD")
        self.assertIsNotNone(base, "база ветки задачи не определена")
        for rel in SKILLS:
            with self.subTest(file=rel):
                self.assertIn(rel, sections,
                              f"в PLAN.md нет ```diff-секции для {rel}")
                section = sections[rel]
                original, reason = gitcmd.show(base, rel)
                self.assertIsNotNone(original, f"{rel} базы не прочитан: {reason}")
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / rel
                    path.parent.mkdir(parents=True)
                    path.write_text(original, encoding="utf-8")
                    forward = subprocess.run(
                        ["git", "apply", "--check", "-"], cwd=tmp,
                        input=section, capture_output=True, text=True)
                    if forward.returncode != 0:
                        reverse = subprocess.run(
                            ["git", "apply", "--check", "--reverse", "-"],
                            cwd=tmp, input=section, capture_output=True,
                            text=True)
                        self.assertEqual(
                            reverse.returncode, 0,
                            f"{rel}: git apply --check отказал и прямо, и "
                            f"обратно:\n{forward.stderr}\n{reverse.stderr}")
                added = added_lines(section)
                for label, pattern in RULE_WORDS:
                    self.assertRegex(added, re.compile(pattern, re.I),
                                     f"{rel}: в добавленных строках нет: {label}")


# Подпункты AC-9: (метка, слова, которые все обязаны стоять в докстринге
# одного тестового метода с заявкой «Ловит мутацию»).
AC9_ITEMS = (
    ("(а) выкладка и уборка только своего каталога, в т.ч. после исключения",
     ("plank-run", "исключени", "историческ")),
    ("(б) plank-run доступна процессу роли", ("plank-run", "процесс", "рол")),
    ("(в) в tests_writing гоняется черновик", ("tests_writing", "черновик")),
    ("(г) массовое удаление developer восстановлено, не закоммичено, журнал",
     ("developer", "восстановл", "журнал")),
    ("(д) удаление внутри зон developer не восстанавливается",
     ("developer", "зон", "не восстановл")),
)


def branch_test_methods() -> list[tuple[str, str, str]]:
    """(файл, метод, докстринг) тестовых методов `tests/test_*.py`, новых или
    изменённых в ветке относительно базы (вместе с незакоммиченными)."""
    base = gitcmd.diff_base("HEAD")
    changed = gitcmd.git("diff", "--name-only", base, "--", "tests").stdout.split()
    changed += gitcmd.git("ls-files", "--others", "--exclude-standard", "--",
                          "tests").stdout.split()
    methods = []
    for rel in sorted(set(changed)):
        name = Path(rel).name
        path = config.ROOT / rel
        if not (name.startswith("test_") and name.endswith(".py")) or not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                methods.append((rel, node.name, ast.get_docstring(node) or ""))
    return methods


class BranchTestsCoverRequirementsTest(unittest.TestCase):

    def test_ac9_branch_tests_with_mutation_claims_cover_items(self):
        """В `tests/` ветки есть тесты с заявками на каждый подпункт AC-9.

        Сценарий: среди тестовых методов `tests/test_*.py`, новых или
        изменённых в ветке относительно базы, для каждого подпункта (а)–(д)
        находится метод, докстринг которого несёт «Ловит мутацию» и слова
        подпункта.

        Ловит мутацию: долгоживущий файл задачи с тестами восстановления
        удалён из ветки или его методы потеряли заявку «Ловит мутацию» —
        подпункты (г)/(д) не покрыты ни одним методом.
        """
        methods = [m for m in branch_test_methods() if "Ловит мутацию" in m[2]]
        for label, words in AC9_ITEMS:
            with self.subTest(item=label):
                hits = [f"{rel}::{name}" for rel, name, doc in methods
                        if all(w.lower() in doc.lower() for w in words)]
                self.assertTrue(hits, f"AC-9 {label}: нет теста в tests/ с "
                                      f"заявкой «Ловит мутацию» и словами {words}")


if __name__ == "__main__":
    unittest.main()
