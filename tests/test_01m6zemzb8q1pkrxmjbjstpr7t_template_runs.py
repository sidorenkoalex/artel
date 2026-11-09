"""Шаблон байткода интерпретатора в настоящих прогонах pytest пульта (AC-9…AC-14).

Группа: долгоживущий
Красен до реализации: констант `config.PYCACHE_TEMPLATES_DIR`/`PYCACHE_TEMPLATES_ENV` и функции `acceptance.template_dir` ещё нет — подмена места шаблонов в фикстуре падает `AttributeError`, а префикс прогона пуст (шаблона пульт не собирает и не копирует).

Связка «место запуска — окружение прогона — процессы запроса и сборки —
файловая система места шаблонов»: прогоны настоящие (интерпретатор пульта
`stack.pytest_python_executable()`), каждый тест подменяет
`config.PYCACHE_TEMPLATES_DIR` (и переменную `config.PYCACHE_TEMPLATES_ENV`)
своим временным каталогом, общим местом песочницы процесса не пользуется.
`config.LOGS` (замок полного набора) — тоже временный каталог.

Наблюдение «в момент вызова» — подкласс `subprocess.Popen` в модуле
`subprocess` (через него идут и `subprocess.run`, и запуск `pytest-own`):
до старта процесса он снимает состояние префикса прогона, `cwd` и места
шаблонов. Вызов pytest прогона — argv с элементом `pytest` (у обёртки —
её `command[0]`); запрос — без `pytest` и без `PYTHONPYCACHEPREFIX` в
окружении; сборка — без `pytest`, с `PYTHONPYCACHEPREFIX` (указание
Оператора на гейте SPEC, п. 2). Неудача сборки (AC-12 (д)) — подмена
`subprocess.run` только у вызова сборки.

Тест, которому нужен уже стоящий шаблон, берёт фикстуру `built` (шаблон,
собранный пультом в отдельном месте этого теста) и копирует его в своё
место под имя `acceptance.template_dir`. Сведения интерпретатора (пути, версия,
`cache_tag`) тест узнаёт у самого интерпретатора отдельным процессом.
Имена модулей-зондов и значения — от `random`, зерно печатается.

Провалидировано временным стабом реализации (удалён, не закоммичен): все
методы зелёные; каждая заявленная мутация стаба (наполнение без фильтра
AC-2, префикс-ссылка на шаблон, сборка прямо в итоговый каталог,
`PYTHONDONTWRITEBYTECODE` у сборки, место 0755, окружение пульта и `cwd`
прогона у запроса `pytest-own`, распознавание обёртки, вторая строка о
сбое, пропавшая отметка неудачи, снятая проверка доверия места,
наполнение без `run_dir`) краснит свой тест. Мутация «из исключений убран
только `cwd`» здесь не наблюдаема: `cwd` песочницы лежит вне путей
интерпретатора — её держит правило AC-2 (малый файл).
"""
import contextlib
import hashlib
import json
import os
import random
import re
import shutil
import stat
import string
import subprocess
import time
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from unittest import mock

import pytest

from orchestrator import acceptance, config, project_profile, stack, targets

pytestmark = pytest.mark.size("medium")

PHRASE = "шаблон байткода интерпретатора недоступен"
PREFIX_VAR = "PYTHONPYCACHEPREFIX"
NO_WRITE_VAR = "PYTHONDONTWRITEBYTECODE"
MANIFEST = "manifest.json"
REAL_POPEN = subprocess.Popen
REAL_RUN = subprocess.run
CHILD_TIMEOUT_SEC = 60

INFO_SCRIPT = (
    "import json, os, site, sys\n"
    "print(json.dumps({'executable': os.path.realpath(sys.executable),\n"
    "                  'version': sys.version, 'prefix': sys.prefix,\n"
    "                  'paths': [sys.prefix, sys.base_prefix, sys.exec_prefix,\n"
    "                            *site.getsitepackages()],\n"
    "                  'tag': sys.implementation.cache_tag}))\n")

# `.pyc` с заголовком (время изменения, размер) настоящего исходника и
# кодом из другого текста: интерпретатор примет его за свежий.
FAKE_PYC_SCRIPT = (
    "import importlib.util, marshal, os, sys\n"
    "src, out, text = sys.argv[1:4]\n"
    "st = os.stat(src)\n"
    "data = (importlib.util.MAGIC_NUMBER + (0).to_bytes(4, 'little')\n"
    "        + (int(st.st_mtime) & 0xFFFFFFFF).to_bytes(4, 'little')\n"
    "        + (st.st_size & 0xFFFFFFFF).to_bytes(4, 'little')\n"
    "        + marshal.dumps(compile(text, src, 'exec')))\n"
    "os.makedirs(os.path.dirname(out), exist_ok=True)\n"
    "with open(out, 'wb') as fh:\n"
    "    fh.write(data)\n")

STALE_PYC_SCRIPT = (
    "import py_compile, sys\n"
    "py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True,\n"
    "                   invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)\n")


# ------------------------------------------------------------ помощники


def make_rng():
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    return seed, random.Random(seed)


def ident(rng, k: int = 8) -> str:
    return "".join(rng.choices(string.ascii_lowercase, k=k))


