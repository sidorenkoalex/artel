"""Кэш справочника ядра: `orchestrator/reference_cache.get_reference` на настоящем git.

Группа: долгоживущий
Красен до реализации: модуля orchestrator/reference_cache.py ещё нет — `setUp` песочницы падает ImportError на `from orchestrator import reference_cache`.

Каждый тест держит связку «запись задачи в БД — `targets.yaml` — клон
проекта в области проектов — git-объекты коммита — файл кэша — журнал и
алерты». Песочница — `ConnRealGitSandbox`: `config.TARGETS` и
`config.PROJECTS` во временном каталоге, клоны проектов —
`make_project_repo` (настоящий git, внешний проект со своим деревом);
настоящий `targets.yaml` и боевая `.artel/projects` не читаются и не
пишутся.

Запуски процессов считаются подменой `subprocess.Popen` подклассом
настоящего: через него проходят и `subprocess.run`, и прямой `Popen`, а
процесс по-прежнему настоящий. Перехватчик запуска (`hooks`) может
бросить исключение (git «не ответил») или изменить мир до старта
процесса (сдвинуть подменённые часы, удалить объект blob).

Форму значения `get_reference` SPEC называет полями `text`, `note`,
`state`; тест читает их атрибутом или ключом (`field`).
"""
import ast
import builtins
import contextlib
import hashlib
import io
import os
import random
import re
import shutil
import subprocess
import time
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import alerts, config, repo_context, store
from tests.sandbox import ConnRealGitSandbox, artel_target_entry, make_project_repo

# Область проектов пульта на момент импорта модуля — до любой подмены
# песочницей: с ней и подменённым корнем `repo_context.projects_root()`
# отвечает `NO_AREA`.
LOADED_PROJECTS = config.PROJECTS

PROJECT = "proj"
TASK = "T901"
BRANCH = "task/t901-core-reference"
STATES = ("off", "fresh", "cached", "unverified", "absent")
BUILT = "справочник ядра: построен"
SOURCES = {"brief": "brief.core_reference", "merge": "fsm.core_reference_regen"}

CORE = '''"""Ядро проекта: справочный модуль."""


def engine(v: int, scale: float = 1.0) -> float:
    """Двигатель проекта."""
    return v * scale
'''
SETTINGS = '''"""Настройки проекта."""

LIMIT_A = 4242  # предел проекта
'''
SETTING = {"modules": ["lib/core.py", "conf/settings.py"],
           "constants_module": "conf/settings.py", "constants": ["LIMIT_A"]}
ENGINE = "engine(v: int, scale: float = 1.0) -> float"

ENTRY_TEXT = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


def users_count() -> int:
    """Пользователей у функции фикстуры — не меньше порога `config`."""
    return max(config.CORE_REFERENCE_MIN_USES, 1)


def project_files() -> dict:
    files = {"lib/core.py": CORE, "conf/settings.py": SETTINGS}
    files.update({f"use/u{i}.py": "from lib import core\ncore.engine(1)\n"
                  for i in range(users_count())})
    return files


def entry_yaml(name: str, setting: dict | None) -> str:
    text = ENTRY_TEXT.format(name=name, base=config.MAIN_BRANCH)
    if setting is None:
        return text
    lines = ["    core_reference:"]
    for key, value in setting.items():
        if isinstance(value, list):
            lines.append(f"      {key}: [{', '.join(str(x) for x in value)}]")
        else:
            lines.append(f"      {key}: {value}")
    return text + "\n".join(lines) + "\n"


def field(result, name: str):
    return result[name] if isinstance(result, dict) else getattr(result, name)


def squeeze(text: str) -> str:
    return "".join(text.split())


def has_signature(text: str, signature: str) -> bool:
    wanted = squeeze(signature)
    return any(wanted in squeeze(line) for line in text.split("\n"))


def numbers(text: str) -> set:
    return set(re.findall(r"\b\d+\b", text))


