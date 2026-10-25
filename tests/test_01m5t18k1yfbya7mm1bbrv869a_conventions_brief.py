"""Конвенции внешнего проекта в брифе ролей и пакете ревьювера — из файла
пульта `.artel/projects/<проект>/conventions.md`, а не из `CLAUDE.md`/
`AGENTS.md` проекта; заголовок отметки разбора скрыт; пометки «не
разобраны»/«не прочитаны»; предел размера по тексту без заголовка; фильтр
обвязки в `knowledge`; миссии ролей.

Группа: долгоживущий

Красен до реализации: бриф задачи внешнего проекта несёт `CLAUDE.md`/`AGENTS.md` базы проекта блоком `PROJECT_CONVENTIONS` и не читает `conventions.md` пульта — компонента `conventions.md (.artel/projects/<проект>/conventions.md)`, пометок «конвенции проекта не разобраны» и записи журнала «бриф: конвенции проекта не разобраны» нет; `knowledge` показывает файлы обвязки, строк «путь обвязки, пропущен»/«пропущено файлов обвязки» нет (поля `agent_wrapper` до мержа задачи 01M5T19041 запись и не принимает); миссии analyst/developer называют «CLAUDE.md и AGENTS.md его базовой ветки».

Публичная поверхность: сборка брифа и пакета — `role_prompt.mission_brief_package(conn, task_id, t, role, cwd)` (так шаг роли собирает промпт: бриф analyst, developer, spec_auditor, добавка test_author, пакет ревьювера у роли reviewer; отказ — `SystemExit`); журнал — `store.task_steps`; область проектов — `repo_context.projects_root()`; потолок файла — `config.CONTEXT_FILE_MAX_BYTES`, пометка пропуска — `context_package.render_component`; разбор заголовка — `yamlmini.mapping`/`yamlmini.YamlError`.

Окружение — фикстура `real_git` (`tests.sandbox.RealGitSandbox`): корень
пульта — настоящий git с шаблонами на `main`. Учебный внешний проект —
клон `make_project_repo` в области проектов песочницы, запись в
`config.TARGETS` песочницы со своей базовой веткой; в базе `CLAUDE.md`
«ПРАВИЛО-ПРОЕКТА» и `AGENTS.md` «ПРАВИЛО-АГЕНТА», те же файлы — в рабочей
копии задачи (`worktrees/<id>` области проекта, ветка задачи от базы).
`conventions.md` «КОНВЕНЦИЯ-ПУЛЬТА» — в области проекта песочницы под
заголовком отметки со случайными значениями `base_sha` и blob. Документы
задачи — ссылка `refs/artifacts/<id>` клона. Сбой ОС при чтении
`conventions.md` — подмена функций чтения файла (`open`, `Path.open`,
`Path.read_text`, `Path.read_bytes`, `os.open`) только для его пути.

Имена проекта, ветки, задачи и тексты выбираются модулем `random`; зерно
печатается и входит в текст провала.

Файл провалидирован временным стабом реализации (компонент
`conventions.md` в `brief._project_conventions_parts`, фильтр обвязки в
`knowledge` с `agent_wrapper` плоского поля записи, миссии без перечня
файлов проекта): все методы зелёные; мутации стаба «нет закрывающей `---`
— файл без заголовка», «фильтр каталога только в корне», «сбой ОС —
„файла нет“», «миссия analyst прежняя» красят AC-3, AC-5, AC-2, AC-7. Стаб
удалён, код репозитория не тронут.
"""
import builtins
import contextlib
import hashlib
import os
import random
import re
import shutil
import string
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import (config, context_package, repo_context, role_prompt,
                          store, yamlmini)
from tests.sandbox import make_project_repo

REPO_ROOT = Path(__file__).resolve().parent.parent
ULID_CHARS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
HEX = "0123456789abcdef"
DOCS_REF_PREFIX = "refs/artifacts/"
TASK_REPO = "orchestrator.artifact_branch.task_repo"

ROLES = ("analyst", "developer", "spec_auditor", "test_author", "reviewer")
MANIFEST_ROLES = ("developer", "spec_auditor", "reviewer")

UNPARSED = "конвенции проекта не разобраны"
UNPARSED_ACTION = "бриф: конвенции проекта не разобраны"
UNREAD = "конвенции проекта не прочитаны"
UNREAD_ACTION = "бриф: конвенции проекта не прочитаны"
BROKEN_REASON = "заголовок отметки не читается"