def interp() -> str:
    return stack.pytest_python_executable()


def run_interp(*args: str) -> subprocess.CompletedProcess:
    return REAL_RUN([interp(), *args], capture_output=True, text=True,
                    timeout=CHILD_TIMEOUT_SEC, start_new_session=True)


def inside(path, parent) -> bool:
    child, base = os.path.realpath(path), os.path.realpath(parent)
    return child == base or child.startswith(base.rstrip(os.sep) + os.sep)


def snapshot(root) -> dict:
    """{путь от `root` через `/`: sha256 байтов} файлов каталога."""
    root = Path(root)
    if not root.is_dir():
        return {}
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def files_under(root) -> list:
    root = Path(root)
    return [p for p in root.rglob("*")] if root.is_dir() else []


def write_manifest(template: Path) -> None:
    files = {k: v for k, v in snapshot(template).items() if k != MANIFEST}
    (template / MANIFEST).write_text(json.dumps(files), encoding="utf-8")


def intact(template: Path) -> bool:
    manifest = template / MANIFEST
    text = manifest.read_text(encoding="utf-8") if manifest.is_file() else None
    files = {k: v for k, v in snapshot(template).items() if k != MANIFEST}
    return acceptance.manifest_intact(text, files)


def visible_dirs(place) -> list:
    place = Path(place)
    return sorted(p.name for p in place.iterdir()
                  if p.is_dir() and not p.name.startswith(".")) if place.is_dir() else []


def dot_dirs(place) -> list:
    place = Path(place)
    return sorted(p.name for p in place.iterdir()
                  if p.is_dir() and p.name.startswith(".")) if place.is_dir() else []


def phrase_lines(err: str) -> list:
    return [line for line in err.splitlines() if line.startswith(PHRASE)]


def has_pytest_dir(key: str) -> bool:
    return "_pytest" in key.split("/")[:-1]


class Spy:
    """Записи о каждом запуске процесса: argv, `cwd`, окружение и
    состояние каталогов В МОМЕНТ запуска."""

    def __init__(self, place=None, run_head: str | None = None):
        self.place = place
        self.run_head = run_head
        self.calls: list[SimpleNamespace] = []

    def popen(self):
        spy = self

        class SpyPopen(REAL_POPEN):
            def __init__(self, args, *a, **kw):
                spy.record(args, kw)
                super().__init__(args, *a, **kw)

        return SpyPopen

    def record(self, args, kw) -> None:
        argv = [os.fspath(a) for a in (args if isinstance(args, (list, tuple))
                                       else [args])]
        env = kw.get("env")
        cwd = kw.get("cwd")
        prefix = env.get(PREFIX_VAR) if env is not None else None
        call = SimpleNamespace(
            argv=argv, env=dict(env) if env is not None else None,
            cwd=os.fspath(cwd) if cwd is not None else None, prefix=prefix,
            prefix_existed=bool(prefix) and os.path.isdir(prefix),
            prefix_files=snapshot(prefix) if prefix else {},
            prefix_links=[str(p) for p in files_under(prefix) if p.is_symlink()]
            if prefix else [],
            prefix_is_link=bool(prefix) and os.path.islink(prefix),
            cwd_listing=sorted(os.listdir(cwd)) if cwd is not None
            and os.path.isdir(cwd) else None,
            place_intact={name: intact(Path(self.place) / name)
                          for name in visible_dirs(self.place)}
            if self.place is not None else {})
        self.calls.append(call)

    def is_run(self, call) -> bool:
        if self.run_head is not None:
            return bool(call.argv) and call.argv[0] == self.run_head
        return "pytest" in call.argv

    def runs(self) -> list:
        return [c for c in self.calls if self.is_run(c)]

    def helpers(self, interpreter: str) -> list:
        """Вызовы запроса и сборки: интерпретатор прогона, без `pytest`."""
        real = os.path.realpath(interpreter)
        return [c for c in self.calls if not self.is_run(c)
                and "pytest" not in c.argv and c.argv
                and os.path.realpath(c.argv[0]) == real]

    def builds(self) -> list:
        return [c for c in self.calls if "pytest" not in c.argv
                and c.env is not None and PREFIX_VAR in c.env]


@contextlib.contextmanager
def spying(spy: Spy):
    with mock.patch.object(acceptance.subprocess, "Popen", spy.popen()):
        yield spy


def is_build_call(cmd, kwargs) -> bool:
    argv = [os.fspath(a) for a in cmd] if isinstance(cmd, (list, tuple)) else [cmd]
    env = kwargs.get("env")
    return "pytest" not in argv and env is not None and PREFIX_VAR in env


class FailingBuild:
    """Подмена `subprocess.run`: вызов сборки отдаёт «успех» без файлов
    (`empty`) или бросает `TimeoutExpired` (`timeout`); прочие вызовы —
    настоящий `subprocess.run`."""

    def __init__(self, mode: str):
        self.mode = mode
        self.builds = 0

    def __call__(self, cmd, *args, **kwargs):
        if not is_build_call(cmd, kwargs):
            return REAL_RUN(cmd, *args, **kwargs)
        self.builds += 1
        if self.mode == "timeout":
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout") or 60)
        return subprocess.CompletedProcess(cmd, 0, "", "")


