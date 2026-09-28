"""AC-13 — PLAN.md несёт четыре приложения к `skills/` с содержанием
требования 8, каждое применяется `git apply --check` на чистом дереве, а
временное правило «Долгоживущие свойства — в `tests/`, не только в
планке» в `skills/review-checklist.md` приложением не тронуто.

PLAN.md читается ТОЛЬКО из артефактной ветки задачи
(`gitcmd.show(artifact_branch.branch_name(TASK_ID), …)`): пульт
материализует в среду прогона планки лишь `acceptance_tests/`. Приложения
разбирает тот же `guard.plan_appendices`, что гейт применимости и мерж.
«Чистое дерево» — база диффа задачи (`gitcmd.diff_base`), приложение
накладывается на её индекс во временном файле индекса, рабочие файлы
репозитория не трогаются; уже применённое Оператором приложение
засчитывается обратным наложением.

Опорные фрагменты содержания сверяются без учёта регистра и пробелов:
абзац скила вправе переноситься по ширине строки.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё не написан (его пишет developer после этого шага) — `gitcmd.show` по артефактной ветке ничего не возвращает.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artifact_branch, gitcmd  # noqa: E402
from scripts import guard  # noqa: E402

TASK_ID = "01M3N0BWYQ9KHVN41Z4G72706R"

# Опорные фрагменты требования 8 — по файлу скила.
REQUIRED = {
    "skills/test-authoring.md": (
        "Группа: долгоживущий", "Группа: разовый", "Заменяет: tests/",
        "Ловит мутацию", "tests/sandbox.py", "_util.py", "_sandbox.py",
        "random", "зерн"),
    "skills/escalation-rules.md": ("amend-tests", "ADR-0012", "эскал"),
    "skills/coding-standards.md": ("двойник", "мутаци", "tests/"),
    "skills/review-checklist.md": ("долгоживущ", "разов", "мутаци",
                                   "в общем виде"),
}
TEMPORARY_RULE = "**Долгоживущие свойства — в `tests/`, не только в планке**"


def flat(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def added_text(diff: str) -> str:
    return "\n".join(line[1:] for line in diff.splitlines()
                     if line.startswith("+") and not line.startswith("+++"))


def removed_lines(diff: str) -> list[str]:
    return [line[1:] for line in diff.splitlines()
            if line.startswith("-") and not line.startswith("---")]


def git(*args: str, env: dict | None = None,
        stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, input=stdin,
                          capture_output=True, text=True, env=env)


class PlanSkillAppendicesTest(unittest.TestCase):

    def setUp(self):
        text, _reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                    f"tasks/{TASK_ID}/PLAN.md")
        self.assertTrue(
            text, f"PLAN.md задачи не найден в артефактной ветке "
                  f"{artifact_branch.branch_name(TASK_ID)}")
        appendices, errors = guard.plan_appendices(text)
        self.appendices = appendices
        self.errors = errors
        self.base = gitcmd.diff_base("HEAD", repo=REPO_ROOT)
        self.assertTrue(self.base, "база диффа задачи не вычислена")

    def diffs_for(self, path: str) -> list[str]:
        return [a.diff for a in self.appendices if path in a.paths]

    def test_ac13_four_appendices_with_requirement_8_content(self):
        """PLAN.md разбирается без ошибок приложений, и для каждого из
        четырёх скилов есть приложение, чьи добавляемые строки несут
        опорные фрагменты требования 8 (две группы и строка группы,
        «Заменяет: tests/…», помощники `tests/sandbox.py`, `random` с
        зерном; эскалация с правкой `amend-tests` по ADR-0012; двойник
        в `tests/` и временная мутация; граница групп и «в общем виде»).

        Ловит мутацию: приложены три диффа из четырёх (например, забыт
        `skills/coding-standards.md`) либо приложение к
        `skills/test-authoring.md` не несёт точного текста строки группы
        — подтест этого скила покраснеет.
        """
        self.assertEqual(self.errors, [], "ошибки разбора приложений PLAN.md")
        for path, fragments in REQUIRED.items():
            with self.subTest(path=path):
                diffs = self.diffs_for(path)
                self.assertTrue(diffs, f"нет приложения к {path}")
                added = flat("\n".join(added_text(d) for d in diffs))
                for fragment in fragments:
                    self.assertIn(flat(fragment), added,
                                  f"{path}: в добавляемых строках нет {fragment!r}")

    def test_ac13_each_appendix_applies_on_clean_tree(self):
        """Каждое приложение к четырём скилам накладывается `git apply
        --check --cached` на индекс базы диффа задачи (или, если уже
        применено Оператором, накладывается в обратную сторону).

        Ловит мутацию: заголовок хунка `@@ -N,M +N,M @@` собран руками, и
        число строк `M` не совпадает с телом хунка (класс T046/T047) — код
        возврата `git apply --check` ненулевой в обе стороны.
        """
        for path in REQUIRED:
            for diff in self.diffs_for(path):
                with self.subTest(path=path):
                    fd, index = tempfile.mkstemp()
                    os.close(fd)
                    self.addCleanup(os.unlink, index)
                    env = {**os.environ, "GIT_INDEX_FILE": index}
                    read = git("read-tree", self.base, env=env)
                    self.assertEqual(read.returncode, 0, read.stderr)
                    direct = git("apply", "--check", "--cached", "-",
                                 env=env, stdin=diff)
                    if direct.returncode == 0:
                        continue
                    reverse = git("apply", "--check", "--cached", "--reverse",
                                  "-", env=env, stdin=diff)
                    self.assertEqual(
                        reverse.returncode, 0,
                        f"{path}: приложение не накладывается ни прямо, ни "
                        f"обратно:\n{direct.stderr}\n{reverse.stderr}")

    def test_ac13_temporary_review_rule_is_untouched(self):
        """Ни одна строка абзаца временного правила «Долгоживущие свойства
        — в `tests/`, не только в планке» из `skills/review-checklist.md`
        базы не удаляется и не заменяется приложением.

        Ловит мутацию: приложение к `skills/review-checklist.md`
        переформулирует или снимает временное правило (правка строки
        абзаца даёт в диффе удаляемую `-`-строку) — пересечение удаляемых
        строк с абзацем непусто.
        """
        shown = git("show", f"{self.base}:skills/review-checklist.md")
        self.assertEqual(shown.returncode, 0, shown.stderr)
        lines = shown.stdout.splitlines()
        start = next((i for i, line in enumerate(lines)
                      if TEMPORARY_RULE in line), None)
        self.assertIsNotNone(start, "абзаца временного правила нет в базе")
        paragraph = []
        for line in lines[start:]:
            if not line.strip():
                break
            paragraph.append(line)
        removed = set()
        for diff in self.diffs_for("skills/review-checklist.md"):
            removed.update(removed_lines(diff))
        touched = [line for line in paragraph if line in removed]
        self.assertEqual(touched, [],
                         "приложение правит абзац временного правила")


if __name__ == "__main__":
    unittest.main()
