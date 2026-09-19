"""AC-9 (tasks/01M2XJKKPHM5XDAE42838AMBQH/SPEC.md): PLAN.md несёт
приложением unified diff к `skills/test-authoring.md` с абзацем
требования 6 (источник артефактов планки — только артефактная ветка), и
в PLAN.md подтверждено, что `git apply --check` на этом дифе прошёл на
чистом дереве.

PLAN.md читается ТОЛЬКО из артефактной ветки задачи
(`gitcmd.show(artifact_branch.branch_name(TASK_ID), …)`) — без запасного
чтения с диска: пульт материализует в среду прогона планки лишь
`acceptance_tests/`, и дисковый запасной путь был бы ровно тем дефектом,
который чинит эта задача.

Красен до реализации: PLAN.md задачи ещё не создан (его пишет роль
developer после этого шага) — `gitcmd.show` по артефактной ветке
возвращает пустоту, и тест падает на проверке «PLAN.md найден».
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artifact_branch, gitcmd  # noqa: E402

TASK_ID = "01M2XJKKPHM5XDAE42838AMBQH"
TARGET_FILE = "skills/test-authoring.md"
DIFF_HEADER = f"diff --git a/{TARGET_FILE} b/{TARGET_FILE}"

_FENCED_DIFF = re.compile(
    r"```(?:diff|patch)\n(" + re.escape(DIFF_HEADER) + r".*?)\n```",
    re.DOTALL)

# Опорные части абзаца требования 6 — проверяются по СОДЕРЖАНИЮ, а не
# дословным совпадением всей формулировки: правило должно назвать
# источник (артефактная ветка через `gitcmd.show`), отказать диску и
# объяснить почему (пульт материализует только `acceptance_tests/`).
REQUIRED_FRAGMENTS = (
    "gitcmd.show(artifact_branch.branch_name(TASK_ID)",
    "артефактн",
    "диск",
    "acceptance_tests/",
)


def plan_text() -> str | None:
    """Текст PLAN.md — из артефактной ветки задачи тем же примитивом,
    которым читает артефакты сам пульт."""
    text, _reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                f"tasks/{TASK_ID}/PLAN.md")
    return text or None


def extract_diff(text: str) -> str | None:
    """Приложенный диф: фенсированный блок ```diff, а если приложение
    оформлено без ограды — от строки `diff --git …` до конца ограды,
    следующего заголовка раздела или конца документа."""
    fenced = _FENCED_DIFF.search(text)
    if fenced:
        return fenced.group(1) + "\n"
    start = text.find(DIFF_HEADER)
    if start == -1:
        return None
    lines = []
    for line in text[start:].splitlines():
        if line.startswith("```") or line.startswith("## "):
            break
        lines.append(line)
    return "\n".join(lines) + "\n"


def merge_base() -> str:
    """sha точки расхождения ветки задачи с базой интеграции."""
    for ref in ("origin/main", "main"):
        res = subprocess.run(["git", "merge-base", ref, "HEAD"],
                             cwd=REPO_ROOT, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    raise AssertionError("не нашлась база интеграции (origin/main, main)")


class PlanAttachesSkillDiffTest(unittest.TestCase):

    def setUp(self):
        self.plan = plan_text()
        self.assertIsNotNone(
            self.plan,
            f"PLAN.md задачи не найден в артефактной ветке "
            f"{artifact_branch.branch_name(TASK_ID)} — приложение диффа "
            f"AC-9 обязанность роли developer")

    def test_ac9_plan_attaches_applicable_diff_to_test_authoring_skill(self):
        """PLAN.md несёт приложением unified diff по
        `skills/test-authoring.md`, и этот диф накладывается на чистое
        дерево базы интеграции: `git apply --check` в отдельном
        временном worktree возвращает 0 (либо, если Оператор уже применил
        приложение, накладывается в обратную сторону).

        Ловит мутацию: диф собран руками, и заголовок хунка `@@ -N,M
        +N,M @@` не совпадает с реальным диапазоном файла (класс дефекта
        T046/T047, ровно тот, ради которого conventions-core требует
        прогонять `git apply --check` перед сдачей) — `returncode`
        станет ненулевым и прямо, и в обратную сторону, и тест покраснеет
        вместо тихого «приложение на месте».
        """
        diff_text = extract_diff(self.plan)
        self.assertIsNotNone(
            diff_text,
            f"в PLAN.md нет приложения с '{DIFF_HEADER}' (AC-9)")

        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                ["git", "worktree", "add", "--detach", "--quiet", tmp,
                 merge_base()],
                cwd=REPO_ROOT, check=True, capture_output=True, text=True)
            try:
                direct = subprocess.run(
                    ["git", "apply", "--check", "-"], cwd=tmp,
                    input=diff_text, capture_output=True, text=True)
                if direct.returncode != 0:
                    reverse = subprocess.run(
                        ["git", "apply", "--check", "--reverse", "-"],
                        cwd=tmp, input=diff_text,
                        capture_output=True, text=True)
                    self.assertEqual(
                        0, reverse.returncode,
                        f"git apply --check отказал и прямо, и обратно "
                        f"(диф не накладывается и не применён):\n"
                        f"{direct.stderr}\n{reverse.stderr}")
            finally:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", tmp],
                    cwd=REPO_ROOT, check=True, capture_output=True, text=True)

    def test_ac9_attached_diff_adds_the_artifact_source_paragraph(self):
        """Добавляемые дифом строки несут абзац требования 6: источник
        артефактов планки — артефактная ветка через
        `gitcmd.show(artifact_branch.branch_name(TASK_ID), …)`, диск
        рабочей копии источником не является, потому что пульт
        материализует только `acceptance_tests/`.

        Ловит мутацию: приложен диф, правящий скил о чём угодно другом
        (например, только добавляющий ссылку на эту задачу), без самого
        правила — роль, ради которой задача и затевалась, правила в
        скиле не увидит; проверка добавленных строк покраснеет на первом
        же недостающем фрагменте.
        """
        diff_text = extract_diff(self.plan)
        self.assertIsNotNone(diff_text, "в PLAN.md нет приложения-диффа")
        added = "\n".join(line[1:] for line in diff_text.splitlines()
                          if line.startswith("+")
                          and not line.startswith("+++"))
        # Пробелы и переносы схлопываются: абзац скила переносится по
        # ширине строки, и вызов `gitcmd.show(...)` вправе оказаться
        # разорванным переносом — это не отсутствие правила.
        flat = re.sub(r"\s+", "", added).lower()
        for fragment in REQUIRED_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertIn(re.sub(r"\s+", "", fragment).lower(), flat)

    def test_ac9_plan_confirms_git_apply_check_passed(self):
        """Вне текста самого приложения PLAN.md подтверждает прогон
        `git apply --check` на чистом дереве — то самое подтверждение,
        которого требует и AC-9, и conventions-core.

        Ловит мутацию: диф приложен молча, без подтверждения прогона
        (автор счёл проверку необязательной) — в тексте PLAN.md за
        вычетом самого диффа упоминания `git apply --check` не окажется.
        """
        diff_text = extract_diff(self.plan) or ""
        prose = self.plan.replace(diff_text, "")
        self.assertIn("git apply --check", prose)


if __name__ == "__main__":
    unittest.main()