def probe_source(code_dir: Path, module: str, *, wt_dir=None, wt_module=None,
                 root_file=None) -> str:
    """Текст тестового модуля-зонда: импорт модулей и проверка, что их
    подложенный байткод не исполнен, — на уровне модуля (видно и сбору)."""
    text = ("import importlib.util\nimport sys\n\n"
            f"sys.path.insert(0, {str(code_dir)!r})\n"
            f"import {module}\n"
            f"if {module}.VALUE != 'real':\n"
            "    raise RuntimeError('исполнен подложенный байткод модуля cwd')\n")
    if wt_dir is not None:
        text += (f"sys.path.insert(0, {str(wt_dir)!r})\n"
                 f"import {wt_module}\n"
                 f"if {wt_module}.VALUE != 'real':\n"
                 "    raise RuntimeError('исполнен подложенный байткод WORKTREES')\n")
    if root_file is not None:
        text += (f"spec = importlib.util.spec_from_file_location('probe_root_mod', "
                 f"{str(root_file)!r})\n"
                 "root_mod = importlib.util.module_from_spec(spec)\n"
                 "spec.loader.exec_module(root_mod)\n"
                 "if hasattr(root_mod, 'INJECTED'):\n"
                 "    raise RuntimeError('исполнен подложенный байткод ROOT')\n")
    text += ("\n\ndef test_probe():\n"
             f"    assert {module}.VALUE == 'real'\n")
    return text


def make_project(base: Path, rng, **probe) -> SimpleNamespace:
    """Рабочая копия `code` (модуль-зонд и `tests/`), каталог планки
    `task/acceptance_tests` с тем же тестом."""
    code = Path(os.path.realpath(base)) / "code"
    (code / "tests").mkdir(parents=True)
    module = "probe_cwd_" + ident(rng)
    (code / f"{module}.py").write_text("VALUE = 'real'\n", encoding="utf-8")
    test_name = f"test_probe_{ident(rng)}.py"
    text = probe_source(code, module, **probe)
    (code / "tests" / test_name).write_text(text, encoding="utf-8")
    task = base / "task"
    (task / "acceptance_tests").mkdir(parents=True)
    (task / "acceptance_tests" / test_name).write_text(text, encoding="utf-8")
    return SimpleNamespace(code=code, module=module, test_name=test_name, task=task)


def own_profile(command) -> project_profile.Profile:
    return project_profile.Profile(
        command=tuple(command), long_lived_dir="tests",
        long_lived_name="test_<id>_<name>.py", weakening_scope=("tests/**",),
        mutation_claim_scope=("tests/**",), runner=targets.PROFILE_RUNNER_OWN,
        workdir="", env=MappingProxyType({}))


@contextlib.contextmanager
def place_patched(base: Path, *, no_write: bool = False):
    """Место шаблонов — `base/templates` (ещё не создано); переменная места
    — то же значение; окружение пульта без унаследованного префикса."""
    place = Path(os.path.realpath(base)) / "templates"
    logs = base / "logs"
    with mock.patch.object(config, "PYCACHE_TEMPLATES_DIR", str(place)), \
         mock.patch.object(config, "LOGS", logs), \
         mock.patch.object(config, "FULL_SUITE_WORKERS", 1), \
         mock.patch.dict(os.environ, {config.PYCACHE_TEMPLATES_ENV: str(place)}):
        os.environ.pop(PREFIX_VAR, None)
        os.environ.pop(NO_WRITE_VAR, None)
        if no_write:
            os.environ[NO_WRITE_VAR] = "1"
        yield place


# ------------------------------------------------------------ фикстуры


@pytest.fixture
def info():
    """Сведения интерпретатора пульта — от него самого."""
    res = run_interp("-c", INFO_SCRIPT)
    return SimpleNamespace(**json.loads(res.stdout)) if res.returncode == 0 else None


@pytest.fixture
def built(tmp_path_factory, info):
    """Шаблон интерпретатора пульта, собранный пультом в отдельном месте
    прогоном тривиальной планки; путь его каталога."""
    base = tmp_path_factory.mktemp("built")
    rng = random.Random(random.randrange(1 << 32))
    project = make_project(base, rng)
    with place_patched(base):
        acceptance.run(project.task, cwd=project.code)
        return Path(acceptance.template_dir(info.executable, info.version, info.prefix))


@pytest.fixture
def place(tmp_path):
    with place_patched(tmp_path) as path:
        yield path


def template_path(info) -> Path:
    return Path(acceptance.template_dir(info.executable, info.version, info.prefix))


def seed_template(place: Path, built: Path, info) -> Path:
    """Копия собранного шаблона в место теста под именем `template_dir`."""
    place.mkdir(mode=0o700, exist_ok=True)
    os.chmod(place, 0o700)
    target = template_path(info)
    shutil.copytree(built, target)
    return target


def admitted_everywhere(files: dict, info, cwd) -> list:
    """Файлы префикса, чей исходник не допущен правилом AC-2."""
    excluded = [str(cwd), str(config.WORKTREES), str(config.PROJECTS)]
    bad = []
    for rel in files:
        source = acceptance.pycache_source(rel)
        if source is None or not acceptance.template_admits(source, info.paths, excluded):
            bad.append(rel)
    return bad


