"""Документация правила коммита пультом и приложение-диф к скилам в PLAN.md.

Группа: разовый
Красен до реализации: docs/stack.md и docs/operator-session.md ещё не описывают коммит пультом и отказ git на нём, PLAN.md с приложением в артефактной ветке ещё нет (его пишет developer).

Разовый: проверяется факт этой задачи — содержимое документов её ветки и
приложение в её PLAN.md (после мержа приложение применяет Оператор, и
проверять станет нечего). Документы читаются из дерева кода, в котором
идёт прогон (`config.ROOT` — корень, из которого импортирован пульт); PLAN.md
— только из артефактной ветки (`gitcmd.show`). Приложения разбирает тот же
`guard.plan_appendices`, что и гейт приложений пульта; применимость —
`git apply --check` подряд, в порядке разбора, на временном detached
worktree головы ветки задачи (чистое дерево ветки). Приложение, уже
применённое в дереве (Оператор перенёс его до прогона), засчитывается по
`git apply --check --reverse`.
"""
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from orchestrator import artifact_branch, config, gitcmd
from scripts import guard

TASK_ID = "01M3VFYP4RXBY0BG8D3A0B18HD"
CODING_STANDARDS = "skills/coding-standards.md"
CONVENTIONS_CORE = "skills/conventions-core.md"
# Буквальные формулировки «Завершения хода» на базе задачи, которые
# приложение обязано убрать (AC-7).
MUST_END_WITH_COMMIT = "Ход разработчика заканчивается коммитом кода"
COMMIT_BY_PULT_IS_DEFECT = "запишет это в журнал как дефект шага"
# «коммит пульта», «коммите кода пультом», «пульт коммитит», «пульт не
# смог закоммитить» — коммит, который делает пульт (до пяти слов между).
PULT_COMMIT = re.compile(
    r"коммит\w*\s+(?:\S+\s+){0,5}пульт|пульт\w*\s+(?:\S+\s+){0,5}\w*коммит",
    re.I)


def _flat(text: str) -> str:
    return " ".join(text.split())


def _doc(rel: str) -> str:
    path = Path(config.ROOT) / rel
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _paragraphs(text: str) -> list[str]:
    return [_flat(p) for p in re.split(r"\n\s*\n|\n(?=\s*[-*] )", text)
            if p.strip()]


def _sections(text: str) -> list[str]:
    return [_flat(s) for s in re.split(r"\n(?=#{1,6} )", text) if s.strip()]


class DocsDescribePultCommitTest(unittest.TestCase):

    def test_ac6_stack_md_states_pult_commits_step_code(self):
        """docs/stack.md дерева ветки задачи.

        Наблюдение: в документе есть абзац (или пункт списка), где сказано
        про коммит («коммит…») пультом и что роль коммитить не обязана
        («роль», «не обязан…»).

        Ловит мутацию: правило в docs/stack.md не добавлено (или добавлено
        без оговорки, что роль коммитить не обязана) — такого абзаца нет.
        """
        text = _doc("docs/stack.md")
        self.assertTrue(text, "docs/stack.md не найден в дереве ветки")
        found = [p for p in _paragraphs(text)
                 if re.search(r"пульт", p, re.I) and re.search(r"коммит", p, re.I)
                 and re.search(r"\bрол", p, re.I)
                 and re.search(r"не\s+обязан", p, re.I)]
        self.assertTrue(found, "docs/stack.md не описывает правило: штатный "
                               "коммит кода результата шага делает пульт, роль "
                               "коммитить не обязана")

    def test_ac6_operator_session_md_describes_git_failure_record(self):
        """docs/operator-session.md дерева ветки задачи.

        Наблюдение: в документе есть раздел, который называет операцию git
        коммита пульта (`add`, `reset` или `commit`) и worktree, а в одном
        его абзаце сказано о записи журнала («журнал») при отказе/ошибке
        git («git», «отказ…»/«ошибк…»/«сбо…») на коммите пульта (`коммит…`
        и `пульт…` не дальше пяти слов друг от друга).

        Ловит мутацию: описание записи журнала об отказе git на коммите
        пульта в docs/operator-session.md не добавлено — ни один раздел не
        несёт всех признаков разом.
        """
        text = _doc("docs/operator-session.md")
        self.assertTrue(text, "docs/operator-session.md не найден в дереве ветки")
        found = [s for s in _sections(text)
                 if re.search(r"\b(?:add|reset|commit)\b", s)
                 and re.search(r"worktree", s, re.I)
                 and any(re.search(r"журнал", p, re.I)
                         and re.search(r"\bgit\b", p)
                         and PULT_COMMIT.search(p)
                         and re.search(r"отказ|ошибк|сбо", p, re.I)
                         for p in _paragraphs(s))]
        self.assertTrue(found, "docs/operator-session.md не описывает запись "
                               "журнала при отказе git на коммите пульта")


