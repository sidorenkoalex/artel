"""Документы `knowledge` компонента внешнего проекта в брифе ролей и пакете
ревьювера: куски элементов-файлов и элементов-каталогов после конвенций
проекта, предел каталога, пометки элементов, убирание повторов, имена из
листинга каталога только внутри границы недоверенных данных; прежний вывод
побайтно у записи `test_profile`, компонента без `knowledge`, записи из
нескольких компонентов, отказа и пропуска `decide`, исключения `targets`.

Группа: долгоживущий

Красен до реализации: `_project_conventions_parts` читает только `CLAUDE.md`/`AGENTS.md` корня базы и поле `knowledge` компонента не читает — кусков элементов, строк «документы knowledge: …», пометок элементов и записи журнала «бриф: документы knowledge сокращены» нет, константы `brief.KNOWLEDGE_DIR_MAX_FILES` нет; методы AC-9 и AC-10 зелены и сегодня — эталон снят с нынешнего кода, они держат прежний вывод, который реализация не должна менять.

Публичная поверхность, которую читает файл:

- сборка брифа — `brief.developer_brief`, `brief.spec_auditor_brief`
  (оформление с описью), `brief.analyst_map_component`,
  `brief.test_author_answer_component` (оформление без описи) —
  `(conn, task_id)`; пакет ревьювера — `review.review_package(conn,
  task_id, title, branch)["text"]`;
- идентификатор границ — подмена `brief.new_run_id`, маркеры —
  `brief.wrap_boundary`; пометки — `brief.PROJECT_CONVENTIONS_ABSENT_MARK`,
  `brief.PROJECT_CONVENTIONS_UNREAD_MARK`; предел каталога —
  `brief.KNOWLEDGE_DIR_MAX_FILES`; потолок файла —
  `config.CONTEXT_FILE_MAX_BYTES`;
- журнал задачи — `store.task_steps`;
- чтение записи проекта — `project_profile.decide`,
  `project_profile.components` (подменяются исключением
  `targets.TargetsError` в сценариях AC-10).

Окружение — `tests.sandbox.RealGitSandbox`: корень пульта — настоящий
git-репозиторий, он же клон артели. Учебный внешний проект — клон
`make_project_repo` в области проектов песочницы (без `origin`), его запись
в `config.TARGETS` песочницы — `components:` из одного компонента с полем
`knowledge` (либо иная форма записи сценария); документы `knowledge` лежат
в коммите базовой ветки клона, ветка задачи отведена от неё; конвенции
проекта — `conventions.md` в области проекта песочницы (SPEC
01M5T18K1YFBYA7MM1BBRV869A).
Символьные ссылки и подмодули — записи дерева с режимами 120000 и 160000.
Сбой git — подменённый `subprocess.run`, отвечающий кодом 128 и stderr с
уникальной строкой на git-вызовы клона, где упомянут нужный путь. Имена
проекта, базы, компонента, файлов и их тексты выбираются модулем `random`;
зерно печатается и входит в текст провала.

Эталон прежнего вывода (AC-9, AC-10) записан явным текстом на
фиксированном входе: проект `ETALON_PROJECT`, база `ETALON_BASE`,
`conventions.md` пульта — `ETALON_CLAUDE`, `brief.new_run_id` отдаёт
`ETALON_RUN_ID`; от эталона, снятого с кода до задачи 01M5T18K1YFBYA7MM1BBRV869A,
он отличается только тем, что куски `CLAUDE.md`/`AGENTS.md` базы и их
пометки заменены компонентом `conventions.md`. Эталон — склейка
кусков `_project_conventions_parts` переводом строки (так их склеивают все
пять потребителей) в трёх способах оформления; тест ищет его в собранном
тексте и требует, чтобы вне него не было ни упоминания проекта, ни слова
`knowledge`, ни пометок конвенций.

Файл провалидирован временным стабом реализации в `orchestrator/brief.py`
(чтение `knowledge` единственного компонента при `decide(...).profile.
from_components`, `ls-tree -z`, предел, пометки, убирание повторов); все
методы зелёные. Мутации стаба: `ls-tree` без `-z` красит AC-7; обход
`decide` чтением `components(target)[0]` красит AC-10 (несколько
компонентов, отказ `decide`, исключение `decide`); убирание повторов после
предела красит AC-3 (повторы до предела); путь с пометкой в «показанных»
красит AC-6 (пометки). Стаб удалён, код репозитория не тронут.
"""
import os
import random
import re
import string
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import brief, config, project_profile, review, store, targets
from tests.sandbox import RealGitSandbox, make_project_repo

ABSENT_MARK = brief.PROJECT_CONVENTIONS_ABSENT_MARK
UNREAD_MARK = brief.PROJECT_CONVENTIONS_UNREAD_MARK
TRUNCATED_ACTION = "бриф: документы knowledge сокращены"
DOCS_REF_PREFIX = "refs/artifacts/"
ULID_CHARS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

BUILDERS = {
    "developer": "developer_brief",
    "spec_auditor": "spec_auditor_brief",
    "analyst": "analyst_map_component",
    "test_author": "test_author_answer_component",
}
MANIFEST_ROLES = ("developer", "spec_auditor")
JOURNAL_ROLES = ("analyst", "test_author")
ALL_ROLES = (*BUILDERS, "reviewer")

ENTRY_HEAD = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""
PROFILE_FIELDS = (
    ("command", "[python3, -m, pytest]"),
    ("long_lived_dir", "tests"),
    ("long_lived_name", "test_<id>_<name>.py"),
    ("weakening_scope", "[tests/**/*.py]"),
    ("mutation_claim_scope", "[tests/test_*.py]"),
)

ETALON_PROJECT = "uchebnyetalon"
ETALON_BASE = "osnova-etalon"
ETALON_COMPONENT = "yadro"
ETALON_RUN_ID = "0123456789abcdef0123456789abcdef"
ETALON_CLAUDE = ("# Конвенции учебного проекта\n\n"
                 "Правило проекта: тесты рядом с кодом.\n")

