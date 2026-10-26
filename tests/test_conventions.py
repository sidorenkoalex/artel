"""Конвенции внешнего проекта из файла пульта (`orchestrator/conventions.py`):
разбор заголовка отметки, отказы `conventions-stamp` по решению гейта
ANSWER-2 п.1 (символьная ссылка, не UTF-8, клон не репозиторий, источник —
ссылка или подмодуль), счёт файлов обвязки элемента-каталога `knowledge`
только по `*.md` (ANSWER-2 п.2), сверка ветки отметки в `doctor` (SPEC
01M5T18K1YFBYA7MM1BBRV869A).

Свойства, которых нет в долгоживущих файлах задачи
(`tests/test_01m5t18k1yfbya7mm1bbrv869a_*.py`).
"""
import io
import os
import shutil
import unittest
from contextlib import redirect_stdout

from orchestrator import brief, config, conventions, store
from tests.sandbox import RealGitSandbox, make_project_repo

PROJECT = "uchebnyconv"
BASE = "osnova-conv"
ENTRY = f"""  {PROJECT}:
    forge: github
    url: file:///nonexistent/{PROJECT}
    base: {BASE}
    token_slot: {PROJECT}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""
COMPONENT = """    components:
      yadro:
        command: [python3, -m, pytest]
        long_lived_dir: tests
        long_lived_name: test_<id>_<name>.py
        weakening_scope: [tests/**/*.py]
        mutation_claim_scope: [tests/test_*.py]
        knowledge: [{knowledge}]
