"""Отметка разбора конвенций внешнего проекта (`artel.py conventions-stamp`),
сверка дрейфа в `doctor` (проверка `project-conventions`), работа без сети.

Группа: долгоживущий

Красен до реализации: команды `conventions-stamp` в `artel.py` нет (диспетчер отказывает неизвестной команде — отметка в исправном состоянии не ставится, заголовка в `conventions.md` нет), проверки `project-conventions` среди `doctor.all_checks` нет.

Публичная поверхность: команда — `artel.main()` с `sys.argv`
`["artel.py", "conventions-stamp", <проект>, <файл>…]` (успех — без
`SystemExit` или с кодом 0; отказ — `SystemExit` с иным кодом, причина — в
выводе или тексте выхода); проверки — `doctor.all_checks(conn)`, строка —
`Check` с именем `project-conventions`, полями `status` и `detail`; область
проектов — `repo_context.projects_root()`; разбор заголовка —
`yamlmini.mapping`.

Окружение — фикстура `real_git` (`tests.sandbox.RealGitSandbox`). Учебный
внешний проект — клон `make_project_repo` в области проектов песочницы, его
запись в `config.TARGETS` со своей базовой веткой. В базе — `AGENTS.md`,
`CLAUDE.md`, `docs/x.md`, `README.txt`; `HEAD` клона — на другой ветке, где
`AGENTS.md` и `CLAUDE.md` другие; в рабочем дереве — незакоммиченная правка
`AGENTS.md`. Коммиты в ветки клона — временным индексом (`read-tree`,
`update-index`, `write-tree`, `commit-tree`, `update-ref`), мимо его
рабочего дерева. `doctor` исполняет только git: прочие внешние процессы
отвечают `FileNotFoundError`, дом пользователя — каталог песочницы.
Запрет сети — подмена `subprocess.run`/`subprocess.Popen` (запись вызовов)
и `socket.socket.connect`/`socket.create_connection` (отказ с записью);
вызовы `doctor` относятся к проверке по кадру стека
`orchestrator/doctor/project_conventions.py`.

Имена проекта и веток, тексты файлов выбираются модулем `random`; зерно
печатается и входит в текст провала.

Файл провалидирован временным стабом реализации (`orchestrator/
conventions.py` с командой и сверкой, вызов из `orchestrator/doctor/
project_conventions.py` в цикле `all_checks`): все методы зелёные; мутации
стаба «сверка по `HEAD`», «отметка по `HEAD`», «нет закрывающей `---` —
файл без заголовка», «`git fetch` перед сверкой» красят AC-10, AC-8, AC-9 и
AC-11, AC-13. Стаб удалён, код репозитория не тронут.
"""
import contextlib
import io
import os
import random
import shutil
import socket
import string
import subprocess
import sys
import traceback
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import artel, config, doctor, repo_context, store, yamlmini
from tests.sandbox import make_project_repo

HEX = "0123456789abcdef"
CHECK = "project-conventions"
NETWORK_GIT = ("fetch", "ls-remote", "push")
CHECK_FRAME = os.path.join("orchestrator", "doctor", "project_conventions.py")

DRIFT = "конвенции проекта изменились с последнего разбора"
NO_STAMP = "нет отметки разбора"
BROKEN = "заголовок отметки не читается"
ONBOARDING = "docs/target-onboarding.md"

ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


def word(rng: random.Random, k: int = 8) -> str:
    return "".join(rng.choices(string.ascii_lowercase, k=k))


def hex40(rng: random.Random) -> str:
    return "".join(rng.choices(HEX, k=40))


class Recorder:
    """Записанные вызовы внешних процессов и попытки сокет-соединений:
    (argv, вызван ли из проверки `project-conventions`)."""

    def __init__(self):
        self.calls: list = []
        self.connects: list = []

    @staticmethod
    def from_check() -> bool:
        return any(frame.filename.endswith(CHECK_FRAME)
                   for frame in traceback.extract_stack())

    def network_git(self, only_check: bool) -> list:
        return [argv for argv, own in self.calls
                if (own or not only_check) and argv
                and Path(argv[0]).name == "git"
                and any(part in NETWORK_GIT for part in argv[1:])]

    def sockets(self, only_check: bool) -> list:
        return [args for args, own in self.connects if own or not only_check]


