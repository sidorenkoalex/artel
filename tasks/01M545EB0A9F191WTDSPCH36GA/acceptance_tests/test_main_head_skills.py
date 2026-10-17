"""Проектный скил — из головы `main` пульта, не с диска пульта.

Группа: разовый

Красен до реализации: бриф шага задачи внешнего проекта не несёт проектных скилов вовсе — main-текстов `project_skills` в промпте нет (AC-2), а скил, который есть только на диске пульта, не отказывает сборку брифа — шаг уходит в запуск агента (AC-3).

Разовый, хотя проверяет свойство кода: различить «есть в голове main» и
«есть только на диске» можно лишь подменой чтения головы main
(`gitcmd.show`/`gitcmd.ls_tree_files`), а git-модуль долгоживущему файлу
недоступен (`scripts/guard.py`, признак «git-модуль»). Сценарии брифа —
те же, что в долгоживущем файле задачи
`tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`
(`ProjectSkillsBriefSandbox`); здесь поверх них голова `main` пульта —
дерево сценария `self.main_tree`, а диск `config.ROOT/skills/` несёт для
проектных скилов ДРУГОЙ текст (незакоммиченная правка).

Подмена: чтение головы `main` (`gitcmd.show(config.MAIN_BRANCH, rel,
repo=config.ROOT)` — правило скилов роли, SPEC требование 2) для путей
`skills/…` (после нормализации) отвечает деревом сценария; остальные
чтения — прежней дисковой подменой песочницы (`disk_backed_show`).
`gitcmd.ls_tree_files` головы main по `skills/` — тем же деревом.

Провалидирован временным стабом реализации (проверка имени и
`gitcmd.show` головы main в `runner`): оба метода зелёные в нескольких
прогонах; мутация «скил читается с диска `config.ROOT/skills/`» красит оба.
Стаб удалён.

Имена и тексты скилов, порядок поля, роль шага — модулем `random`; зерно
печатается и входит в текст провала.
"""
import posixpath
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from orchestrator import config, gitcmd  # noqa: E402
from tests import test_01m545eb0a9f191wtdspch36ga_project_role_step as long_lived  # noqa: E402
from tests.sandbox import disk_backed_ls_tree_files, disk_backed_show  # noqa: E402


class MainHeadSandbox(long_lived.ProjectSkillsBriefSandbox):
    """Голова `main` пульта — дерево сценария, отличное от диска пульта."""

    def setUp(self):
        super().setUp()
        self.main_tree = {
            f"skills/{path.name}": path.read_text(encoding="utf-8")
            for path in (self.root / "skills").glob("*.md")}
        self.patch(gitcmd, "show", self.main_show)
        self.patch(gitcmd, "ls_tree_files", self.main_ls_tree)

    def in_main_skills(self, branch: str, rel: str):
        """Нормализованный путь, если чтение адресовано голове `main` и
        попадает в `skills/`; иначе None."""
        if branch != config.MAIN_BRANCH:
            return None
        norm = posixpath.normpath(rel)
        if norm == "skills" or norm.startswith("skills/"):
            return norm
        return None

    def main_show(self, branch, rel, *, repo=None):
        norm = self.in_main_skills(branch, rel)
        if norm is None:
            return disk_backed_show(branch, rel, repo=repo)
        if norm in self.main_tree:
            return self.main_tree[norm], ""
        return None, (f"fatal: path '{rel}' does not exist in "
                      f"'{config.MAIN_BRANCH}'")

    def main_ls_tree(self, branch, rel_dir, *, repo=None):
        norm = self.in_main_skills(branch, rel_dir)
        if norm is None:
            return disk_backed_ls_tree_files(branch, rel_dir, repo=repo)
        prefix = norm.rstrip("/") + "/"
        return sorted(path for path in self.main_tree
                      if path == norm or path.startswith(prefix))

    def place_in_main(self, rel: str, text: str) -> None:
        self.main_tree[posixpath.normpath(rel)] = text

    def main_text(self, rel: str) -> str:
        return self.main_tree[rel]

    def project_skill(self, tag: str) -> tuple:
        """Скил в голове main; на диске пульта — другой текст того же файла."""
        name, text = super().project_skill(tag)
        (self.root / "skills" / f"{name}.md").write_text(
            f"# Диск {name}\n\nНЕЗАКОММИЧЕННОЕ {long_lived.word(self.rnd, 12)}.\n",
            encoding="utf-8")
        return name, text


class MainHeadSkillsTest(MainHeadSandbox):

    def test_ac2_project_skill_text_from_main_head_not_disk(self):
        """В бриф идёт текст проектного скила из головы main, не с диска пульта.

        Сценарий: внешний проект с 2–4 проектными скилами в случайном
        порядке поля; у каждого текст в голове `main` пульта отличается от
        текста того же файла на диске `config.ROOT/skills/`. Шаг задачи
        проекта доходит до запуска агента; main-тексты стоят после скилов
        роли в порядке поля (общий сценарий долгоживущего файла), и ни
        одного дискового текста в промпте нет.

        Ловит мутацию: проектный скил читается с диска рабочей копии пульта
        (`(config.ROOT / "skills" / f"{name}.md").read_text()`), а не
        `gitcmd.show` головы main — в промпте дисковый текст, main-текста
        нет."""
        skills, prompt, _role = self.brief_with_project_skills()
        for name, _text in skills:
            disk = (self.root / "skills" / f"{name}.md").read_text(encoding="utf-8")
            self.assertFalse(disk in prompt, self.note(
                f"скил {name} взят с диска пульта, а не из головы main"))

    def test_ac3_skill_only_on_pult_disk_refuses_brief(self):
        """Скил есть на диске пульта, но не в голове main — отказ сборки брифа.

        Сценарий: файл `skills/<имя>.md` лежит на диске `config.ROOT`, в
        голове `main` его нет; внешний проект называет его в
        `project_skills` среди верных скилов. Шаг задачи проекта не
        запускает агента; строка отказа называет проект, `project_skills`
        и имя; `targets.load()` читает файл; задача соседнего проекта с
        верным полем доходит до запуска агента со своим скилом в брифе.

        Ловит мутацию: существование скила проверяется по диску пульта
        (`Path.exists()`/чтение файла), а не по голове main — незакоммиченный
        скил проходит, шаг уходит в запуск агента."""
        disk_only = f"disk{long_lived.word(self.rnd)}"
        (self.root / "skills" / f"{disk_only}.md").write_text(
            "# только на диске пульта\n", encoding="utf-8")
        self.assert_invalid_name_refused("только на диске", disk_only)


if __name__ == "__main__":
    unittest.main()
