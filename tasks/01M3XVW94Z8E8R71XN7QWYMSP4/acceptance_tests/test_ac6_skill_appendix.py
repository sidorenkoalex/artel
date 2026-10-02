"""AC-6: приложение PLAN.md к `skills/test-authoring.md` — правило «в acceptance_tests/ не класть .md».

Группа: разовый

Красен до реализации: PLAN.md задачи ещё нет в артефактной ветке — его пишет разработчик вместе с приложением; тест падает на чтении PLAN.md.

Источник PLAN.md — артефактная ветка (`gitcmd.show`), разбор приложений
— тем же `guard.plan_appendices`, которым пульт применяет их на мерже.
Приложение проверяется `git apply --check` на `skills/test-authoring.md`
базы ветки (`gitcmd.diff_base`, точка расхождения с `origin/main`) во
временном чистом каталоге; если оно уже применено в базе (прогон после
мержа), сверяется обратное наложение. Смысл добавленного текста —
опорами (основы слов), не точной формулировкой.
"""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from orchestrator import artifact_branch, gitcmd
from scripts import guard

TASK_ID = "01M3XVW94Z8E8R71XN7QWYMSP4"
SKILL = "skills/test-authoring.md"


def _git_apply(cwd: str, diff: str, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "apply", *flags, "-"], cwd=cwd, input=diff,
                          capture_output=True, text=True)


class SkillAppendixTest(unittest.TestCase):

    def test_ac6_plan_appendix_forbids_md_in_acceptance_tests(self):
        """PLAN несёт применимое приложение к скилу с правилом о `.md` и причиной.

        PLAN.md читается из артефактной ветки; среди его приложений есть
        приложение к `skills/test-authoring.md`, которое `git apply --check`
        принимает на чистом каталоге с файлом скила базы ветки. Добавленные
        строки говорят: в `acceptance_tests/` не класть файлы `.md`;
        пояснения — в докстрингах тестов и в PLAN/SPEC; причина — снимок
        переносит каталог в main, где `guard --all` требует заголовочный
        блок у каждого `.md`.

        Ловит мутацию: приложение не к тому скилу или с хедером хунка, не
        совпадающим с файлом (`git apply --check` отказывает); правило без
        причины (нет опор «guard»/«заголовоч»/«main») или без адреса
        пояснений (нет «докстринг»/«PLAN»/«SPEC»).
        """
        text, reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                   f"tasks/{TASK_ID}/PLAN.md")
        self.assertIsNotNone(text, f"PLAN.md нет в артефактной ветке: {reason}")
        appendices, errors = guard.plan_appendices(text)
        self.assertEqual([], errors, f"приложения PLAN не разобраны: {errors}")
        mine = [a for a in appendices if SKILL in a.paths]
        self.assertTrue(mine, f"в PLAN.md нет приложения к {SKILL}")
        diff = "".join(a.diff for a in mine)

        base = gitcmd.diff_base("HEAD")
        self.assertIsNotNone(base, "git не назвал базу ветки")
        shown = gitcmd.git("show", f"{base}:{SKILL}")
        self.assertEqual(0, shown.returncode, shown.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / SKILL
            target.parent.mkdir(parents=True)
            target.write_text(shown.stdout, encoding="utf-8")
            forward = _git_apply(tmp, diff, "--check")
            if forward.returncode != 0:
                reverse = _git_apply(tmp, diff, "--check", "--reverse")
                self.assertEqual(
                    0, reverse.returncode,
                    f"приложение к {SKILL} не накладывается на базу {base} ни "
                    f"прямо, ни обратно:\n{forward.stderr}\n{reverse.stderr}")

        added = "\n".join(line[1:] for line in diff.splitlines()
                          if line.startswith("+") and not line.startswith("+++")
                          and line[1:].strip())
        flat = re.sub(r"\s+", " ", added).lower()
        for stem in ("acceptance_tests", ".md", "докстринг", "plan", "spec",
                     "сним", "main", "guard", "--all", "заголовоч"):
            self.assertIn(stem, flat,
                          f"в добавленном правиле нет опоры «{stem}»:\n{added}")


if __name__ == "__main__":
    unittest.main()
