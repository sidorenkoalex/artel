"""Бриф роли задачи внешнего проекта: конвенции проекта из файла пульта
`.artel/projects/<проект>/conventions.md` вместо карты кодовой базы и
`CLAUDE.md` пульта, `CLAUDE.md`/`AGENTS.md` проекта в бриф не идут (SPEC
01M5T18K1YFBYA7MM1BBRV869A); пометки «конвенции проекта не разобраны» и
«конвенции проекта не прочитаны»; сборка без сверки свежести и регенерации
карты пульта и без алертов карты; миссии ролей о составе брифа.

Группа: долгоживущий

Красен до реализации: бриф задачи внешнего проекта собирается как бриф артели — несёт проекцию карты пульта, `MAP_PROJECTION_NOTE`, пометку стухлости карты и `CLAUDE.md` пульта, конвенций проекта и пометок «файла нет»/«конвенции проекта не прочитаны» в нём нет, добавка test_author без ANSWER — `None`; сборка сверяет свежесть карты (`git diff` от `built_at_sha` в корне пульта), запускает её регенерацию и заводит алерты карты; миссии developer/analyst/spec_auditor называют карту кодовой базы в брифе.

Публичная поверхность, которую читает файл:

- сборка брифа — `brief.developer_brief`, `brief.analyst_map_component`,
  `brief.spec_auditor_brief`, `brief.test_author_answer_component`
  (`conn, task_id`); отказ шага — `SystemExit`;
- миссии — `role_prompt.mission_brief_package(conn, task_id, t, role, cwd)`;
- журнал задачи — `store.task_steps`, алерты — `alerts.open_alerts`;
- признаки карты пульта в брифе — `brief.MAP_PROJECTION_LABEL`,
  `brief.MAP_PROJECTION_NOTE`, `brief.MAP_REL` и уникальный текст карты
  фикстуры; `CLAUDE.md` пульта — уникальный текст фикстуры.

Окружение — `tests.sandbox.RealGitSandbox`: корень пульта — настоящий
git-репозиторий с `main`, на котором лежат карта (стухшая: после её
`built_at_sha` правился `orchestrator/*.py`, регенератора в песочнице нет),
`CLAUDE.md` и шаблоны пульта. Учебный внешний проект — клон
`make_project_repo` в области проектов песочницы, его запись в
`config.TARGETS` песочницы со своей базовой веткой; `CLAUDE.md`/`AGENTS.md`
проекта лежат в корне этой ветки клона, `conventions.md` с уникальным
текстом — в области проекта песочницы (`config.PROJECTS / <проект>`); в
сценариях AC-9 у записи — компонент с элементом `knowledge`, читаемым из
базы клона (ANSWER-2, У5). Документы задачи (SPEC.md, TZ.md) — коммит
ссылки документов `refs/artifacts/<id>` в клоне проекта.

Сценарии сбоя чтения базы: «клона нет» — клон удалён, «ветки базы нет» —
ветка базы удалена из клона, «git не ответил» — подменённый
`subprocess.run` отвечает `OSError` на git-вызовы вне корня пульта, где
упомянута базовая ветка, «контекст проекта не разрешён» — записи проекта
нет в `config.TARGETS`. В сценариях «клона нет» и «контекст не разрешён»
документы задачи читаются из копии клона подменой
`orchestrator.artifact_branch.task_repo`: так подменяется только чтение
базовой ветки проекта, SPEC.md задачи читается (AC-9). Сбой чтения
`conventions.md` пульта (AC-10) — подменённый `os.open` отвечает
`OSError` только для его пути.

Имена проекта и базовой ветки, тексты файлов конвенций и карты выбираются
модулем `random`; зерно печатается и входит в текст провала.

Файл провалидирован временным стабом реализации: развилка по
`repo_context.is_artel` в четырёх функциях брифа, конвенции — `ls-tree` и
`show` коммита `reference_cache.branch_commit(клон, база)`, миссии без
карты у внешнего проекта; все методы зелёные. Мутации стаба «сбой `show`
помечен „файла нет“» и «`_fresh_map_text_and_note` до развилки» красят
AC-10, AC-11 и AC-12. Стаб удалён, код репозитория не тронут.
"""
import contextlib
import hashlib
import os
import random
import re
import shutil
import string
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import alerts, brief, config, role_prompt, store
from scripts import codebase_map
from tests.sandbox import RealGitSandbox, make_project_repo

REPO_ROOT = Path(__file__).resolve().parent.parent

ROLES = ("developer", "analyst", "spec_auditor", "test_author")
BUILDERS = {
    "developer": "developer_brief",
    "analyst": "analyst_map_component",
    "spec_auditor": "spec_auditor_brief",
    "test_author": "test_author_answer_component",
}
MANIFEST_ROLES = ("developer", "spec_auditor")

