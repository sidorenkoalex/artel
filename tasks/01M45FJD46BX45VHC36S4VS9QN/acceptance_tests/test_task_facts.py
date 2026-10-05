"""Факты этой задачи: карта кодовой базы на голове ветки (AC-28) и
приложения PLAN к защищённым путям (AC-29).

Группа: разовый

Красен до реализации: карта на голове ветки не перегенерирована после
новых файлов задачи и строки «Назначение» модулей механики не называют
её понятий (AC-28); PLAN.md задачи ещё нет — приложений нет (AC-29).

Карта сверяется без записи на диск: `build_modules`/`render` генератора
`scripts/codebase_map.py` на корне рабочей копии, сравнение — без
заголовка `built_at_sha` (sha коммита, в котором карта перегенерирована,
по построению предшествует голове). PLAN читается помощником пульта
`artifact_text`, применимость приложения — `apply_check` к дереву HEAD.
Сторож инварианта 38 из приложения к `tests/test_invariants.py`
прогоняется во временном `git worktree` головы с наложенным приложением:
его новые и изменённые методы обязаны пройти.

Стаб корректной реализации не строился: оба критерия — факты
артефактов задачи (карта, PLAN), а не поведение кода; проверено, что на
сегодняшней голове оба красны по названной выше причине.
"""
import ast
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import (CODE_ROOT, apply_check, artifact_text,  # noqa: E402
                   branch_diff)

sys.path.insert(0, CODE_ROOT)
from scripts import codebase_map, guard  # noqa: E402

MAP = Path(CODE_ROOT) / "docs" / "codebase-map.md"
MECHANICS_NODE = "orchestrator/advance_gates/test_integrity.py"
TERMS = {
    "Меняемое поведение": r"меняем\w*\s+поведени",
    "смена ожидания": r"смен\w*\s+ожидани",
    "ослабление": r"ослаблени",
    "двусторонний прогон": r"двусторонн\w*\s+прогон",
    "сверка с объявленным": r"сверк\w*\s+с\s+объявленн",
    "строгость": r"строгост",
    "храповик": r"храповик",
}
APPENDIX_PATHS = ("templates/SPEC.md", "skills/spec-authoring.md",
                  "skills/coding-standards.md", "skills/review-checklist.md",
                  "docs/invariants.md", "tests/test_invariants.py")