# Склейка кусков `_project_conventions_parts` переводом строки —
# оформление `_journal_component` (analyst, test_author).
ETALON_JOURNAL = (
    '### conventions.md (.artel/projects/uchebnyetalon/conventions.md)\n'
    '\n'
    '=== ГРАНИЦА НЕДОВЕРЕННЫХ ДАННЫХ 0123456789abcdef0123456789abcdef ===\n'
    '# Конвенции учебного проекта\n'
    '\n'
    'Правило проекта: тесты рядом с кодом.\n'
    '=== КОНЕЦ ГРАНИЦЫ НЕДОВЕРЕННЫХ ДАННЫХ 0123456789abcdef0123456789abcdef ===\n'
)
# То же — оформление `_manifest_component` (developer, spec_auditor).
ETALON_MANIFEST = (
    '### conventions.md (.artel/projects/uchebnyetalon/conventions.md) — 122 '
    'байт, sha256=52d5db695cef072cdca2f7227787e01faf1ab0167d846fc7e8a574bad85'
    '01f14\n'
    '\n'
    '=== ГРАНИЦА НЕДОВЕРЕННЫХ ДАННЫХ 0123456789abcdef0123456789abcdef ===\n'
    '# Конвенции учебного проекта\n'
    '\n'
    'Правило проекта: тесты рядом с кодом.\n'
    '=== КОНЕЦ ГРАНИЦЫ НЕДОВЕРЕННЫХ ДАННЫХ 0123456789abcdef0123456789abcdef ===\n'
)
# То же — оформление `review._conventions_component` (пакет ревьювера);
# у этого входа побайтно совпадает с описью `_manifest_component`, но
# держится отдельным литералом: способы оформления вправе разойтись.
ETALON_REVIEW = (
    '### conventions.md (.artel/projects/uchebnyetalon/conventions.md) — 122 '
    'байт, sha256=52d5db695cef072cdca2f7227787e01faf1ab0167d846fc7e8a574bad85'
    '01f14\n'
    '\n'
    '=== ГРАНИЦА НЕДОВЕРЕННЫХ ДАННЫХ 0123456789abcdef0123456789abcdef ===\n'
    '# Конвенции учебного проекта\n'
    '\n'
    'Правило проекта: тесты рядом с кодом.\n'
    '=== КОНЕЦ ГРАНИЦЫ НЕДОВЕРЕННЫХ ДАННЫХ 0123456789abcdef0123456789abcdef ===\n'
)
ETALONS = {"developer": ETALON_MANIFEST, "spec_auditor": ETALON_MANIFEST,
           "analyst": ETALON_JOURNAL, "test_author": ETALON_JOURNAL,
           "reviewer": ETALON_REVIEW}


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


def boundary_markers(run_id: str) -> tuple[str, str]:
    """Открывающий и закрывающий маркеры границ `run_id` — из самой
    `brief.wrap_boundary`, без знания их формы."""
    probe = "\x00ТЕЛО\x00"
    head, tail = brief.wrap_boundary(run_id, probe).split(probe)
    return head.strip(), tail.strip()


