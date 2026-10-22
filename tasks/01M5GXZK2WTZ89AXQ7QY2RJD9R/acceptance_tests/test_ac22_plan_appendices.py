"""AC-22: приложения PLAN к `templates/SPEC.md` и `skills/spec-authoring.md` — раздел «## Заменяемые тесты» после «Меняемое поведение», правило аналитика, матрица неослабления, ни одна существующая строка не тронута.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё нет в ссылке документов — приложений нет.

Факт задачи: PLAN.md читается помощником пульта (`_pult.artifact_text`),
приложения разбираются `guard.plan_appendices`, применимость к дереву HEAD —
`_pult.apply_check`. Итог наложения смотрится на копии двух файлов HEAD во
временном git-репозитории (`git apply`): существующие строки обоих файлов
остаются подряд в прежнем порядке (дифф только вставляет), а вставленный
текст несёт названное критерием.
"""
import difflib
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, apply_check, artifact_text  # noqa: E402

sys.path.insert(0, CODE_ROOT)
from scripts import guard  # noqa: E402

TEMPLATE = "templates/SPEC.md"
SKILL = "skills/spec-authoring.md"
SECTION = "Заменяемые тесты"
RULE = "только смена поведения по требованию; ослабление сюда не входит"
WHOLE = re.compile(r"целиком[^\n]*обратн\w*\s+кавычк|обратн\w*\s+кавычк[^\n]*целиком")
REPO_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR",
            "GIT_NAMESPACE", "GIT_PREFIX")


def clean_env() -> dict:
    """Окружение без переменных, которыми git находит репозиторий в обход
    `-C` (тот же перечень, что у помощника пульта)."""
    return {k: v for k, v in os.environ.items() if k not in REPO_ENV}


def git(repo, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, timeout=60, env=clean_env())


def norm(text: str) -> str:
    return text.lower().replace("ё", "е")


class Ac22PlanAppendicesTest(unittest.TestCase):

    def setUp(self):
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md нет в ссылке документов задачи")
        appendices, errors = guard.plan_appendices(plan)
        self.assertEqual(errors, [], f"ошибки приложений PLAN: {errors}")
        self.mine = [a for a in appendices
                     if set(a.paths) & {TEMPLATE, SKILL}]
        self.assertTrue(self.mine, "в PLAN нет приложений к шаблону и скилу")
        self.before, self.after = {}, {}
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.assertEqual(git(repo, "init", "-q").returncode, 0)
            for rel in (TEMPLATE, SKILL):
                shown = git(CODE_ROOT, "show", f"HEAD:{rel}")
                self.assertEqual(shown.returncode, 0, shown.stderr)
                self.before[rel] = shown.stdout
                (repo / rel).parent.mkdir(parents=True, exist_ok=True)
                (repo / rel).write_text(shown.stdout, encoding="utf-8")
            for i, appendix in enumerate(self.mine):
                patch = repo / f"appendix-{i}.diff"
                patch.write_text(appendix.diff, encoding="utf-8")
                applied = git(repo, "apply", "--whitespace=nowarn", str(patch))
                self.assertEqual(applied.returncode, 0, applied.stderr)
            for rel in (TEMPLATE, SKILL):
                self.after[rel] = (repo / rel).read_text(encoding="utf-8")

    def added(self, rel: str) -> str:
        old, new = self.before[rel].splitlines(), self.after[rel].splitlines()
        lines = []
        for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(
                None, old, new, autojunk=False).get_opcodes():
            if tag in ("insert", "replace"):
                lines += new[j1:j2]
        return "\n".join(lines)

    def test_ac22_appendices_apply_and_keep_existing_lines(self):
        """Приложения применимы к HEAD и только вставляют строки: каждая существующая строка обоих файлов на месте и в прежнем порядке.

        Ловит мутацию: приложение правит существующую строку шаблона
        (например, пункт «Меняемое поведение») — после наложения прежней
        строки нет; приложение не применяется к HEAD (хедер хунка с чужим
        диапазоном) — `apply_check` возвращает ответ git.
        """
        for appendix in self.mine:
            with self.subTest(paths=appendix.paths):
                self.assertEqual(apply_check(appendix.diff), "")
        for rel in (TEMPLATE, SKILL):
            with self.subTest(rel=rel):
                self.assertNotEqual(self.before[rel], self.after[rel],
                                    f"{rel}: приложение его не меняет")
                matcher = difflib.SequenceMatcher(
                    None, self.before[rel].splitlines(),
                    self.after[rel].splitlines(), autojunk=False)
                changed = [op for op in matcher.get_opcodes()
                           if op[0] in ("delete", "replace")]
                self.assertEqual(changed, [], f"{rel}: удалены или изменены "
                                              f"строки {changed}")

    def test_ac22_template_section_after_behavior_change(self):
        """`templates/SPEC.md`: раздел «## Заменяемые тесты» стоит следующим за «## Меняемое поведение», несёт форму пункта и правило «только смена поведения по требованию; ослабление сюда не входит».

        Ловит мутацию: раздел вставлен в конец шаблона или до «Меняемое
        поведение» — следующий за ним заголовок другой; нет формы пункта
        `→ AC-<n>:` или правила о смене поведения — текста нет в теле.
        """
        text = self.after[TEMPLATE]
        heads = re.findall(r"^##\s+(.+?)\s*$", text, re.M)
        self.assertIn("Меняемое поведение", heads)
        self.assertIn(SECTION, heads)
        self.assertEqual(heads[heads.index("Меняемое поведение") + 1], SECTION,
                         f"заголовки шаблона: {heads}")
        body = guard.section_body(text, SECTION)
        self.assertIn("→ AC-", body)
        self.assertIn(norm(RULE), norm(" ".join(text.split())))

    def test_ac22_both_name_matrix_and_whole_id_in_backticks(self):
        """Оба приложения называют раздел «## Матрица неослабления» и правило «идентификатор целиком в обратных кавычках»; скил несёт правило аналитика требования 7.

        Ловит мутацию: приложение скила не называет матрицу либо мандат на
        путь файла («Ослабление тестов разрешено:») для строгого режима;
        правило о находках «исчез» и «прежняя версия красная» пропущено —
        вставленного текста нет.
        """
        for rel in (TEMPLATE, SKILL):
            with self.subTest(rel=rel):
                added = norm(" ".join(self.added(rel).split()))
                self.assertIn("## матрица неослабления", added)
                self.assertRegex(added, WHOLE)
        skill = norm(" ".join(self.added(SKILL).split()))
        for needle in ("заменяемые тесты", "меняемое поведение",
                       "ослабление тестов разрешено:", "исчез",
                       "прежняя версия красная"):
            with self.subTest(needle=needle):
                self.assertIn(needle, skill)


if __name__ == "__main__":
    unittest.main()