def tree_snapshot(root: Path) -> dict:
    """Путь -> sha256 файлов дерева песочницы, кроме git-объектов и БД."""
    found = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if (".git" in rel.parts or path.name.startswith("state.db")
                or not path.is_file()):
            continue
        found[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def refuse(*_args, **_kwargs):
    raise OSError("замена файла запрещена тестом")


@contextlib.contextmanager
def replace_fails():
    """Замена файла (`os.replace`/`os.rename`) отказывает `OSError`."""
    with mock.patch.object(os, "replace", refuse), \
            mock.patch.object(os, "rename", refuse):
        yield


class ReferenceSandbox(ConnRealGitSandbox):
    """Проекты с полем `core_reference`, задачи на их ветках, счёт запусков."""

    def setUp(self):
        super().setUp()
        from orchestrator import reference_cache
        from scripts import core_reference
        self.reference_cache = reference_cache
        self.generator = core_reference
        self.declared = {}
        self.clones = {}
        self.runs = []
        self.hooks = []
        self.recording = False
        sandbox = self
        real_popen = subprocess.Popen

        class SpyPopen(real_popen):
            def __init__(self, args, *rest, **kwargs):
                if sandbox.recording:
                    argv = ([str(a) for a in args]
                            if isinstance(args, (list, tuple)) else [str(args)])
                    sandbox.runs.append(argv)
                    for hook in list(sandbox.hooks):
                        hook(argv)
                super().__init__(args, *rest, **kwargs)

        patcher = mock.patch.object(subprocess, "Popen", SpyPopen)
        patcher.start()
        self.addCleanup(patcher.stop)

    # --- мир ----------------------------------------------------------------

    def write_targets(self) -> None:
        text = "targets:\n" + artel_target_entry()
        for name, setting in self.declared.items():
            text += entry_yaml(name, setting)
        if config.TARGETS.is_dir():
            config.TARGETS.rmdir()
        config.TARGETS.write_text(text, encoding="utf-8")

    def declare(self, name: str, setting: dict | None) -> None:
        self.declared[name] = setting
        self.write_targets()

    def add_project(self, name: str = PROJECT, setting: dict | None = SETTING,
                    files: dict | None = None, task: str = TASK,
                    branch: str = BRANCH) -> str:
        """Проект с записью в `targets.yaml`, клоном, задачей на ветке; sha коммита."""
        self.declare(name, setting)
        clone = make_project_repo(name, origin=False)
        self.clones[name] = clone
        self.git("-C", str(clone), "checkout", "-q", "-b", branch)
        store.insert_task(self.conn, task, "Задача", "in_dev", branch, name, 25.0)
        return self.commit(name, project_files() if files is None else files)

    def commit(self, name: str, files: dict, message: str = "правка") -> str:
        clone = self.clones[name]
        for rel, content in files.items():
            path = clone / rel
            if content is None:
                path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8")
        self.git("-C", str(clone), "add", "-A")
        self.git("-C", str(clone), "commit", "-q", "--allow-empty", "-m", message)
        return self.head(name)

    def head(self, name: str = PROJECT) -> str:
        return self.git("-C", str(self.clones[name]), "rev-parse", "HEAD").strip()

    def cache_path(self, name: str = PROJECT) -> Path:
        return config.PROJECTS / name / "knowledge" / "derived" / "core-reference.md"

    def drop_cache(self, name: str = PROJECT) -> None:
        path = self.cache_path(name)
        if path.is_symlink() or path.exists():
            path.unlink()

    # --- вызов и наблюдения -------------------------------------------------

    def get(self, task: str = TASK, reason: str = "brief", sha: str | None = None,
            hooks=()):
        self.runs, self.hooks, self.recording = [], list(hooks), True
        try:
            return self.reference_cache.get_reference(self.conn, task,
                                                      reason=reason, sha=sha)
        finally:
            self.recording, self.hooks = False, []

    def git_runs(self) -> list:
        return [argv for argv in self.runs if argv and Path(argv[0]).name == "git"]

    def runs_of(self, subcommand: str) -> list:
        return [argv for argv in self.git_runs() if subcommand in argv]

    def built(self, task: str = TASK) -> list:
        return [row for row in store.task_steps(self.conn, task)
                if BUILT in f"{row['action']} {row['detail']}"]

    def ack_all(self) -> None:
        """Подтвердить открытые алерты: тот же сбой следующего подслучая заводит новый."""
        for row in alerts.open_alerts(self.conn):
            alerts.ack(self.conn, row["id"], "test", "снят тестом")

    def new_alerts(self, since: int, target: str = PROJECT) -> list:
        return [row for row in alerts.open_alerts(self.conn)
                if row["id"] > since and row["target"] == target]

    def assert_state(self, result, state: str) -> None:
        self.assertEqual(state, field(result, "state"),
                         f"note: {field(result, 'note')!r}")

    @contextlib.contextmanager
    def counted_reads(self, path: Path):
        """Открытия `path` на чтение (`open`/`io.open`, через них и `Path.read_*`)."""
        reads = []
        real_open = builtins.open
        target = Path(path).resolve()

        def spy(file, mode="r", *args, **kwargs):
            if (isinstance(file, (str, bytes, os.PathLike))
                    and not any(flag in mode for flag in "wax+")):
                try:
                    same = Path(os.fsdecode(file)).resolve() == target
                except (OSError, ValueError):
                    same = False
                if same:
                    reads.append(mode)
            return real_open(file, mode, *args, **kwargs)

        with mock.patch.object(builtins, "open", spy), \
                mock.patch.object(io, "open", spy):
            yield reads


def raise_on(subcommand: str | None, exc_factory):
    """Перехватчик запуска: git (подкоманда `subcommand` или любой) бросает исключение."""
    def hook(argv):
        if Path(argv[0]).name == "git" and (subcommand is None or subcommand in argv):
            raise exc_factory(argv)
    return hook


class SourceReadingTest(ReferenceSandbox):
    """AC-10: пакетное чтение коммита, пропуски, пределы и общий срок."""

    def test_ac10_two_git_launches_whatever_the_number_of_files(self):
        """Сборка на переданном sha — один `ls-tree` и один `cat-file --batch` при любом числе файлов.

        Число `.py` в коммите случайно — малое и большое; запуски считаются
        и через `subprocess.run`, и через `subprocess.Popen`.

        Ловит мутацию: исходники читаются `git show <sha>:<путь>` на файл
        (число запусков растёт с числом файлов) или `cat-file` зовётся на
        каждый blob.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        self.add_project()
        for count in (rng.randint(1, 4), rng.randint(40, 80)):
            with self.subTest(files=count):
                sha = self.commit(PROJECT, {f"fill/f{i}.py": f"VALUE_{i} = {i}\n"
                                            for i in range(count)})
                result = self.get(sha=sha)
                self.assert_state(result, "fresh")
                runs = self.git_runs()
                self.assertLessEqual(len(runs), 2, f"зерно: {seed}: {runs}")
                self.assertEqual(1, len(self.runs_of("ls-tree")), runs)
                cat = [argv for argv in runs if "cat-file" in argv]
                self.assertEqual(1, len(cat), runs)
                self.assertTrue(any(arg.startswith("--batch") for arg in cat[0]), cat)

    def test_ac10_no_cat_file_without_suitable_blobs(self):
        """В коммите без `.py` `cat-file` не запускается.

        Ловит мутацию: `cat-file --batch` запускается с пустым входом
        безусловно — второй запуск git есть.
        """
        sha = self.add_project(files={"README.txt": "кода нет\n"})
        self.get(sha=sha)
        self.assertEqual([], self.runs_of("cat-file"), self.git_runs())
        self.assertLessEqual(len(self.git_runs()), 1, self.git_runs())

    def test_ac10_malformed_sha_is_refused_before_any_git_launch(self):
        """sha не из 40 шестнадцатеричных знаков отклоняется без единого запуска git.

        Ловит мутацию: sha уходит в `git ls-tree` без проверки формы
        (`-x` — опция git, `HEAD` — не коммит) — запуск git есть.
        """
        self.add_project()
        for bad in ("-x", "HEAD", "abc123", "g" * 40, "a" * 39, "a" * 41,
                    " " + "a" * 39, "--output=x" + "a" * 30):
            with self.subTest(sha=bad):
                result = self.get(sha=bad)
                self.assertEqual([], self.git_runs())
                self.assertNotIn(field(result, "state"), ("fresh", "cached"))

    def test_ac10_reads_commit_objects_not_the_working_tree(self):
        """Незакоммиченная правка модуля в клоне в справочник не попадает.

        Ловит мутацию: сборка читает файлы рабочего дерева клона (или
        делает checkout) — в тексте «Незакоммиченный двигатель».
        """
        sha = self.add_project()
        core = self.clones[PROJECT] / "lib" / "core.py"
        core.write_text(CORE.replace("Двигатель проекта.", "Незакоммиченный двигатель."),
                        encoding="utf-8")
        result = self.get()
        self.assert_state(result, "fresh")
        text = field(result, "text")
        self.assertIn("Двигатель проекта.", text)
        self.assertNotIn("Незакоммиченный", text)
        self.assertIn(sha, text)

    def test_ac10_links_submodules_large_and_missing_blobs_are_skipped_and_counted(self):
        """Ссылки, подмодули, крупные blob и ответ `missing` не разбираются и посчитаны числом.

        Базовый коммит: модуль с `edge` и пользователи на один меньше
        порога. Каждый вид добавляет `k` записей (случайное, не
        встречающееся числом в базовом тексте) с обращением к `core.edge`
        там, где у записи есть текст: символьные ссылки с целью
        `core.edge`, подмодули (gitlink), blob крупнее подменённого
        `CORE_REFERENCE_MAX_BLOB_BYTES`, blob'ы, чей объект удаляется
        перед запуском `cat-file` (ответ `missing`). `edge` в справочник
        не входит, число `k` в тексте появляется.

        Ловит мутацию: отбор записей `ls-tree` без режима (ссылка 120000
        разобрана — `edge` войдёт), без типа (gitlink 160000 ушёл в
        `cat-file`), без размера (крупный blob разобран), строка `missing`
        роняет разбор ответа, либо пропуски не считаются (числа `k` нет).
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        core = ('"""Модуль края."""\n\n\n'
                'def edge(v: int) -> int:\n    """Край."""\n    return v\n')
        files = {"lib/core.py": core}
        files.update({f"use/u{i}.py": "from lib import core\ncore.edge\n"
                      for i in range(users_count() - 1)})
        base = self.add_project(setting={"modules": ["lib/core.py"]}, files=files)
        clone = self.clones[PROJECT]
        baseline = field(self.get(sha=base), "text")
        self.assertFalse(has_signature(baseline, "edge(v: int) -> int"), baseline)
        limit = 4096

        def links(k):
            (clone / "links").mkdir()
            for i in range(k):
                (clone / "links" / f"l{i}.py").symlink_to("core.edge")
            return self.commit(PROJECT, {}), (), contextlib.nullcontext()

        def submodules(k):
            for i in range(k):
                self.git("-C", str(clone), "update-index", "--add", "--cacheinfo",
                         f"160000,{base},subs/s{i}.py")
            self.git("-C", str(clone), "commit", "-q", "-m", "подмодули")
            return self.head(), (), contextlib.nullcontext()

        def large(k):
            sha = self.commit(PROJECT, {
                f"big/b{i}.py": "from lib import core\ncore.edge\n" + "#" * (limit + 64) + "\n"
                for i in range(k)})
            return sha, (), mock.patch.object(config, "CORE_REFERENCE_MAX_BLOB_BYTES", limit)

        def missing(k):
            sha = self.commit(PROJECT, {
                f"ghosts/g{i}.py": f"from lib import core\ncore.edge\n# призрак {i}\n"
                for i in range(k)})
            blobs = [self.git("-C", str(clone), "rev-parse", f"HEAD:ghosts/g{i}.py").strip()
                     for i in range(k)]

            def drop_objects(argv):
                if "cat-file" in argv:
                    for blob in blobs:
                        obj = clone / ".git" / "objects" / blob[:2] / blob[2:]
                        if obj.exists():
                            obj.unlink()
            return sha, (drop_objects,), contextlib.nullcontext()

        kinds = (("символьные ссылки", links), ("подмодули", submodules),
                 ("крупные blob", large), ("ответ missing", missing))
        for kind, make in kinds:
            with self.subTest(kind=kind):
                self.git("-C", str(clone), "reset", "-q", "--hard", base)
                self.git("-C", str(clone), "clean", "-fdq")
                k = rng.choice([n for n in range(11, 30)
                                if str(n) not in numbers(baseline)])
                sha, hooks, patch = make(k)
                with patch:
                    result = self.get(sha=sha, hooks=hooks)
                context = f"зерно: {seed}, вид «{kind}», k={k}"
                self.assert_state(result, "fresh")
                text = field(result, "text")
                self.assertFalse(has_signature(text, "edge(v: int) -> int"),
                                 f"{context}\n{text}")
                self.assertIn(str(k), numbers(text), f"{context}\n{text}")

    def test_ac8_non_utf8_blob_is_counted_and_excluded_from_usage(self):
        """Blob коммита не в UTF-8 сборку не роняет, в подсчёт не входит и посчитан числом.

        Базовый коммит: модуль с `edge` и пользователи на один меньше
        порога; затем `k` (случайное, не встречающееся числом в базовом
        тексте) файлов с обращением к `core.edge` и байтом `\\xff` в
        комментарии. Такой файл получается только из git-объекта:
        `build` принимает тексты.

        Ловит мутацию: blob декодируется с заменой (`errors="replace"`) и
        разбирается — `edge` войдёт в справочник; `UnicodeDecodeError` не
        пойман — сборка не `fresh`; неразобранные не посчитаны — числа `k`
        в тексте нет.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        core = ('"""Модуль края."""\n\n\n'
                'def edge(v: int) -> int:\n    """Край."""\n    return v\n')
        files = {"lib/core.py": core}
        files.update({f"use/u{i}.py": "from lib import core\ncore.edge\n"
                      for i in range(users_count() - 1)})
        base = self.add_project(setting={"modules": ["lib/core.py"]}, files=files)
        baseline = field(self.get(sha=base), "text")
        k = rng.choice([n for n in range(11, 30) if str(n) not in numbers(baseline)])
        sha = self.commit(PROJECT, {f"latin/l{i}.py": b"from lib import core\n"
                                    b"core.edge\n# \xff\xfe\n" for i in range(k)})
        result = self.get(sha=sha)
        context = f"зерно: {seed}, k={k}"
        self.assert_state(result, "fresh")
        text = field(result, "text")
        self.assertFalse(has_signature(text, "edge(v: int) -> int"), f"{context}\n{text}")
        self.assertIn(str(k), numbers(text), f"{context}\n{text}")

    def test_ac10_limits_by_listing_sizes_stop_before_cat_file(self):
        """Число файлов, объём по размерам `ls-tree` и вывод `ls-tree` сверх предела — `absent` без `cat-file`.

        Пределы подменяются на значения от фактического коммита: на один
        файл меньше, на один байт меньше суммы размеров `.py`, вывод
        `ls-tree` — 10 байт. Кэш не пишется, `note` не пуст.

        Ловит мутацию: пределы проверяются после чтения `cat-file` (запуск
        `cat-file` есть), не проверяются вовсе (справочник собран), вывод
        `ls-tree` читается целиком без предела.
        """
        files = project_files()
        sha = self.add_project(files=files)
        py = {rel: text for rel, text in files.items() if rel.endswith(".py")}
        total = sum(len(text.encode("utf-8")) for text in py.values())
        for attr, value in (("CORE_REFERENCE_MAX_FILES", len(py) - 1),
                            ("CORE_REFERENCE_MAX_SOURCE_BYTES", total - 1),
                            ("CORE_REFERENCE_MAX_LISTING_BYTES", 10)):
            with self.subTest(limit=attr):
                self.drop_cache()
                with mock.patch.object(config, attr, value):
                    result = self.get(sha=sha)
                self.assert_state(result, "absent")
                self.assertEqual([], self.runs_of("cat-file"), self.git_runs())
                self.assertFalse(self.cache_path().exists())
                self.assertFalse(field(result, "text"))
                self.assertTrue(field(result, "note"))

    def test_ac10_shared_deadline_stops_the_build(self):
        """Общий срок, исчерпанный к `cat-file`, после него или во время разбора, — `absent`.

        Часы (`time.monotonic`, `time.time`, `time.perf_counter`) подменены
        и прыгают на срок `config.CORE_REFERENCE_GIT_TIMEOUT_SEC` плюс час
        в выбранный момент: при запуске `ls-tree`, при запуске `cat-file`
        или на первом `ast.parse` сборки. Настоящего ожидания нет. Срок,
        исчерпанный к второму вызову, второго вызова (`cat-file`) не
        допускает; исчерпанный до разбора — разбора не начинает
        (`ast.parse` в сборке не зовётся).

        Ловит мутацию: второму вызову передаётся полный срок, а не остаток
        (`cat-file` запущен после прыжка при `ls-tree`), срок не
        проверяется сразу после `cat-file` (разбор начат — `ast.parse`
        вызван) или после разбора — справочник собран.
        """
        sha = self.add_project()
        jump = config.CORE_REFERENCE_GIT_TIMEOUT_SEC + 3600
        offset = [0.0]
        clocks = {name: getattr(time, name) for name in
                  ("monotonic", "time", "perf_counter")}
        real_parse = ast.parse

        def jump_on(subcommand):
            def hook(argv):
                if subcommand in argv:
                    offset[0] += jump
            return hook

        def parse(*args, **kwargs):
            if self.recording:
                parsed[0] += 1
                if moment == "разбор" and parsed[0] == 1:
                    offset[0] += jump
            return real_parse(*args, **kwargs)

        with contextlib.ExitStack() as stack:
            for name, real in clocks.items():
                stack.enter_context(mock.patch.object(
                    time, name, lambda real=real: real() + offset[0]))
            stack.enter_context(mock.patch.object(ast, "parse", parse))
            for moment in ("ls-tree", "cat-file", "разбор"):
                with self.subTest(moment=moment):
                    self.drop_cache()
                    offset[0] = 0.0
                    parsed = [0]
                    if moment == "разбор":
                        result = self.get(sha=sha)
                        self.assertTrue(parsed[0], "разбор не вызывал ast.parse")
                    else:
                        result = self.get(sha=sha, hooks=(jump_on(moment),))
                        self.assertEqual(0, parsed[0],
                                         "разбор начат после исчерпания срока")
                    if moment == "ls-tree":
                        self.assertEqual([], self.runs_of("cat-file"),
                                         "второй вызов после исчерпания срока")
                    self.assert_state(result, "absent")
                    self.assertFalse(self.cache_path().exists())
                    self.assertTrue(field(result, "note"))


def wide_files(count: int) -> tuple[dict, dict]:
    """`count` маленьких модулей по функции и пользователи всех: тело кэша много больше blob."""
    files = {}
    for i in range(count):
        files[f"lib/m{i}.py"] = (f'"""Модуль номер {i}."""\n\n\n'
                                 f"def f{i}(v: int) -> int:\n"
                                 f'    """Функция номер {i} модуля проекта."""\n'
                                 "    return v\n")
    imports = "from lib import " + ", ".join(f"m{i}" for i in range(count)) + "\n"
    calls = "".join(f"m{i}.f{i}(1)\n" for i in range(count))
    files.update({f"use/u{j}.py": imports + calls for j in range(users_count())})
    return files, {"modules": [f"lib/m{i}.py" for i in range(count)]}


class CacheFileTest(ReferenceSandbox):
    """AC-11: место кэша, атомарная запись, одно чтение, правила годности."""

    def test_ac11_cache_is_written_only_under_knowledge_derived(self):
        """Сборка меняет в дереве песочницы ровно один файл — `<область>/<проект>/knowledge/derived/core-reference.md`.

        Ловит мутацию: кэш пишется в клон проекта, в `knowledge/` без
        `derived/`, рядом с `targets.yaml` или временный файл остаётся
        после замены — изменённых файлов больше одного или путь другой.

        Служебные файлы самого журнала (метка сессии пульта) заводятся
        пробной записью журнала до снимка — они не предмет проверки.
        """
        self.add_project()
        store.journal(self.conn, TASK, "test", "проба журнала до снимка")
        before = tree_snapshot(self.root)
        result = self.get()
        self.assert_state(result, "fresh")
        after = tree_snapshot(self.root)
        changed = {p for p in after if before.get(p) != after[p]} | (
            set(before) - set(after))
        expected = str(self.cache_path().relative_to(self.root))
        self.assertEqual({expected}, changed)
        self.assertEqual(self.cache_path().read_text(encoding="utf-8"),
                         field(result, "text"))

    def test_ac11_failed_replace_keeps_previous_cache_intact(self):
        """Сбой замены файла при новой сборке оставляет прежний кэш байт в байт.

        Ловит мутацию: запись прямо в файл кэша (`write_text` по месту)
        вместо временного файла и замены — после сбоя файл перезаписан
        текстом нового sha.
        """
        self.add_project()
        self.assert_state(self.get(), "fresh")
        previous = self.cache_path().read_bytes()
        sha = self.commit(PROJECT, {"use/extra.py": "EXTRA = 2\n"})
        with replace_fails():
            result = self.get()
        self.assertEqual(previous, self.cache_path().read_bytes())
        self.assert_state(result, "fresh")
        self.assertIn(sha, field(result, "text"))

    def test_ac11_cache_file_is_read_once_per_call(self):
        """На выдачу файл кэша открывается на чтение один раз — и при `cached`, и при пересборке.

        Ловит мутацию: шапка и тело читаются двумя прочтениями (шапка
        построчно, затем тело `read_text`) — открытий два.
        """
        self.add_project()
        self.assert_state(self.get(), "fresh")
        with self.counted_reads(self.cache_path()) as reads:
            result = self.get()
        self.assert_state(result, "cached")
        self.assertEqual(1, len(reads), reads)
        self.commit(PROJECT, {"use/extra.py": "EXTRA = 2\n"})
        with self.counted_reads(self.cache_path()) as reads:
            result = self.get()
        self.assert_state(result, "fresh")
        self.assertLessEqual(len(reads), 1, reads)

    def test_ac11_rebuilds_on_any_mismatch_and_reuses_a_full_match(self):
        """Новый sha, другая настройка, испорченное тело, чужой `generator_sha256`, не файл, крупный файл — пересборка.

        После каждой пересборки (`fresh`, новая запись «справочник ядра:
        построен») повторная выдача на том же sha — `cached` без записи
        журнала и с текстом файла кэша. Предел размера файла кэша
        подменяется так, что blob'ы коммита в него влезают, а файл кэша
        больше четырёх пределов.

        Ловит мутацию: годность сверяет только `built_at_sha` (другая
        настройка, тело, генератор отданы как `cached`), sha256 тела не
        пересчитывается, символьная ссылка принята за файл (`is_file`
        вместо `lstat`), размер файла не проверяется, или кэш
        перестраивается и при полном совпадении (запись журнала на
        повторной выдаче).
        """
        files, setting = wide_files(8)
        self.add_project(setting=setting, files=files)
        self.assert_state(self.get(), "fresh")
        cache = self.cache_path()
        expected_gen = hashlib.sha256(
            Path(self.generator.__file__).read_bytes()).hexdigest()

        def assert_reused():
            count = len(self.built())
            result = self.get()
            self.assert_state(result, "cached")
            self.assertEqual(count, len(self.built()))
            self.assertEqual(cache.read_text(encoding="utf-8"), field(result, "text"))

        def new_sha():
            self.commit(PROJECT, {"use/more.py": "MORE = 1\n"})

        def other_setting():
            self.declare(PROJECT, {"modules": setting["modules"][:-1]})

        def corrupt_body():
            text = cache.read_text(encoding="utf-8")
            self.assertIn("Функция номер 1 модуля проекта.", text)
            cache.write_text(text.replace("Функция номер 1 модуля проекта.",
                                          "Подменённое описание функции."),
                             encoding="utf-8")

        def other_generator():
            text = cache.read_text(encoding="utf-8")
            self.assertIn(expected_gen, text)
            cache.write_text(text.replace(expected_gen, "0" * 64), encoding="utf-8")

        def not_a_file():
            copy = self.root / "cache-copy.md"
            shutil.copyfile(cache, copy)
            cache.unlink()
            cache.symlink_to(copy)

        assert_reused()
        for case, spoil in (("новый sha", new_sha), ("другая настройка", other_setting),
                            ("испорченное тело", corrupt_body),
                            ("другой generator_sha256", other_generator),
                            ("не обычный файл", not_a_file)):
            with self.subTest(case=case):
                count = len(self.built())
                spoil()
                self.assert_state(self.get(), "fresh")
                self.assertEqual(count + 1, len(self.built()))
                assert_reused()
        with self.subTest(case="крупнее четырёх CORE_REFERENCE_MAX_BLOB_BYTES"):
            size = cache.stat().st_size
            biggest = max(len(text.encode("utf-8")) for text in files.values())
            limit = (size - 1) // 4
            self.assertGreaterEqual(limit, biggest, "фикстура: кэш мал для проверки")
            count = len(self.built())
            with mock.patch.object(config, "CORE_REFERENCE_MAX_BLOB_BYTES", limit):
                self.assert_state(self.get(), "fresh")
            self.assertEqual(count + 1, len(self.built()))
            assert_reused()

    def test_ac11_generator_sha256_is_hash_of_the_loaded_generator_file(self):
        """`generator_sha256` в шапке — sha256 байт файла загруженного модуля генератора.

        В песочнице `config.ROOT` — временный каталог без
        `scripts/core_reference.py`.

        Ловит мутацию: хэш берётся от `config.ROOT / "scripts" /
        "core_reference.py"` (в песочнице файла нет — сборка падает) или
        от пути/имени модуля, а не байт файла (значение не совпадёт).
        """
        self.assertFalse((config.ROOT / "scripts" / "core_reference.py").exists())
        expected = hashlib.sha256(Path(self.generator.__file__).read_bytes()).hexdigest()
        self.add_project()
        result = self.get()
        self.assert_state(result, "fresh")
        self.assertIn(expected, field(result, "text"))


class StatesTest(ReferenceSandbox):
    """AC-12: исходы `get_reference` и отсутствие побочных эффектов у `off`."""

    def snapshot_effects(self, task: str) -> tuple:
        return (len(store.task_steps(self.conn, task)), store.max_alert_id(self.conn))

    def test_ac12_off_without_field_or_entry_has_no_side_effects(self):
        """Проект без поля и задача проекта без записи в читаемом `targets.yaml` — `off` без следов.

        Ловит мутацию: проект без поля идёт в сборку с настройкой по
        умолчанию (запуск git, кэш) или отсутствие записи считается
        нечитаемым файлом (алерт, `absent`).
        """
        self.add_project(name="plain", setting=None, task="T902",
                         branch="task/t902-plain")
        store.insert_task(self.conn, "T903", "Задача", "in_dev", "task/t903-ghost",
                          "ghost", 25.0)
        for task, project in (("T902", "plain"), ("T903", "ghost")):
            with self.subTest(project=project):
                before = self.snapshot_effects(task)
                result = self.get(task=task)
                self.assert_state(result, "off")
                self.assertEqual([], self.git_runs())
                self.assertEqual(before, self.snapshot_effects(task))
                self.assertFalse((config.PROJECTS / project / "knowledge" / "derived").exists())
                self.assertFalse(field(result, "text"))

    def test_ac12_no_area_is_off_before_reading_targets(self):
        """При `NO_AREA` — `off` без пометки, git, журнала, алерта, файла и чтения `targets.yaml`.

        `NO_AREA` воспроизводится так, как его видит пульт: корень
        подменён, а область проектов — та, что была при загрузке модулей
        (и `repo_context.projects_root` подменён тем же ответом).

        Ловит мутацию: проверка области стоит после чтения `targets.yaml`
        (файл открыт) или её нет (запуск git, запись журнала и кэша).
        """
        self.add_project()
        cache = self.cache_path()
        before = self.snapshot_effects(TASK)
        with mock.patch.object(config, "PROJECTS", LOADED_PROJECTS), \
                mock.patch.object(repo_context, "projects_root",
                                  return_value=repo_context.NO_AREA), \
                self.counted_reads(config.TARGETS) as reads:
            result = self.get()
        self.assert_state(result, "off")
        self.assertFalse(field(result, "note"))
        self.assertFalse(field(result, "text"))
        self.assertEqual([], self.git_runs())
        self.assertEqual([], reads)
        self.assertEqual(before, self.snapshot_effects(TASK))
        self.assertFalse(cache.exists())

    def test_ac12_unreadable_or_invalid_targets_give_absent_with_note_and_alert(self):
        """Нечитаемый `targets.yaml`, запись без разбора поля, неверное поле — `absent`, пометка, алерт.

        Ловит мутацию: сбой чтения настройки отдаётся как `off` (молчаливое
        выключение справочника) или без алерта.
        """
        self.add_project()
        artel = artel_target_entry()
        cases = {
            "файл не UTF-8": b"targets:\n  proj: \xff\xfe\n",
            "файл не разбирается": "targets:\n  proj: [unclosed\n",
            "каталог вместо файла": None,
            "запись не набор полей": "targets:\n" + artel + "  proj: 5\n",
            "запись без поля forge": "targets:\n" + artel + entry_yaml(
                PROJECT, SETTING).replace("    forge: github\n", ""),
            "неверное поле": "targets:\n" + artel + entry_yaml(PROJECT, {"modules": []}),
        }
        for case, content in cases.items():
            with self.subTest(case=case):
                self.drop_cache()
                self.ack_all()
                if content is None:
                    config.TARGETS.unlink()
                    config.TARGETS.mkdir()
                elif isinstance(content, bytes):
                    config.TARGETS.write_bytes(content)
                else:
                    config.TARGETS.write_text(content, encoding="utf-8")
                since = store.max_alert_id(self.conn)
                result = self.get()
                self.write_targets()
                self.assert_state(result, "absent")
                self.assertTrue(field(result, "note"))
                self.assertFalse(field(result, "text"))
                self.assertTrue([a for a in self.new_alerts(since)
                                 if a["kind"] == "incident"
                                 and a["source"] == SOURCES["brief"]])

    def test_ac12_unknown_branch_head_gives_unverified_or_absent(self):
        """Голову ветки не узнать — при кэше `unverified` с «не сверен: …, built_at_sha=…», без — `absent`.

        Причины: ветки задачи нет, клона нет, git не отвечает (запуск
        бросает `OSError`).

        Ловит мутацию: при неизвестной голове кэш отдаётся как `cached`
        (без пометки), исходы `unverified`/`absent` перепутаны или
        пометка не называет `built_at_sha` кэша.
        """
        sha = self.add_project()
        self.assert_state(self.get(), "fresh")
        content = self.cache_path().read_text(encoding="utf-8")
        clone = self.clones[PROJECT]
        away = clone.with_name("repo-away")

        def no_branch():
            self.git("-C", str(clone), "checkout", "-q", config.MAIN_BRANCH)
            self.git("-C", str(clone), "branch", "-q", "-D", BRANCH)
            return ()

        def restore_branch():
            self.git("-C", str(clone), "branch", "-q", BRANCH, sha)
            self.git("-C", str(clone), "checkout", "-q", BRANCH)

        def no_clone():
            clone.rename(away)
            return ()

        def restore_clone():
            away.rename(clone)

        causes = (("ветки нет", no_branch, restore_branch),
                  ("клона нет", no_clone, restore_clone),
                  ("git не отвечает",
                   lambda: (raise_on(None, lambda argv: OSError("git молчит")),),
                   lambda: None))
        for with_cache in (True, False):
            if not with_cache:
                self.drop_cache()
            for cause, spoil, restore in causes:
                with self.subTest(cause=cause, cache=with_cache):
                    hooks = spoil()
                    try:
                        result = self.get(hooks=hooks)
                    finally:
                        restore()
                    note = field(result, "note")
                    if with_cache:
                        self.assert_state(result, "unverified")
                        self.assertEqual(content, field(result, "text"))
                        self.assertIn("не сверен", note)
                        self.assertIn(f"built_at_sha={sha}", note)
                    else:
                        self.assert_state(result, "absent")
                        self.assertTrue(note)
                        self.assertFalse(field(result, "text"))

    def test_ac12_known_sha_with_failed_source_and_foreign_cache_is_absent(self):
        """sha известен, источник упал или вышел за пределы, кэш другого sha — `absent`, алерт, кэш не отдан.

        Ловит мутацию: при сбое источника отдаётся кэш другого sha как
        `unverified`/`cached` или сбой проходит без алерта.
        """
        self.add_project()
        self.assert_state(self.get(), "fresh")

        def missing_object():
            return {"sha": "d" * 40}, contextlib.nullcontext()

        def over_limit():
            self.commit(PROJECT, {"use/extra.py": "EXTRA = 2\n"})
            return {}, mock.patch.object(config, "CORE_REFERENCE_MAX_FILES", 1)

        def git_fails():
            sha = self.commit(PROJECT, {"use/other.py": "OTHER = 3\n"})
            return ({"sha": sha, "hooks": (raise_on("ls-tree",
                                                    lambda argv: OSError("сбой")),)},
                    contextlib.nullcontext())

        for case, make in (("переданный sha без объекта", missing_object),
                           ("голова ветки сверх предела", over_limit),
                           ("git упал на чтении", git_fails)):
            with self.subTest(case=case):
                self.ack_all()
                kwargs, patch = make()
                since = store.max_alert_id(self.conn)
                with patch:
                    result = self.get(**kwargs)
                self.assert_state(result, "absent")
                self.assertFalse(field(result, "text"))
                self.assertTrue(field(result, "note"))
                self.assertTrue([a for a in self.new_alerts(since)
                                 if a["kind"] == "incident"])

    def test_ac12_passed_sha_is_used_instead_of_the_branch_head(self):
        """Переданный `sha` даёт справочник того коммита, `sha=None` — головы ветки.

        Ловит мутацию: параметр `sha` игнорируется (взята голова ветки —
        в тексте «второй версии» и sha головы).
        """
        first = self.add_project()
        second = self.commit(PROJECT, {"lib/core.py": CORE.replace(
            "Двигатель проекта.", "Двигатель второй версии.")})
        result = self.get(sha=first)
        self.assert_state(result, "fresh")
        text = field(result, "text")
        self.assertIn("Двигатель проекта.", text)
        self.assertNotIn("второй версии", text)
        self.assertIn(first, text)
        self.assertNotIn(second, text)
        text = field(self.get(), "text")
        self.assertIn("Двигатель второй версии.", text)
        self.assertIn(second, text)

    def test_ac12_each_build_journals_sha_sizes_duration_and_reason(self):
        """Каждая сборка — запись «справочник ядра: построен» с sha, числами и поводом.

        Числа записи (байты, число записей, длительность) SPEC по форме не
        фиксирует: проверяется, что кроме sha в записи не меньше трёх
        чисел.

        Ловит мутацию: запись журнала не пишется, пишется без sha или без
        повода (`brief`/`merge` не различимы), без размеров и длительности.
        """
        first = self.add_project()
        second = self.commit(PROJECT, {"use/extra.py": "E = 1\n"})
        for reason, sha in (("brief", first), ("merge", second)):
            with self.subTest(reason=reason):
                count = len(self.built())
                self.assert_state(self.get(reason=reason, sha=sha), "fresh")
                rows = self.built()
                self.assertEqual(count + 1, len(rows))
                entry = f"{rows[-1]['action']} {rows[-1]['detail']}"
                self.assertIn(sha, entry)
                self.assertIn(reason, entry)
                rest = entry.replace(sha, " ")
                self.assertGreaterEqual(len(re.findall(r"\d+(?:[.,]\d+)?", rest)), 3,
                                        entry)

    def test_ac12_never_raises_on_git_write_or_parse_failure(self):
        """Сбой запуска git, срок git, сбой записи кэша, неразбираемый модуль — исход без исключения.

        Ловит мутацию: `OSError`/`TimeoutExpired` запуска git, `OSError`
        записи или `SyntaxError` модуля настройки не пойманы — исключение
        выходит из `get_reference`.
        """
        self.add_project()
        timeout = lambda argv: subprocess.TimeoutExpired(argv, 1)  # noqa: E731
        cases = (
            ("git не запускается", {"hooks": (raise_on(None, lambda a: OSError("нет")),)},
             contextlib.nullcontext),
            ("cat-file не запускается",
             {"hooks": (raise_on("cat-file", lambda a: OSError("нет")),)},
             contextlib.nullcontext),
            ("срок ls-tree истёк", {"hooks": (raise_on("ls-tree", timeout),)},
             contextlib.nullcontext),
            ("запись кэша падает", {}, replace_fails),
        )
        for case, kwargs, patch in cases:
            with self.subTest(case=case):
                self.drop_cache()
                with patch():
                    result = self.get(**kwargs)
                self.assertIn(field(result, "state"), STATES)
        with self.subTest(case="модуль не разбирается"):
            self.drop_cache()
            self.commit(PROJECT, {"lib/core.py": "def broken(:\n"})
            self.assertIn(field(self.get(), "state"), STATES)


class AlertsTest(ReferenceSandbox):
    """AC-13: каждый сбой — алерт `incident` по проекту с источником от повода и пометка."""

    TIME = re.compile(r"\d{1,2}:\d{2}")

    def failure(self, case: str, name: str):
        """Привести проект `name` к сбою `case`; (аргументы вызова, контекст на время вызова)."""
        null = contextlib.nullcontext
        if case == "модуль не найден":
            self.declare(name, dict(SETTING, modules=SETTING["modules"] + ["lib/nope.py"]))
        elif case == "имя константы не найдено":
            self.declare(name, dict(SETTING, constants=["LIMIT_A", "NOPE_CONST"]))
        elif case == "модуль не разобран":
            self.commit(name, {"lib/core.py": "def broken(:\n"})
        elif case == "источник недоступен":
            return {"sha": random.choice("de") * 40}, null
        elif case == "сверх пределов":
            return {}, lambda: mock.patch.object(config, "CORE_REFERENCE_MAX_FILES", 1)
        elif case == "кэш не записан":
            return {}, replace_fails
        elif case == "targets.yaml не читается":
            config.TARGETS.write_bytes(b"targets:\n  \xff\xfe\n")
        elif case == "неверное поле":
            self.declare(name, {"modules": []})
        return {}, null

    CASES = ("модуль не найден", "имя константы не найдено", "модуль не разобран",
             "источник недоступен", "сверх пределов", "кэш не записан",
             "targets.yaml не читается", "неверное поле")

    def test_ac13_each_failure_raises_incident_by_reason_with_note(self):
        """Восемь сбоев требования 7 при `brief` и `merge` — алерт `incident` с источником повода.

        Текст алерта не несёт sha коммита (ни полного, ни семизначного
        префикса) и времени; `note` не пуст.

        Ловит мутацию: один из сбоев молчит (нет алерта или пометки),
        источник алерта не зависит от `reason` или алерт заводится по
        артели, а не по проекту задачи, в тексте — sha или время.
        """
        for i, case in enumerate(self.CASES):
            name, task = f"p{i}", f"T8{i:02d}"
            with self.subTest(case=case):
                self.add_project(name=name, task=task, branch=f"task/t8{i:02d}-x")
                sha = self.head(name)
                kwargs, patch = self.failure(case, name)
                for reason in ("brief", "merge"):
                    self.drop_cache(name)
                    since = store.max_alert_id(self.conn)
                    with patch():
                        result = self.get(task=task, reason=reason, **kwargs)
                    self.assertTrue(field(result, "note"), f"{case}/{reason}")
                    raised = [a for a in self.new_alerts(since, target=name)
                              if a["kind"] == "incident"
                              and a["source"] == SOURCES[reason]]
                    self.assertTrue(raised, f"{case}/{reason}: "
                                    f"{[dict(a) for a in alerts.open_alerts(self.conn)]}")
                    for alert in raised:
                        for known in (sha, kwargs.get("sha")):
                            if known:
                                self.assertNotIn(known[:7], alert["message"])
                        self.assertNotRegex(alert["message"], self.TIME)
                self.write_targets()

    def test_ac13_repeated_failure_keeps_one_open_alert(self):
        """Тот же сбой на другом sha и с другими размерами не заводит второй открытый алерт.

        Ловит мутацию: в текст алерта попали sha, время, размеры или
        число файлов — повторная сборка заводит новую строку алертов.
        """
        cases = ("модуль не найден", "источник недоступен", "сверх пределов",
                 "кэш не записан", "targets.yaml не читается")
        for i, case in enumerate(cases):
            name, task = f"r{i}", f"T7{i:02d}"
            with self.subTest(case=case):
                self.add_project(name=name, task=task, branch=f"task/t7{i:02d}-x")
                for attempt in range(2):
                    kwargs, patch = self.failure(case, name)
                    if case == "источник недоступен":
                        kwargs = {"sha": "de"[attempt] * 40}
                    self.drop_cache(name)
                    with patch():
                        self.get(task=task, **kwargs)
                    if attempt == 0 and case != "targets.yaml не читается":
                        self.commit(name, {f"use/grow{attempt}.py": "G = 1\n" * 40})
                opened = [a for a in alerts.open_alerts(self.conn)
                          if a["target"] == name and a["kind"] == "incident"
                          and a["source"] == SOURCES["brief"]]
                self.assertEqual(1, len(opened), [a["message"] for a in opened])
                self.write_targets()

    def test_ac13_unwritten_cache_gives_fresh_text_from_memory(self):
        """Кэш не записан — `fresh`, текст справочника из памяти, пометка и алерт.

        Ловит мутацию: сбой записи кэша превращён в `absent` (текст
        потерян) или текст отдаётся пустым.
        """
        sha = self.add_project()
        since = store.max_alert_id(self.conn)
        with replace_fails():
            result = self.get()
        self.assert_state(result, "fresh")
        text = field(result, "text")
        self.assertIn(sha, text)
        self.assertTrue(has_signature(text, ENGINE), text)
        self.assertTrue(field(result, "note"))
        self.assertTrue(self.new_alerts(since))
        self.assertFalse(self.cache_path().exists())


class ExternalProjectTest(ReferenceSandbox):
    """AC-15: внешний проект с другим деревом — свой клон, своя настройка, своя область."""

    def test_ac15_external_projects_build_from_their_clones_into_their_areas(self):
        """Два внешних проекта с модулями вне `orchestrator/` — кэш каждого в своей области.

        Ловит мутацию: модули ищутся в дереве пульта (`config.ROOT`) или
        в клоне артели, кэш пишется в область артели или общий путь, либо
        настройка берётся не из записи проекта — тексты проектов
        смешиваются или пусты.
        """
        n = users_count()
        alpha_files = {"src/alpha_engine.py":
                       '"""Двигатель альфы."""\n\n\n'
                       "def ignite(power: int) -> str:\n"
                       '    """Зажигание альфы."""\n    return str(power)\n'}
        alpha_files.update({f"app/a{i}.py": "from src import alpha_engine\n"
                            "alpha_engine.ignite(3)\n" for i in range(n)})
        beta_files = {"pkg/beta/core_b.py":
                      '"""Сборщик беты."""\n\n\n'
                      "def assemble(parts: list[str]) -> str:\n"
                      '    """Сборка беты."""\n    return "".join(parts)\n',
                      "pkg/beta/limits.py": '"""Пределы беты."""\n\n'
                                            "BETA_LIMIT = 6174  # предел беты\n"}
        beta_files.update({f"tools/b{i}.py": "from pkg.beta import core_b\n"
                           "core_b.assemble([])\n" for i in range(n)})
        projects = {
            "alpha": ({"modules": ["src/alpha_engine.py"]}, alpha_files, "T601",
                      "ignite(power: int) -> str", "src/alpha_engine.py",
                      ("assemble", "BETA_LIMIT")),
            "beta": ({"modules": ["pkg/beta/core_b.py", "pkg/beta/limits.py"],
                      "constants_module": "pkg/beta/limits.py",
                      "constants": ["BETA_LIMIT"]}, beta_files, "T602",
                     "assemble(parts: list[str]) -> str", "pkg/beta/core_b.py",
                     ("ignite", "alpha_engine")),
        }
        heads = {}
        for name, (setting, files, task, *_rest) in projects.items():
            heads[name] = self.add_project(name=name, setting=setting, files=files,
                                           task=task, branch=f"task/{task.lower()}-x")
        for name, (_s, _f, task, signature, module, foreign) in projects.items():
            with self.subTest(project=name):
                result = self.get(task=task)
                self.assert_state(result, "fresh")
                text = field(result, "text")
                self.assertTrue(has_signature(text, signature), text)
                self.assertIn(module, text)
                self.assertIn(heads[name], text)
                for fragment in foreign:
                    self.assertNotIn(fragment, text)
                self.assertEqual(self.cache_path(name).read_text(encoding="utf-8"), text)
        self.assertTrue([line for line in
                         self.cache_path("beta").read_text(encoding="utf-8").split("\n")
                         if "BETA_LIMIT" in line and "6174" in line])
        self.assertFalse(self.cache_path(config.DEFAULT_TARGET).exists())


if __name__ == "__main__":
    unittest.main()