def copies_of(prefix_files: dict, template_files: dict) -> list:
    """Файлы префикса, которых нет в шаблоне с теми же байтами."""
    return [rel for rel, digest in prefix_files.items()
            if template_files.get(rel) != digest]


# ------------------------------------------------------------ AC-9


def test_ac9_stale_worktree_pyc_not_executed_with_warm_prefix(place, built, info, capsys):
    """Устаревший `.pyc` рабочей копии не исполняется, префикс несёт копию шаблона.

    Шаблон собран (копия в место теста). В рабочей копии модуль и его
    `.pyc` в `__pycache__` от другой версии с тем же временем изменения и
    размером исходника (случай 02.10). `acceptance.run` с `cwd` на рабочую
    копию зелёный — тест видит текущий исходник; в момент вызова pytest
    префикс непуст, каждый его файл — байт в байт файл шаблона, среди них
    байткод `_pytest`.

    Ловит мутацию: префикс наполняется ссылками/копией и байткода путей
    `cwd` либо не наполняется вовсе — в первом случае подложенный байткод
    исполнится (прогон красный), во втором префикс в момент вызова пуст.
    """
    seed, rng = make_rng()
    template = seed_template(place, built, info)
    template_files = snapshot(template)
    project = make_project(place.parent, rng)
    source = project.code / f"{project.module}.py"
    old_text = f"VALUE = {''.join(rng.choices(string.ascii_lowercase, k=12))!r}\n"
    new_text = "VALUE = 'real'"
    new_text += " " * (len(old_text) - len(new_text) - 1) + "\n"
    source.write_text(old_text, encoding="utf-8")
    pycache = project.code / "__pycache__"
    pycache.mkdir()
    res = run_interp("-c", STALE_PYC_SCRIPT, str(source),
                     str(pycache / f"{project.module}.{info.tag}.pyc"))
    assert res.returncode == 0, res.stderr
    st = source.stat()
    source.write_text(new_text, encoding="utf-8")
    os.utime(source, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert source.stat().st_size == st.st_size

    with spying(Spy()) as spy:
        green, tail = acceptance.run(project.task, cwd=project.code)

    assert green, f"зерно {seed}: исполнен устаревший байткод\n{tail}"
    runs = spy.runs()
    assert runs, f"зерно {seed}: вызова pytest нет"
    for call in runs:
        assert call.prefix_files, f"зерно {seed}: префикс пуст в момент вызова"
        assert not copies_of(call.prefix_files, template_files), f"зерно {seed}"
        assert any(has_pytest_dir(rel) for rel in call.prefix_files), f"зерно {seed}"


# ------------------------------------------------------------ AC-10

PLACES = ("run", "collect", "run_repeat", "run_plank", "run_full_suite",
          "run_plank_own")


def invoke_place(name: str, project) -> bool:
    """Прогон места требования 7; зелёный ли исход."""
    rel = f"tests/{project.test_name}"
    if name == "run":
        return acceptance.run(project.task, cwd=project.code)[0]
    if name == "collect":
        return acceptance.collect(project.task, cwd=project.code)[0]
    if name == "run_repeat":
        return acceptance.run_repeat([rel], cwd=project.code) == []
    if name == "run_plank":
        return acceptance.run_plank([rel], project.code)[0] == 0
    if name == "run_full_suite":
        return acceptance.run_full_suite(project.code)[0]
    profile = own_profile([interp(), "-m", "pytest"])
    return acceptance.run_plank([rel], project.code, profile=profile)[0] == 0


def inject(template: Path, source: Path, text: str, tag: str) -> str:
    """Подложить в шаблон байткод `source` из текста `text`; манифест —
    пересчитан. Путь файла от каталога шаблона."""
    real = os.path.realpath(source)
    rel = f"{os.path.dirname(real).lstrip('/')}/{Path(real).stem}.{tag}.pyc"
    res = run_interp("-c", FAKE_PYC_SCRIPT, real, str(template / rel), text)
    assert res.returncode == 0, res.stderr
    write_manifest(template)
    return rel


@pytest.mark.parametrize("name", PLACES)
def test_ac10_fill_filters_cwd_worktrees_and_root(place, built, info, name):
    """Каждое место наполнения копирует только файлы, допущенные AC-2.

    В целый шаблон подложен байткод модуля из `cwd` прогона, модуля под
    `config.WORKTREES` (подменён каталогом теста) и файла
    `config.ROOT/orchestrator/__init__.py` (вне путей интерпретатора);
    манифест пересчитан — шаблон цел по AC-5. Зонд прогона импортирует все
    три модуля на уровне модуля и падает, если исполнен подложенный код.
    В момент вызова pytest у каждого файла префикса исходник (AC-1)
    допущен AC-2 с исключёнными `cwd`, `WORKTREES`, `PROJECTS`; префикс
    непуст; исход места зелёный.

    Ловит мутацию: в месте (в том числе в `_own_env` профиля `pytest-own`)
    копируется весь шаблон без фильтра AC-2 — подложенные файлы оказываются
    в префиксе, зонд исполняет их байткод и прогон краснеет.
    """
    seed, rng = make_rng()
    template = seed_template(place, built, info)
    assert intact(template), f"зерно {seed}: собранный шаблон не цел"
    worktrees = Path(os.path.realpath(place.parent)) / "worktrees"
    wt_dir = worktrees / ident(rng)
    wt_dir.mkdir(parents=True)
    wt_module = "probe_wt_" + ident(rng)
    (wt_dir / f"{wt_module}.py").write_text("VALUE = 'real'\n", encoding="utf-8")
    root_file = Path(config.ROOT) / "orchestrator" / "__init__.py"
    project = make_project(place.parent, rng, wt_dir=wt_dir, wt_module=wt_module,
                           root_file=root_file)
    with mock.patch.object(config, "WORKTREES", worktrees):
        injected = [
            inject(template, project.code / f"{project.module}.py",
                   "VALUE = 'fake'\n", info.tag),
            inject(template, wt_dir / f"{wt_module}.py", "VALUE = 'fake'\n", info.tag),
            inject(template, root_file, "INJECTED = True\n", info.tag),
        ]
        assert intact(template), f"зерно {seed}: подложенный шаблон не цел"
        with spying(Spy()) as spy:
            green = invoke_place(name, project)
        runs = spy.runs()
        assert runs, f"зерно {seed}: {name}: вызова pytest нет"
        for call in runs:
            assert call.prefix_files, f"зерно {seed}: {name}: префикс не наполнен"
            bad = admitted_everywhere(call.prefix_files, info, project.code)
            assert not bad, f"зерно {seed}: {name}: недопущенные файлы {bad}"
            assert not set(injected) & set(call.prefix_files), f"зерно {seed}: {name}"
    assert green, f"зерно {seed}: {name}: исход красный — исполнен подложенный байткод?"


@pytest.mark.parametrize("profile_kind", ["pult", "own"])
def test_ac10_place_env_without_run_dir_stays_cold(place, built, info, capsys,
                                                   profile_kind):
    """`acceptance.place_env(profile)` без `run_dir` — префикс пуст, строки нет.

    Шаблон цел и стоит в месте теста. Окружение места без каталога прогона
    (так его берёт двусторонний прогон) — у раннера пульта и у
    `pytest-own`: каталог `PYTHONPYCACHEPREFIX` пуст, строки
    `шаблон байткода интерпретатора недоступен` в stderr пульта нет.

    Ловит мутацию: наполнение вставлено в `place_env` безусловно (без
    каталога прогона `cwd` неизвестен) либо отказ печатает строку о сбое —
    префикс непуст или строка появляется.
    """
    seed_template(place, built, info)
    profile = None if profile_kind == "pult" else own_profile([interp(), "-m", "pytest"])
    capsys.readouterr()
    with acceptance.place_env(profile) as env:
        prefix = env[PREFIX_VAR]
        files = snapshot(prefix)
    err = capsys.readouterr().err
    assert files == {}, f"{profile_kind}: префикс без run_dir наполнен"
    assert phrase_lines(err) == [], err


# ------------------------------------------------------------ AC-11


def test_ac11_runs_write_own_prefixes_template_untouched(place, built, info):
    """Два прогона подряд пишут байткод в свои префиксы; шаблон не меняется.

    Окружение без `PYTHONDONTWRITEBYTECODE`; зонд каждого прогона
    импортирует свой новый модуль (его байткод пишется в префикс). После
    обоих прогонов перечень файлов шаблона и их байты прежние; префиксы —
    разные каталоги, существовавшие в момент вызова; ни префикс, ни файл в
    нём не ссылка и не ведут в каталог шаблона; после возврата префиксов нет.

    Ловит мутацию: префикс — сам каталог шаблона или ссылка на него
    (запись прогона меняет шаблон) либо файлы копируются символьными
    ссылками — сверка содержимого шаблона, путей и ссылок краснеет.
    """
    seed, rng = make_rng()
    template = seed_template(place, built, info)
    before = snapshot(template)
    prefixes = []
    for _ in range(2):
        project = make_project(place.parent / ident(rng), rng)
        with spying(Spy()) as spy:
            green, tail = acceptance.run(project.task, cwd=project.code)
        assert green, f"зерно {seed}\n{tail}"
        for call in spy.runs():
            assert call.prefix_existed, f"зерно {seed}: префикса нет в момент вызова"
            assert not call.prefix_is_link, f"зерно {seed}: префикс — ссылка"
            assert not call.prefix_links, f"зерно {seed}: ссылки {call.prefix_links}"
            assert not inside(call.prefix, template), f"зерно {seed}: {call.prefix}"
            assert not inside(template, call.prefix), f"зерно {seed}: {call.prefix}"
            prefixes.append(call.prefix)
    assert len(prefixes) == 2 and len(set(prefixes)) == 2, f"зерно {seed}: {prefixes}"
    assert snapshot(template) == before, f"зерно {seed}: шаблон изменён прогоном"
    for prefix in prefixes:
        assert not os.path.exists(prefix), f"зерно {seed}: {prefix} не убран"


# ------------------------------------------------------------ AC-12

STATES = ("a_intact", "b_no_manifest", "v_bytes_changed", "g_mode_0755",
          "d_build_empty", "d_build_timeout", "e_after_failure",
          "zh_failure_aged")


def run_observed(project, capsys, fake_run=None):
    """Прогон пульта под наблюдением; (зелёный, хвост, spy, строки о сбое)."""
    capsys.readouterr()
    spy = Spy()
    with contextlib.ExitStack() as stack_:
        stack_.enter_context(spying(spy))
        if fake_run is not None:
            stack_.enter_context(mock.patch.object(acceptance.subprocess, "run",
                                                   side_effect=fake_run))
        green, tail = acceptance.run(project.task, cwd=project.code)
    return green, tail, spy, phrase_lines(capsys.readouterr().err)


def run_prefixes(spy) -> list:
    return [call.prefix_files for call in spy.runs()]


@pytest.mark.parametrize("state", STATES)
def test_ac12_run_outcome_follows_template_decision(place, built, info, capsys, state):
    """Исход прогона `acceptance.run` в каждом состоянии шаблона — решение AC-7.

    (а) шаблон цел — префикс наполнен, строки нет; (б) удалён манифест и
    (в) изменены байты файла `_pytest` — префикс пуст, одна строка, каталог
    шаблона убран, следующий прогон собирает его и наполняет префикс;
    (г) права места 0755 — префикс пуст, одна строка, в месте ничего не
    тронуто; (д) сборка «успешна» без файлов либо бросает `TimeoutExpired`
    — префикс пуст, одна строка, рядом `<имя шаблона>.failed`, каталога
    шаблона нет; (е) сразу после (д) — сборки нет, префикс пуст, одна
    строка; (ж) отметка старше `config.PYCACHE_TEMPLATE_RETRY_SEC` —
    сборка запускается. Во всех — исход зелёный, сводка «1 passed».

    Ловит мутацию: отказ шаблона поднимает исключение или меняет исход
    прогона, строка о сбое печатается дважды (при отказе и при уборке) или
    не печатается, повреждённый шаблон не убирается, отметка неудачи не
    пишется или не читается — расходится исход, число строк или файлы места.
    """
    seed, rng = make_rng()
    project = make_project(place.parent, rng)
    template = template_path(info)
    failed = Path(str(template) + ".failed")
    fake = None
    if state in ("a_intact", "b_no_manifest", "v_bytes_changed", "g_mode_0755"):
        seed_template(place, built, info)
    if state == "b_no_manifest":
        (template / MANIFEST).unlink()
    if state == "v_bytes_changed":
        manifest = json.loads((template / MANIFEST).read_text(encoding="utf-8"))
        victim = template / rng.choice(sorted(k for k in manifest if has_pytest_dir(k)))
        data = victim.read_bytes()
        victim.write_bytes(data[:-1] + bytes([data[-1] ^ 0xFF]))
    if state == "g_mode_0755":
        os.chmod(place, 0o755)
    if state in ("d_build_empty", "e_after_failure", "zh_failure_aged"):
        fake = FailingBuild("empty")
    if state == "d_build_timeout":
        fake = FailingBuild("timeout")
    if state in ("e_after_failure", "zh_failure_aged"):
        green, tail, _spy, _lines = run_observed(project, capsys, fake)
        assert failed.is_file(), f"зерно {seed}: отметки неудачи нет после (д)"
    if state == "zh_failure_aged":
        old = time.time() - config.PYCACHE_TEMPLATE_RETRY_SEC - 120
        failed.write_text(str(int(old)), encoding="utf-8")
        os.utime(failed, (old, old))
    if fake is not None:
        fake.builds = 0
    place_before = snapshot(place)
    try:
        green, tail, spy, lines = run_observed(project, capsys, fake)
    finally:
        if place.is_dir():
            os.chmod(place, 0o700)

    assert green, f"зерно {seed}: {state}: исход изменился\n{tail}"
    assert re.search(r"\b1 passed\b", tail), f"зерно {seed}: {state}\n{tail}"
    prefixes = run_prefixes(spy)
    assert prefixes, f"зерно {seed}: {state}: вызова pytest нет"
    if state == "a_intact":
        assert lines == [], f"зерно {seed}: {lines}"
        assert all(prefixes), f"зерно {seed}: префикс не наполнен"
        return
    assert len(lines) == 1, f"зерно {seed}: {state}: строки о сбое {lines}"
    assert all(p == {} for p in prefixes), f"зерно {seed}: {state}: префикс не пуст"
    if state in ("b_no_manifest", "v_bytes_changed"):
        assert not template.exists(), f"зерно {seed}: {state}: шаблон не убран"
        green, tail, spy, _lines = run_observed(project, capsys)
        assert green, f"зерно {seed}: {state}: повторный прогон\n{tail}"
        assert spy.builds(), f"зерно {seed}: {state}: повторный прогон не собрал шаблон"
        assert all(run_prefixes(spy)), f"зерно {seed}: {state}: префикс не наполнен"
        assert template.is_dir() and intact(template), f"зерно {seed}: {state}"
    elif state == "g_mode_0755":
        assert snapshot(place) == place_before, f"зерно {seed}: место изменено"
        assert template.is_dir(), f"зерно {seed}: шаблон удалён из недоверенного места"
    elif state in ("d_build_empty", "d_build_timeout"):
        assert fake.builds >= 1, f"зерно {seed}: {state}: сборка не запускалась"
        assert failed.is_file(), f"зерно {seed}: {state}: нет {failed.name}"
        assert not template.exists(), f"зерно {seed}: {state}: шаблон есть"
    elif state == "e_after_failure":
        assert fake.builds == 0 and not spy.builds(), f"зерно {seed}: сборка запущена"
    elif state == "zh_failure_aged":
        assert fake.builds >= 1, f"зерно {seed}: сборка не запущена по старой отметке"


# ------------------------------------------------------------ AC-13


class RaceBuild:
    """Обёртка `subprocess.run`: после настоящего процесса сборки, до
    возврата, кладёт в итоговый каталог целый чужой шаблон (победитель
    гонки)."""

    def __init__(self, plant):
        self.plant = plant
        self.planted = None

    def __call__(self, cmd, *args, **kwargs):
        res = REAL_RUN(cmd, *args, **kwargs)
        if is_build_call(cmd, kwargs) and self.planted is None:
            self.planted = self.plant()
        return res


@pytest.mark.parametrize("race", [False, True])
def test_ac13_build_without_bytecode_env_publishes_whole_template(tmp_path, built, info,
                                                                  capsys, race):
    """Сборка при `PYTHONDONTWRITEBYTECODE=1` у пульта даёт целый шаблон в месте 0700.

    Шаблона нет, место ещё не создано. После прогона: шаблон цел по AC-5 и
    несёт байткод `_pytest`; права места 0700; префикс в момент вызова
    pytest наполнен файлами шаблона; в момент каждого вызова сборки каждый
    каталог места без `.` — целый шаблон; каталогов с `.` в месте нет.
    Вариант гонки: пока сборка не вернулась, итоговый каталог занимает
    чужой целый шаблон с лишним файлом — после прогона итоговый каталог
    байт в байт равен подложенному, каталогов staging нет.

    Ловит мутацию: `PYTHONDONTWRITEBYTECODE` пульта не снят у сборки
    (шаблон без `_pytest` — неудача), место создаётся с правами по umask
    (0755), или файлы копируются прямо в итоговый каталог без staging и
    атомарной замены — недособранный каталог виден в момент сборки,
    подложенный шаблон перезаписан или staging остаётся.
    """
    seed, rng = make_rng()
    with place_patched(tmp_path, no_write=True) as place:
        final = template_path(info)

        def plant() -> dict:
            shutil.copytree(built, final)
            marker = final / f"planted_{ident(rng)}" / f"m.{info.tag}.pyc"
            marker.parent.mkdir()
            marker.write_bytes(rng.randbytes(32))
            write_manifest(final)
            return snapshot(final)

        racer = RaceBuild(plant) if race else None
        spy = Spy(place=place)
        with contextlib.ExitStack() as stack_:
            stack_.enter_context(spying(spy))
            if racer is not None:
                stack_.enter_context(mock.patch.object(
                    acceptance.subprocess, "run", side_effect=racer))
            project = make_project(tmp_path, rng)
            green, tail = acceptance.run(project.task, cwd=project.code)

        assert green, f"зерно {seed}\n{tail}"
        assert stat.S_IMODE(os.lstat(place).st_mode) == 0o700, f"зерно {seed}"
        assert final.is_dir() and intact(final), f"зерно {seed}: шаблон не цел"
        manifest = json.loads((final / MANIFEST).read_text(encoding="utf-8"))
        assert any(has_pytest_dir(k) for k in manifest), f"зерно {seed}: без _pytest"
        builds = spy.builds()
        assert builds, f"зерно {seed}: сборки не было"
        for call in builds:
            assert all(call.place_intact.values()), f"зерно {seed}: {call.place_intact}"
        template_files = snapshot(final)
        for prefix_files in run_prefixes(spy):
            assert prefix_files, f"зерно {seed}: префикс не наполнен"
            assert not copies_of(prefix_files, template_files), f"зерно {seed}"
        assert dot_dirs(place) == [], f"зерно {seed}: {dot_dirs(place)}"
        if race:
            assert racer.planted is not None, f"зерно {seed}: сборка не через run"
            assert snapshot(final) == racer.planted, f"зерно {seed}: шаблон перезаписан"


# ------------------------------------------------------------ AC-14


def test_ac14_own_recognized_interpreter_fills_from_its_template(place, info, capsys):
    """`pytest-own` с распознанным `command[0]` — префикс из шаблона этого интерпретатора.

    `command[0]` — абсолютный путь интерпретатора песочницы (venv пульта).
    В `os.environ` пульта — случайная метка. Шаблона нет: пульт спрашивает
    интерпретатор и собирает шаблон. В момент вызова прогона префикс
    наполнен файлами каталога `template_dir` по реальному пути,
    `sys.version` и `sys.prefix` интерпретатора. Запрос и сборка шли с
    `cwd` в пустом временном каталоге, без метки пульта, с `HOME` не
    пульта. `HOME` и префикс прогона после возврата убраны.

    Ловит мутацию: запрос или сборка `pytest-own` запущены с окружением
    пульта (`dict(os.environ)`) вместо `_own_env` либо с `cwd` прогона —
    метка, `HOME` пульта или непустой `cwd` видны в записи вызова.
    """
    seed, rng = make_rng()
    mark = "ARTEL_LEAK_" + ident(rng).upper()
    tree = Path(os.path.realpath(place.parent)) / "tree"
    tree.mkdir()
    module = "probe_cwd_" + ident(rng)
    (tree / f"{module}.py").write_text("VALUE = 'real'\n", encoding="utf-8")
    (tree / "test_probe.py").write_text(probe_source(tree, module), encoding="utf-8")
    command = interp()
    profile = own_profile([command, "-m", "pytest"])
    pult_home = os.environ.get("HOME")
    with mock.patch.dict(os.environ, {mark: ident(rng)}), spying(Spy()) as spy:
        code, output = acceptance.run_plank(["test_probe.py"], tree, profile=profile)

    assert code == 0, f"зерно {seed}\n{output}"
    template = Path(acceptance.template_dir(info.executable, info.version, info.prefix))
    assert template.is_dir(), f"зерно {seed}: шаблона {template} нет"
    template_files = snapshot(template)
    runs = spy.runs()
    assert runs, f"зерно {seed}: вызова прогона нет"
    for call in runs:
        assert call.prefix_files, f"зерно {seed}: префикс не наполнен"
        assert not copies_of(call.prefix_files, template_files), f"зерно {seed}"
        assert call.env.get("HOME") != pult_home, f"зерно {seed}"
        assert not os.path.exists(call.env["HOME"]), f"зерно {seed}: HOME не убран"
        assert not os.path.exists(call.prefix), f"зерно {seed}: префикс не убран"
    helpers = spy.helpers(command)
    assert any(c.env is None or PREFIX_VAR not in c.env for c in helpers), \
        f"зерно {seed}: запроса нет: {[c.argv for c in helpers]}"
    assert any(c.env is not None and PREFIX_VAR in c.env for c in helpers), \
        f"зерно {seed}: сборки нет: {[c.argv for c in helpers]}"
    for call in helpers:
        assert call.cwd is not None, f"зерно {seed}: {call.argv} без cwd"
        assert call.cwd_listing == [], f"зерно {seed}: cwd {call.cwd} {call.cwd_listing}"
        assert not inside(call.cwd, tree), f"зерно {seed}: cwd {call.cwd} в дереве"
        assert call.env is not None and mark not in call.env, f"зерно {seed}: метка"
        assert call.env.get("HOME") != pult_home, f"зерно {seed}: HOME пульта"


def test_ac14_own_unrecognized_command_runs_once_cold(place, built, info, capsys):
    """Нераспознанный `command[0]` — префикс пуст, строки нет, команда исполнена один раз.

    Шаблон интерпретатора стоит в месте. Команда профиля — обёртка
    `./run-tests.sh` в дереве прогона: она дописывает строку в файл-счётчик
    и передаёт управление pytest интерпретатора пульта. После прогона в
    счётчике ровно одна строка; префикс в момент вызова пуст; строки о
    сбое нет; `HOME` и префикс прогона — не пульта и убраны.

    Ловит мутацию: интерпретатор выясняется исполнением команды проекта
    (`<команда> -c …`) или шаблон копируется без распознавания — счётчик
    больше одного либо префикс непуст.
    """
    seed, rng = make_rng()
    seed_template(place, built, info)
    tree = Path(os.path.realpath(place.parent)) / "tree"
    tree.mkdir()
    module = "probe_cwd_" + ident(rng)
    (tree / f"{module}.py").write_text("VALUE = 'real'\n", encoding="utf-8")
    (tree / "test_probe.py").write_text(probe_source(tree, module), encoding="utf-8")
    counter = place.parent / "counter.txt"
    wrapper = tree / "run-tests.sh"
    wrapper.write_text(f'#!/bin/sh\necho run >> "{counter}"\n'
                       f'exec "{interp()}" -m pytest "$@"\n', encoding="utf-8")
    wrapper.chmod(0o755)
    profile = own_profile(["./run-tests.sh"])
    pult_home = os.environ.get("HOME")
    capsys.readouterr()
    with spying(Spy(run_head="./run-tests.sh")) as spy:
        code, output = acceptance.run_plank(["test_probe.py"], tree, profile=profile)
    err = capsys.readouterr().err

    assert code == 0, f"зерно {seed}\n{output}"
    assert counter.read_text(encoding="utf-8").splitlines() == ["run"], f"зерно {seed}"
    assert phrase_lines(err) == [], err
    runs = spy.runs()
    assert len(runs) == 1, f"зерно {seed}: {[c.argv for c in spy.calls]}"
    call = runs[0]
    assert call.prefix_existed and call.prefix_files == {}, f"зерно {seed}"
    assert call.env.get("HOME") != pult_home, f"зерно {seed}"
    assert not os.path.exists(call.env["HOME"]), f"зерно {seed}: HOME не убран"
    assert not os.path.exists(call.prefix), f"зерно {seed}: префикс не убран"