"""
BODY = "# Конвенции\n\nСтиль: короткие функции.\n"
SHA = "a" * 40
BLOB = "b" * 40


def header(**fields) -> str:
    lines = {"conventions_stamp": "1", "base_branch": BASE,
             "base_sha": f'"{SHA}"', "sources": f'\n  AGENTS.md: "{BLOB}"'}
    lines.update(fields)
    return "---\n" + "".join(f"{k}: {v}\n" for k, v in lines.items()) + "---\n"


class ParseTest(unittest.TestCase):
    """Три вида файла требования 6 и текст для брифа."""

    def test_stamped_body_is_text_after_closing_fence(self):
        """Файл с годным заголовком: вид `stamped`, тело — побайтно текст
        после закрывающей `---`, поля разобраны.

        Ловит мутацию: тело берётся с закрывающей строкой `---` или без
        первой строки текста — бриф несёт обломок заголовка либо теряет
        строку конвенций."""
        parsed = conventions.parse(header() + BODY)
        self.assertEqual(parsed.kind, conventions.STAMPED)
        self.assertEqual(parsed.body, BODY)
        self.assertEqual(parsed.fields["sources"], {"AGENTS.md": BLOB})

    def test_fence_block_without_stamp_key_is_plain_whole_file(self):
        """Файл начинается блоком `---` без `conventions_stamp` (обычный
        frontmatter): вид `plain`, в бриф идёт весь файл с блоком.

        Ловит мутацию: любой блок `---` считается заголовком отметки и
        срезается — frontmatter конвенций пропадает из брифа."""
        text = "---\ntitle: правила\n---\n" + BODY
        parsed = conventions.parse(text)
        self.assertEqual(parsed.kind, conventions.PLAIN)
        self.assertEqual(parsed.body, text)

    def test_uppercase_or_unquoted_numeric_sha_is_broken(self):
        """`base_sha` из 40 цифр без кавычек (разбирается числом) и blob
        не 40 символов — сломанный заголовок, в бриф ничего.

        Ловит мутацию: значение приводится `str()` перед проверкой — число
        проходит как sha."""
        for text in (header(base_sha="1" * 40) + BODY,
                     header(sources='\n  AGENTS.md: "abc"') + BODY):
            with self.subTest(text=text.splitlines()[3]):
                self.assertEqual(conventions.parse(text).kind,
                                 conventions.BROKEN_KIND)


class ConventionsSandbox(RealGitSandbox):
    """Учебный внешний проект: клон с базовой веткой, `conventions.md`
    пульта."""

    def prepare(self, files: dict, knowledge: str | None = None,
                links: dict | None = None, gitlinks=()) -> None:
        entry = ENTRY + (COMPONENT.format(knowledge=knowledge)
                         if knowledge is not None else "")
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(text.rstrip("\n") + "\n" + entry,
                                  encoding="utf-8")
        self.clone = make_project_repo(PROJECT, origin=False)
        self.git("-C", str(self.clone), "checkout", "-q", "-b", BASE)
        for rel, body in files.items():
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        for rel, target in (links or {}).items():
            os.symlink(target, self.clone / rel)
        self.git("-C", str(self.clone), "add", "-A", "-f")
        head = self.git("-C", str(self.clone), "rev-parse", "HEAD").strip()
        for rel in gitlinks:
            self.git("-C", str(self.clone), "update-index", "--add",
                     "--cacheinfo", f"160000,{head},{rel}")
        self.git("-C", str(self.clone), "commit", "-q", "-m", "база")
        self.path = config.PROJECTS / PROJECT / "conventions.md"
        self.path.write_text(BODY, encoding="utf-8")

    def stamp(self, *files: str) -> tuple:
        """(код выхода, вывод) `conventions-stamp`; 0 — успех."""
        out = io.StringIO()
        with redirect_stdout(out):
            try:
                conventions.cmd_conventions_stamp([PROJECT, *files])
            except SystemExit as exc:
                return exc.code, str(exc.code)
        return 0, out.getvalue()

    def snapshot(self):
        if self.path.is_symlink():
            return ("ссылка", os.readlink(self.path))
        return self.path.read_bytes()


class StampRefusalTest(ConventionsSandbox):
    """Отказы `conventions-stamp` решения гейта ANSWER-2 п.1: именованная
    причина, файл не меняется, через ссылку не пишется."""

    def assert_refused(self, files, needle: str) -> None:
        before = self.snapshot()
        code, out = self.stamp(*files)
        self.assertNotEqual(code, 0, out)
        self.assertIn(needle, out)
        self.assertEqual(self.snapshot(), before)

    def test_symlink_conventions_refused_target_untouched(self):
        """`conventions.md` — символьная ссылка на файл без заголовка.

        Отказ «не обычный файл»; ни ссылка, ни её цель не изменились.

        Ловит мутацию: файл читается и пишется по ссылке (`open` без
        `O_NOFOLLOW`, `write_text` по пути) — цель получает заголовок."""
        self.prepare({"AGENTS.md": "# A\n"})
        real = self.path.parent / "real.md"
        real.write_text(BODY, encoding="utf-8")
        self.path.unlink()
        os.symlink(real, self.path)
        self.assert_refused(["AGENTS.md"], conventions.NOT_REGULAR)
        self.assertEqual(real.read_text(encoding="utf-8"), BODY)

    def test_non_utf8_conventions_refused(self):
        """`conventions.md` — байты cp1251.

        Отказ «текст не в UTF-8», байты прежние.

        Ловит мутацию: файл декодируется с заменой — заголовок пишется над
        искажённым телом."""
        self.prepare({"AGENTS.md": "# A\n"})
        self.path.write_bytes("Правило\n".encode("cp1251"))
        self.assert_refused(["AGENTS.md"], conventions.NOT_UTF8)

    def test_clone_dir_not_a_repository_refused(self):
        """Путь клона — каталог без `.git` внутри репозитория песочницы.

        Отказ «не репозиторий git».

        Ловит мутацию: проверяется только `is_dir()` — git поднимается к
        репозиторию песочницы и читает чужие ветки."""
        self.prepare({"AGENTS.md": "# A\n"})
        shutil.rmtree(self.clone / ".git")
        self.assert_refused(["AGENTS.md"], "не репозиторий git")

    def test_source_symlink_and_submodule_refused(self):
        """Источник в дереве базы — символьная ссылка, затем подмодуль.

        Отказ с видом записи дерева («символьная ссылка», «подмодуль»).

        Ловит мутацию: режим записи дерева не проверяется — в `sources`
        попадает id ссылки или коммита подмодуля."""
        self.prepare({"AGENTS.md": "# A\n"}, links={"link.md": "AGENTS.md"},
                     gitlinks=("vendor",))
        self.assert_refused(["link.md"], "символьная ссылка")
        self.assert_refused(["vendor"], "подмодуль")

    def test_successful_stamp_keeps_mode_and_body(self):
        """Исправная отметка по файлу с правами 0640.

        Файл начинается заголовком с blob `AGENTS.md` базы, тело прежнее,
        права прежние.

        Ловит мутацию: атомарная замена создаёт файл с правами временного
        (0600) — Оператор теряет чтение группой."""
        self.prepare({"AGENTS.md": "# A\n"})
        os.chmod(self.path, 0o640)
        code, out = self.stamp("AGENTS.md")
        self.assertEqual(code, 0, out)
        parsed = conventions.parse(self.path.read_text(encoding="utf-8"))
        self.assertEqual(parsed.kind, conventions.STAMPED)
        self.assertEqual(parsed.body, BODY)
        blob = self.git("-C", str(self.clone), "rev-parse",
                        f"refs/heads/{BASE}:AGENTS.md").strip()
        self.assertEqual(parsed.fields["sources"], {"AGENTS.md": blob})
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o640)


class DriftBranchTest(ConventionsSandbox):

    def test_stamp_of_other_branch_warns(self):
        """Заголовок отметки с `base_branch`, не совпадающей с базой записи
        проекта, при совпадающих blob.

        `conventions.drift` — `warn` с обеими ветками.

        Ловит мутацию: `base_branch` заголовка не сверяется — отметка по
        чужой ветке выглядит свежей."""
        self.prepare({"AGENTS.md": "# A\n"})
        code, out = self.stamp("AGENTS.md")
        self.assertEqual(code, 0, out)
        text = self.path.read_text(encoding="utf-8")
        self.path.write_text(text.replace(f"base_branch: {BASE}",
                                          "base_branch: drugaya", 1),
                             encoding="utf-8")
        status, detail = conventions.drift(PROJECT)
        self.assertEqual(status, "warn", detail)
        self.assertIn("drugaya", detail)
        self.assertIn(BASE, detail)


class WrapperCountTest(ConventionsSandbox):

    def test_dir_element_counts_only_md_wrapper_files(self):
        """База: `CLAUDE.md`, `.claude/settings.json`, `.claude/r.md`,
        `sub/.claude/x.md`, `.mcp.json`, `guide.md`; `knowledge: [./]`.

        Строка «пропущено файлов обвязки: 3» (`CLAUDE.md`, `.claude/r.md`,
        `sub/.claude/x.md` — `*.md`), не 5; текст `guide.md` в брифе есть,
        текстов обвязки нет.

        Ловит мутацию: N считает все файлы обвязки листинга, не только
        `*.md` (ANSWER-2 п.2) — N = 5."""
        self.prepare({"CLAUDE.md": "# обвязка\n",
                      ".claude/settings.json": "{}\n",
                      ".claude/r.md": "# правило агента\n",
                      "sub/.claude/x.md": "# вложенная обвязка\n",
                      ".mcp.json": "{}\n",
                      "guide.md": "# Руководство ГАЙД-ПРОЕКТА\n"},
                     knowledge="./")
        task = "01" + "K" * 24
        store.insert_task(store.db(), task, "Задача", "in_dev",
                          f"task/{task.lower()}-x", PROJECT, 25.0)
        text = "\n".join(brief._project_conventions_parts(
            store.db(), task, "test_author", "0" * 32,
            brief._journal_component))
        self.assertIn("документы knowledge: каталог ./ — пропущено файлов "
                      "обвязки: 3", text)
        self.assertIn("ГАЙД-ПРОЕКТА", text)
        for wrapped in ("правило агента", "вложенная обвязка", "# обвязка"):
            self.assertNotIn(wrapped, text)


if __name__ == "__main__":
    unittest.main()