ABSENT_MARK = "файла нет"
UNREAD_MARK = "конвенции проекта не прочитаны:"
UNPARSED_MARK = "конвенции проекта не разобраны:"
STALE_MARK = "КАРТА НЕАКТУАЛЬНА"
DOCS_REF_PREFIX = "refs/artifacts/"
TASK_REPO = "orchestrator.artifact_branch.task_repo"
ULID_CHARS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

PROJECT_ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""
COMPONENT_FIELDS = (
    ("command", "[python3, -m, pytest]"),
    ("long_lived_dir", "tests"),
    ("long_lived_name", "test_<id>_<name>.py"),
    ("weakening_scope", "[tests/**/*.py]"),
    ("mutation_claim_scope", "[tests/test_*.py]"),
)


def word(rng: random.Random, k: int = 8) -> str:
    return "".join(rng.choices(string.ascii_lowercase, k=k))


def git_repo_of(argv: list, kwargs: dict) -> str:
    """Каталог, в котором исполняется git-вызов: `-C <путь>` либо `cwd`."""
    for i, part in enumerate(argv[:-1]):
        if part == "-C":
            return str(Path(argv[i + 1]).resolve())
    cwd = kwargs.get("cwd")
    return str(Path(cwd).resolve()) if cwd is not None else str(Path.cwd())


def call_text(argv: list, kwargs: dict) -> str:
    stdin = kwargs.get("input")
    if isinstance(stdin, bytes):
        stdin = stdin.decode("utf-8", "replace")
    return " ".join(argv) + "\n" + (stdin or "")


