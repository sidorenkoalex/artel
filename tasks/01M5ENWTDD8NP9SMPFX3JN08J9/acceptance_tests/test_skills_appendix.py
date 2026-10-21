"""Приложения PLAN к `skills/test-authoring.md` и `skills/review-checklist.md`: раздел Vitest в конце скила автора тестов, дописки к правилам ревью, применимость.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё не написан — приложений к скилам нет, `artifact_text("PLAN.md")` возвращает `None`.

PLAN читается помощником пульта (`_pult.artifact_text`), приложения
разбираются тем же разбором, что гейт применимости
(`scripts.guard.plan_appendices`), применимость — `_pult.apply_check`.
Содержимое проверяется по тексту скилов после наложения приложений: файлы
скилов дерева HEAD рабочей копии кода копируются во временный каталог, и
приложения накладываются туда `git apply` по порядку — рабочая копия не
меняется.

Провалидировано временным стабом реализации (удалён, не закоммичен):
PLAN с двумя приложениями по требованию 7 — оба метода зелёные.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, apply_check, artifact_text  # noqa: E402

if CODE_ROOT not in sys.path:
    sys.path.insert(0, CODE_ROOT)
from scripts import guard  # noqa: E402

AUTHORING = "skills/test-authoring.md"
CHECKLIST = "skills/review-checklist.md"
HEADING = re.compile(r"^#+ .*Компонент с меткой `AC-<n>: ` \(Vitest\)", re.M)


def head_text(rel: str) -> str:
    return subprocess.run(["git", "-C", CODE_ROOT, "show", f"HEAD:{rel}"],
                          capture_output=True, text=True, check=True).stdout


class SkillsAppendixSandbox(unittest.TestCase):

    def appendices(self) -> list:
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md задачи нет в ссылке документов")
        found, errors = guard.plan_appendices(plan)
        self.assertEqual(errors, [], "ошибки разбора приложений PLAN")
        return [a for a in found if {AUTHORING, CHECKLIST} & set(a.paths)]

    def patched(self) -> tuple:
        """({путь: прежний текст}, {путь: текст после приложений})."""
        chosen = self.appendices()
        original = {rel: head_text(rel) for rel in (AUTHORING, CHECKLIST)}
        with tempfile.TemporaryDirectory() as tmp:
            for rel, text in original.items():
                path = Path(tmp) / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            for number, appendix in enumerate(chosen, 1):
                run = subprocess.run(["git", "apply", "-"], cwd=tmp,
                                     input=appendix.diff, capture_output=True,
                                     text=True)
                self.assertEqual(run.returncode, 0,
                                 f"приложение {number} ({appendix.paths}) не "
                                 f"наложилось: {run.stderr}")
            after = {rel: (Path(tmp) / rel).read_text(encoding="utf-8")
                     for rel in original}
        return original, after


class Ac10SkillsAppendixTest(SkillsAppendixSandbox):

    def test_ac10_appendices_present_and_applicable(self):
        """PLAN несёт приложения к обоим скилам, каждое проходит проверку применимости к дереву HEAD.

        Сценарий: среди приложений PLAN (разбор гейта, без ошибок) есть
        затрагивающие `skills/test-authoring.md` и
        `skills/review-checklist.md`; `apply_check` каждого — пустой ответ
        git.

        Ловит мутацию: скилы правлены в ветке, а не приложением, — в PLAN
        приложений нет; хедер хунка не совпадает с диапазоном файла —
        `git apply --check` отвечает ошибкой.
        """
        chosen = self.appendices()
        touched = {p for a in chosen for p in a.paths}
        self.assertIn(AUTHORING, touched)
        self.assertIn(CHECKLIST, touched)
        for number, appendix in enumerate(chosen, 1):
            with self.subTest(appendix=number, paths=appendix.paths):
                self.assertEqual(apply_check(appendix.diff), "")

    def test_ac10_authoring_section_appended_at_end(self):
        """Скил автора тестов после приложений — прежний текст целиком плюс новый раздел в конце о компоненте с меткой `AC-<n>: ` (Vitest).

        Сценарий: текст `skills/test-authoring.md` после наложения
        начинается с прежнего текста файла байт в байт; дописанный хвост
        содержит заголовок «Компонент с меткой `AC-<n>: ` (Vitest)», вводную
        об отнесении разделов о unittest к Python-компоненту и артели, и
        содержание требования 7: метку `AC-<n>: `, запреты, каталог планки
        `plank_layout` и импорты относительно выкладки, пометки `//`,
        долгоживущий файл по шаблону `long_lived`, прогон `plank-run`.

        Ловит мутацию: раздел вставлен в середину или прежняя строка
        скила переписана — прежний текст не префикс; раздел без вводной об
        unittest или без пометок `//`.
        """
        original, after = self.patched()
        old, new = original[AUTHORING], after[AUTHORING]
        self.assertTrue(new.startswith(old), "прежний текст скила изменён")
        tail = new[len(old):]
        self.assertRegex(tail, HEADING)
        tail = tail[HEADING.search(tail).start():]
        lower = tail.lower()
        for token in ("unittest", "python", "артел", "запрещ", "plank_layout",
                      "импорт", "//", "long_lived", "plank-run"):
            with self.subTest(token=token):
                self.assertIn(token, lower)
        self.assertGreaterEqual(tail.count("AC-<n>: "), 2,
                                "метка `AC-<n>: ` только в заголовке")

    def test_ac10_checklist_additions_name_section(self):
        """Скил ревью после приложений несёт дописки о `pult-vitest` к правилам «Долгоживущие свойства — в `tests/`» и «Дифф tests/ — только импорты и пути патчей», с названием раздела «Изменённые утверждения тестов».

        Сценарий: в тексте `skills/review-checklist.md` после наложения
        фрагмент от правила «Долгоживущие свойства — в `tests/`» до
        следующего заголовка `## ` называет `pult-vitest` и «каталог
        долгоживущих тестов компонента»; фрагмент от правила «Дифф tests/ —
        только импорты и пути патчей» до следующего пункта называет
        `pult-vitest`; дописанный текст называет раздел пакета ревьювера
        «Изменённые утверждения тестов» и строки гейта исходов.

        Ловит мутацию: дописка только заменяет `tests/` на каталог
        компонента без названия раздела пакета ревьювера; дописка сделана
        к одному из двух правил.
        """
        original, after = self.patched()
        old, new = original[CHECKLIST], after[CHECKLIST]
        self.assertNotEqual(old, new)
        rule39 = new.find("**Долгоживущие свойства — в `tests/`")
        self.assertNotEqual(rule39, -1)
        end39 = new.find("\n## ", rule39)
        region39 = new[rule39:end39 if end39 != -1 else len(new)]
        self.assertIn("pult-vitest", region39)
        self.assertIn("каталог долгоживущих тестов компонента", region39)
        rule102 = new.find("**Дифф tests/ — только импорты и пути патчей.**")
        self.assertNotEqual(rule102, -1)
        ends = [i for i in (new.find("\n- **", rule102 + 1),
                            new.find("\n## ", rule102 + 1)) if i != -1]
        region102 = new[rule102:min(ends) if ends else len(new)]
        self.assertIn("pult-vitest", region102)
        old_lines = set(old.splitlines())
        added = "\n".join(line for line in new.splitlines()
                          if line not in old_lines)
        self.assertIn("Изменённые утверждения тестов", added)
        self.assertRegex(added.lower(), r"гейт\w* исход")


if __name__ == "__main__":
    unittest.main()
