"""AC-6: приложение PLAN.md к `skills/escalation-rules.md` добавляет в
раздел «Как эскалировать» пункт о снятии `status: escalate` после ANSWER.

Группа: разовый

Красен до реализации: PLAN.md задачи ещё нет в артефактной ветке — его
пишет разработчик вместе с приложением; тест падает на чтении PLAN.md.

Источник PLAN.md — артефактная ветка (`gitcmd.show`), разбор приложений
— тем же `guard.plan_appendices`, которым пульт применяет их на мерже.
Приложение накладывается `git apply --check`, затем `git apply` на
`skills/escalation-rules.md` базы ветки (`gitcmd.diff_base`, точка
расхождения с `origin/main`) во временном каталоге — чистое дерево; если
оно уже применено в базе (прогон после мержа), сверяется обратное
наложение, и текстом «после» служит сама база. Проверяется добавленный
приложением текст: он целиком лежит в разделе «## Как эскалировать» и
несёт смысловые опоры критерия (основы слов, не точную формулировку).
"""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from orchestrator import artifact_branch, gitcmd
from scripts import guard

TASK_ID = "01M3XTF1CEBXT4J7P0EKG5J342"
SKILL = "skills/escalation-rules.md"
SECTION = "Как эскалировать"


def _plan_text():
    return gitcmd.show(artifact_branch.branch_name(TASK_ID),
                       f"tasks/{TASK_ID}/PLAN.md")


def _section(text: str, title: str) -> str:
    match = re.search(rf"^##\s+{re.escape(title)}\s*$", text, re.M)
    if match is None:
        return ""
    rest = text[match.end():]
    nxt = re.search(r"^##\s", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def _git_apply(cwd: str, diff: str, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "apply", *flags, "-"], cwd=cwd, input=diff,
                          capture_output=True, text=True)


class EscalationRulesAppendixTest(unittest.TestCase):

    def setUp(self):
        text, reason = _plan_text()
        self.assertIsNotNone(text, f"PLAN.md нет в артефактной ветке: {reason}")
        appendices, errors = guard.plan_appendices(text)
        self.assertEqual([], errors, f"приложения PLAN не разобраны: {errors}")
        mine = [a for a in appendices if SKILL in a.paths]
        self.assertTrue(mine, f"в PLAN.md нет приложения к {SKILL}")
        self.diff = "".join(a.diff for a in mine)
        self.added = "\n".join(
            line[1:] for line in self.diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
            and line[1:].strip())
        self.after = self._skill_after_appendix()

    def _skill_after_appendix(self) -> str:
        base = gitcmd.diff_base("HEAD")
        self.assertIsNotNone(base, "git не назвал базу ветки")
        shown = gitcmd.git("show", f"{base}:{SKILL}")
        self.assertEqual(0, shown.returncode, shown.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / SKILL
            target.parent.mkdir(parents=True)
            target.write_text(shown.stdout, encoding="utf-8")
            check = _git_apply(tmp, self.diff, "--check")
            if check.returncode == 0:
                applied = _git_apply(tmp, self.diff)
                self.assertEqual(0, applied.returncode, applied.stderr)
                return target.read_text(encoding="utf-8")
            reverse = _git_apply(tmp, self.diff, "--check", "--reverse")
            self.assertEqual(
                0, reverse.returncode,
                f"приложение к {SKILL} не проходит git apply --check на базе "
                f"{base} ни прямо, ни обратно:\n{check.stderr}\n{reverse.stderr}")
            return shown.stdout

    def test_ac6_appendix_adds_unescalate_after_answer_point(self):
        """Приложение добавляет в «Как эскалировать» пункт о снятии escalate после ANSWER.

        PLAN.md берётся из артефактной ветки, приложение к скилу проходит
        `git apply --check` на базе ветки и накладывается; добавленные
        строки целиком лежат в разделе «## Как эскалировать» и говорят:
        после ответа Оператора (ANSWER) роль снимает `status: escalate`
        в PLAN.md — сдаёт `ready` либо новую эскалацию с новым батчем, а
        оставленный прежний `status: escalate` пульт читает как новую
        эскалацию.

        Ловит мутацию: пункт вставлен в другой раздел скила («Чего не
        делать») — строки приложения окажутся вне раздела «Как
        эскалировать»; хедер хунка не совпадает с файлом — `git apply
        --check` откажет; пункт без исхода `ready`, без новой эскалации
        с новым батчем или без последствия оставленного `status:
        escalate` — нет соответствующей опоры в добавленном тексте.
        """
        section = _section(self.after, SECTION)
        self.assertTrue(section, f"в {SKILL} нет раздела «## {SECTION}»")
        outside = [line for line in self.added.splitlines()
                   if line.strip() not in section]
        self.assertEqual([], outside,
                         f"строки приложения легли вне раздела «{SECTION}»")
        flat = re.sub(r"\s+", " ", self.added)
        low = flat.lower()
        for anchor in ("ANSWER", "status: escalate", "PLAN.md", "ready"):
            self.assertIn(anchor, flat,
                          f"в добавленном пункте нет «{anchor}»:\n{self.added}")
        for stem in ("сним", "нов", "батч", "пульт"):
            self.assertIn(stem, low,
                          f"в добавленном пункте нет опоры «{stem}»:\n{self.added}")


if __name__ == "__main__":
    unittest.main()