class KnowledgeSandbox(RealGitSandbox):
    """Пульт и учебный внешний проект на настоящем git; задача проекта со
    SPEC.md и TZ.md в ссылке документов клона."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.run_id = "".join(self.rng.choices("0123456789abcdef", k=32))
        self.git_fail = None
        self.stderr_nonce = f"STDERR-{word(self.rng, 12)}"
        self.extra_env = {}

    # ------------------------------------------------------------ обвязка

    def note(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def cgit(self, *args: str) -> str:
        return self.git("-C", str(self.clone), *args)

    def doc(self, tag: str) -> str:
        return (f"# {tag} {word(self.rng, 6)}\n\n"
                f"Текст документа {word(self.rng, 16)}.\n")

    def component_block(self, name: str, fields: list) -> str:
        return f"      {name}:\n" + "".join(
            f"        {key}: {value}\n" for key, value in fields)

    def entry(self, record: str, knowledge) -> str:
        text = ENTRY_HEAD.format(name=self.project, base=self.base)
        kn = ([("knowledge", "[" + ", ".join(knowledge) + "]")]
              if knowledge is not None else [])
        if record == "test_profile":
            return text + "    test_profile:\n" + "".join(
                f"      {key}: {value}\n" for key, value in PROFILE_FIELDS)
        if record == "bare":
            return text
        if record == "component":
            return text + "    components:\n" + self.component_block(
                self.component, [*PROFILE_FIELDS, *kn])
        if record == "refused":
            fields = [f for f in PROFILE_FIELDS if f[0] != "command"]
            return text + "    components:\n" + self.component_block(
                self.component, [*fields, *kn])
        if record == "multi":
            return text + "    components:\n" + "".join(
                self.component_block(name, [*PROFILE_FIELDS,
                                            ("paths", f"[{name}/.*]"), *kn])
                for name in (self.component, f"{self.component}b"))
        raise AssertionError(record)

    def prepare(self, files: dict, knowledge=None, *, record: str = "component",
                links: dict | None = None, gitlinks=(), fixed: bool = False,
                branch_files: dict | None = None,
                tree_files: dict | None = None) -> None:
        """Учебный проект: `files` (путь -> str | bytes), символьные ссылки
        `links` (путь -> цель) и подмодули `gitlinks` — в коммите базовой
        ветки клона; запись проекта вида `record` с полем `knowledge`;
        ветка задачи отведена от базы (её версии файлов — `branch_files`),
        клон стоит на `main` с файлами `tree_files` в рабочем дереве;
        `conventions.md` пульта — `ETALON_CLAUDE` у `fixed`, иначе
        уникальный текст."""
        if fixed:
            self.project, self.base = ETALON_PROJECT, ETALON_BASE
            self.component = ETALON_COMPONENT
            self.run_id = ETALON_RUN_ID
        else:
            self.project = f"uchebny{word(self.rng)}"
            self.base = f"osnova-{word(self.rng)}"
            self.component = f"komp{word(self.rng, 5)}"
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(
            text.rstrip("\n") + "\n" + self.entry(record, knowledge),
            encoding="utf-8")
        self.clone = make_project_repo(self.project, origin=False)
        self.cgit("checkout", "-q", "-b", self.base)
        (self.clone / "README.md").write_text(
            f"# Учебный проект {self.project}\n", encoding="utf-8")
        for rel, body in files.items():
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(body, bytes):
                path.write_bytes(body)
            else:
                path.write_text(body, encoding="utf-8")
        for rel, target in (links or {}).items():
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(target, path)
        self.cgit("add", "-A")
        head = self.cgit("rev-parse", "HEAD").strip()
        for rel in gitlinks:
            self.cgit("update-index", "--add", "--cacheinfo",
                      f"160000,{head},{rel}")
        self.cgit("commit", "-q", "-m", "база проекта")

        self.task = "01" + "".join(self.rng.choices(ULID_CHARS, k=24))
        self.branch = f"task/{self.task.lower()}-uchebnaya"
        self.cgit("checkout", "-q", "-b", self.branch)
        for rel, body in (branch_files or {}).items():
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        (self.clone / "kod.py").write_text(
            f"ZNACHENIE = {self.rng.randrange(10 ** 6)!r}\n", encoding="utf-8")
        self.cgit("add", "-A")
        self.cgit("commit", "-q", "-m", "правка задачи")
        self.cgit("checkout", "-q", "-f", config.MAIN_BRANCH)
        for rel, body in (tree_files or {}).items():
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")

        store.insert_task(self.conn, self.task, "Учебная задача", "in_dev",
                          self.branch, self.project, 25.0)
        self.commit_docs({
            "SPEC.md": f"# SPEC\n\nSPEC учебной задачи {word(self.rng, 12)}.\n",
            "TZ.md": f"# ТЗ\n\nТЗ учебной задачи {word(self.rng)}.\n"})
        self.pult_text = (ETALON_CLAUDE if fixed
                          else self.doc("Конвенции пульта"))
        (config.PROJECTS / self.project / "conventions.md").write_text(
            self.pult_text, encoding="utf-8")

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

    # -------------------------------------------------------- подмена git

    def spy(self):
        """`subprocess.run`: git-вызов клона, для которого `self.git_fail(текст
        вызова)` истинно, отвечает кодом 128 и stderr с уникальной строкой."""
        real = subprocess.run
        clone = str(self.clone.resolve())
        case = self

        def run(cmd, *args, **kwargs):
            argv = [str(p) for p in cmd] if isinstance(cmd, (list, tuple)) \
                else [str(cmd)]
            if (case.git_fail is not None and argv
                    and Path(argv[0]).name == "git"
                    and git_repo_of(argv, kwargs) == clone
                    and case.git_fail(call_text(argv, kwargs))):
                err = f"fatal: {case.stderr_nonce}\n"
                textual = (kwargs.get("text") or kwargs.get("universal_newlines")
                           or kwargs.get("encoding"))
                if textual:
                    return subprocess.CompletedProcess(cmd, 128, "", err)
                return subprocess.CompletedProcess(cmd, 128, b"", err.encode())
            return real(cmd, *args, **kwargs)

        return mock.patch.object(subprocess, "run", run)

    # ------------------------------------------------------------- сборка

    def build(self, role: str) -> dict:
        """Бриф роли (или пакет ревьювера): текст, текст отказа
        `SystemExit`, новые записи журнала задачи."""
        rows = store.task_steps(self.conn, self.task)
        mark = rows[-1]["id"] if rows else 0
        text, refusal = None, None
        with mock.patch.object(brief, "new_run_id", return_value=self.run_id), \
                mock.patch.dict(os.environ, self.extra_env), self.spy():
            try:
                if role == "reviewer":
                    text = review.review_package(self.conn, self.task,
                                                 "Учебная задача",
                                                 self.branch)["text"]
                else:
                    text = getattr(brief, BUILDERS[role])(self.conn, self.task)
            except SystemExit as exc:
                refusal = str(exc.code)
        new_rows = [r for r in store.task_steps(self.conn, self.task)
                    if r["id"] > mark]
        return {"text": text, "refusal": refusal, "rows": new_rows}

    def text_of(self, role: str) -> str:
        built = self.build(role)
        self.assertIsNone(built["refusal"], self.note(
            f"{role}: сборка отказала: {built['refusal']}"))
        self.assertIsNotNone(built["text"], self.note(f"{role}: текста нет"))
        return built["text"]

    # ------------------------------------------------------------ сверки

    def outside(self, text: str) -> str:
        """Текст без блоков внутри границ `run_id` (маркеры включительно)."""
        opener, closer = boundary_markers(self.run_id)
        return re.sub(re.escape(opener) + r".*?" + re.escape(closer), "",
                      text, flags=re.S)

    def chunk(self, text: str, fragment: str) -> tuple[str, str]:
        """(строка заголовка `### …`, тело внутри границы) куска, в теле
        которого стоит `fragment`."""
        opener, closer = boundary_markers(self.run_id)
        pos = text.find(fragment)
        self.assertGreaterEqual(pos, 0, self.note(f"нет текста {fragment!r}"))
        start = text.rfind(opener, 0, pos)
        self.assertGreaterEqual(start, 0, self.note(
            f"текст {fragment!r} вне границы недоверенных данных"))
        self.assertNotIn(closer, text[start:pos], self.note(
            f"текст {fragment!r} вне границы недоверенных данных"))
        end = text.find(closer, pos)
        self.assertGreater(end, pos, self.note(f"граница {fragment!r} не закрыта"))
        body = text[start + len(opener):end].strip("\n")
        head_end = text.rfind("\n### ", 0, start)
        self.assertGreaterEqual(head_end, 0, self.note(
            f"у текста {fragment!r} нет заголовка куска"))
        header = text[head_end + 1:text.index("\n", head_end + 1)]
        return header, body

    def header_pos(self, text: str, header_start: str) -> int:
        pos = text.find("\n### " + header_start)
        self.assertGreaterEqual(pos, 0, self.note(
            f"нет заголовка «### {header_start}»"))
        return pos

    def file_label(self, path: str) -> str:
        return (f"{path} (knowledge компонента {self.component}, ветка "
                f"{self.base} проекта {self.project})")

    def dir_label(self, element: str, k: int, m: int) -> str:
        return (f"knowledge компонента {self.component}, каталог {element}, "
                f"документ {k} из {m} (ветка {self.base} проекта "
                f"{self.project})")

    def lines_with(self, text: str, *needles: str) -> list:
        return [line for line in text.splitlines()
                if all(n in line for n in needles)]

    def journal_text(self, rows: list) -> list:
        return [f"{r['action']}: {r['detail'] or ''}" for r in rows]

    def assert_journaled(self, rows: list, phrase: str) -> None:
        journal = self.journal_text(rows)
        self.assertTrue(any(phrase in entry for entry in journal), self.note(
            f"в журнале нет записи с «{phrase}»:\n" + "\n".join(journal)))

    def assert_etalon(self, role: str, text: str, hidden=()) -> None:
        """Эталон прежнего вывода стоит в тексте целиком; вне него — ни
        упоминания проекта, ни `knowledge`, ни пометок конвенций, ни текстов
        `hidden`."""
        etalon = ETALONS[role]
        pos = text.find(etalon)
        self.assertGreaterEqual(pos, 0, self.note(
            f"{role}: в тексте нет эталона прежнего вывода конвенций"))
        rest = text[:pos] + text[pos + len(etalon):]
        for needle in (f"проекта {self.project}", "knowledge", ABSENT_MARK,
                       UNREAD_MARK, *hidden):
            self.assertNotIn(needle, rest, self.note(
                f"{role}: вне эталона «{needle}»"))


# ----------------------------------------------------------------- AC-1

class ElementFileTest(KnowledgeSandbox):

    def test_ac1_element_files_after_conventions_in_record_order(self):
        """Компонент с `knowledge: [<подкаталог>/<файл>, <файл корня>]`.

        `conventions.md` пульта — текст эталона, в корне базы `CLAUDE.md`,
        `AGENTS.md` нет; два элемента-файла — в подкаталоге и в корне, их
        другие версии лежат на ветке задачи и в рабочем дереве клона. В
        добавке test_author и брифе developer: компонент `conventions.md`
        побайтно (эталон), за ним — куски элементов в порядке записи;
        заголовок куска — «<путь> (knowledge компонента <имя>, ветка <base>
        проекта <target>)», тело — текст коммита базы.

        Ловит мутацию: элементы `knowledge` не читаются, либо куски
        вставлены перед `conventions.md`, либо отсортированы вместо порядка
        записи, либо текст взят с ветки задачи или рабочего дерева, либо
        путь в подкаталоге не найден (`ls-tree` без пути) — в тексте нет
        куска элемента, порядок или текст другие."""
        deep = f"pravila/{word(self.rng, 5)}/stil.md"
        top = "rukovodstvo.md"
        texts = {deep: self.doc("Стиль"), top: self.doc("Руководство")}
        self.prepare({"CLAUDE.md": ETALON_CLAUDE, **texts}, [deep, top],
                     fixed=True,
                     branch_files={p: self.doc("Ветка задачи") for p in texts},
                     tree_files={p: self.doc("Рабочее дерево") for p in texts})
        for role in ("test_author", "developer"):
            with self.subTest(роль=role):
                text = self.text_of(role)
                etalon = ETALONS[role]
                pos = text.find(etalon)
                self.assertGreaterEqual(pos, 0, self.note(
                    f"{role}: компонент conventions.md не побайтно"))
                previous = pos + len(etalon)
                for path in (deep, top):
                    header, body = self.chunk(text, texts[path].strip())
                    label = "### " + self.file_label(path)
                    if role in JOURNAL_ROLES:
                        self.assertEqual(header, label, self.note(role))
                    else:
                        self.assertTrue(header.startswith(label + " — "),
                                        self.note(f"{role}: {header}"))
                    self.assertEqual(body.strip(), texts[path].strip(),
                                     self.note(f"{role}: тело {path}"))
                    at = text.find(texts[path].strip())
                    self.assertGreater(at, previous, self.note(
                        f"{role}: кусок {path} не после предыдущего"))
                    previous = at


# ----------------------------------------------------------------- AC-2

class ElementDirTest(KnowledgeSandbox):

    def test_ac2_dir_element_md_files_sorted_paths_inside_boundary(self):
        """Компонент с `knowledge: [docs/]`; под `docs/` — три `*.md` (один
        в подкаталоге), `*.txt` и `*.py`.

        В добавке test_author и брифе developer — куски трёх `*.md` в
        порядке путей, заголовок «knowledge компонента <имя>, каталог docs/,
        документ <k> из 3 (ветка <base> проекта <target>)», первая строка
        тела — «путь: <путь>», далее текст файла; текста `*.txt`/`*.py` нет;
        имён файлов каталога нет ни вне границ, ни в записях журнала.

        Ловит мутацию: каталог читается без `-r` (файл подкаталога
        пропал), фильтр `*.md` снят (виден текст `*.txt`), порядок не по
        пути, M посчитан до фильтра, путь файла выведен в заголовок или в
        запись журнала «бриф: компонент» — нарушается одна из сверок."""
        names = sorted({word(self.rng, 6) for _ in range(6)})[:3]
        sub = f"sub{word(self.rng, 4)}"
        paths = sorted([f"docs/{names[0]}.md", f"docs/{names[1]}.md",
                        f"docs/{sub}/{names[2]}.md"])
        texts = {p: self.doc("Документ") for p in paths}
        noise = {f"docs/{word(self.rng)}.txt": self.doc("Не md"),
                 f"docs/{word(self.rng)}.py": f"# {word(self.rng, 12)}\n"}
        files = dict(texts, **noise)
        shuffled = list(files.items())
        self.rng.shuffle(shuffled)
        self.prepare(dict(shuffled), ["docs/"])
        for role in ("test_author", "developer"):
            with self.subTest(роль=role):
                built = self.build(role)
                self.assertIsNone(built["refusal"], self.note(str(built["refusal"])))
                text = built["text"]
                previous = -1
                for k, path in enumerate(paths, start=1):
                    header, body = self.chunk(text, texts[path].strip())
                    label = "### " + self.dir_label("docs/", k, len(paths))
                    if role in JOURNAL_ROLES:
                        self.assertEqual(header, label, self.note(role))
                    else:
                        self.assertTrue(header.startswith(label + " — "),
                                        self.note(f"{role}: {header}"))
                    first, _, rest = body.partition("\n")
                    self.assertEqual(first, f"путь: {path}", self.note(role))
                    self.assertIn(texts[path].strip(), rest, self.note(role))
                    at = text.find(texts[path].strip())
                    self.assertGreater(at, previous, self.note(
                        f"{role}: {path} не в порядке путей"))
                    previous = at
                for path, body in noise.items():
                    self.assertNotIn(body.strip(), text, self.note(
                        f"{role}: показан не *.md {path}"))
                outside = self.outside(text)
                journal = "\n".join(self.journal_text(built["rows"]))
                for path in paths:
                    name = path.rsplit("/", 1)[1]
                    self.assertNotIn(name, outside, self.note(
                        f"{role}: имя {name} вне границы"))
                    self.assertNotIn(name, journal, self.note(
                        f"{role}: имя {name} в журнале"))


# ----------------------------------------------------------------- AC-3

class DirLimitTest(KnowledgeSandbox):

    def dir_files(self, count: int) -> dict:
        names = set()
        while len(names) < count:
            names.add(word(self.rng, 7))
        return {f"docs/{name}.md": self.doc("Документ") for name in names}

    def test_ac3_dir_over_limit_shows_first_files_line_and_journal(self):
        """Компонент с `knowledge: [docs/, <файл>]`; в `docs/` —
        `KNOWLEDGE_DIR_MAX_FILES` + 1..3 файлов `*.md`.

        Показаны первые по пути `KNOWLEDGE_DIR_MAX_FILES` файлов (подписи
        «документ <k> из <предел>»), остальных текстов нет; строка
        «документы knowledge: каталог docs/ — показаны первые <предел>
        файлов из <N>» стоит после последнего куска каталога и до куска
        следующего элемента; в журнале — запись «бриф: документы knowledge
        сокращены» с `docs/` и N в детали.

        Ловит мутацию: предел не применён (показаны все), отрезаны не
        последние по пути, строка предела потеряна или стоит до кусков
        каталога, запись журнала не заведена или без N."""
        limit = brief.KNOWLEDGE_DIR_MAX_FILES
        extra = self.rng.randint(1, 3)
        texts = self.dir_files(limit + extra)
        tail = f"{word(self.rng)}.md"
        tail_text = self.doc("Следующий элемент")
        self.prepare(dict(texts, **{tail: tail_text}), ["docs/", tail])
        built = self.build("test_author")
        self.assertIsNone(built["refusal"], self.note(str(built["refusal"])))
        text = built["text"]
        paths = sorted(texts)
        for k, path in enumerate(paths[:limit], start=1):
            header, _ = self.chunk(text, texts[path].strip())
            self.assertEqual(header, "### " + self.dir_label("docs/", k, limit),
                             self.note(path))
        for path in paths[limit:]:
            self.assertNotIn(texts[path].strip(), text, self.note(
                f"показан файл сверх предела {path}"))
        line = (f"документы knowledge: каталог docs/ — показаны первые "
                f"{limit} файлов из {limit + extra}")
        outside = self.outside(text)
        self.assertTrue(self.lines_with(outside, line), self.note(
            f"нет строки «{line}»"))
        at = text.find(line)
        last = text.find(texts[paths[limit - 1]].strip())
        self.assertGreater(at, last, self.note("строка предела до кусков каталога"))
        self.assertLess(at, text.find(tail_text.strip()), self.note(
            "строка предела после куска следующего элемента"))
        rows = [r for r in built["rows"] if r["action"] == TRUNCATED_ACTION]
        self.assertTrue(rows, self.note(f"нет записи журнала «{TRUNCATED_ACTION}»"))
        self.assertTrue(any("docs/" in (r["detail"] or "")
                            and str(limit + extra) in (r["detail"] or "")
                            for r in rows), self.note(
            f"деталь без docs/ и N: {[r['detail'] for r in rows]}"))

    def test_ac3_shown_paths_removed_before_limit(self):
        """Компонент с `knowledge: [docs/<первый>.md, docs/]`; в `docs/` —
        `KNOWLEDGE_DIR_MAX_FILES` + 1 файлов `*.md`.

        Первый файл показан один раз (элементом-файлом); каталог после
        убирания повтора укладывается в предел: показаны все остальные с
        подписью «из <предел>», строки «показаны первые» и записи журнала о
        сокращении нет.

        Ловит мутацию: повтор убирается после отсчёта предела — каталог
        считается переполненным, последний файл отрезан, появляется строка
        предела; либо повтор не убран — текст первого файла дважды."""
        limit = brief.KNOWLEDGE_DIR_MAX_FILES
        texts = self.dir_files(limit + 1)
        paths = sorted(texts)
        self.prepare(texts, [paths[0], "docs/"])
        built = self.build("test_author")
        self.assertIsNone(built["refusal"], self.note(str(built["refusal"])))
        text = built["text"]
        self.assertEqual(text.count(texts[paths[0]].strip()), 1, self.note(
            "первый файл показан не один раз"))
        for k, path in enumerate(paths[1:], start=1):
            header, _ = self.chunk(text, texts[path].strip())
            self.assertEqual(header, "### " + self.dir_label("docs/", k, limit),
                             self.note(path))
        self.assertNotIn("показаны первые", text, self.note("строка предела"))
        self.assertFalse([r for r in built["rows"]
                          if r["action"] == TRUNCATED_ACTION],
                         self.note("запись о сокращении"))


# ----------------------------------------------------------------- AC-4

class NonRegularInDirTest(KnowledgeSandbox):

    def test_ac4_symlinks_submodules_skipped_and_dir_without_md(self):
        """Компонент с `knowledge: [docs/, <каталог без md>/]`; в `docs/` —
        обычный `*.md`, символьная ссылка `*.md` на него и подмодуль с
        именем `*.md`; во втором каталоге — только `*.txt`.

        Ссылка и подмодуль в документы не входят и в счёт не идут
        (обычный файл подписан «документ 1 из 1»); строка «документы
        knowledge: каталог docs/ — пропущено не обычных файлов: 2»; имён
        ссылки и подмодуля нет ни в тексте, ни в журнале; строка «документы
        knowledge: каталог <второй>/ — файлов *.md нет».

        Ловит мутацию: режимы 120000/160000 не отсеиваются (ссылка
        показана вторым документом, M = 2 или 3), строка о пропуске не
        выведена или с именами, каталог без `*.md` молча пропущен."""
        regular = f"docs/{word(self.rng)}.md"
        link = f"docs/ssylka{word(self.rng)}.md"
        sub = f"docs/podmodul{word(self.rng)}.md"
        empty = f"pusto{word(self.rng, 5)}"
        body = self.doc("Обычный")
        self.prepare({regular: body,
                      f"{empty}/{word(self.rng)}.txt": self.doc("txt")},
                     ["docs/", f"{empty}/"],
                     links={link: regular.rsplit("/", 1)[1]}, gitlinks=(sub,))
        mode = self.cgit("ls-tree", self.base, "--", link, sub)
        self.assertIn("120000", mode, self.note("фикстура: нет ссылки"))
        self.assertIn("160000", mode, self.note("фикстура: нет подмодуля"))
        for role in ("test_author", "developer"):
            with self.subTest(роль=role):
                built = self.build(role)
                self.assertIsNone(built["refusal"], self.note(str(built["refusal"])))
                text = built["text"]
                header, _ = self.chunk(text, body.strip())
                self.assertTrue(header.startswith(
                    "### " + self.dir_label("docs/", 1, 1)), self.note(header))
                self.assertEqual(text.count(body.strip()), 1, self.note(
                    "текст обычного файла не один раз (ссылка показана)"))
                outside = self.outside(text)
                for line in ("документы knowledge: каталог docs/ — пропущено "
                             "не обычных файлов: 2",
                             f"документы knowledge: каталог {empty}/ — файлов "
                             f"*.md нет"):
                    self.assertTrue(self.lines_with(outside, line), self.note(
                        f"{role}: нет строки «{line}»"))
                journal = "\n".join(self.journal_text(built["rows"]))
                for name in (link, sub):
                    short = name.rsplit("/", 1)[1]
                    self.assertNotIn(short, text, self.note(f"{role}: {short}"))
                    self.assertNotIn(short, journal, self.note(
                        f"{role}: {short} в журнале"))


# ----------------------------------------------------------------- AC-5

class ElementKindMarksTest(KnowledgeSandbox):

    def test_ac5_wrong_kind_elements_marked_and_journaled(self):
        """Компонент с `knowledge: [<каталог без «/»>, <файл>/, <ссылка>,
        <подмодуль>]`.

        Пометки: «конвенции проекта не прочитаны: <каталог>: каталог —
        элемент-каталог пишется с «/» на конце»; «… <файл>/: не каталог —
        элемент-файл пишется без «/»»; у ссылки и подмодуля — «конвенции
        проекта не прочитаны» с элементом и причиной «не обычный файл»; у
        каждой — запись журнала с той же причиной.

        Ловит мутацию: элемент без «/», оказавшийся каталогом, помечен
        «файла нет» или прочитан как каталог; «/» у файла молча снят и файл
        показан; ссылка разыменована и показана как файл; пометка без
        записи журнала."""
        folder = f"spravka{word(self.rng, 4)}"
        guide = f"rukovodstvo{word(self.rng, 4)}.md"
        link = f"ssylka{word(self.rng, 4)}.md"
        sub = f"podmodul{word(self.rng, 4)}"
        guide_text = self.doc("Руководство")
        self.prepare({f"{folder}/{word(self.rng)}.md": self.doc("Справка"),
                      guide: guide_text},
                     [folder, f"{guide}/", link, sub],
                     links={link: guide}, gitlinks=(sub,))
        for role in ("test_author", "developer"):
            with self.subTest(роль=role):
                built = self.build(role)
                self.assertIsNone(built["refusal"], self.note(str(built["refusal"])))
                text, rows = built["text"], built["rows"]
                for phrase in (
                        f"{folder}: каталог — элемент-каталог пишется с «/» "
                        f"на конце",
                        f"{guide}/: не каталог — элемент-файл пишется без «/»"):
                    self.assertTrue(self.lines_with(
                        text, f"{UNREAD_MARK}: {phrase}"), self.note(
                        f"{role}: нет пометки «{UNREAD_MARK}: {phrase}»"))
                    self.assert_journaled(rows, phrase)
                for element in (link, sub):
                    lines = self.lines_with(text, UNREAD_MARK, element,
                                            "не обычный файл")
                    self.assertTrue(lines, self.note(
                        f"{role}: нет пометки «не обычный файл» у {element}"))
                    self.assertTrue(any(
                        element in entry and "не обычный файл" in entry
                        for entry in self.journal_text(rows)), self.note(
                        f"{role}: нет записи журнала у {element}"))
                self.assertNotIn(guide_text.strip(), text, self.note(
                    f"{role}: файл показан по элементу с «/» или по ссылке"))


# ----------------------------------------------------------------- AC-6

class RepeatsAndMarksTest(KnowledgeSandbox):

    def test_ac6_shown_paths_not_repeated(self):
        """Компонент с `knowledge: [./<файл корня>.md, docs/<a>.md, docs/,
        <файл корня>.md]`; в базе нейтральный файл корня (вне обвязки),
        `docs/<a>.md`, `docs/<b>.md`.

        Текст файла корня и текст `docs/<a>.md` — по одному разу; кусок
        каталога — только `docs/<b>.md` с подписью «документ 1 из 1»;
        второго заголовка «<файл корня>.md (knowledge компонента …» нет.

        Ловит мутацию: «./<файл корня>.md» не сведён к пути дерева, повтор
        между элементами не убран, каталог не учёл уже показанный файл
        (M = 2) — текст выведен дважды или подпись другая."""
        root_name = f"{word(self.rng)}.md"
        claude = self.doc("Корень")
        a_path, b_path = sorted(f"docs/{word(self.rng)}.md" for _ in range(2))
        a_text, b_text = self.doc("A"), self.doc("B")
        self.prepare({root_name: claude, a_path: a_text, b_path: b_text},
                     [f"./{root_name}", a_path, "docs/", root_name])
        for role in ("test_author", "developer"):
            with self.subTest(роль=role):
                text = self.text_of(role)
                self.assertEqual(text.count(claude.strip()), 1, self.note(role))
                self.assertEqual(text.count(a_text.strip()), 1, self.note(role))
                header, _ = self.chunk(text, b_text.strip())
                self.assertTrue(header.startswith(
                    "### " + self.dir_label("docs/", 1, 1)), self.note(header))
                self.assertEqual(len(self.lines_with(
                    text, f"### {root_name} (knowledge компонента")), 1,
                    self.note(role))

    def test_ac6_size_skip_in_render_counts_as_shown(self):
        """Нейтральный файл корня базы (вне обвязки) крупнее
        `config.CONTEXT_FILE_MAX_BYTES`; компонент с `knowledge: [<файл>.md,
        ./<файл>.md]`; бриф developer (оформление с потолком файла).

        Заголовок файла — один, с пропуском по размеру; второго куска
        `knowledge` на тот же путь нет.

        Ловит мутацию: «показанным» считается только кусок, вошедший в
        текст, — пропущенный по размеру файл выводится второй раз куском
        второго элемента."""
        root_name = f"{word(self.rng)}.md"
        filler = f"Строка правил {word(self.rng)} " + "ж" * 60 + "\n"
        count = config.CONTEXT_FILE_MAX_BYTES // len(filler.encode()) + 20
        claude = "# Большие правила\n\n" + filler * count
        self.prepare({root_name: claude}, [root_name, f"./{root_name}"])
        text = self.text_of("developer")
        headers = [line for line in text.splitlines()
                   if line.startswith("### ") and root_name in line]
        self.assertEqual(len(headers), 1, self.note(f"заголовки: {headers}"))
        self.assertIn("пропущен", headers[0], self.note(headers[0]))

    def test_ac6_marked_paths_not_counted_as_shown(self):
        """В корне базы файла `<нет>.md` нет, `<не-UTF-8>.md` — байты не
        UTF-8 (оба пути вне обвязки); компонент с `knowledge: [<нет>.md,
        ./<нет>.md, <не-UTF-8>.md, ./<не-UTF-8>.md]`.

        Пометка «файла нет» с `<нет>.md` — не меньше двух (по элементу на
        путь), пометка «конвенции проекта не прочитаны» с `<не-UTF-8>.md` —
        не меньше двух.

        Ловит мутацию: путь с пометкой заносится в «показанные» — второй
        элемент на тот же путь молча пропущен, вторая пометка не
        выведена."""
        absent = f"net{word(self.rng)}.md"
        broken = f"kodirovka{word(self.rng)}.md"
        raw = f"# Правила {word(self.rng)}\n".encode("cp1251")
        self.prepare({broken: raw},
                     [absent, f"./{absent}", broken, f"./{broken}"])
        text = self.text_of("test_author")
        self.assertGreaterEqual(len(self.lines_with(text, ABSENT_MARK,
                                                    absent)), 2,
                                self.note(text))
        self.assertGreaterEqual(len(self.lines_with(text, UNREAD_MARK,
                                                    broken)), 2,
                                self.note(text))

    def test_ac6_missing_element_file_marked_absent(self):
        """Компонент с `knowledge: [<путь>]`, пути в дереве базы нет.

        Есть пометка «файла нет» с этим путём; пометки «конвенции проекта
        не прочитаны» с ним нет.

        Ловит мутацию: отсутствие пути в дереве принято за сбой git
        (пометка «не прочитаны»), либо элемент молча пропущен."""
        missing = f"docs/{word(self.rng)}.md"
        self.prepare({"CLAUDE.md": self.doc("CLAUDE")}, [missing])
        text = self.text_of("test_author")
        self.assertTrue(self.lines_with(text, ABSENT_MARK, missing),
                        self.note(text))
        self.assertFalse(self.lines_with(text, UNREAD_MARK, missing),
                         self.note(text))

    def test_ac6_element_file_non_utf8_and_git_failure_marked_unread(self):
        """Элемент-файл — байты не UTF-8 (сценарий 1) либо `git` на его
        чтении отвечает кодом 128 (сценарий 2).

        Пометка «конвенции проекта не прочитаны» с путём элемента и запись
        журнала с ним; текста элемента и пометки «файла нет» с ним нет.

        Ловит мутацию: сбой чтения элемента помечен «файла нет» или пропущен
        молча, либо пометка без записи журнала, либо `UnicodeDecodeError`
        роняет сборку."""
        for scenario in ("utf8", "git"):
            with self.subTest(сценарий=scenario):
                element = f"{word(self.rng)}.md"
                body = self.doc("Элемент")
                data = (body.encode("cp1251") if scenario == "utf8"
                        else body)
                self.prepare({element: data}, [element])
                if scenario == "git":
                    self.git_fail = lambda call, e=element: e in call
                built = self.build("test_author")
                self.git_fail = None
                self.assertIsNone(built["refusal"], self.note(str(built["refusal"])))
                text = built["text"]
                self.assertTrue(self.lines_with(text, UNREAD_MARK, element),
                                self.note(text))
                self.assertFalse(self.lines_with(text, ABSENT_MARK, element),
                                 self.note(text))
                self.assertNotIn(body.strip(), text, self.note(scenario))
                self.assert_journaled(built["rows"], element)

    def test_ac6_dir_file_failure_marked_without_path_and_stderr(self):
        """Файл элемента-каталога — байты не UTF-8 (класс «текст не в
        UTF-8») либо `git` на его чтении отвечает кодом 128 со stderr
        (класс «сбой git»); соседние файлы каталога читаются.

        Пометка «конвенции проекта не прочитаны: каталог docs/, документ
        <k>: <класс>» и запись журнала с той же строкой; ни в пометке, ни в
        тексте вне границ, ни в журнале нет имени файла и stderr git;
        соседи показаны.

        Ловит мутацию: пометка каталога собрана прежним путём — с путём
        файла или причиной git со stderr; класс причины перепутан; запись
        журнала не заведена."""
        for scenario, reason in (("utf8", "текст не в UTF-8"),
                                 ("git", "сбой git")):
            with self.subTest(сценарий=scenario):
                names = sorted({word(self.rng) for _ in range(5)})[:3]
                paths = [f"docs/{name}.md" for name in names]
                texts = {p: self.doc("Документ") for p in paths}
                bad = paths[1]
                files = dict(texts)
                if scenario == "utf8":
                    files[bad] = texts[bad].encode("cp1251")
                self.prepare(files, ["docs/"])
                if scenario == "git":
                    self.git_fail = lambda call, b=bad: b in call
                built = self.build("test_author")
                self.git_fail = None
                self.assertIsNone(built["refusal"], self.note(str(built["refusal"])))
                text = built["text"]
                pattern = re.compile(
                    re.escape(f"{UNREAD_MARK}: каталог docs/, документ ")
                    + r"\d+" + re.escape(f": {reason}"))
                marks = [line for line in text.splitlines()
                         if pattern.search(line)]
                self.assertTrue(marks, self.note(
                    f"нет пометки «{UNREAD_MARK}: каталог docs/, документ "
                    f"<k>: {reason}»:\n{text}"))
                phrase = pattern.search(marks[0]).group(0).split(": ", 1)[1]
                self.assert_journaled(built["rows"], phrase)
                outside = self.outside(text)
                journal = "\n".join(self.journal_text(built["rows"]))
                short = bad.rsplit("/", 1)[1]
                for where, blob in (("вне границ", outside),
                                    ("в журнале", journal)):
                    self.assertNotIn(short, blob, self.note(
                        f"имя файла {where}"))
                    self.assertNotIn(self.stderr_nonce, blob, self.note(
                        f"stderr git {where}"))
                for path in paths:
                    if path != bad:
                        self.assertIn(texts[path].strip(), text,
                                      self.note(f"сосед {path} не показан"))


# ----------------------------------------------------------------- AC-7

class CyrillicNamesTest(KnowledgeSandbox):

    def test_ac7_cyrillic_file_and_dir_names_read_from_base(self):
        """Компонент с `knowledge: [<кириллический файл>.md, <кириллический
        каталог>/]`; git прогона принудительно с `core.quotePath=true`
        (`GIT_CONFIG_*`), так что вывод `ls-tree` без `-z` экранирует
        имена.

        Тексты обоих файлов в брифе test_author и developer; пометок
        «файла нет» и «конвенции проекта не прочитаны» нет; первая строка
        куска файла каталога — «путь: <кириллический путь>».

        Ловит мутацию: состав дерева читается `ls-tree` без `-z` — имя
        приходит в кавычках с восьмеричными escape, файл помечен «файла
        нет»."""
        top = f"правила-{self.rng.choice(['проекта', 'команды', 'стиля'])}.md"
        folder = f"документы{self.rng.randrange(100)}"
        inner = f"{folder}/обзор-{self.rng.choice(['кода', 'тестов'])}.md"
        top_text, inner_text = self.doc("Правила"), self.doc("Обзор")
        self.prepare({"CLAUDE.md": self.doc("CLAUDE"),
                      "AGENTS.md": self.doc("AGENTS"),
                      top: top_text, inner: inner_text}, [top, f"{folder}/"])
        self.extra_env = {"GIT_CONFIG_COUNT": "1",
                          "GIT_CONFIG_KEY_0": "core.quotePath",
                          "GIT_CONFIG_VALUE_0": "true"}
        for role in ("test_author", "developer"):
            with self.subTest(роль=role):
                text = self.text_of(role)
                self.assertIn(top_text.strip(), text, self.note(role))
                _, body = self.chunk(text, inner_text.strip())
                self.assertEqual(body.partition("\n")[0], f"путь: {inner}",
                                 self.note(role))
                self.assertFalse(self.lines_with(text, ABSENT_MARK),
                                 self.note(text))
                self.assertFalse(self.lines_with(text, UNREAD_MARK),
                                 self.note(text))


# ----------------------------------------------------------------- AC-8

class UnreadBaseTest(KnowledgeSandbox):

    def test_ac8_unread_base_single_mark_lists_knowledge(self):
        """Компонент с `knowledge: [<файл>, docs/]`; базовая ветка удалена
        из клона после отведения ветки задачи.

        В брифе test_author и developer — ровно одна строка с «конвенции
        проекта не прочитаны»; в ней — оба элемента `knowledge`; кусков
        `knowledge` нет.

        Ловит мутацию: пометка базы не перечисляет элементы `knowledge`,
        либо элементы `knowledge` дают по своей пометке вслед за общей."""
        element = f"{word(self.rng)}.md"
        self.prepare({"CLAUDE.md": self.doc("CLAUDE"),
                      element: self.doc("Элемент"),
                      f"docs/{word(self.rng)}.md": self.doc("Документ")},
                     [element, "docs/"])
        self.cgit("branch", "-D", self.base)
        for role in ("test_author", "developer"):
            with self.subTest(роль=role):
                text = self.text_of(role)
                lines = self.lines_with(text, UNREAD_MARK)
                self.assertEqual(len(lines), 1, self.note(f"{role}: {lines}"))
                for name in (element, "docs/"):
                    self.assertIn(name, lines[0], self.note(
                        f"{role}: в пометке нет {name}"))
                self.assertNotIn("knowledge компонента", text, self.note(role))


# ----------------------------------------------------------------- AC-9

class EtalonTest(KnowledgeSandbox):

    def check(self, record: str) -> None:
        nonce = self.doc("Не показывать")
        self.prepare({"CLAUDE.md": ETALON_CLAUDE,
                      f"docs/{word(self.rng)}.md": nonce}, None,
                     record=record, fixed=True)
        for role in ALL_ROLES:
            with self.subTest(роль=role):
                self.assert_etalon(role, self.text_of(role), (nonce.strip(),))

    def test_ac9_test_profile_record_output_matches_etalon(self):
        """Запись `test_profile` с `CLAUDE.md` в базе и без `AGENTS.md`,
        `conventions.md` пульта — текст эталона.

        Во всех пяти потребителях (оформление с описью, без описи, пакет
        ревьювера) кусок конвенций побайтно равен эталону; вне него нет ни
        проекта, ни `knowledge`, ни пометок.

        Ловит мутацию: правка задачи сменила подпись или пометку прежних
        кусков (`where`, порядок, перевод строки) либо добавила строку о
        `knowledge` записи без компонентов — эталон не найден или вне него
        лишний текст."""
        self.check("test_profile")

    def test_ac9_component_without_knowledge_matches_etalon(self):
        """Запись `components:` из одного компонента без поля `knowledge`.

        Кусок конвенций побайтно равен эталону пина у всех пяти
        потребителей.

        Ловит мутацию: у компонента без `knowledge` выводится строка вида
        «документы knowledge: нет» или прежние куски переподписаны — вне
        эталона появляется `knowledge` или эталона нет."""
        self.check("component")


# ---------------------------------------------------------------- AC-10

class OldOutputKeptTest(KnowledgeSandbox):

    def check(self, record: str, roles=ALL_ROLES, patches=()) -> None:
        element = f"{word(self.rng)}.md"
        element_text = self.doc("Элемент")
        dir_text = self.doc("Каталог")
        self.prepare({"CLAUDE.md": ETALON_CLAUDE, element: element_text,
                      f"docs/{word(self.rng)}.md": dir_text},
                     [element, "docs/"], record=record, fixed=True)
        for role in roles:
            with self.subTest(роль=role):
                with mock.patch.object(project_profile, "decide",
                                       wraps=project_profile.decide) as decide, \
                        mock.patch.object(project_profile, "components",
                                          wraps=project_profile.components) as comps:
                    for name in patches:
                        mocked = decide if name == "decide" else comps
                        mocked.side_effect = targets.TargetsError(
                            f"запись проекта не годна {word(self.rng)}")
                    text = self.text_of(role)
                self.assert_etalon(role, text, (element_text.strip(),
                                                dir_text.strip()))

    def test_ac10_multi_component_record_keeps_old_output(self):
        """Запись из двух компонентов, у обоих `knowledge` (отказ `decide`
        `MULTI_COMPONENT_PENDING`).

        У брифов developer, spec_auditor, analyst, test_author — эталон
        пина, текстов элементов нет. (Пакет ревьювера при отказе `decide`
        не собирается вовсе — своим отказом вне конвенций.)

        Ловит мутацию: условие обходит `decide` и берёт
        `components(target)[0]` — куски `knowledge` первого компонента
        попадают в бриф."""
        self.check("multi", roles=tuple(BUILDERS))

    def test_ac10_single_component_with_decide_refusal_keeps_old_output(self):
        """Единственный компонент с `knowledge`, но без подполя `command` —
        `decide` отказывает (профиль не прочитан).

        У брифов developer, spec_auditor, analyst, test_author — эталон
        пина (пакет ревьювера при отказе `decide` не собирается).

        Ловит мутацию: условие читает `components(target)[0]` без сверки
        исхода `decide` — куски `knowledge` попадают в бриф."""
        self.check("refused", roles=tuple(BUILDERS))

    def test_ac10_skip_decide_keeps_old_output(self):
        """Запись без профиля и компонентов — `decide` отдаёт пропуск.

        У всех пяти потребителей — эталон пина.

        Ловит мутацию: пропуск `decide` трактуется как отказ сборки
        конвенций — вместо кусков пометка или исключение."""
        self.check("bare")

    def test_ac10_targets_error_in_decide_keeps_old_output(self):
        """Компонент с `knowledge`; `project_profile.decide` бросает
        `targets.TargetsError`.

        Сборка брифов developer, spec_auditor, analyst, test_author не
        падает; у каждого — эталон пина. (Пакет ревьювера зовёт `decide`
        и вне конвенций — его этот сценарий не собирает.)

        Ловит мутацию: исключение `targets` из `decide` не перехвачено —
        сборка брифа падает исключением."""
        self.check("component", roles=tuple(BUILDERS), patches=("decide",))

    def test_ac10_targets_error_in_components_keeps_old_output(self):
        """Компонент с `knowledge`; `project_profile.components` бросает
        `targets.TargetsError`, `decide` отвечает профилем компонента.

        Сборка брифов developer, spec_auditor, analyst, test_author не
        падает; у каждого — эталон пина.

        Ловит мутацию: исключение `targets` из `components` не перехвачено
        — сборка падает; либо при сбое `components` элементы берутся из
        другого источника записи и выводятся."""
        self.check("component", roles=tuple(BUILDERS), patches=("components",))

    def test_ac10_artel_brief_has_no_knowledge(self):
        """Задача артели; запись артели — `components:` из одного компонента
        с `knowledge: [CLAUDE.md, docs/]`, оба пути в `main` артели.

        В пакете ревьювера задачи артели нет ни текстов этих файлов, ни
        «knowledge компонента», ни «документы knowledge», ни прежних кусков
        конвенций проекта.

        Ловит мутацию: развилка «артель или внешний проект» у вызова
        `_project_conventions_parts` снята — у артели появляются куски
        конвенций и `knowledge`."""
        claude, doc = self.doc("CLAUDE артели"), self.doc("Документ артели")
        (self.root / "CLAUDE.md").write_text(claude, encoding="utf-8")
        (self.root / "docs").mkdir(exist_ok=True)
        (self.root / "docs" / f"{word(self.rng)}.md").write_text(
            doc, encoding="utf-8")
        self.git("add", "CLAUDE.md", "docs")
        self.git("commit", "-q", "-m", "правила артели")
        self.project, self.base, self.component = (config.DEFAULT_TARGET,
                                                   config.MAIN_BRANCH, "pult")
        config.TARGETS.write_text("targets:\n" + ENTRY_HEAD.format(
            name=self.project, base=self.base) + "    components:\n"
            + self.component_block(self.component, [
                *PROFILE_FIELDS, ("knowledge", "[CLAUDE.md, docs/]")]),
            encoding="utf-8")
        self.task = "01" + "".join(self.rng.choices(ULID_CHARS, k=24))
        self.branch = f"task/{self.task.lower()}-artel"
        self.git("checkout", "-q", "-b", self.branch)
        (self.root / "kod.py").write_text("ZNACHENIE = 1\n", encoding="utf-8")
        self.git("add", "kod.py")
        self.git("commit", "-q", "-m", "правка задачи")
        self.git("checkout", "-q", config.MAIN_BRANCH)
        store.insert_task(self.conn, self.task, "Задача артели", "in_dev",
                          self.branch, self.project, 25.0)
        self.clone = self.root
        self.commit_docs({"SPEC.md": "# SPEC\n\nЗадача артели.\n",
                          "PLAN.md": "# PLAN\n\nПлан.\n"})
        text = self.text_of("reviewer")
        for needle in (claude.strip(), doc.strip(), "knowledge компонента",
                       "документы knowledge", "(корень ветки"):
            self.assertNotIn(needle, text, self.note(f"у артели «{needle}»"))


# ---------------------------------------------------------------- AC-11

class ConsumersTest(KnowledgeSandbox):

    def prepare_consumers(self) -> None:
        self.claude, self.agents = self.doc("CLAUDE"), self.doc("AGENTS")
        self.element = f"rules{word(self.rng, 4)}.md"
        self.element_text = self.doc("Правила")
        self.dir_text = self.doc("Документ каталога")
        self.prepare({"CLAUDE.md": self.claude, "AGENTS.md": self.agents,
                      self.element: self.element_text,
                      f"docs/{word(self.rng)}.md": self.dir_text},
                     [self.element, "docs/"])

    def test_ac11_knowledge_in_four_role_briefs(self):
        """Компонент с `knowledge: [<файл>, docs/]`.

        Тексты элемента-файла и файла каталога есть в брифе developer,
        аудитора SPEC, аналитика и добавке test_author.

        Ловит мутацию: чтение `knowledge` добавлено в одного вызывающего
        (например, только `developer_brief`), а не внутрь
        `_project_conventions_parts` — у остальных ролей кусков нет."""
        self.prepare_consumers()
        for role in BUILDERS:
            with self.subTest(роль=role):
                text = self.text_of(role)
                for body in (self.element_text, self.dir_text):
                    self.assertIn(body.strip(), text, self.note(role))

    def test_ac11_reviewer_package_knowledge_after_conventions_in_order(self):
        """Компонент с `knowledge: [<файл>, docs/]` (порядок записи — не
        алфавитный: файл `rules…` раньше `docs/`).

        В пакете ревьювера заголовки идут так: `conventions.md` пульта,
        кусок элемента-файла, кусок файла каталога.

        Ловит мутацию: в пакете ревьювера куски `knowledge` не выводятся,
        стоят до `conventions.md` или отсортированы по пути."""
        self.prepare_consumers()
        text = self.text_of("reviewer")
        order = [self.header_pos(text, "conventions.md ("),
                 self.header_pos(text, self.file_label(self.element)),
                 self.header_pos(text, self.dir_label("docs/", 1, 1))]
        self.assertEqual(order, sorted(order), self.note(f"порядок: {order}"))
        for body in (self.element_text, self.dir_text):
            self.assertIn(body.strip(), text, self.note("текст knowledge"))


if __name__ == "__main__":
    unittest.main()