class ExternalBriefSandbox(RealGitSandbox):
    """Пульт и учебный внешний проект на настоящем git; задача проекта со
    SPEC.md в ссылке документов клона."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.pult_seeded = False
        self.calls: list = []

    # ------------------------------------------------------------ обвязка

    def note(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def cgit(self, *args: str) -> str:
        return self.git("-C", str(self.clone), *args)

    def seed_pult(self, big_map: bool = False) -> None:
        """Голова `main` пульта: стухшая карта (после её `built_at_sha`
        правился `orchestrator/*.py`), `CLAUDE.md` пульта и шаблоны."""
        if self.pult_seeded:
            return
        self.pult_seeded = True
        stub = self.root / "orchestrator" / f"stub_{word(self.rng)}.py"
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text("VALUE = 1\n", encoding="utf-8")
        self.git("add", str(stub))
        self.git("commit", "-q", "-m", "пульт: модуль")
        self.map_sha = self.git("rev-parse", "HEAD").strip()
        self.map_nonce = f"КАРТА-ПУЛЬТА-{word(self.rng, 12)}"
        lines = ["---", f"built_at_sha: {self.map_sha}", "---", "",
                 f"# Codebase-map пульта {self.map_nonce}", ""]
        if big_map:
            filler = f"строка карты пульта {self.map_nonce} " + "x" * 80
            count = config.CONTEXT_FILE_MAX_BYTES // len(filler.encode()) + 50
            lines += [filler] * count
        map_text = "\n".join(lines) + "\n"
        (self.root / "docs").mkdir(exist_ok=True)
        (self.root / brief.MAP_REL).write_text(map_text, encoding="utf-8")
        self.pult_claude_nonce = f"КОНВЕНЦИИ-ПУЛЬТА-{word(self.rng, 12)}"
        (self.root / "CLAUDE.md").write_text(
            f"# Конвенции пульта {self.pult_claude_nonce}\n", encoding="utf-8")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates",
                        dirs_exist_ok=True)
        stub.write_text("VALUE = 2\n", encoding="utf-8")
        self.git("add", "docs", "CLAUDE.md", "templates", str(stub))
        self.git("commit", "-q", "-m", "пульт: карта и конвенции")
        if big_map:
            projected = codebase_map.project_for_brief(map_text)
            self.assertGreater(len(projected.encode("utf-8")),
                               config.CONTEXT_FILE_MAX_BYTES,
                               self.note("фикстура: карта не крупнее потолка"))
        stale = self.git("diff", "--name-only", self.map_sha, "HEAD", "--",
                         "orchestrator/*.py")
        self.assertTrue(stale.strip(), self.note("фикстура: карта не стухла"))

    def prepare(self, files: dict, big_map: bool = False,
                pult_text: str | None = None, with_pult: bool = True,
                knowledge: list | None = None) -> None:
        """Новый учебный проект: файлы `files` в корне его базовой ветки
        клона (клон стоит на `main`, где их нет), задача проекта со SPEC.md
        и TZ.md в ссылке документов клона; `conventions.md` пульта с текстом
        `pult_text` (по умолчанию — уникальным), если `with_pult`; запись с
        компонентом и элементами `knowledge`, если они заданы."""
        self.seed_pult(big_map)
        self.project = f"uchebny{word(self.rng)}"
        self.base = f"osnova-{word(self.rng)}"
        self.entry = PROJECT_ENTRY.format(name=self.project, base=self.base)
        if knowledge is not None:
            fields = [*COMPONENT_FIELDS,
                      ("knowledge", "[" + ", ".join(knowledge) + "]")]
            self.entry += (f"    components:\n      komp{word(self.rng, 5)}:\n"
                           + "".join(f"        {k}: {v}\n" for k, v in fields))
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(text.rstrip("\n") + "\n" + self.entry,
                                  encoding="utf-8")
        self.clone = make_project_repo(self.project, origin=False)
        self.cgit("checkout", "-q", "-b", self.base)
        (self.clone / "README.md").write_text(
            f"# Учебный проект {self.project}\n", encoding="utf-8")
        for name, body in files.items():
            (self.clone / name).write_text(body, encoding="utf-8")
        self.cgit("add", "README.md", *files)
        self.cgit("commit", "-q", "-m", "база проекта")
        self.cgit("checkout", "-q", config.MAIN_BRANCH)

        self.task = "01" + "".join(self.rng.choices(ULID_CHARS, k=24))
        self.branch = f"task/{self.task.lower()}-uchebnaya"
        store.insert_task(self.conn, self.task, "Учебная задача", "in_dev",
                          self.branch, self.project, 25.0)
        self.spec_nonce = f"SPEC-ZADACHI-{word(self.rng, 12)}"
        self.commit_docs({
            "SPEC.md": f"# SPEC\n\n{self.spec_nonce}\n",
            "TZ.md": f"# ТЗ\n\nТЗ учебной задачи {word(self.rng)}.\n"})
        self.pult_rel = f".artel/projects/{self.project}/conventions.md"
        self.pult_path = config.PROJECTS / self.project / "conventions.md"
        self.pult_text = None
        if with_pult:
            self.pult_text = (pult_text if pult_text is not None
                              else self.conventions("conventions.md пульта"))
            self.pult_path.write_text(self.pult_text, encoding="utf-8")

    def commit_docs(self, files: dict) -> None:
        """Коммит документов задачи в ссылку `refs/artifacts/<id>` клона —
        временным индексом, мимо рабочего дерева и индекса клона."""
        src = self.root / ".artel" / f"docs-src-{word(self.rng)}"
        for name, body in files.items():
            path = src / config.TASKS.name / self.task / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        index = src.parent / f"{src.name}.index"
        with mock.patch.dict(os.environ, {"GIT_INDEX_FILE": str(index)}):
            self.cgit("--work-tree", str(src), "add", "-A")
            tree = self.cgit("write-tree").strip()
        commit = self.cgit("commit-tree", tree, "-m", "документы").strip()
        self.cgit("update-ref", DOCS_REF_PREFIX + self.task, commit)

    def drop_project_entry(self) -> None:
        text = config.TARGETS.read_text(encoding="utf-8")
        self.assertIn(self.entry, text)
        config.TARGETS.write_text(text.replace(self.entry, ""), encoding="utf-8")

    def docs_from_copy(self, stack: contextlib.ExitStack) -> Path:
        """Документы задачи — из копии клона: чтение базовой ветки проекта
        лишается клона или контекста, SPEC.md задачи остаётся читаемым."""
        copy = self.root / ".artel" / f"docs-copy-{word(self.rng)}"
        shutil.copytree(self.clone, copy, symlinks=True)
        stack.enter_context(mock.patch(TASK_REPO, lambda task_id: copy))
        return copy

    # -------------------------------------------------------- подмена git

    def spy(self, fail=None):
        """`subprocess.run`, записывающий вызовы; `fail(argv, kwargs)` —
        истина — вызов отвечает `OSError`, как git, который не ответил."""
        real = subprocess.run
        calls = self.calls

        def run(cmd, *args, **kwargs):
            argv = [str(p) for p in cmd] if isinstance(cmd, (list, tuple)) \
                else [str(cmd)]
            calls.append((argv, kwargs.get("cwd")))
            if fail is not None and fail(argv, kwargs):
                raise OSError(f"git не ответил: подмена {word(self.rng, 6)}")
            return real(cmd, *args, **kwargs)

        return mock.patch.object(subprocess, "run", run)

    def is_project_git(self, argv: list, kwargs: dict) -> bool:
        return (bool(argv) and Path(argv[0]).name == "git"
                and git_repo_of(argv, kwargs) != str(self.root.resolve()))

    def fail_base_reads(self, argv: list, kwargs: dict) -> bool:
        return (self.is_project_git(argv, kwargs)
                and self.base in call_text(argv, kwargs))

    def fail_claude_reads(self, argv: list, kwargs: dict) -> bool:
        return (self.is_project_git(argv, kwargs)
                and "CLAUDE.md" in call_text(argv, kwargs))

    def fail_pult_read(self, message: str):
        """Подмена `os.open`: открытие `conventions.md` пульта отвечает
        `OSError` с текстом `message`, прочие пути открываются как прежде."""
        real = os.open
        target = os.path.realpath(self.pult_path)

        def fake_open(path, *args, **kwargs):
            if os.path.realpath(os.fspath(path)) == target:
                raise OSError(message)
            return real(path, *args, **kwargs)

        return mock.patch.object(os, "open", fake_open)

    # ------------------------------------------------------------- сборка

    def build(self, role: str) -> dict:
        """Бриф роли: текст (или `None`), текст отказа `SystemExit`, новые
        записи журнала задачи."""
        rows = store.task_steps(self.conn, self.task)
        mark = rows[-1]["id"] if rows else 0
        text, refusal = None, None
        try:
            text = getattr(brief, BUILDERS[role])(self.conn, self.task)
        except SystemExit as exc:
            refusal = str(exc.code)
        new_rows = [r for r in store.task_steps(self.conn, self.task)
                    if r["id"] > mark]
        return {"text": text, "refusal": refusal, "rows": new_rows}

    def built_text(self, role: str, built: dict) -> str:
        self.assertIsNone(built["refusal"], self.note(
            f"{role}: сборка брифа отказала: {built['refusal']}"))
        self.assertIsNotNone(built["text"], self.note(f"{role}: брифа нет"))
        return built["text"]

    def mission(self, role: str) -> str:
        t = store.get_task(self.conn, self.task)
        mission, _brief, _package = role_prompt.mission_brief_package(
            self.conn, self.task, t, role, self.root / "wt")
        return mission

    # ------------------------------------------------------------ сверки

    def assert_no_pult(self, role: str, text: str) -> None:
        for marker, what in (
                (self.map_nonce, "текст карты пульта"),
                (brief.MAP_PROJECTION_LABEL, "заголовок проекции карты"),
                (brief.MAP_PROJECTION_NOTE.strip(), "MAP_PROJECTION_NOTE"),
                (STALE_MARK, "пометка свежести карты"),
                (self.pult_claude_nonce, "текст CLAUDE.md пульта")):
            self.assertNotIn(marker, text, self.note(f"{role}: в брифе {what}"))

    def header_of(self, text: str, fragment: str) -> str:
        """Строка заголовка `### …` компонента, в чьём теле стоит
        `fragment`."""
        pos = text.find(fragment)
        self.assertGreaterEqual(pos, 0, self.note(f"нет текста {fragment!r}"))
        start = text.rfind("\n### ", 0, pos)
        self.assertGreaterEqual(start, 0, self.note(
            f"у текста {fragment!r} нет заголовка компонента"))
        return text[start + 1:text.index("\n", start + 1)]

    def mark_lines(self, text: str, mark: str) -> list:
        return [line for line in text.splitlines() if mark in line]

    def assert_reason_journaled(self, role: str, text: str, rows: list,
                                mark: str = UNREAD_MARK) -> None:
        """У каждой пометки `mark` («не прочитаны» или «не разобраны»):
        <причина>» — запись журнала задачи с той же причиной."""
        journal = [f"{r['action']}: {r['detail'] or ''}" for r in rows]
        lines = self.mark_lines(text, mark)
        self.assertTrue(lines, self.note(f"{role}: нет пометки «{mark}»"))
        for line in lines:
            reason = line.split(mark, 1)[1].split(" — ")[0].strip()
            reason = reason.rstrip(" .;)»")
            self.assertTrue(reason, self.note(f"{role}: пометка без причины: {line}"))
            self.assertTrue(any(reason in entry for entry in journal), self.note(
                f"{role}: причины {reason!r} нет в журнале задачи:\n"
                + "\n".join(journal)))

    def conventions(self, tag: str) -> str:
        return (f"# {tag} учебного проекта {word(self.rng, 12)}\n\n"
                f"Правило проекта {word(self.rng, 16)}.\n")


class ProjectConventionsInBriefTest(ExternalBriefSandbox):
    """AC-2–AC-5: `conventions.md` пульта в брифе; `CLAUDE.md` базы
    проекта, карты и `CLAUDE.md` пульта в нём нет."""

    def check_role(self, role: str) -> None:
        claude = self.conventions("conventions.md")
        base_claude = self.conventions("CLAUDE.md")
        self.prepare({"CLAUDE.md": base_claude}, pult_text=claude)
        text = self.built_text(role, self.build(role))
        self.assertIn(claude.strip(), text, self.note(
            f"{role}: в брифе нет текста conventions.md пульта"))
        self.assert_no_pult(role, text)
        self.assertNotIn(base_claude.strip(), text, self.note(
            f"{role}: в брифе текст CLAUDE.md базы проекта"))

    def test_ac2_developer_brief_carries_project_claude_not_pult_map(self):
        """Бриф developer задачи учебного проекта с `CLAUDE.md` в базе и
        `conventions.md` пульта.

        Бриф несёт текст `conventions.md` пульта и не несёт ни текста
        `CLAUDE.md` базовой ветки проекта, ни проекции карты пульта, ни её
        пометки свежести, ни `MAP_PROJECTION_NOTE`, ни текста `CLAUDE.md`
        пульта.

        Ловит мутацию: развилка «проект задачи — артель или внешний» в
        `developer_brief` не сделана — бриф по-прежнему кладёт проекцию
        карты и `CLAUDE.md` с main пульта, конвенций проекта в нём нет;
        либо бриф по-прежнему читает `CLAUDE.md` базы проекта."""
        self.check_role("developer")

    def test_ac3_analyst_brief_carries_project_claude_not_pult_map(self):
        """Добавка analyst задачи учебного проекта с `CLAUDE.md` в базе и
        `conventions.md` пульта.

        Текст `conventions.md` пульта есть; текста `CLAUDE.md` базы,
        проекции карты, пометки свежести, `MAP_PROJECTION_NOTE` и
        `CLAUDE.md` пульта нет.

        Ловит мутацию: развилка сделана только в `developer_brief`, а
        `analyst_map_component` по-прежнему кладёт карту пульта и не несёт
        конвенций проекта; либо несёт `CLAUDE.md` базы проекта."""
        self.check_role("analyst")

    def test_ac4_spec_auditor_brief_carries_project_claude_not_pult_map(self):
        """Бриф spec_auditor задачи учебного проекта с `CLAUDE.md` в базе и
        `conventions.md` пульта.

        Текст `conventions.md` пульта есть; текста `CLAUDE.md` базы,
        проекции карты, пометки свежести, `MAP_PROJECTION_NOTE` и
        `CLAUDE.md` пульта нет.

        Ловит мутацию: `spec_auditor_brief` оставлен без развилки — карта
        пульта с `MAP_PROJECTION_NOTE` в брифе, конвенций проекта нет; либо
        в брифе текст `CLAUDE.md` базы проекта."""
        self.check_role("spec_auditor")

    def test_ac5_test_author_addition_exists_without_answer(self):
        """Добавка test_author задачи учебного проекта без ANSWER, причины
        возврата и справочника ядра.

        Добавка не `None`, несёт текст `conventions.md` пульта, не несёт
        текста `CLAUDE.md` базы проекта и ничего от карты и `CLAUDE.md`
        пульта.

        Ловит мутацию: `test_author_answer_component` по-прежнему отдаёт
        `None`, когда нет ANSWER, причины возврата и справочника, — бриф
        test_author внешнего проекта остаётся без конвенций; либо добавка
        несёт `CLAUDE.md` базы проекта."""
        self.check_role("test_author")


class BothConventionFilesTest(ExternalBriefSandbox):
    """AC-6: конвенции проекта — один компонент `conventions.md` пульта,
    опись — как у соседей роли; `CLAUDE.md` и `AGENTS.md` проекта ни одной
    версии в брифе нет (SPEC 01M5T18K1YFBYA7MM1BBRV869A, ANSWER-1 У4,
    ANSWER-2 У6)."""

    def test_ac6_both_files_from_base_branch_as_separate_components(self):
        """Учебный проект с `CLAUDE.md` и `AGENTS.md` в базе; их другие
        версии — в рабочем дереве клона, на ветке задачи и в её рабочей
        копии; `conventions.md` пульта с уникальным текстом.

        Бриф каждой из четырёх ролей несёт текст `conventions.md` под
        заголовком компонента, называющим файл; строка заголовка
        `### conventions.md (.artel/projects/<проект>/conventions.md)` в
        брифе ровно одна, и текст стоит под ней. У developer/spec_auditor
        заголовок несёт размер в байтах и sha256 текста; у
        analyst/test_author — без размера и sha256. Ни одного текста
        `CLAUDE.md`/`AGENTS.md` проекта — ни базы, ни других версий.

        Ловит мутацию: файлы конвенций по-прежнему читаются из проекта — с
        базы, диска рабочей копии задачи, рабочего дерева клона или ветки
        задачи — в брифе их текст; либо компонент `conventions.md` задвоен
        или слит с другим (строк заголовка не одна, текст не под ней); либо
        у analyst/test_author компонент оформлен описью developer
        (`— N байт, sha256=…`)."""
        base = {"CLAUDE.md": self.conventions("CLAUDE.md"),
                "AGENTS.md": self.conventions("AGENTS.md")}
        self.prepare(base)
        others = list(base.values())
        # Рабочее дерево клона (стоит на main, где файлов нет).
        for name in base:
            text = self.conventions(f"{name} рабочего дерева клона")
            (self.clone / name).write_text(text, encoding="utf-8")
            others.append(text)
        # Ветка задачи и её рабочая копия.
        wt = config.PROJECTS / self.project / "worktrees" / self.task
        self.cgit("worktree", "add", "-q", "-b", self.branch, str(wt), self.base)
        for name in base:
            text = self.conventions(f"{name} ветки задачи")
            (wt / name).write_text(text, encoding="utf-8")
            others.append(text)
        self.git("-C", str(wt), "commit", "-q", "-am", "конвенции ветки задачи")
        for name in base:
            text = self.conventions(f"{name} рабочей копии задачи")
            (wt / name).write_text(text, encoding="utf-8")
            others.append(text)

        name, body = "conventions.md", self.pult_text
        label = f"### {name} ({self.pult_rel})"
        for role in ROLES:
            with self.subTest(role=role):
                text = self.built_text(role, self.build(role))
                self.assertIn(body.strip(), text, self.note(
                    f"{role}: нет текста {name} пульта"))
                header = self.header_of(text, body.strip())
                self.assertIn(name, header, self.note(
                    f"{role}: заголовок компонента {name}: {header}"))
                size = len(body.encode("utf-8"))
                sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
                if role in MANIFEST_ROLES:
                    self.assertIn(f"{size} байт", header, self.note(
                        f"{role}: в описи {name} нет размера: {header}"))
                    self.assertIn(f"sha256={sha}", header, self.note(
                        f"{role}: в описи {name} нет sha256: {header}"))
                else:
                    self.assertNotIn("sha256", header, self.note(
                        f"{role}: у {name} опись: {header}"))
                    self.assertNotIn(" байт", header, self.note(
                        f"{role}: у {name} размер в заголовке: {header}"))
                label_lines = [line for line in text.splitlines()
                               if line == label or line.startswith(f"{label} — ")]
                self.assertEqual(len(label_lines), 1, self.note(
                    f"{role}: строк заголовка {label}: {label_lines}"))
                self.assertEqual(header, label_lines[0], self.note(
                    f"{role}: текст {name} не под своим заголовком: {header}"))
                for other in others:
                    self.assertNotIn(other.strip(), text, self.note(
                        f"{role}: в брифе файл проекта: {other.splitlines()[0]}"))


class AbsentFileMarkTest(ExternalBriefSandbox):
    """AC-7, AC-8: пометка «конвенции проекта не разобраны: файла нет —
    <путь conventions.md>» (SPEC 01M5T18K1YFBYA7MM1BBRV869A, требование
    4)."""

    def check_absent(self, files: dict) -> None:
        self.prepare(files, with_pult=False)
        missing = self.pult_rel
        for role in ROLES:
            with self.subTest(role=role):
                text = self.built_text(role, self.build(role))
                lines = [line for line in self.mark_lines(text, ABSENT_MARK)
                         if f"{UNPARSED_MARK} {ABSENT_MARK} — {missing}" in line]
                self.assertTrue(lines, self.note(
                    f"{role}: нет пометки «{UNPARSED_MARK} {ABSENT_MARK} — "
                    f"{missing}»"))

    def test_ac7_missing_claude_md_marked_absent(self):
        """Учебный проект без `conventions.md` пульта; в базе — `AGENTS.md`
        или ничего из конвенций.

        Бриф каждой из четырёх ролей собирается без отказа и несёт
        пометку «конвенции проекта не разобраны: файла нет —
        .artel/projects/<проект>/conventions.md».

        Ловит мутацию: отсутствие файла пульта роняет сборку (`sys.exit`,
        как `_main_branch_text`) либо молча пропускает компонент без
        пометки."""
        files = {}
        if self.rng.random() < 0.5:
            files["AGENTS.md"] = self.conventions("AGENTS.md")
        self.check_absent(files)

    def test_ac8_missing_agents_md_marked_absent(self):
        """Учебный проект с `CLAUDE.md` в базе, но без `conventions.md`
        пульта.

        Бриф каждой из четырёх ролей несёт пометку «конвенции проекта не
        разобраны: файла нет — .artel/projects/<проект>/conventions.md».

        Ловит мутацию: при отсутствии файла пульта бриф откатывается к
        `CLAUDE.md` базы — пометки нет."""
        self.check_absent({"CLAUDE.md": self.conventions("CLAUDE.md")})


class UnreadConventionsTest(ExternalBriefSandbox):
    """AC-9, AC-10: базу прочитать нельзя — пометка «конвенции проекта не
    прочитаны: <причина>»; `conventions.md` пульта прочитать нельзя —
    «конвенции проекта не разобраны: <причина>»; запись журнала, шаг не
    отказывает."""

    def run_scenario(self, scenario: str) -> None:
        # У записи — элемент `knowledge`, ради которого база и читается
        # (ANSWER-2, У5); `conventions.md` пульта — на месте.
        self.prepare({"CLAUDE.md": self.conventions("CLAUDE.md"),
                      "guide.md": self.conventions("guide.md")},
                     knowledge=["guide.md"])
        with contextlib.ExitStack() as stack:
            fail = None
            if scenario == "клона нет":
                self.docs_from_copy(stack)
                shutil.rmtree(self.clone)
            elif scenario == "ветки базы в клоне нет":
                self.cgit("branch", "-D", self.base)
            elif scenario == "git не ответил":
                fail = self.fail_base_reads
            elif scenario == "контекст проекта не разрешён":
                self.docs_from_copy(stack)
                self.drop_project_entry()
            stack.enter_context(self.spy(fail))
            results = {role: self.build(role) for role in ROLES}
        for role, built in results.items():
            with self.subTest(scenario=scenario, role=role):
                text = self.built_text(role, built)
                if role in MANIFEST_ROLES:
                    self.assertIn(self.spec_nonce, text, self.note(
                        f"{scenario}/{role}: в брифе нет SPEC.md задачи"))
                self.assertNotIn(ABSENT_MARK, text, self.note(
                    f"{scenario}/{role}: пометка «{ABSENT_MARK}» вместо "
                    f"«{UNREAD_MARK}»"))
                self.assert_reason_journaled(f"{scenario}/{role}", text,
                                             built["rows"])

    def test_ac9_unreadable_base_marked_unread_and_journaled(self):
        """Базу учебного проекта прочитать нельзя: клона нет, ветки базы
        нет, git не ответил, контекст проекта не разрешён; у записи —
        элемент `knowledge` из базы, `conventions.md` пульта на месте.

        В каждом сценарии бриф каждой из четырёх ролей собирается без
        `SystemExit`, несёт пометку «конвенции проекта не прочитаны:
        <причина>» и не несёт «файла нет»; в журнале задачи — запись с той
        же причиной. У developer/spec_auditor SPEC.md задачи в брифе есть.

        Ловит мутацию: сбой чтения базы трактуется как «файла нет» (пометка
        «файла нет» вместо «не прочитаны»), либо роняет сборку `sys.exit`,
        либо причина не пишется в журнал задачи."""
        for scenario in ("клона нет", "ветки базы в клоне нет",
                         "git не ответил", "контекст проекта не разрешён"):
            self.run_scenario(scenario)

    def test_ac10_failed_file_read_marked_unread_not_absent(self):
        """`conventions.md` пульта есть, но его открытие отвечает `OSError`
        (подмена `os.open` только для его пути).

        Бриф каждой из четырёх ролей собирается без `SystemExit`, на месте
        компонента несёт пометку «конвенции проекта не разобраны: <текст
        ошибки ОС>», а не «файла нет»; в журнале задачи — запись с той же
        причиной (решение гейта 10).

        Ловит мутацию: любой сбой чтения файла пульта помечается «файла
        нет»; либо `OSError` вне перехвата роняет сборку."""
        self.prepare({"CLAUDE.md": self.conventions("CLAUDE.md")})
        message = f"сбой чтения {word(self.rng, 10)}"
        with self.fail_pult_read(message):
            results = {role: self.build(role) for role in ROLES}
        for role, built in results.items():
            with self.subTest(role=role):
                text = self.built_text(role, built)
                absent = [line for line in self.mark_lines(text, ABSENT_MARK)
                          if "conventions.md" in line]
                self.assertEqual(absent, [], self.note(
                    f"{role}: сбой чтения conventions.md помечен «{ABSENT_MARK}»"))
                self.assertTrue(any(message in line for line in
                                    self.mark_lines(text, UNPARSED_MARK)),
                                self.note(f"{role}: пометка без текста ошибки ОС"))
                self.assert_reason_journaled(role, text, built["rows"],
                                             UNPARSED_MARK)


class PultMapUntouchedTest(ExternalBriefSandbox):
    """AC-11, AC-12: сборка брифа внешней задачи не сверяет и не
    регенерирует карту пульта, не меняет его рабочую копию и не заводит
    алертов карты."""

    def pult_snapshot(self) -> tuple:
        return (self.git("rev-parse", "HEAD"),
                self.git("status", "--porcelain"),
                self.git("diff", "HEAD"),
                self.git("ls-files", "-s"),
                (self.root / brief.MAP_REL).read_bytes())

    def test_ac11_no_map_freshness_check_or_regeneration(self):
        """Сборка брифов четырёх ролей задачи учебного проекта при стухшей
        карте пульта.

        Подменённый `subprocess.run` не видит ни git-вызова с
        `built_at_sha` карты (сверка свежести), ни запуска
        `scripts/codebase_map.py` (регенерация); HEAD, индекс, рабочее
        дерево и `docs/codebase-map.md` пульта до и после совпадают.

        Ловит мутацию: `_fresh_map_text_and_note` зовётся до развилки по
        проекту (например, чтобы потом выбросить карту), — сверка
        `git diff <built_at_sha> HEAD` в корне пульта и регенерация
        запускаются."""
        self.prepare({"CLAUDE.md": self.conventions("CLAUDE.md")})
        before = self.pult_snapshot()
        with self.spy():
            for role in ROLES:
                self.build(role)
        freshness = [argv for argv, _cwd in self.calls
                     if Path(argv[0]).name == "git" and self.map_sha in argv]
        regen = [argv for argv, _cwd in self.calls
                 if any("codebase_map.py" in part for part in argv)]
        self.assertEqual(freshness, [], self.note("сверка свежести карты"))
        self.assertEqual(regen, [], self.note("регенерация карты"))
        self.assertEqual(self.pult_snapshot(), before,
                         self.note("рабочая копия пульта изменилась"))

    def test_ac12_no_map_alerts(self):
        """Сборка брифов четырёх ролей задачи учебного проекта при карте
        пульта, чья проекция крупнее потолка файла брифа и которая стухла
        относительно main.

        Ни одного нового алерта карты: ни о размере, ни о стухлости,
        неудачной регенерации или откате.

        Ловит мутацию: `_handle_map_size_alert` или сверка свежести
        остаются на пути сборки брифа внешней задачи — с ней заводятся
        алерты `brief.codebase_map_oversized`/`brief.codebase_map`."""
        self.prepare({"CLAUDE.md": self.conventions("CLAUDE.md")},
                     big_map=True)
        before = {row["id"] for row in alerts.open_alerts(self.conn)}
        for role in ROLES:
            self.build(role)
        new = [row for row in alerts.open_alerts(self.conn)
               if row["id"] not in before]
        about_map = [f"{row['source']}: {row['message']}" for row in new
                     if "codebase_map" in (row["source"] or "")
                     or brief.MAP_REL in (row["message"] or "")]
        self.assertEqual(about_map, [], self.note("алерты карты"))


class ExternalMissionsTest(ExternalBriefSandbox):
    """AC-13, AC-14: миссии ролей задачи внешнего проекта о составе
    брифа."""

    MAP_PHRASE = re.compile(r"[Кк]арт[аеуы] кодовой базы")

    def test_ac13_developer_mission_names_project_conventions_and_skills(self):
        """Миссия developer задачи учебного проекта.

        Говорит, что в брифе — конвенции проекта, а правила работы роли —
        в скилах пульта; фразы о карте кодовой базы «целиком в БРИФЕ РОЛИ»
        в ней нет.

        Ловит мутацию: миссия developer не разведена по проекту — у задачи
        внешнего проекта осталась строка «SPEC задачи, карта кодовой базы,
        конвенции проекта … — целиком в БРИФЕ РОЛИ»."""
        self.prepare({"CLAUDE.md": self.conventions("CLAUDE.md")})
        mission = self.mission("developer")
        self.assertIsNone(self.MAP_PHRASE.search(mission), self.note(
            f"миссия developer называет карту кодовой базы:\n{mission}"))
        self.assertIn("конвенции проекта", mission, self.note(mission))
        self.assertRegex(mission, r"скил\w*", self.note(mission))
        self.assertIn("пульт", mission, self.note(mission))

    def test_ac14_analyst_and_spec_auditor_missions_omit_map(self):
        """Миссии analyst и spec_auditor задачи учебного проекта не
        упоминают карту кодовой базы.

        Ловит мутацию: правка миссий сделана только у developer — analyst
        («Карта кодовой базы и шаблоны … — в БРИФЕ РОЛИ») или spec_auditor
        («…карта кодовой базы и шаблон…») по-прежнему её называют."""
        self.prepare({"CLAUDE.md": self.conventions("CLAUDE.md")})
        for role in ("analyst", "spec_auditor"):
            with self.subTest(role=role):
                mission = self.mission(role)
                self.assertIsNone(self.MAP_PHRASE.search(mission), self.note(
                    f"миссия {role} называет карту кодовой базы:\n{mission}"))


if __name__ == "__main__":
    unittest.main()
