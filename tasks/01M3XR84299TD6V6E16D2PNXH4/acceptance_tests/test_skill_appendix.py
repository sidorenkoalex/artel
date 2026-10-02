"""AC-1, AC-2: приложение PLAN.md к `skills/coding-standards.md` добавляет
в раздел «Тесты» пункт о тестовых методах `tests/`.

Группа: разовый

Красен до реализации: PLAN.md задачи ещё нет в артефактной ветке —
его пишет разработчик вместе с приложением; оба теста падают на чтении
PLAN.md.

Источник PLAN.md — артефактная ветка (`gitcmd.show`), разбор приложений
— тем же `guard.plan_appendices`, которым пульт применяет их на мерже.
Приложение накладывается `git apply` на `skills/coding-standards.md`
базы ветки (`gitcmd.diff_base`, точка расхождения с `origin/main`) во
временном каталоге; если оно уже применено в базе (прогон после мержа),
сверяется обратное наложение, и текстом «после» служит сама база.
Проверяется добавленный приложением текст: он целиком лежит в разделе
«## Тесты» и несёт смысловые опоры критерия (основы слов, а не точную
формулировку).
"""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from orchestrator import artifact_branch, gitcmd
from scripts import guard

TASK_ID = "01M3XR84299TD6V6E16D2PNXH4"
SKILL = "skills/coding-standards.md"


def _plan_text():
    text, reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                               f"tasks/{TASK_ID}/PLAN.md")
    return text, reason


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


class SkillAppendixTest(unittest.TestCase):

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
        self.tests_section = _section(self.after, "Тесты")
        self.flat = re.sub(r"\s+", " ", self.added).lower()

    def _skill_after_appendix(self) -> str:
        base = gitcmd.diff_base("HEAD")
        self.assertIsNotNone(base, "git не назвал базу ветки")
        shown = gitcmd.git("show", f"{base}:{SKILL}")
        self.assertEqual(0, shown.returncode, shown.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / SKILL
            target.parent.mkdir(parents=True)
            target.write_text(shown.stdout, encoding="utf-8")
            forward = _git_apply(tmp, self.diff)
            if forward.returncode == 0:
                return target.read_text(encoding="utf-8")
            reverse = _git_apply(tmp, self.diff, "--check", "--reverse")
            self.assertEqual(
                0, reverse.returncode,
                f"приложение к {SKILL} не накладывается на базу {base} ни "
                f"прямо, ни обратно:\n{forward.stderr}\n{reverse.stderr}")
            return shown.stdout

    def _assert_added_in_tests_section(self):
        self.assertTrue(self.tests_section, f"в {SKILL} нет раздела «## Тесты»")
        outside = [line for line in self.added.splitlines()
                   if line.strip() not in self.tests_section]
        self.assertEqual([], outside,
                         "строки приложения легли вне раздела «Тесты»")

    def test_ac1_appendix_adds_tests_point_no_silent_removal_or_rename(self):
        """Приложение добавляет в «Тесты» пункт: метод не удаляется и не переименовывается молча.

        PLAN.md берётся из артефактной ветки, приложение к скилу
        накладывается на базу; добавленные строки целиком лежат в
        разделе «## Тесты» и говорят о существующем методе `tests/`, о
        запрете удалять и переименовывать его молча, о сохранении имени
        метода при переписывании и о том, что верные проверки не
        выбрасываются.

        Ловит мутацию: пункт вставлен в другой раздел скила (например
        «Запрещено») — строки приложения окажутся вне раздела «Тесты»;
        пункт без условия о сохранении имени метода или о верных
        проверках — нет соответствующей опоры в добавленном тексте.
        """
        self._assert_added_in_tests_section()
        for stem in ("tests/", "метод", "удал", "переимен", "молч", "сохран",
                     "провер", "верн"):
            self.assertIn(stem, self.flat,
                          f"в добавленном пункте нет опоры «{stem}»:\n{self.added}")
        self.assertRegex(self.flat, r"\bим(я|ена|ени)\b",
                         f"пункт не говорит об имени метода:\n{self.added}")

    def test_ac2_appendix_requires_escalation_before_step_with_method_list(self):
        """Тот же пункт требует эскалации до сдачи шага с перечнем методов, причиной и заменой.

        Добавленный приложением текст раздела «Тесты» требует эскалации
        до сдачи шага, называет перечень в форме
        `tests/<файл>.py::<Класс>::<метод>`, причину и замену и называет
        штатный ответ на эскалацию каналом мандата.

        Ловит мутацию: пункт допускает эскалацию «после отказа гейта»
        вместо «до сдачи шага» — нет опоры «до сдачи»; перечень без формы
        `::<Класс>::<метод>` — регулярное выражение перечня не находит;
        пропущена причина, замена или мандат через ответ — нет опоры.
        """
        self._assert_added_in_tests_section()
        for stem in ("эскал", "до сдачи", "причин", "замен", "мандат", "ответ"):
            self.assertIn(stem, self.flat,
                          f"в добавленном пункте нет опоры «{stem}»:\n{self.added}")
        self.assertRegex(self.added, r"tests/\S+\.py::\S+::\S+",
                         "пункт не называет перечень tests/<файл>.py::<Класс>::<метод>")


if __name__ == "__main__":
    unittest.main()