def without_header(text: str) -> str:
    """Карта без заголовка `--- built_at_sha … ---`."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            return text[end + len("\n---\n"):]
    return text


def added_files(diff: str) -> list:
    """Пути файлов, заведённых диффом задачи (`new file mode`)."""
    found = []
    for block in re.split(r"(?m)^diff --git ", diff)[1:]:
        header = block.split("\n", 1)[0]
        if re.search(r"(?m)^new file mode", block.split("@@", 1)[0]):
            found.append(header.split(" b/", 1)[1].strip())
    return found


def added_lines(diff: str) -> str:
    return "\n".join(line[1:] for line in diff.splitlines()
                     if line.startswith("+") and not line.startswith("+++"))


class CodebaseMapTest(unittest.TestCase):

    def test_ac28_map_matches_generator_on_branch_head(self):
        """`docs/codebase-map.md` на голове ветки совпадает с выводом генератора (без заголовка sha).

        Сценарий: генератор строит карту по `orchestrator/`, `scripts/`,
        `tests/` рабочей копии; текст сравнивается с файлом карты.

        Ловит мутацию: карта не перегенерирована после последней правки
        модуля (новый модуль задачи или его докстринг/функции не в карте) —
        тексты расходятся.
        """
        root = Path(CODE_ROOT)
        modules, resolved, imported_by = codebase_map.build_modules(root)
        built = codebase_map.render(modules, resolved, imported_by, "")
        on_disk = MAP.read_text(encoding="utf-8")
        self.assertEqual(without_header(on_disk), without_header(built),
                         "docs/codebase-map.md расходится с выводом "
                         "scripts/codebase_map.py — карта не перегенерирована")

    def test_ac28_purpose_lines_name_mechanics_terms(self):
        """Строки «Назначение» узла `test_integrity.py` и модулей, заведённых задачей, вместе называют все семь понятий механики.

        Сценарий: модули механики — `orchestrator/advance_gates/
        test_integrity.py` и новые модули задачи в `orchestrator/` и
        `scripts/`; строка «Назначение» каждого берётся из карты;
        понятие ищется по корню слова без учёта регистра (падеж
        допустим).

        Ловит мутацию: первая строка докстринга узла или нового модуля
        осталась прежней («Узел сравнения tests/ …») и не называет,
        например, храповик или двусторонний прогон — понятие в перечне
        недостающих.
        """
        text = MAP.read_text(encoding="utf-8")
        purposes = dict(re.findall(r"(?m)^## (\S+)\n\n\*\*Назначение:\*\* (.*)$", text))
        modules = [MECHANICS_NODE] + [
            p for p in added_files(branch_diff())
            if p.endswith(".py") and p.split("/", 1)[0] in ("orchestrator", "scripts")]
        lines = [purposes.get(m, "") for m in modules]
        joined = "\n".join(lines)
        missing = [term for term, pattern in TERMS.items()
                   if not re.search(pattern, joined, re.I)]
        self.assertEqual(missing, [], f"модули механики: {modules}\n"
                                      f"строки «Назначение»:\n{joined}")


class PlanAppendixTest(unittest.TestCase):

    def appendices(self) -> dict:
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md задачи нет")
        found, errors = guard.plan_appendices(plan)
        self.assertEqual(errors, [], f"приложения PLAN не разбираются: {errors}")
        by_path = {}
        for appendix in found:
            for path in appendix.paths:
                by_path[path] = appendix.diff
        return by_path

    def test_ac29_appendices_present_and_apply_on_clean_tree(self):
        """Шесть приложений PLAN есть, `git apply --check` каждого к дереву HEAD проходит, содержание — требования 15.

        Сценарий: для каждого из шести путей в PLAN есть приложение;
        `apply_check` к HEAD — пустой ответ git; добавленные строки
        несут: шаблон SPEC — заголовок «## Меняемое поведение» и образец
        строки `путь::Класс::метод` с «→» и «(требование N)»; навык
        аналитика — раздел и запрет оформлять ослабление разделом; навык
        разработчика — раздел и эскалацию прочих правок; чек-лист ревью —
        «было → стало»; инварианты — двусторонний прогон и храповик.

        Ловит мутацию: приложение подготовлено против устаревшего текста
        файла (хедер хунка не совпадает) — `apply_check` возвращает ответ
        git; приложение к одному из шести путей не вложено в PLAN.
        """
        by_path = self.appendices()
        for path in APPENDIX_PATHS:
            with self.subTest(path=path):
                self.assertIn(path, by_path, f"нет приложения к {path}")
                self.assertEqual(apply_check(by_path[path]), "",
                                 f"приложение к {path} не применяется")
        checks = {
            "templates/SPEC.md": (r"^##\s+Меняемое поведение",
                                  r"`tests/\S+::\S+::\S+`.*→.*\(требование\s+\S+\)"),
            "skills/spec-authoring.md": (r"Меняемое поведение", r"ослаблени"),
            "skills/coding-standards.md": (r"Меняемое поведение|раздел\w* SPEC",
                                           r"эскалаци"),
            "skills/review-checklist.md": (r"было\s*→\s*стало",),
            "docs/invariants.md": (r"двусторонн", r"храповик"),
        }
        for path, patterns in checks.items():
            if path not in by_path:
                continue
            added = added_lines(by_path[path])
            for pattern in patterns:
                with self.subTest(path=path, pattern=pattern):
                    self.assertRegex(added, re.compile(pattern, re.M | re.I),
                                     f"приложение к {path}: добавленные строки:\n{added}")

    def test_ac29_invariant_sentry_refuses_outside_change_and_passes_with_mandate(self):
        """Сторож инварианта 38 из приложения к `tests/test_invariants.py` проходит на голове ветки.

        Сценарий: приложение накладывается во временном `git worktree`
        головы; его новые и изменённые методы (по `qualified_test_methods`)
        несут мандат ослабления и отказ перехода и проходят pytest в этом
        дереве.

        Ловит мутацию: сторож ждёт прежнего поведения (смена утверждения
        вне перечня переход не останавливает) — на голове с реализацией он
        красен; сторож без мандатной половины — в добавленных строках нет
        мандата ослабления.
        """
        by_path = self.appendices()
        self.assertIn("tests/test_invariants.py", by_path)
        diff = by_path["tests/test_invariants.py"]
        added = added_lines(diff)
        self.assertRegex(added, r"Ослабление тестов разрешено|WEAKENING_MANDATE|мандат",
                         "сторож не несёт мандата ослабления")
        self.assertRegex(added, r"гейт неослабления|REFUSAL_ACTION|отказ|refus",
                         "сторож не проверяет отказ перехода")
        with tempfile.TemporaryDirectory(prefix="ac29-") as tmp:
            tree = Path(tmp) / "tree"
            subprocess.run(["git", "-C", CODE_ROOT, "worktree", "add", "--detach",
                            str(tree), "HEAD"], check=True, capture_output=True)
            try:
                rel = "tests/test_invariants.py"
                before = (tree / rel).read_text(encoding="utf-8")
                patch = Path(tmp) / "appendix.diff"
                patch.write_text(diff, encoding="utf-8")
                subprocess.run(["git", "-C", str(tree), "apply", str(patch)],
                               check=True, capture_output=True)
                after = (tree / rel).read_text(encoding="utf-8")
                old = guard.qualified_test_methods(before)
                new = guard.qualified_test_methods(after)
                touched = [name for name, node in new.items()
                           if name not in old
                           or ast.dump(node) != ast.dump(old[name])]
                self.assertTrue(touched, "приложение не заводит и не меняет ни "
                                         "одного тестового метода")
                nodes = [f"{rel}::{name}" for name in touched]
                res = subprocess.run([sys.executable, "-m", "pytest", *nodes,
                                      "-p", "no:cacheprovider", "-q"],
                                     cwd=tree, capture_output=True, text=True,
                                     timeout=600)
                self.assertEqual(res.returncode, 0,
                                 f"сторож красен на голове ветки:\n{res.stdout[-3000:]}"
                                 f"\n{res.stderr[-2000:]}")
            finally:
                subprocess.run(["git", "-C", CODE_ROOT, "worktree", "remove",
                                "--force", str(tree)], capture_output=True)


if __name__ == "__main__":
    unittest.main()