class StampScene:
    """Учебный внешний проект: база, ветка `HEAD` с другими файлами,
    незакоммиченная правка рабочего дерева, `conventions.md` пульта."""

    def __init__(self, sb, seed: int):
        self.sb = sb
        self.seed = seed
        self.rng = random.Random(seed)
        self.conn = store.db()

    def msg(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def cgit(self, *args: str) -> str:
        return self.sb.git("-C", str(self.clone), *args)

    def tagged(self, tag: str) -> str:
        return f"# {tag}\n\n{tag}-{word(self.rng, 12)}: {word(self.rng, 10)}.\n"

    def prepare(self) -> None:
        self.project = f"uchebny{word(self.rng)}"
        self.base = f"osnova-{word(self.rng)}"
        self.other = f"drugaya-{word(self.rng)}"
        self.entry = ENTRY.format(name=self.project, base=self.base)
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(text.rstrip("\n") + "\n" + self.entry,
                                  encoding="utf-8")
        self.clone = make_project_repo(self.project, origin=False)
        self.cgit("checkout", "-q", "-b", self.base)
        for rel, tag in (("AGENTS.md", "AGENTS-БАЗЫ"), ("CLAUDE.md", "CLAUDE-БАЗЫ"),
                         ("docs/x.md", "ДОКУМЕНТ"), ("README.txt", "ПРОЧЕЕ")):
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.tagged(tag), encoding="utf-8")
        self.cgit("add", "-A", "-f")
        self.cgit("commit", "-q", "-m", "база проекта")
        self.cgit("checkout", "-q", "-b", self.other)
        for rel in ("AGENTS.md", "CLAUDE.md"):
            (self.clone / rel).write_text(self.tagged(f"{rel}-ДРУГОЙ-ВЕТКИ"),
                                          encoding="utf-8")
        self.cgit("commit", "-q", "-am", "другая ветка")
        (self.clone / "AGENTS.md").write_text(self.tagged("ПРАВКА-ДЕРЕВА"),
                                              encoding="utf-8")
        area = repo_context.projects_root() / self.project
        self.conventions = area / "conventions.md"
        self.body = (f"# Конвенции учебного проекта\n\nКОНВЕНЦИЯ-ПУЛЬТА-"
                     f"{word(self.rng, 12)}: стиль {word(self.rng)}.\n")
        self.write(self.body)

    def write(self, text) -> None:
        self.conventions.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            self.conventions.write_bytes(text)
        else:
            self.conventions.write_text(text, encoding="utf-8")

    def snapshot(self):
        """Байты `conventions.md`; `None` — пути нет."""
        if not os.path.lexists(self.conventions):
            return None
        if self.conventions.is_dir():
            return ("каталог", sorted(p.name for p in self.conventions.iterdir()))
        if self.conventions.is_symlink():
            return ("ссылка", os.readlink(self.conventions))
        return self.conventions.read_bytes()

    def header(self, **lines) -> str:
        """Заголовок отметки требования 6 со случайными значениями; `lines`
        — замена значения строки по ключу (`None` — строку убрать)."""
        fields = {
            "conventions_stamp": " 1",
            "base_branch": f" {self.base}",
            "base_sha": f' "{hex40(self.rng)}"',
            "sources": (f'\n  AGENTS.md: "{hex40(self.rng)}"'
                        f'\n  CLAUDE.md: "{hex40(self.rng)}"'),
        }
        fields.update(lines)
        body = "".join(f"{key}:{value}\n" for key, value in fields.items()
                       if value is not None)
        return f"---\n{body}---\n"

    def rev(self, spec: str) -> str:
        return self.cgit("rev-parse", spec).strip()

    def commit_to(self, branch: str, changes: dict) -> str:
        """Коммит в `branch` клона временным индексом: путь -> текст или
        `None` (удалить); рабочее дерево и индекс клона не трогаются."""
        tmp = self.sb.root / ".artel" / f"idx-{word(self.rng)}"
        tmp.mkdir(parents=True, exist_ok=True)
        with mock.patch.dict(os.environ,
                             {"GIT_INDEX_FILE": str(tmp / "index")}):
            self.cgit("read-tree", f"refs/heads/{branch}")
            for rel, body in changes.items():
                if body is None:
                    self.cgit("update-index", "--force-remove", "--", rel)
                    continue
                src = tmp / f"blob-{word(self.rng)}"
                src.write_text(body, encoding="utf-8")
                blob = self.cgit("hash-object", "-w", str(src)).strip()
                self.cgit("update-index", "--add", "--cacheinfo",
                          f"100644,{blob},{rel}")
            tree = self.cgit("write-tree").strip()
        parent = self.rev(f"refs/heads/{branch}")
        commit = self.cgit("commit-tree", tree, "-p", parent,
                           "-m", f"коммит в {branch}").strip()
        self.cgit("update-ref", f"refs/heads/{branch}", commit)
        return commit

    # --------------------------------------------------------- команды

    def stamp(self, *args: str) -> tuple:
        """(успех, вывод) `artel.py conventions-stamp <args>`."""
        out, err = io.StringIO(), io.StringIO()
        ok, tail = True, ""
        with mock.patch.object(sys, "argv",
                               ["artel.py", "conventions-stamp", *args]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                artel.main()
            except SystemExit as exc:
                if exc.code not in (0, None):
                    ok = False
                    tail = f"\n{exc.code}"
        return ok, out.getvalue() + err.getvalue() + tail

    def checks(self, recorder: Recorder | None = None) -> list:
        """Строки `project-conventions` всех проверок `doctor`: исполняется
        только git, дом пользователя — каталог песочницы."""
        real_run, real_popen = subprocess.run, subprocess.Popen

        def allowed(cmd) -> bool:
            argv = [cmd] if isinstance(cmd, (str, Path)) else list(cmd)
            if recorder is not None:
                recorder.calls.append(([str(p) for p in argv],
                                       recorder.from_check()))
            return bool(argv) and Path(str(argv[0])).name == "git"

        def run(cmd, *args, **kwargs):
            if allowed(cmd):
                return real_run(cmd, *args, **kwargs)
            raise FileNotFoundError("песочница: внешний процесс не запускается")

        def popen(cmd, *args, **kwargs):
            if allowed(cmd):
                return real_popen(cmd, *args, **kwargs)
            raise FileNotFoundError("песочница: внешний процесс не запускается")

        home = self.sb.root / ".artel" / "dom"
        home.mkdir(parents=True, exist_ok=True)
        with mock.patch.object(subprocess, "run", side_effect=run), \
                mock.patch.object(subprocess, "Popen", side_effect=popen), \
                mock.patch.object(Path, "home", lambda *a, **k: home):
            checks = doctor.all_checks(store.db())
        return [c for c in checks if c.name.startswith(CHECK)]


def header_block(text: str) -> str | None:
    """Тело блока между первой строкой `---` и следующей; `None` — блока
    нет."""
    lines = text.split("\n")
    if lines[0] != "---" or "---" not in lines[1:]:
        return None
    end = lines.index("---", 1)
    return "\n".join(lines[1:end]) + "\n"


def split_stamp(text: str) -> tuple:
    """(разобранный заголовок | None, текст после строки `---`)."""
    block = header_block(text)
    if block is None:
        return None, text
    end = text.index("\n---\n") + len("\n---\n")
    return yamlmini.mapping(block), text[end:]


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


@pytest.fixture
def scene(real_git, seed):
    return StampScene(real_git, seed)


def assert_stamped(scene: StampScene, files: tuple, body: str) -> dict:
    """Заголовок требования 6 по `refs/heads/<base>` клона над прежним
    телом; возвращает разобранный заголовок."""
    text = scene.conventions.read_text(encoding="utf-8")
    assert text.startswith("---\n"), scene.msg(f"нет заголовка:\n{text[:200]}")
    stamp, rest = split_stamp(text)
    assert stamp is not None and "conventions_stamp" in stamp, scene.msg(
        f"заголовок без conventions_stamp:\n{text[:400]}")
    assert rest == body, scene.msg("текст под заголовком изменился")
    base_sha = scene.rev(f"refs/heads/{scene.base}")
    assert stamp["base_branch"] == scene.base, scene.msg(str(stamp))
    assert stamp["base_sha"] == base_sha, scene.msg(
        f"base_sha {stamp['base_sha']!r}, а refs/heads/{scene.base} — {base_sha}")
    assert f'base_sha: "{base_sha}"' in text, scene.msg("base_sha не в кавычках")
    expected = {rel: scene.rev(f"{base_sha}:{rel}") for rel in files}
    assert stamp["sources"] == expected, scene.msg(
        f"sources {stamp['sources']!r}, ожидалось {expected!r}")
    for rel, blob in expected.items():
        assert f'{rel}: "{blob}"' in text, scene.msg(f"blob {rel} не в кавычках")
    return stamp


# ------------------------------------------------------------------ AC-8

@pytest.mark.parametrize("start", ["без заголовка", "с прежним заголовком"])
def test_ac8_stamp_reads_base_ref_not_head_or_worktree(scene, start):
    """`HEAD` клона — на другой ветке с другими `AGENTS.md`/`CLAUDE.md`,
    рабочее дерево правит `AGENTS.md`; `conventions.md` — без заголовка или
    с прежним заголовком (другие `base_sha` и `sources`).

    После `conventions-stamp <проект> AGENTS.md CLAUDE.md` файл начинается
    заголовком требования 6: `base_branch` записи, `base_sha` равен
    `git rev-parse refs/heads/<base>`, `sources` — ровно оба файла с blob
    `git rev-parse <base_sha>:<файл>` (sha и blob в кавычках); текст под
    заголовком побайтно прежний. После коммита в базу, меняющего
    `CLAUDE.md`, повторная команда ставит новый `base_sha` и новый blob
    `CLAUDE.md`, тело то же.

    Ловит мутацию: коммит берётся `rev-parse HEAD` клона — `base_sha` и
    blob другой ветки; blob считается `git hash-object` файла рабочего
    дерева — blob `AGENTS.md` правки дерева; прежний заголовок не
    снимается, а новый дописывается сверху — тело несёт старый заголовок;
    `sources` дополняется к прежним вместо замены."""
    scene.prepare()
    head_blob = scene.rev("HEAD:AGENTS.md")
    tree_blob = scene.cgit("hash-object", str(scene.clone / "AGENTS.md")).strip()
    base_blob = scene.rev(f"refs/heads/{scene.base}:AGENTS.md")
    assert len({head_blob, tree_blob, base_blob}) == 3, scene.msg(
        "фикстура: версии AGENTS.md совпадают")
    if start == "с прежним заголовком":
        scene.write(scene.header(sources=f'\n  README.txt: "{hex40(scene.rng)}"')
                    + scene.body)
    files = ("AGENTS.md", "CLAUDE.md")
    ok, out = scene.stamp(scene.project, *files)
    assert ok, scene.msg(f"conventions-stamp отказал:\n{out}")
    first = assert_stamped(scene, files, scene.body)

    scene.commit_to(scene.base, {"CLAUDE.md": scene.tagged("CLAUDE-НОВЫЙ")})
    ok, out = scene.stamp(scene.project, *files)
    assert ok, scene.msg(f"повторный conventions-stamp отказал:\n{out}")
    second = assert_stamped(scene, files, scene.body)
    assert second["base_sha"] != first["base_sha"], scene.msg(
        "base_sha после нового коммита базы прежний")
    assert second["sources"]["CLAUDE.md"] != first["sources"]["CLAUDE.md"], \
        scene.msg("blob CLAUDE.md после нового коммита базы прежний")


# ------------------------------------------------------------------ AC-9

STAMP_REFUSALS = ["проект артели", "неизвестный проект", "клона нет",
                  "нет refs/heads/<base>", "файлы не названы",
                  "файла нет в дереве", "путь — каталог", "conventions.md нет",
                  "нет закрывающей ---", "sources — список",
                  "элемент sources без blob", "base_branch пуст",
                  "base_branch не строка"]


@pytest.mark.parametrize("case", STAMP_REFUSALS)
def test_ac9_stamp_refuses_without_touching_file(scene, case):
    """`conventions-stamp` в сценарии отказа: проект артели; неизвестный
    проект; путь клона не существует; в клоне нет `refs/heads/<base>`;
    файлы не названы; файла нет в дереве коммита базы; путь в дереве —
    каталог; `conventions.md` нет; заголовок сломан — без закрывающей
    `---`, `sources` — список, элемент `sources` без blob, `base_branch`
    пуст, `base_branch` — число.

    Сначала та же команда в исправном состоянии проекта ставит отметку
    (команда есть и работает); затем в сценарии отказа выходит ненулевым
    кодом с непустой причиной; `conventions.md` (у артели и неизвестного
    проекта — файл в их каталоге области проектов) побайтно прежний,
    отсутствующий — не появился.

    Ловит мутацию: неизвестный файл пропускается молча и заголовок
    пишется по остальным; каталог `docs` принимается за файл (`rev-parse
    <sha>:docs` даёт id дерева); при отсутствии `conventions.md` он
    создаётся с одним заголовком; сломанный заголовок не распознаётся и
    заменяется новым; проект артели не отсекается."""
    scene.prepare()
    ok, out = scene.stamp(scene.project, "AGENTS.md", "CLAUDE.md")
    assert ok, scene.msg(f"conventions-stamp в исправном состоянии отказал:\n{out}")
    project = scene.project
    files = ["AGENTS.md", "CLAUDE.md"]
    if case == "проект артели":
        project = config.DEFAULT_TARGET
    elif case == "неизвестный проект":
        project = f"nety{word(scene.rng)}"
    if project != scene.project:
        scene.conventions = (repo_context.projects_root() / project
                             / "conventions.md")
        scene.write(scene.body)
    if case == "клона нет":
        shutil.rmtree(scene.clone)
    elif case == "нет refs/heads/<base>":
        scene.cgit("branch", "-D", scene.base)
    elif case == "файлы не названы":
        files = []
    elif case == "файла нет в дереве":
        files = ["AGENTS.md", f"{word(scene.rng)}.md"]
    elif case == "путь — каталог":
        files = ["AGENTS.md", "docs"]
    elif case == "conventions.md нет":
        scene.conventions.unlink()
    elif case == "нет закрывающей ---":
        scene.write(scene.header().rsplit("---\n", 1)[0] + scene.body)
    elif case == "sources — список":
        scene.write(scene.header(sources=" [AGENTS.md, CLAUDE.md]") + scene.body)
    elif case == "элемент sources без blob":
        scene.write(scene.header(sources=(
            f'\n  AGENTS.md:\n  CLAUDE.md: "{hex40(scene.rng)}"')) + scene.body)
    elif case == "base_branch пуст":
        scene.write(scene.header(base_branch=' ""') + scene.body)
    elif case == "base_branch не строка":
        scene.write(scene.header(base_branch=f" {scene.rng.randrange(1, 10**6)}")
                    + scene.body)
    before = scene.snapshot()
    ok, out = scene.stamp(project, *files)
    assert not ok, scene.msg(f"{case}: conventions-stamp не отказал:\n{out}")
    assert out.strip(), scene.msg(f"{case}: отказ без причины")
    assert scene.snapshot() == before, scene.msg(
        f"{case}: conventions.md изменён при отказе")


# ----------------------------------------------------------------- AC-10

@pytest.mark.parametrize("change", ["AGENTS.md изменён в базе",
                                    "в базе изменён другой файл",
                                    "CLAUDE.md удалён из базы"])
def test_ac10_doctor_drift_by_base_ref_only(scene, change):
    """После `conventions-stamp <проект> AGENTS.md CLAUDE.md` в клоне с
    `HEAD` на другой ветке и правкой рабочего дерева.

    Строка `project-conventions` проекта — `ok`; после коммита в ветку
    `HEAD`, меняющего `AGENTS.md`, и новой правки `AGENTS.md` в рабочем
    дереве — `ok`; затем коммит в базу: меняет `AGENTS.md` — `warn` с
    «конвенции проекта изменились с последнего разбора» и `AGENTS.md`;
    меняет `README.txt` (не из `sources`) — `ok`; удаляет `CLAUDE.md` —
    `warn` с той же фразой и `CLAUDE.md`. `conventions.md` после каждого
    прогона `doctor` побайтно прежний.

    Ловит мутацию: сверка идёт по `HEAD` клона или по рабочему дереву —
    после коммита в `HEAD` уже `warn`; сверка по всему дереву коммита, а
    не по `sources`, — правка `README.txt` даёт `warn`; удалённый файл
    `sources` пропускается — `ok` вместо `warn`; `doctor` переписывает
    заголовок под текущую базу."""
    scene.prepare()
    ok, out = scene.stamp(scene.project, "AGENTS.md", "CLAUDE.md")
    assert ok, scene.msg(f"conventions-stamp отказал:\n{out}")
    stamped = scene.snapshot()

    def row():
        rows = scene.checks()
        assert len(rows) == 1, scene.msg(f"строк {CHECK}: {rows}")
        assert scene.snapshot() == stamped, scene.msg(
            "doctor изменил conventions.md")
        return rows[0]

    first = row()
    assert first.status == "ok", scene.msg(f"сразу после отметки: {first}")
    scene.commit_to(scene.other, {"AGENTS.md": scene.tagged("AGENTS-HEAD-НОВЫЙ")})
    (scene.clone / "AGENTS.md").write_text(scene.tagged("ПРАВКА-ДЕРЕВА-2"),
                                           encoding="utf-8")
    second = row()
    assert second.status == "ok", scene.msg(
        f"после коммита в HEAD и правки дерева: {second}")
    if change == "AGENTS.md изменён в базе":
        scene.commit_to(scene.base, {"AGENTS.md": scene.tagged("AGENTS-БАЗЫ-2")})
        expected = ("warn", "AGENTS.md")
    elif change == "в базе изменён другой файл":
        scene.commit_to(scene.base, {"README.txt": scene.tagged("ПРОЧЕЕ-2")})
        expected = ("ok", None)
    else:
        scene.commit_to(scene.base, {"CLAUDE.md": None})
        expected = ("warn", "CLAUDE.md")
    third = row()
    assert third.status == expected[0], scene.msg(f"{change}: {third}")
    if expected[1] is not None:
        assert DRIFT in third.detail and expected[1] in third.detail, \
            scene.msg(f"{change}: detail без «{DRIFT}» и {expected[1]}: "
                      f"{third.detail}")


# ----------------------------------------------------------------- AC-11

DOCTOR_CASES = [
    ("без заголовка", NO_STAMP),
    ("нет закрывающей ---", BROKEN), ("YamlError", BROKEN),
    ("base_sha не 40 hex", BROKEN), ("sources — список", BROKEN),
    ("элемент sources без blob", BROKEN), ("base_branch пуст", BROKEN),
    ("base_branch не строка", BROKEN),
    ("conventions.md нет", ONBOARDING),
    ("каталог", "не обычный файл"), ("символьная ссылка", "не обычный файл"),
    ("не UTF-8", "UTF-8"),
    ("клона нет", None), ("нет refs/heads/<base>", None),
]


@pytest.mark.parametrize("case,phrase", DOCTOR_CASES)
def test_ac11_doctor_warns_with_reason_and_never_raises(scene, case, phrase):
    """`doctor` для внешнего проекта: `conventions.md` без заголовка; со
    сломанным заголовком (случаи AC-3); нет файла; каталог; символьная
    ссылка на файл с годным заголовком; текст не в UTF-8; путь клона не
    существует (заголовок годный); в клоне нет `refs/heads/<base>`.

    `doctor.all_checks` не бросает исключения; строка `project-conventions`
    проекта ровно одна, её статус — `warn`, `detail` непуст и несёт фразу
    случая: «нет отметки разбора», «заголовок отметки не читается»,
    ссылку `docs/target-onboarding.md`, «не обычный файл», «UTF-8».

    Ловит мутацию: файл без заголовка сверяется как отмеченный — `ok`;
    сломанный `sources` (список, `None`) роняет сверку исключением;
    символьная ссылка читается по цели — `ok`; `UnicodeDecodeError` вне
    перехвата; удалённый клон или ветка базы дают `ok` или исключение
    git."""
    scene.prepare()
    files = ("AGENTS.md", "CLAUDE.md")
    ok, out = scene.stamp(scene.project, *files)
    assert ok, scene.msg(f"conventions-stamp отказал:\n{out}")
    stamped = scene.conventions.read_text(encoding="utf-8")
    good_header = stamped[:len(stamped) - len(scene.body)]
    if case == "без заголовка":
        scene.write(scene.body)
    elif case == "нет закрывающей ---":
        scene.write(good_header.rsplit("---\n", 1)[0] + scene.body)
    elif case == "YamlError":
        scene.write("---\nconventions_stamp: 1\nэто не пара ключ и значение\n"
                    "---\n" + scene.body)
    elif case == "base_sha не 40 hex":
        scene.write(scene.header(base_sha=f' "{hex40(scene.rng)[:39]}"')
                    + scene.body)
    elif case == "sources — список":
        scene.write(scene.header(sources=" [AGENTS.md, CLAUDE.md]") + scene.body)
    elif case == "элемент sources без blob":
        scene.write(scene.header(sources=(
            f'\n  AGENTS.md:\n  CLAUDE.md: "{hex40(scene.rng)}"')) + scene.body)
    elif case == "base_branch пуст":
        scene.write(scene.header(base_branch=' ""') + scene.body)
    elif case == "base_branch не строка":
        scene.write(scene.header(base_branch=f" {scene.rng.randrange(1, 10**6)}")
                    + scene.body)
    elif case == "conventions.md нет":
        scene.conventions.unlink()
    elif case == "каталог":
        scene.conventions.unlink()
        scene.conventions.mkdir()
    elif case == "символьная ссылка":
        real = scene.conventions.parent / f"real-{word(scene.rng)}.md"
        real.write_text(stamped, encoding="utf-8")
        scene.conventions.unlink()
        os.symlink(real, scene.conventions)
    elif case == "не UTF-8":
        codec = scene.rng.choice(("cp1251", "koi8-r"))
        scene.write(stamped.encode("utf-8")
                    + f"Правило {word(scene.rng)}\n".encode(codec))
    elif case == "клона нет":
        shutil.rmtree(scene.clone)
    elif case == "нет refs/heads/<base>":
        scene.cgit("checkout", "-q", "-f", scene.other)
        scene.cgit("branch", "-D", scene.base)
    rows = scene.checks()
    assert len(rows) == 1, scene.msg(f"{case}: строк {CHECK}: {rows}")
    assert rows[0].status == "warn", scene.msg(f"{case}: {rows[0]}")
    assert rows[0].detail.strip(), scene.msg(f"{case}: warn без причины")
    if phrase is not None:
        assert phrase in rows[0].detail, scene.msg(
            f"{case}: в detail нет «{phrase}»: {rows[0].detail}")


def test_ac11_artel_has_no_project_conventions_row(scene):
    """Проверки `doctor` в песочнице, где записан только проект артели, и
    после добавления одного внешнего проекта.

    Без внешних проектов строк `project-conventions` нет; с одним внешним
    — ровно одна, у артели строки нет.

    Ловит мутацию: цикл по проектам не отсекает `config.DEFAULT_TARGET` —
    у артели появляется строка `project-conventions` (`warn` «файла
    нет»)."""
    assert scene.checks() == [], scene.msg("строка project-conventions у артели")
    scene.prepare()
    rows = scene.checks()
    assert len(rows) == 1, scene.msg(f"строк {CHECK} при одном проекте: {rows}")


# ----------------------------------------------------------------- AC-13

def test_ac13_stamp_and_doctor_without_network(scene):
    """`conventions-stamp <проект> AGENTS.md CLAUDE.md` и проверки
    `doctor` сценария AC-10 при записи вызовов `subprocess.run`/`Popen` и
    отказе `socket.socket.connect`/`socket.create_connection`.

    Заголовок — как в AC-8 (`base_sha` — `refs/heads/<base>`, blob файлов
    на нём); строка `project-conventions` — `ok`, после коммита в базу,
    меняющего `AGENTS.md`, — `warn` с «конвенции проекта изменились с
    последнего разбора». Ни одного git-вызова `fetch`/`ls-remote`/`push` и
    ни одной попытки сокета — за всю команду и в вызовах из проверки
    `project-conventions`.

    Ловит мутацию: перед отметкой или сверкой база освежается `git fetch
    origin <base>` либо читается `git ls-remote` — в записи появляется
    сетевой git-вызов."""
    scene.prepare()
    stamp_rec, check_rec = Recorder(), Recorder()
    real_run, real_popen = subprocess.run, subprocess.Popen

    def recording(real, rec):
        def call(cmd, *args, **kwargs):
            argv = [cmd] if isinstance(cmd, (str, Path)) else list(cmd)
            rec.calls.append(([str(p) for p in argv], True))
            return real(cmd, *args, **kwargs)
        return call

    def refusing(rec):
        def connect(*args, **kwargs):
            rec.connects.append((args, rec.from_check() or rec is stamp_rec))
            raise OSError("сеть в тесте запрещена")
        return connect

    with mock.patch.object(subprocess, "run", recording(real_run, stamp_rec)), \
            mock.patch.object(subprocess, "Popen",
                              recording(real_popen, stamp_rec)), \
            mock.patch.object(socket.socket, "connect", refusing(stamp_rec)), \
            mock.patch.object(socket, "create_connection", refusing(stamp_rec)):
        ok, out = scene.stamp(scene.project, "AGENTS.md", "CLAUDE.md")
    assert ok, scene.msg(f"conventions-stamp отказал:\n{out}")
    assert_stamped(scene, ("AGENTS.md", "CLAUDE.md"), scene.body)

    with mock.patch.object(socket.socket, "connect", refusing(check_rec)), \
            mock.patch.object(socket, "create_connection", refusing(check_rec)):
        first = scene.checks(check_rec)
        scene.commit_to(scene.base, {"AGENTS.md": scene.tagged("AGENTS-БАЗЫ-2")})
        second = scene.checks(check_rec)
    assert [r.status for r in first] == ["ok"], scene.msg(str(first))
    assert [r.status for r in second] == ["warn"], scene.msg(str(second))
    assert DRIFT in second[0].detail, scene.msg(second[0].detail)
    assert any(own for _argv, own in check_rec.calls), scene.msg(
        "фикстура: ни одного вызова из проверки project-conventions")
    assert stamp_rec.network_git(only_check=False) == [], scene.msg(
        "сетевые git-вызовы conventions-stamp")
    assert check_rec.network_git(only_check=True) == [], scene.msg(
        "сетевые git-вызовы проверки project-conventions")
    assert stamp_rec.sockets(only_check=False) == [], scene.msg(
        "сокеты conventions-stamp")
    assert check_rec.sockets(only_check=True) == [], scene.msg(
        "сокеты проверки project-conventions")