ENTRY = """  {name}:
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


def hex40(rng: random.Random) -> str:
    return "".join(rng.choices(HEX, k=40))


class Scene:
    """Пульт и учебный внешний проект на настоящем git; задача проекта с
    рабочей копией и документами в ссылке документов клона."""

    def __init__(self, sb, seed: int):
        self.sb = sb
        self.seed = seed
        self.rng = random.Random(seed)
        self.conn = store.db()
        shutil.copytree(REPO_ROOT / "templates", sb.root / "templates",
                        dirs_exist_ok=True)
        sb.git("add", "templates")
        sb.git("commit", "-q", "-m", "пульт: шаблоны")

    def msg(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def cgit(self, *args: str) -> str:
        return self.sb.git("-C", str(self.clone), *args)

    def tagged(self, tag: str) -> str:
        return (f"# Файл учебного проекта\n\n{tag}-{word(self.rng, 12)}: "
                f"правило {word(self.rng, 10)}.\n")

    # ----------------------------------------------------------- проект

    def prepare(self, base_files: dict | None = None, knowledge=None,
                agent_wrapper=None, extra_base: dict | None = None) -> None:
        """Учебный проект: `base_files` (путь -> str | bytes) — коммит базы
        (по умолчанию `CLAUDE.md` и `AGENTS.md`, к ним — `extra_base`);
        запись с компонентом и
        `knowledge`, если он задан; ветка задачи от базы с рабочей копией
        в области проекта; `conventions.md` под заголовком отметки."""
        self.project = f"uchebny{word(self.rng)}"
        self.base = f"osnova-{word(self.rng)}"
        entry = ENTRY.format(name=self.project, base=self.base)
        if agent_wrapper is not None:
            entry += f"    agent_wrapper: [{', '.join(agent_wrapper)}]\n"
        if knowledge is not None:
            self.component = f"komp{word(self.rng, 5)}"
            fields = [*COMPONENT_FIELDS,
                      ("knowledge", "[" + ", ".join(knowledge) + "]")]
            entry += (f"    components:\n      {self.component}:\n"
                      + "".join(f"        {k}: {v}\n" for k, v in fields))
        self.entry = entry
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(text.rstrip("\n") + "\n" + entry,
                                  encoding="utf-8")
        self.clone = make_project_repo(self.project, origin=False)
        self.claude_text = self.tagged("ПРАВИЛО-ПРОЕКТА")
        self.agents_text = self.tagged("ПРАВИЛО-АГЕНТА")
        if base_files is None:
            base_files = {"CLAUDE.md": self.claude_text,
                          "AGENTS.md": self.agents_text, **(extra_base or {})}
        self.cgit("checkout", "-q", "-b", self.base)
        for rel, body in base_files.items():
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(body, bytes):
                path.write_bytes(body)
            else:
                path.write_text(body, encoding="utf-8")
        self.cgit("add", "-A", "-f")
        self.cgit("commit", "-q", "-m", "база проекта")
        # `main` клона — на коммите базы: diff пакета ревьювера несёт
        # только правку задачи, не файлы базы.
        self.cgit("branch", "-f", config.MAIN_BRANCH, self.base)

        self.task = "01" + "".join(self.rng.choices(ULID_CHARS, k=24))
        self.branch = f"task/{self.task.lower()}-uchebnaya"
        self.cgit("checkout", "-q", "-b", self.branch)
        (self.clone / "kod.py").write_text(
            f"ZNACHENIE = {self.rng.randrange(10 ** 6)!r}\n", encoding="utf-8")
        self.cgit("add", "kod.py")
        self.cgit("commit", "-q", "-m", "правка задачи")
        self.cgit("checkout", "-q", "-f", config.MAIN_BRANCH)
        area = repo_context.projects_root() / self.project
        self.worktree = area / "worktrees" / self.task
        self.cgit("worktree", "add", "-q", str(self.worktree), self.branch)

        store.insert_task(self.conn, self.task, "Учебная задача", "in_dev",
                          self.branch, self.project, 25.0)
        self.commit_docs({
            "SPEC.md": f"# SPEC\n\nSPEC учебной задачи {word(self.rng)}.\n",
            "TZ.md": f"# ТЗ\n\nТЗ учебной задачи {word(self.rng)}.\n",
            "PLAN.md": f"# PLAN\n\nПлан учебной задачи {word(self.rng)}.\n"})

        self.conventions = area / "conventions.md"
        self.rel = f".artel/projects/{self.project}/conventions.md"
        self.label = f"conventions.md ({self.rel})"
        self.nonce = f"КОНВЕНЦИЯ-ПУЛЬТА-{word(self.rng, 12)}"
        self.body = (f"# Конвенции учебного проекта\n\n{self.nonce}: стиль "
                     f"{word(self.rng, 10)}.\n")
        self.stamp_sha = hex40(self.rng)
        self.stamp_blobs = {"AGENTS.md": hex40(self.rng),
                            "CLAUDE.md": hex40(self.rng)}
        self.write_conventions(self.header() + self.body)

    def header(self, **lines) -> str:
        """Заголовок отметки требования 6; `lines` — замена строк по ключу
        (значение — строки после ключа целиком, `None` — строку убрать)."""
        fields = {
            "conventions_stamp": " 1",
            "base_branch": f" {self.base}",
            "base_sha": f' "{self.stamp_sha}"',
            "sources": "\n" + "".join(f'  {name}: "{blob}"\n'
                                      for name, blob in self.stamp_blobs.items()
                                      ).rstrip("\n"),
        }
        fields.update(lines)
        body = "".join(f"{key}:{value}\n" for key, value in fields.items()
                       if value is not None)
        return f"---\n{body}---\n"

    def write_conventions(self, text) -> None:
        self.conventions.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            self.conventions.write_bytes(text)
        else:
            self.conventions.write_text(text, encoding="utf-8")

    def commit_docs(self, files: dict) -> None:
        """Документы задачи — коммит ссылки `refs/artifacts/<id>` клона
        временным индексом, мимо рабочего дерева клона."""
        src = self.sb.root / ".artel" / f"docs-src-{word(self.rng)}"
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
        config.TARGETS.write_text(text.replace(self.entry, ""), encoding="utf-8")

    def docs_from_copy(self, stack) -> None:
        """Документы задачи — из копии клона: контекст проекта не
        разрешается, SPEC.md задачи остаётся читаемым."""
        copy = self.sb.root / ".artel" / f"docs-copy-{word(self.rng)}"
        shutil.copytree(self.clone, copy, symlinks=True)
        stack.enter_context(mock.patch(TASK_REPO, lambda task_id: copy))

    # ------------------------------------------------------------ сборка

    def build(self, role: str) -> dict:
        """Бриф роли (у reviewer — пакет) так, как его собирает шаг роли:
        текст, отказ `SystemExit`, новые записи журнала задачи."""
        rows = store.task_steps(self.conn, self.task)
        mark = rows[-1]["id"] if rows else 0
        text, refusal = None, None
        t = store.get_task(self.conn, self.task)
        try:
            _mission, brief_text, package = role_prompt.mission_brief_package(
                self.conn, self.task, t, role, self.worktree)
            text = package["text"] if role == "reviewer" else brief_text
        except SystemExit as exc:
            refusal = str(exc.code)
        new_rows = [r for r in store.task_steps(self.conn, self.task)
                    if r["id"] > mark]
        return {"text": text, "refusal": refusal, "rows": new_rows}

    def mission(self, role: str) -> str:
        t = store.get_task(self.conn, self.task)
        mission, _brief, _package = role_prompt.mission_brief_package(
            self.conn, self.task, t, role, self.worktree)
        return mission


def header_of(text: str, fragment: str) -> str | None:
    """Строка заголовка `### …` компонента, в теле которого стоит
    `fragment`; `None` — фрагмента или заголовка нет."""
    pos = text.find(fragment)
    if pos < 0:
        return None
    start = text.rfind("\n### ", 0, pos)
    if start < 0:
        return None
    return text[start + 1:text.index("\n", start + 1)]


def journal_lines(rows: list) -> list:
    return [f"{r['action']}: {r['detail'] or ''}" for r in rows]


def has_journal(rows: list, action: str, needle: str) -> bool:
    return any(r["action"] == action and needle in (r["detail"] or "")
               for r in rows)


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


@pytest.fixture
def scene(real_git, seed):
    return Scene(real_git, seed)


def built_text(scene: Scene, role: str, built: dict) -> str:
    assert built["refusal"] is None, scene.msg(
        f"{role}: сборка отказала: {built['refusal']}")
    assert built["text"] is not None, scene.msg(f"{role}: текста нет")
    return built["text"]


# ------------------------------------------------------------------ AC-1

@pytest.mark.parametrize("with_knowledge", [False, True])
def test_ac1_pult_conventions_single_component_in_five_points(scene,
                                                             with_knowledge):
    """Учебный проект с `CLAUDE.md`/`AGENTS.md` в базе и рабочей копии и
    `conventions.md` под заголовком отметки; во втором варианте у записи —
    компонент с `knowledge: [<нейтральный файл>.md]`.

    В брифе analyst, developer, spec_auditor, добавке test_author и пакете
    ревьювера «КОНВЕНЦИЯ-ПУЛЬТА» стоит ровно один раз, в единственном
    компоненте с заголовком `### conventions.md (.artel/projects/<проект>/
    conventions.md)`; у developer, spec_auditor и ревьювера заголовок несёт
    размер и sha256 текста без заголовка отметки, у analyst и test_author
    — ни размера, ни sha256. Текстов `CLAUDE.md`/`AGENTS.md`, значений
    `base_sha` и blob заголовка и строки `conventions_stamp` нет. Текст
    элемента `knowledge` стоит после «КОНВЕНЦИЯ-ПУЛЬТА».

    Ловит мутацию: блок `PROJECT_CONVENTIONS` оставлен рядом с новым
    компонентом — в брифе текст `CLAUDE.md` базы; файл пульта читается
    целиком — в брифе строки `conventions_stamp`/`base_sha`; опись
    считается по файлу с заголовком — sha256 в заголовке не совпадает; у
    analyst компонент оформлен описью developer; компонент `conventions.md`
    добавлен после документов `knowledge` — порядок обратный."""
    if with_knowledge:
        neutral = f"{word(scene.rng)}.md"
        neutral_text = scene.tagged("НЕЙТРАЛЬНЫЙ-ДОКУМЕНТ")
        scene.prepare(extra_base={neutral: neutral_text}, knowledge=[neutral])
    else:
        scene.prepare()
        neutral_text = None
    raw = scene.body.encode("utf-8")
    size, sha = len(raw), hashlib.sha256(raw).hexdigest()
    for role in ROLES:
        text = built_text(scene, role, scene.build(role))
        assert text.count(scene.nonce) == 1, scene.msg(
            f"{role}: «КОНВЕНЦИЯ-ПУЛЬТА» встречается "
            f"{text.count(scene.nonce)} раз")
        headers = [line for line in text.splitlines()
                   if line.startswith(f"### {scene.label}")]
        assert len(headers) == 1, scene.msg(
            f"{role}: заголовков компонента {scene.label}: {headers}")
        header = header_of(text, scene.nonce)
        assert header == headers[0], scene.msg(
            f"{role}: «КОНВЕНЦИЯ-ПУЛЬТА» не в компоненте {scene.label}: "
            f"{header!r}")
        if role in MANIFEST_ROLES:
            assert f"{size} байт" in header, scene.msg(
                f"{role}: в описи нет размера текста без заголовка: {header}")
            assert f"sha256={sha}" in header, scene.msg(
                f"{role}: в описи нет sha256 текста без заголовка: {header}")
        else:
            assert "sha256" not in header and " байт" not in header, \
                scene.msg(f"{role}: у компонента опись: {header}")
        for needle, what in (
                (scene.claude_text.strip(), "текст CLAUDE.md проекта"),
                (scene.agents_text.strip(), "текст AGENTS.md проекта"),
                ("ПРАВИЛО-ПРОЕКТА", "ПРАВИЛО-ПРОЕКТА"),
                ("ПРАВИЛО-АГЕНТА", "ПРАВИЛО-АГЕНТА"),
                (scene.stamp_sha, "base_sha заголовка"),
                *((blob, f"blob {name} заголовка")
                  for name, blob in scene.stamp_blobs.items()),
                ("conventions_stamp", "строка conventions_stamp")):
            assert needle not in text, scene.msg(f"{role}: в брифе {what}")
        if neutral_text is not None:
            pos = text.find(neutral_text.strip())
            assert pos >= 0, scene.msg(f"{role}: нет текста элемента knowledge")
            assert text.find(scene.nonce) < pos, scene.msg(
                f"{role}: элемент knowledge стоит раньше КОНВЕНЦИЯ-ПУЛЬТА")


# ------------------------------------------------------------------ AC-2

class OsErrorOnRead:
    """Подмена функций чтения файла: чтение пути `target` отвечает
    `OSError` с текстом `message`; остальные пути читаются как прежде."""

    def __init__(self, target: Path, message: str):
        self.target = os.path.realpath(target)
        self.message = message

    def hit(self, path) -> bool:
        try:
            return os.path.realpath(os.fspath(path)) == self.target
        except TypeError:
            return False

    def patches(self) -> list:
        real_open, real_os_open = builtins.open, os.open
        real_path_open = Path.open
        real_read_text, real_read_bytes = Path.read_text, Path.read_bytes
        fail = self

        def fake_open(file, *args, **kwargs):
            if fail.hit(file):
                raise OSError(fail.message)
            return real_open(file, *args, **kwargs)

        def fake_os_open(path, *args, **kwargs):
            if fail.hit(path):
                raise OSError(fail.message)
            return real_os_open(path, *args, **kwargs)

        def fake_path_open(self, *args, **kwargs):
            if fail.hit(self):
                raise OSError(fail.message)
            return real_path_open(self, *args, **kwargs)

        def fake_read_text(self, *args, **kwargs):
            if fail.hit(self):
                raise OSError(fail.message)
            return real_read_text(self, *args, **kwargs)

        def fake_read_bytes(self, *args, **kwargs):
            if fail.hit(self):
                raise OSError(fail.message)
            return real_read_bytes(self, *args, **kwargs)

        return [mock.patch.object(builtins, "open", fake_open),
                mock.patch.object(os, "open", fake_os_open),
                mock.patch.object(Path, "open", fake_path_open),
                mock.patch.object(Path, "read_text", fake_read_text),
                mock.patch.object(Path, "read_bytes", fake_read_bytes)]


def spoil_conventions(scene: Scene, case: str) -> str | None:
    """`conventions.md` сценария `case`; ожидаемая причина пометки (`None`
    — у сбоя ОС причина — текст ошибки, его знает сценарий)."""
    path = scene.conventions
    if case == "файла нет":
        path.unlink()
        return "файла нет"
    if case == "каталог":
        path.unlink()
        path.mkdir()
        (path / "x.md").write_text(scene.body, encoding="utf-8")
        return "не обычный файл"
    if case == "символьная ссылка":
        real = path.parent / f"real-{word(scene.rng)}.md"
        real.write_text(scene.header() + scene.body, encoding="utf-8")
        path.unlink()
        os.symlink(real, path)
        return "не обычный файл"
    if case == "не UTF-8":
        codec = scene.rng.choice(("cp1251", "koi8-r"))
        raw = (scene.header() + scene.body).encode("utf-8")
        raw += f"Правило {word(scene.rng)}\n".encode(codec)
        path.write_bytes(raw)
        return "текст не в UTF-8"
    return None


@pytest.mark.parametrize("case", ["файла нет", "каталог", "символьная ссылка",
                                  "не UTF-8", "ошибка ОС"])
def test_ac2_unreadable_conventions_marked_unparsed(scene, case):
    """`conventions.md` нет, он — каталог, символьная ссылка на файл с
    «КОНВЕНЦИЯ-ПУЛЬТА», текст не в UTF-8, либо чтение файла отвечает
    `OSError` (подмена функций чтения файла).

    Во всех пяти точках шаг роли собирает промпт без `SystemExit`; текст
    несёт строку «конвенции проекта не разобраны: <причина> —
    .artel/projects/<проект>/conventions.md» с причиной случая («файла
    нет», «не обычный файл», «текст не в UTF-8», текст ошибки ОС — и тогда
    не «файла нет»), не несёт «ПРАВИЛО-ПРОЕКТА» и «КОНВЕНЦИЯ-ПУЛЬТА»; в
    новых записях журнала задачи — «бриф: конвенции проекта не
    разобраны» с той же причиной.

    Ловит мутацию: при отсутствии файла пульта бриф откатывается к
    `CLAUDE.md` базы — в тексте «ПРАВИЛО-ПРОЕКТА»; символьная ссылка
    читается по цели — в тексте «КОНВЕНЦИЯ-ПУЛЬТА»; `UnicodeDecodeError`
    или `OSError` вне перехвата — `SystemExit`/исключение; любой сбой
    чтения помечается «файла нет»; пометка без записи журнала."""
    scene.prepare()
    expected = spoil_conventions(scene, case)
    message = f"сбой чтения {word(scene.rng, 10)}"
    patches = (OsErrorOnRead(scene.conventions, message).patches()
               if case == "ошибка ОС" else [])
    results = {}
    with contextlib.ExitStack() as stack:
        for patch in patches:
            stack.enter_context(patch)
        for role in ROLES:
            results[role] = scene.build(role)
    reason = expected if expected is not None else message
    for role, built in results.items():
        text = built_text(scene, role, built)
        lines = [line for line in text.splitlines()
                 if f"{UNPARSED}: " in line
                 and line.rstrip().endswith(f" — {scene.rel}")]
        assert lines, scene.msg(f"{case}/{role}: нет строки «{UNPARSED}: … — "
                                f"{scene.rel}»")
        assert any(reason in line for line in lines), scene.msg(
            f"{case}/{role}: причина не «{reason}»: {lines}")
        if case == "ошибка ОС":
            assert not any("файла нет" in line for line in lines), scene.msg(
                f"{case}/{role}: сбой ОС помечен «файла нет»: {lines}")
        assert "ПРАВИЛО-ПРОЕКТА" not in text, scene.msg(
            f"{case}/{role}: в брифе ПРАВИЛО-ПРОЕКТА")
        assert scene.nonce not in text, scene.msg(
            f"{case}/{role}: в брифе КОНВЕНЦИЯ-ПУЛЬТА")
        assert has_journal(built["rows"], UNPARSED_ACTION, reason), scene.msg(
            f"{case}/{role}: нет записи «{UNPARSED_ACTION}» с «{reason}»:\n"
            + "\n".join(journal_lines(built["rows"])))


# ------------------------------------------------------------------ AC-3

BROKEN_CASES = ["нет закрывающей ---", "YamlError", "base_sha не 40 hex",
                "sources — список", "элемент sources без blob",
                "base_branch пуст", "base_branch не строка"]


def broken_text(scene: Scene, case: str) -> str:
    """Текст `conventions.md` со сломанным заголовком случая `case`."""
    if case == "нет закрывающей ---":
        return scene.header().rsplit("---\n", 1)[0] + scene.body
    if case == "YamlError":
        return ("---\nconventions_stamp: 1\nэто не пара ключ и значение\n"
                "---\n" + scene.body)
    if case == "base_sha не 40 hex":
        bad = scene.rng.choice((scene.stamp_sha[:39],
                                scene.stamp_sha[:39] + "g"))
        return scene.header(base_sha=f' "{bad}"') + scene.body
    if case == "sources — список":
        return scene.header(sources=" [AGENTS.md, CLAUDE.md]") + scene.body
    if case == "элемент sources без blob":
        blob = scene.stamp_blobs["CLAUDE.md"]
        return scene.header(
            sources=f'\n  AGENTS.md:\n  CLAUDE.md: "{blob}"') + scene.body
    if case == "base_branch пуст":
        return scene.header(base_branch=' ""') + scene.body
    if case == "base_branch не строка":
        number = scene.rng.randrange(1, 10 ** 6)
        return scene.header(base_branch=f" {number}") + scene.body
    raise ValueError(case)


def header_block(text: str) -> str | None:
    """Тело блока между первой строкой `---` и следующей; `None` —
    закрывающей строки нет."""
    lines = text.split("\n")
    if lines[0] != "---" or "---" not in lines[1:]:
        return None
    end = lines.index("---", 1)
    return "\n".join(lines[1:end]) + "\n"


@pytest.mark.parametrize("case", BROKEN_CASES)
def test_ac3_broken_stamp_header_marked_unparsed(scene, case):
    """`conventions.md` со сломанным заголовком отметки: без закрывающей
    `---`; тело блока, на котором `yamlmini.mapping` отвечает `YamlError`;
    `base_sha` не из 40 шестнадцатеричных; `sources` — список; элемент
    `sources` без blob; `base_branch` пуст; `base_branch` — число.

    Во всех пяти точках шаг роли собирает промпт; текст несёт строку
    «конвенции проекта не разобраны: заголовок отметки не читается —
    .artel/projects/<проект>/conventions.md», не несёт ни строк заголовка
    (`conventions_stamp`, `base_sha`, blob), ни текста под ним; в журнале
    — «бриф: конвенции проекта не разобраны» с этой причиной.

    Ловит мутацию: файл без закрывающей `---` считается файлом без
    заголовка и идёт целиком — в брифе `conventions_stamp`; `YamlError`
    вне перехвата роняет сборку; проверка `sources` берёт только
    «непустое» — список или элемент `None` проходят и текст под
    заголовком показан; `base_branch` не проверяется на строку."""
    scene.prepare()
    text = broken_text(scene, case)
    block = header_block(text)
    if case == "нет закрывающей ---":
        assert block is None, scene.msg("фикстура: блок закрыт")
    elif case == "YamlError":
        with pytest.raises(yamlmini.YamlError):
            yamlmini.mapping(block)
    else:
        parsed = yamlmini.mapping(block)
        assert "conventions_stamp" in parsed, scene.msg(f"фикстура: {parsed}")
        if case == "sources — список":
            assert isinstance(parsed["sources"], list), scene.msg(str(parsed))
        if case == "элемент sources без blob":
            assert parsed["sources"]["AGENTS.md"] is None, scene.msg(str(parsed))
        if case == "base_branch не строка":
            assert not isinstance(parsed["base_branch"], str), scene.msg(
                str(parsed))
    scene.write_conventions(text)
    mark = f"{UNPARSED}: {BROKEN_REASON} — {scene.rel}"
    for role in ROLES:
        built = scene.build(role)
        out = built_text(scene, role, built)
        assert any(mark in line for line in out.splitlines()), scene.msg(
            f"{case}/{role}: нет строки «{mark}»")
        for needle, what in ((scene.nonce, "текст под заголовком"),
                             ("conventions_stamp", "строка conventions_stamp"),
                             (scene.stamp_sha[:39], "base_sha заголовка"),
                             (scene.stamp_blobs["CLAUDE.md"], "blob заголовка")):
            assert needle not in out, scene.msg(f"{case}/{role}: в брифе {what}")
        assert has_journal(built["rows"], UNPARSED_ACTION, BROKEN_REASON), \
            scene.msg(f"{case}/{role}: нет записи «{UNPARSED_ACTION}» с "
                      f"«{BROKEN_REASON}»:\n"
                      + "\n".join(journal_lines(built["rows"])))


# ------------------------------------------------------------------ AC-4

def test_ac4_size_limit_counts_text_without_header(scene):
    """Бриф developer при двух размерах `conventions.md`: текст под
    заголовком крупнее `config.CONTEXT_FILE_MAX_BYTES`; текст под
    заголовком не крупнее предела (недобор — случайный, меньше длины
    заголовка), а вместе с заголовком — крупнее.

    В первом случае в брифе — пометка пропуска
    `context_package.render_component` для подписи компонента и этого
    текста (та же, что получал бы файл конвенций того же размера), самого
    текста нет; во втором — каждая строка текста, заголовок компонента с
    размером и sha256 текста без заголовка отметки и без пометки пропуска.

    Ловит мутацию: размер считается по файлу вместе с заголовком — во
    втором случае компонент пропущен; пропуск сверх предела оформлен своей
    строкой, не прежней пометкой; предел не применён — в первом случае
    текст в брифе."""
    scene.prepare()
    limit = config.CONTEXT_FILE_MAX_BYTES
    header = scene.header()
    head = f"# Конвенции учебного проекта\n\n{scene.nonce}\n"
    filler = f"строка конвенции {word(scene.rng, 6)} " + "x" * 60 + "\n"

    over = head + filler * (limit // len(filler.encode("utf-8")) + 2)
    assert len(over.encode("utf-8")) > limit, scene.msg("фикстура: не крупнее")
    scene.write_conventions(header + over)
    text = built_text(scene, "developer", scene.build("developer"))
    skip = context_package.render_component(scene.label, over)
    assert skip in text, scene.msg(
        f"нет прежней пометки пропуска по размеру:\n{skip}")
    assert scene.nonce not in text, scene.msg("текст сверх предела в брифе")

    shortfall = scene.rng.randrange(1, len(header.encode("utf-8")))
    target = limit - shortfall
    count = (target - len(head.encode("utf-8"))) // len(filler.encode("utf-8"))
    body = head + filler * count
    body += "y" * (target - len(body.encode("utf-8")) - 1) + "\n"
    size = len(body.encode("utf-8"))
    assert size == target and size + len(header.encode("utf-8")) > limit, \
        scene.msg(f"фикстура: размер {size}")
    scene.write_conventions(header + body)
    text = built_text(scene, "developer", scene.build("developer"))
    # Бриф крупнее потолка части делится на части по границам строк —
    # текст компонента сверяется построчно.
    missing = [line for line in set(body.splitlines()) if line not in text]
    assert not missing, scene.msg(
        f"текст под пределом показан не целиком: нет {len(missing)} строк")
    comp = header_of(text, scene.nonce)
    assert comp is not None and comp.startswith(f"### {scene.label}"), \
        scene.msg(f"заголовок компонента: {comp!r}")
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    assert f"{size} байт, sha256={sha}" in comp and "пропущен" not in comp, \
        scene.msg(f"компонент под пределом с пометкой пропуска: {comp}")


# ------------------------------------------------------------------ AC-5

WRAPPED = ("CLAUDE.md", "AGENTS.md", "docs/AGENTS.md", "sub/CLAUDE.md",
           ".claude/rules/r.md", "harness/h.md")
SHOWN = ("docs/arch.md", "guide.md")


def test_ac5_wrapper_paths_skipped_in_knowledge(scene):
    """Запись с `agent_wrapper: [harness/]` и `knowledge: [CLAUDE.md,
    ./AGENTS.md, ./, docs/arch.md]`; в базе ровно восемь `*.md`: шесть
    путей обвязки (`CLAUDE.md`, `AGENTS.md`, `docs/AGENTS.md`,
    `sub/CLAUDE.md`, `.claude/rules/r.md`, `harness/h.md`) и
    `docs/arch.md`, `guide.md`, у каждого свой текст.

    Во всех пяти точках: тексты `docs/arch.md` и `guide.md` есть, текстов
    шести файлов обвязки нет; есть строки «документы knowledge: CLAUDE.md —
    путь обвязки, пропущен», «документы knowledge: ./AGENTS.md — путь
    обвязки, пропущен» и «документы knowledge: каталог ./ — пропущено
    файлов обвязки: 6»; кусков каталога `./` два, каждый — «из 2».

    Ловит мутацию: элемент сверяется со списком обвязки без нормализации
    — `./AGENTS.md` читается; фильтр каталога после отбора — нумерация «из
    8»; фильтр не знает `**/<каталог>/` или `agent_wrapper` записи —
    `.claude/rules/r.md` или `harness/h.md` в брифе; N считает файлы всех
    элементов — не 6."""
    texts = {rel: scene.tagged(f"ДОКУМЕНТ-{i}") for i, rel in
             enumerate((*WRAPPED, *SHOWN))}
    scene.prepare(base_files=texts, agent_wrapper=["harness/"],
                  knowledge=["CLAUDE.md", "./AGENTS.md", "./", "docs/arch.md"])
    for role in ROLES:
        text = built_text(scene, role, scene.build(role))
        lines = text.splitlines()
        for rel in SHOWN:
            assert texts[rel].strip() in text, scene.msg(
                f"{role}: нет текста {rel}")
        for rel in WRAPPED:
            assert texts[rel].strip() not in text, scene.msg(
                f"{role}: в брифе текст файла обвязки {rel}")
        for line in ("документы knowledge: CLAUDE.md — путь обвязки, пропущен",
                     "документы knowledge: ./AGENTS.md — путь обвязки, пропущен",
                     "документы knowledge: каталог ./ — пропущено файлов "
                     "обвязки: 6"):
            assert any(line in own for own in lines), scene.msg(
                f"{role}: нет строки «{line}»")
        chunks = [own for own in lines if own.startswith("### ")
                  and "каталог ./, документ" in own]
        assert len(chunks) == 2, scene.msg(f"{role}: куски каталога ./: {chunks}")
        assert all("из 2" in own for own in chunks), scene.msg(
            f"{role}: нумерация кусков каталога ./: {chunks}")


# ------------------------------------------------------------------ AC-7

def test_ac7_missions_name_pult_conventions_not_project_files(scene):
    """Миссии analyst и developer задачи учебного проекта и исходный текст
    `orchestrator/role_prompt.py`.

    Миссии не содержат «CLAUDE.md и AGENTS.md»; миссия developer содержит
    «конвенции проекта»; строки «CLAUDE.md и AGENTS.md его базовой ветки»
    нет в тексте модуля — ни в одной строке, ни в склейке соседних
    строковых литералов.

    Ловит мутацию: строка миссии исправлена только у developer — миссия
    analyst по-прежнему «Конвенции проекта (CLAUDE.md и AGENTS.md его
    базовой ветки)»; фраза «конвенции проекта» выпала из миссии developer
    вместе с перечнем файлов."""
    scene.prepare()
    for role in ("analyst", "developer"):
        mission = scene.mission(role)
        assert "CLAUDE.md и AGENTS.md" not in mission, scene.msg(
            f"миссия {role} называет файлы проекта:\n{mission}")
    assert "конвенции проекта" in scene.mission("developer"), scene.msg(
        "в миссии developer нет «конвенции проекта»")
    source = Path(role_prompt.__file__).read_text(encoding="utf-8")
    joined = "".join(re.split(r'"\s*\n\s*(?:f)?"', source))
    phrase = "CLAUDE.md и AGENTS.md его базовой ветки"
    assert phrase not in source and phrase not in joined, scene.msg(
        f"в role_prompt.py строка «{phrase}»")


# ----------------------------------------------------------------- AC-14

def test_ac14_unresolved_context_marked_unread_with_conventions(scene):
    """Запись учебного проекта убрана из `config.TARGETS` (контекст не
    разрешается); документы задачи — из копии клона; `conventions.md` в
    области проекта читается.

    Во всех пяти точках шаг роли собирает промпт без `SystemExit`; текст
    несёт строку «конвенции проекта не прочитаны: <непустая причина> —
    <где>» и «КОНВЕНЦИЯ-ПУЛЬТА»; в новых записях журнала у каждой роли —
    «бриф: конвенции проекта не прочитаны».

    Ловит мутацию: при неразрешённом контексте компонент `conventions.md`
    не собирается (возврат одной пометки до чтения файла пульта) —
    «КОНВЕНЦИЯ-ПУЛЬТА» нет; пометка «не прочитаны» выдаётся только при
    `knowledge` — у записи без неё пометки нет; пометка без записи
    журнала."""
    scene.prepare()
    with contextlib.ExitStack() as stack:
        scene.docs_from_copy(stack)
        scene.drop_project_entry()
        results = {role: scene.build(role) for role in ROLES}
    for role, built in results.items():
        text = built_text(scene, role, built)
        lines = [line for line in text.splitlines() if f"{UNREAD}: " in line]
        parts = [line.split(f"{UNREAD}: ", 1)[1].split(" — ", 1)
                 for line in lines]
        assert any(len(p) == 2 and p[0].strip() and p[1].strip()
                   for p in parts), scene.msg(
            f"{role}: нет строки «{UNREAD}: <причина> — <где>»: {lines}")
        assert scene.nonce in text, scene.msg(
            f"{role}: нет текста КОНВЕНЦИЯ-ПУЛЬТА")
        assert any(r["action"] == UNREAD_ACTION for r in built["rows"]), \
            scene.msg(f"{role}: нет записи «{UNREAD_ACTION}»:\n"
                      + "\n".join(journal_lines(built["rows"])))