class PlanSkillsAppendixTest(unittest.TestCase):

    def test_ac7_plan_appendix_to_skills_applies_and_drops_commit_duty(self):
        """PLAN.md задачи из артефактной ветки.

        Наблюдение: `guard.plan_appendices` разбирает приложения без
        ошибок, среди их путей — skills/coding-standards.md и
        skills/conventions-core.md; приложения подряд проходят `git apply
        --check` (или уже применены — `--reverse`) на чистом дереве головы
        ветки; после применения skills/coding-standards.md не содержит ни
        «Ход разработчика заканчивается коммитом кода», ни «запишет это в
        журнал как дефект шага».

        Ловит мутацию: счётчики строк в хедере хунка не совпадают с его
        телом (`git apply --check` отвечает «corrupt patch»), приложение
        не затрагивает conventions-core.md, либо дифф к
        coding-standards.md оставляет требование заканчивать ход коммитом
        кода или квалификацию коммита пультом как дефекта шага.
        """
        plan, reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                   f"tasks/{TASK_ID}/PLAN.md")
        self.assertTrue(plan, f"PLAN.md нет в артефактной ветке: {reason}")
        appendices, errors = guard.plan_appendices(plan)
        self.assertEqual(errors, [], "приложения PLAN.md не разбираются")
        paths = {p for a in appendices for p in a.paths}
        self.assertIn(CODING_STANDARDS, paths)
        self.assertIn(CONVENTIONS_CORE, paths)

        head = gitcmd.head_sha()
        self.assertTrue(head, "git не ответил на голову ветки")
        scratch = Path(tempfile.mkdtemp(prefix="plank-skills-appendix-"))
        added = gitcmd.git("worktree", "add", "--detach", str(scratch), head)
        self.assertEqual(added.returncode, 0, added.stderr)
        patch_dir = Path(tempfile.mkdtemp(prefix="plank-skills-patch-"))
        try:
            for index, appendix in enumerate(appendices):
                patch = patch_dir / f"appendix-{index}.diff"
                patch.write_text(appendix.diff, encoding="utf-8")
                check = gitcmd.in_repo(scratch, "apply", "--check", str(patch))
                if check.returncode == 0:
                    applied = gitcmd.in_repo(scratch, "apply", str(patch))
                    self.assertEqual(applied.returncode, 0, applied.stderr)
                    continue
                reverse = gitcmd.in_repo(scratch, "apply", "--check",
                                         "--reverse", str(patch))
                self.assertEqual(
                    reverse.returncode, 0,
                    f"приложение {', '.join(appendix.paths)} не проходит git "
                    f"apply --check на чистом дереве ветки и не применено:\n"
                    f"{check.stderr}\n{reverse.stderr}")
            result = _flat((scratch / CODING_STANDARDS).read_text(encoding="utf-8"))
        finally:
            gitcmd.git("worktree", "remove", "--force", str(scratch))
            shutil.rmtree(scratch, ignore_errors=True)
            shutil.rmtree(patch_dir, ignore_errors=True)
        self.assertNotIn(MUST_END_WITH_COMMIT, result,
                         "coding-standards.md всё ещё требует заканчивать ход "
                         "коммитом кода")
        self.assertNotIn(COMMIT_BY_PULT_IS_DEFECT, result,
                         "coding-standards.md всё ещё квалифицирует коммит "
                         "пультом как дефект шага")


if __name__ == "__main__":
    unittest.main()
