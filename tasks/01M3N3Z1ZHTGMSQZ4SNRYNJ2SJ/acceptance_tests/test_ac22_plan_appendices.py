"""AC-22 — PLAN.md несёт четыре приложения требования 12:
`skills/test-authoring.md`, `skills/coding-standards.md`,
`skills/review-checklist.md`, `docs/invariants.md` (инвариант 27); каждое
накладывается `git apply --check` на чистом дереве, и PLAN.md этот прогон
подтверждает.

PLAN.md читается ТОЛЬКО из артефактной ветки задачи
(`gitcmd.show(artifact_branch.branch_name(TASK_ID), …)`): пульт
материализует в среду прогона планки лишь `acceptance_tests/`. Приложения
разбирает тот же `guard.plan_appendices`, что гейт применимости и мерж.
«Чистое дерево» — база диффа задачи (`gitcmd.diff_base`): приложение
накладывается на её индекс во временном файле индекса, рабочие файлы
репозитория не трогаются; уже применённое Оператором приложение
засчитывается обратным наложением.

Опорные фрагменты содержания сверяются без учёта регистра и пробелов:
абзац вправе переноситься по ширине строки.

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

TASK_ID = "01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ"

# Опорные фрагменты требования 12 в добавляемых строках — по файлу.
REQUIRED = {
    "skills/test-authoring.md": ("tests/", "префикс"),
    "skills/coding-standards.md": ("долгоживущ",),
    "skills/review-checklist.md": ("долгоживущ",),
    "docs/invariants.md": ("долгоживущ",),
}
# Снимаемые приложением временные правила задачи 1 (требование 12):
# строка базы, несущая фрагмент, обязана уйти из файла.
REMOVED = {
    "skills/test-authoring.md": "До мержа задачи 2",
    "skills/coding-standards.md": "двойника",
}
TEMPORARY_REVIEW_RULE = "**Долгоживущие свойства — в `tests/`, не только в планке**"


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


class PlanAppendicesTest(unittest.TestCase):

    def setUp(self):
        text, _reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                    f"tasks/{TASK_ID}/PLAN.md")
        self.assertTrue(
            text, f"PLAN.md задачи не найден в артефактной ветке "
                  f"{artifact_branch.branch_name(TASK_ID)}")
        self.plan = text
        self.appendices, self.errors = guard.plan_appendices(text)
        self.base = gitcmd.diff_base("HEAD", repo=REPO_ROOT)
        self.assertTrue(self.base, "база диффа задачи не вычислена")

    def diffs_for(self, path: str) -> list[str]:
        return [a.diff for a in self.appendices if path in a.paths]

    def base_text(self, path: str) -> str:
        shown = git("show", f"{self.base}:{path}")
        self.assertEqual(shown.returncode, 0, shown.stderr)
        return shown.stdout

    def test_ac22_four_appendices_with_requirement_12_content(self):
        """PLAN.md разбирается без ошибок приложений; для каждого из
        четырёх файлов есть приложение, чьи добавляемые строки несут
        опорные фрагменты требования 12; временная оговорка задачи 1
        «До мержа задачи 2 …» (test-authoring) и правило «двойник в
        `tests/`» (coding-standards) приложением удалены, если они ещё
        есть в базе.

        Ловит мутацию: приложены три диффа из четырёх (например, забыт
        `docs/invariants.md`) либо приложение к `skills/test-authoring.md`
        добавляет новое правило, не удаляя временную оговорку, — подтест
        этого файла покраснеет.
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
        for path, fragment in REMOVED.items():
            with self.subTest(removed=path):
                base_lines = [line for line in self.base_text(path).splitlines()
                              if fragment in line]
                removed = set()
                for diff in self.diffs_for(path):
                    removed.update(removed_lines(diff))
                kept = [line for line in base_lines if line not in removed]
                self.assertEqual(kept, [],
                                 f"{path}: временное правило задачи 1 не снято")

    def test_ac22_each_appendix_applies_on_clean_tree(self):
        """Каждое приложение к четырём файлам накладывается `git apply
        --check --cached` на индекс базы диффа задачи (или, если уже
        применено Оператором, накладывается в обратную сторону), и PLAN.md
        называет прогон `git apply --check`.

        Ловит мутацию: заголовок хунка `@@ -N,M +N,M @@` собран руками, и
        число строк `M` не совпадает с телом хунка (класс T046/T047) — код
        возврата `git apply --check` ненулевой в обе стороны.
        """
        self.assertIn("git apply --check", self.plan,
                      "PLAN.md не подтверждает прогон git apply --check")
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

    def test_ac22_temporary_review_rule_is_untouched(self):
        """Ни одна строка абзаца временного правила «Долгоживущие свойства
        — в `tests/`, не только в планке» из `skills/review-checklist.md`
        базы не удаляется приложением (ADR-0020, пункт 10).

        Ловит мутацию: приложение к `skills/review-checklist.md`
        переформулирует или снимает временное правило — в диффе появляется
        удаляемая `-`-строка абзаца.
        """
        lines = self.base_text("skills/review-checklist.md").splitlines()
        start = next((i for i, line in enumerate(lines)
                      if TEMPORARY_REVIEW_RULE in line), None)
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
