"""Локальный слой записей внешних проектов: место файла, формат трёх разделов, сведение в прежнюю запись, слияние со слоем репозитория.

Группа: долгоживущий
Красен до реализации: у `targets` нет `local_path()`, а `load()`/`target()`/`core_reference()` не читают `.artel/targets.yaml` — записи локального слоя не видны и не проверяются, отказы формата не поднимаются.

Модульные тесты без песочницы пульта: `config.TARGETS` и `config.PROJECTS`
подменены путями временного каталога pytest, настоящий `targets.yaml` и
слой машины Оператора не читаются. Файл локального слоя тесты кладут по
адресу `config.TARGETS.parent / ".artel" / "targets.yaml"` (требование 1),
а не через `targets.local_path()`: так AC-1 проверяет функцию независимо.

Ожидаемая запись прежнего вида берётся не пересказом сведения, а прежним
загрузчиком: та же запись, положенная плоско в слой репозитория, читается
`targets.load()` до появления локального слоя. Отказ `check()` записи
репозиторного слоя (AC-5, AC-8) и выдача без файла локального слоя (AC-2)
держат прежнее поведение. Имена проектов, значения полей и порядок
записей — от зерна `random`; зерно печатается и входит в текст провала.
"""
import ast
import copy
import inspect
import random

import pytest

from orchestrator import canary, config, targets, yamlmini
from tests.sandbox import artel_target_entry

LETTERS = "abcdefghijkmnopqrstuvwxyz"

# Запись sled пина: плоский вид слоя репозитория. `{cache}` — каталог кэша
# проекта в области пульта песочницы (`config.PROJECTS/sled/cache`); адрес
# репозитория — на localhost (в tests/ сетевых адресов нет, инвариант 35).
SLED_PIN = """  sled:
    forge: github
    url: https://localhost/sledproject/sled
    base: main
    token_slot: sled-github-token
    no_paths: [.claude/, .codex/, .agents/, CLAUDE.md, AGENTS.md, frontend/.claude/, frontend/CLAUDE.md, .devcontainer/, .github/, CODEOWNERS, .pre-commit-config.yaml, backend/pyproject.toml, backend/uv.lock, backend/.python-version, **/conftest.py, frontend/package.json, frontend/package-lock.json, frontend/vitest.config.js]
    project_skills: []
    merge_gate: operator
    test_profile:
      runner: pytest-own
      workdir: backend
      command: [uv, run, --frozen, pytest, -q]
      long_lived_dir: backend/tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [backend/tests/**/*.py]
      mutation_claim_scope: [backend/tests/test_*.py]
      report: junit-xml
      install: []
      full_suite_timeout_sec: 900
      env:
        DEBUG: "true"
        BASE_URL: http://localhost:8000
        CORS_ORIGINS: '["localhost"]'
        JWT__SECRET: test-only-jwt-secret-not-for-production-0123456789
        DB__HOST: 127.0.0.1
        DB__PORT: "1"
        DB__USER: test
        DB__PASSWORD: test
        DB__NAME: sled
        UV_CACHE_DIR: {cache}/uv
        UV_PYTHON_INSTALL_DIR: {cache}/uv-python
        PATH: /opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin
"""

# Та же запись в трёх разделах локального слоя.
SLED_THREE = """  sled:
    description:
      base: main
      test_profile:
        runner: pytest-own
        workdir: backend
        command: [uv, run, --frozen, pytest, -q]
        long_lived_dir: backend/tests
        long_lived_name: test_<id>_<name>.py
        report: junit-xml
        install: []
        full_suite_timeout_sec: 900
        env:
          DEBUG: "true"
          BASE_URL: http://localhost:8000
          CORS_ORIGINS: '["localhost"]'
          JWT__SECRET: test-only-jwt-secret-not-for-production-0123456789
          DB__HOST: 127.0.0.1
          DB__PORT: "1"
          DB__USER: test
          DB__PASSWORD: test
          DB__NAME: sled
          UV_CACHE_DIR: <cache>/uv
          UV_PYTHON_INSTALL_DIR: <cache>/uv-python
    policy:
      no_paths: [.claude/, .codex/, .agents/, CLAUDE.md, AGENTS.md, frontend/.claude/, frontend/CLAUDE.md, .devcontainer/, .github/, CODEOWNERS, .pre-commit-config.yaml, backend/pyproject.toml, backend/uv.lock, backend/.python-version, **/conftest.py, frontend/package.json, frontend/package-lock.json, frontend/vitest.config.js]
      project_skills: []
      merge_gate: operator
      weakening_scope: [backend/tests/**/*.py]
      mutation_claim_scope: [backend/tests/test_*.py]
    machine:
      forge: github
      url: https://localhost/sledproject/sled
      token_slot: sled-github-token
      path: /opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin
"""


class Seed:
    """Зерно сценария: печатается и входит в текст провала."""

    def __init__(self):
        self.value = random.randrange(1 << 30)
        print(f"зерно: {self.value}")
        self.rng = random.Random(self.value)

    def msg(self, text) -> str:
        return f"зерно: {self.value}; {text}"

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def name(self) -> str:
        return "p" + self.word()


@pytest.fixture
def seed():
    return Seed()


@pytest.fixture
def layers(tmp_path, monkeypatch):
    """`config.TARGETS` и `config.PROJECTS` — во временном каталоге."""
    monkeypatch.setattr(config, "TARGETS", tmp_path / "targets.yaml")
    monkeypatch.setattr(config, "PROJECTS", tmp_path / ".artel" / "projects")
    return tmp_path


# ------------------------------------------------------------ запись файлов

def yaml_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    plain = (value and value == value.strip()
             and yamlmini.scalar(value) == value
             and not value.startswith(("'", '"', "[", "#"))
             and " #" not in value)
    if plain:
        return value
    quote = "'" if '"' in value else '"'
    return f"{quote}{value}{quote}"


def dump(mapping: dict, indent: int) -> list:
    out = []
    pad = " " * indent
    for key, value in mapping.items():
        if isinstance(value, dict):
            out.append(f"{pad}{key}:")
            out.extend(dump(value, indent + 2))
        elif isinstance(value, list):
            out.append(f"{pad}{key}: [{', '.join(value)}]")
        else:
            out.append(f"{pad}{key}: {yaml_scalar(value)}")
    return out


def entries_text(entries: dict) -> str:
    return "".join(line + "\n" for line in dump(entries, 2))


def local_file():
    return config.TARGETS.parent / ".artel" / "targets.yaml"


def write_repo(entries: dict | str = "", artel: str | None = None) -> str:
    """Слой репозитория: запись артели песочницы, затем `entries`."""
    tail = entries if isinstance(entries, str) else entries_text(entries)
    text = "targets:\n" + (artel_target_entry() if artel is None else artel) + tail
    config.TARGETS.write_text(text, encoding="utf-8")
    return text


def write_local(entries: dict | str) -> str:
    body = entries if isinstance(entries, str) else entries_text(entries)
    text = "targets:\n" + body
    path = local_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def refusal(call) -> str:
    with pytest.raises(targets.TargetsError) as exc:
        call()
    return str(exc.value)


def cache_dir(name: str) -> str:
    return str(config.PROJECTS / name / "cache")


def flat_loaded(name: str, flat: dict | str) -> dict:
    """Запись `name`, прочитанная прежним загрузчиком из слоя репозитория."""
    path = local_file()
    if path.exists():
        path.unlink()
    write_repo(flat if isinstance(flat, str) else {name: flat})
    return targets.load()[name]


# ------------------------------------------------------------ записи

def profile_pair(seed: Seed, name: str, *, own_runner: bool = False,
                 path: str | None = None, sandbox: str | None = None):
    """(запись в трёх разделах, та же запись прежнего вида) с профилем."""
    rng = seed.rng
    ll_dir = rng.choice(["tests", "src/tests", "backend/tests"])
    weakening = [f"{ll_dir}/**/*.py"]
    claim = [f"{ll_dir}/test_*.py"]
    profile = {"command": ["python3", "-m", "pytest"],
               "long_lived_dir": ll_dir,
               "long_lived_name": "test_<id>_<name>.py"}
    if own_runner:
        profile["runner"] = "pytest-own"
        profile["env"] = {"MODE": rng.choice(["ci", "local", "x" + seed.word()])}
    no_paths = [f"{seed.word()}/", "**/conftest.py"]
    machine = {"forge": rng.choice(["github", "gitlab"]),
               "url": f"https://localhost/{seed.word()}/{name}",
               "token_slot": f"{name}-token"}
    base = rng.choice(["main", "develop", "trunk"])
    three = {"description": {"base": base, "test_profile": profile},
             "policy": {"no_paths": no_paths, "project_skills": [],
                        "merge_gate": "operator",
                        "weakening_scope": weakening,
                        "mutation_claim_scope": claim},
             "machine": dict(machine)}
    flat = dict(machine, base=base, no_paths=no_paths, project_skills=[],
                merge_gate="operator",
                test_profile=dict(profile, weakening_scope=weakening,
                                  mutation_claim_scope=claim))
    if path is not None:
        three["machine"]["path"] = path
        flat["test_profile"]["env"] = dict(profile.get("env", {}), PATH=path)
    if sandbox is not None:
        three["policy"]["sandbox"] = sandbox
        flat["sandbox"] = sandbox
    return copy.deepcopy(three), copy.deepcopy(flat)


def component_three(seed: Seed, name: str, comp: str, **fields) -> dict:
    """Запись в трёх разделах с одним компонентом `comp`."""
    three, _flat = profile_pair(seed, name)
    del three["description"]["test_profile"]
    del three["policy"]["weakening_scope"]
    del three["policy"]["mutation_claim_scope"]
    three["description"]["components"] = {comp: dict(
        {"command": ["python3", "-m", "pytest"], "long_lived_dir": "tests",
         "long_lived_name": "test_<id>_<name>.py"}, **fields)}
    return three


# ------------------------------------------------------------ AC-1

def test_ac1_local_path_follows_targets(tmp_path, monkeypatch, seed):
    """Путь локального слоя вычисляется от `config.TARGETS` в момент вызова.

    Сценарий: `config.TARGETS` подменяется по очереди на `<tmp>/<имя>/targets.yaml`
    для нескольких случайных имён; `targets.local_path()` каждый раз равен
    `<tmp>/<имя>/.artel/targets.yaml`. `config.TARGETS_LOCAL_REL` — строка
    `.artel/targets.yaml`, не `Path`; в перечне переадресации путей клона
    канарейки (`canary._CLONE_CONFIG_ATTRS`, литерал читается разбором
    исходника модуля) есть `TARGETS`.

    Ловит мутацию: локальный путь вычислен от `config.ROOT` или задан
    абсолютной константой при загрузке модуля — после подмены
    `config.TARGETS` функция отдаёт прежний путь; константа объявлена
    `Path`, а не строкой.
    """
    for _ in range(3):
        where = tmp_path / seed.word()
        monkeypatch.setattr(config, "TARGETS", where / "targets.yaml")
        assert targets.local_path() == where / ".artel" / "targets.yaml", seed.msg(where)
    assert isinstance(config.TARGETS_LOCAL_REL, str)
    assert config.TARGETS_LOCAL_REL == ".artel/targets.yaml"
    tree = ast.parse(inspect.getsource(canary))
    attrs = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "_CLONE_CONFIG_ATTRS"
                for t in node.targets):
            attrs = ast.literal_eval(node.value)
    assert attrs is not None, "перечень переадресации клона канарейки не найден"
    assert "TARGETS" in attrs


# ------------------------------------------------------------ AC-2

def test_ac2_no_local_file_keeps_repo_output(layers, seed, capsys):
    """Файла локального слоя нет: `load()` отдаёт ровно слой репозитория, без отказа и без вывода.

    Сценарий: слой репозитория — запись артели и одна-три записи внешних
    проектов со случайными именами (порядок от зерна); файла
    `.artel/targets.yaml` нет. `load()` отдаёт те же имена в том же порядке,
    каждая запись равна разобранной `yamlmini` записи файла; stdout и
    stderr пусты.

    Ловит мутацию: отсутствие файла локального слоя — `TargetsError` или
    пустая выдача; загрузчик печатает предупреждение об отсутствии слоя.
    """
    names = [seed.name() for _ in range(seed.rng.randrange(1, 4))]
    entries = {name: profile_pair(seed, name)[1] for name in names}
    text = write_repo(entries)
    assert not local_file().exists()
    got = targets.load()
    raw = yamlmini.mapping(text)["targets"]
    assert list(got) == list(raw), seed.msg(text)
    for name in raw:
        assert got[name] == raw[name], seed.msg(name)
    out = capsys.readouterr()
    assert out.out == "" and out.err == "", seed.msg(out)


# ------------------------------------------------------------ AC-3

def test_ac3_sled_three_sections_merge_to_pin_entry(layers):
    """Запись sled в трёх разделах сводится в плоскую запись sled пина поле в поле.

    Сценарий: ожидаемое — запись sled пина в слое репозитория, где каталоги
    `UV_CACHE_DIR`/`UV_PYTHON_INSTALL_DIR` — под `config.PROJECTS`
    песочницы; затем слой репозитория — одна артель, а локальный слой —
    та же запись в разделах `description`/`policy`/`machine` с
    `<cache>/uv`, `<cache>/uv-python` и `machine.path`. `load()["sled"]` и
    `target("sled")` равны ожидаемому: `env.UV_CACHE_DIR` —
    `<PROJECTS>/sled/cache/uv`, `env.PATH` — прежний PATH,
    `weakening_scope`/`mutation_claim_scope` — в `test_profile`.

    Ловит мутацию: поле раздела теряется при сведении (`token_slot`,
    `merge_gate`), области профиля остаются на верхнем уровне записи,
    `machine.path` не попадает в `env.PATH`, `<cache>` не подставляется
    или подставляется от `config.ROOT`.
    """
    cache = cache_dir("sled")
    expected = flat_loaded("sled", SLED_PIN.replace("{cache}", cache))
    assert expected["test_profile"]["env"]["UV_CACHE_DIR"] == cache + "/uv"
    write_repo()
    write_local(SLED_THREE)
    assert targets.load()["sled"] == expected
    assert targets.target("sled") == expected


@pytest.mark.parametrize("own_runner", [False, True])
def test_ac3_policy_sandbox_moves_to_top_level(layers, seed, own_runner):
    """`policy.sandbox` синтетической записи переносится на верхний уровень без изменения значения.

    Сценарий: запись со случайным именем, профилем (со своим раннером и
    `machine.path` либо без них) и `policy.sandbox` — `off`, `required`
    или случайным словом. Сведённая запись локального слоя равна той же
    записи прежнего вида со `sandbox:` на верхнем уровне, прочитанной из
    слоя репозитория.

    Ловит мутацию: `policy.sandbox` теряется при сведении, переносится в
    `test_profile` или меняет значение (`off` читается как ложь).
    """
    name = seed.name()
    value = seed.rng.choice(["off", "required", "s" + seed.word()])
    path = "/usr/local/bin:/usr/bin:/bin" if own_runner else None
    three, flat = profile_pair(seed, name, own_runner=own_runner, path=path,
                               sandbox=value)
    expected = flat_loaded(name, flat)
    assert expected["sandbox"] == value
    write_repo()
    write_local({name: three})
    assert targets.load()[name] == expected, seed.msg(three)


# ------------------------------------------------------------ AC-4

def test_ac4_two_components_get_own_path_and_scopes(layers, seed):
    """Запись с двумя компонентами: пути и области — каждому своему компоненту, порядок — по `description.components`.

    Сценарий: два компонента со случайными именами в случайном порядке;
    у одного (от зерна) — свой `machine.components.<имя>.path` и
    `policy.components.<имя>.weakening_scope`, у другого — только
    `policy.components.<имя>.mutation_claim_scope` и своя `env` без PATH;
    общий `machine.path` — другой. Сведённая запись равна той же записи
    прежнего вида из слоя репозитория: у первого `env.PATH` — свой путь,
    у второго — общий `machine.path` рядом с его `env`; имена компонентов
    идут в порядке `description.components`.

    Ловит мутацию: путь или область уходит в чужой компонент; общий
    `machine.path` перекрывает путь компонента; порядок компонентов
    сортируется или берётся из `machine.components`.
    """
    name = seed.name()
    comps = [seed.word(), seed.word()]
    while comps[0] == comps[1]:
        comps[1] = seed.word()
    own = seed.rng.choice(comps)
    other = comps[1] if own == comps[0] else comps[0]
    own_path, common_path = "/opt/own/bin:/usr/bin", "/usr/local/bin:/bin"
    weakening = [f"{own}/tests/**/*.py"]
    claim = [f"{other}/tests/test_*.py"]
    desc_comps, flat_comps = {}, {}
    for comp in comps:
        fields = {"runner": "pytest-own", "command": ["python3", "-m", "pytest"],
                  "paths": f"^{comp}/"}
        if comp == other:
            fields["env"] = {"MODE": "x" + seed.word()}
        desc_comps[comp] = fields
        flat_comps[comp] = dict(fields)
    flat_comps[own] = dict(flat_comps[own], weakening_scope=weakening,
                           env={"PATH": own_path})
    flat_comps[other] = dict(flat_comps[other], mutation_claim_scope=claim,
                             env=dict(desc_comps[other]["env"], PATH=common_path))
    three, flat = profile_pair(seed, name)
    del three["description"]["test_profile"], flat["test_profile"]
    del three["policy"]["weakening_scope"], three["policy"]["mutation_claim_scope"]
    three["description"]["components"] = desc_comps
    three["policy"]["components"] = {other: {"mutation_claim_scope": claim},
                                     own: {"weakening_scope": weakening}}
    three["machine"]["path"] = common_path
    three["machine"]["components"] = {own: {"path": own_path}}
    flat["components"] = flat_comps
    expected = flat_loaded(name, flat)
    write_repo()
    write_local({name: three})
    got = targets.load()[name]
    assert list(got["components"]) == comps, seed.msg(got)
    assert got == expected, seed.msg(three)


# ------------------------------------------------------------ AC-5

def _format_case(seed: Seed, kind: str):
    """(имя записи, запись локального слоя, допустимые имена поля в тексте)."""
    name = seed.name()
    three, flat = profile_pair(seed, name)
    if kind == "неизвестный раздел":
        section = "x" + seed.word()
        three[section] = {"a": "b"}
        return name, three, [section]
    if kind == "no_paths в description":
        three["description"]["no_paths"] = three["policy"].pop("no_paths")
        return name, three, ["no_paths"]
    if kind == "url в policy":
        three["policy"]["url"] = three["machine"].pop("url")
        return name, three, ["url"]
    if kind == "PATH в description.env":
        three, _ = profile_pair(seed, name, own_runner=True)
        three["description"]["test_profile"]["env"]["PATH"] = "usr/bin"
        return name, three, ["PATH"]
    if kind == "нет раздела":
        section = seed.rng.choice(["description", "policy", "machine"])
        del three[section]
        return name, three, [section]
    if kind == "плоская запись":
        return name, flat, list(flat) + ["description", "policy", "machine"]
    if kind in ("чужой компонент в policy", "чужой компонент в machine"):
        comp, ghost = "c" + seed.word(), "g" + seed.word()
        three = component_three(seed, name, comp)
        if kind.endswith("policy"):
            three["policy"]["components"] = {ghost: {"weakening_scope": ["a/**"]}}
        else:
            three["machine"]["components"] = {ghost: {"path": "/usr/bin"}}
        return name, three, [ghost]
    if kind == "sandbox не строка":
        value = seed.rng.choice(['""', "1", "true", "[a, b]"])
        three["policy"]["sandbox"] = "SANDBOX"
        text = entries_text({name: three}).replace("SANDBOX", value)
        return name, text, ["sandbox"]
    if kind == "запись artel":
        three, _ = profile_pair(seed, config.DEFAULT_TARGET)
        return config.DEFAULT_TARGET, three, [config.DEFAULT_TARGET]
    raise AssertionError(kind)


@pytest.mark.parametrize("kind", [
    "неизвестный раздел", "no_paths в description", "url в policy",
    "PATH в description.env", "нет раздела", "плоская запись",
    "чужой компонент в policy", "чужой компонент в machine",
    "sandbox не строка", "запись artel"])
def test_ac5_format_refusal_names_file_entry_field(layers, seed, kind):
    """Отказ формата трёх разделов: `TargetsError` называет путь локального слоя, запись и поле.

    Сценарий: годная запись в трёх разделах со случайным именем портится
    одним способом из перечня требования 2 (неизвестный раздел, поле не в
    своём разделе, `PATH` в `description.env`, нет раздела, плоская запись
    прежнего вида, компонент `policy.components`/`machine.components`,
    которого нет в `description.components`, `policy.sandbox` — пустая
    строка, число, булево или список, запись `artel`). `load()` и
    `target(<имя>)` отказывают; текст называет путь `.artel/targets.yaml`,
    имя записи и испорченное поле (раздел).

    Ловит мутацию: проверка раздела снята — испорченная запись
    принимается; отказ называет `targets.yaml` репозитория вместо
    локального слоя или не называет поле.
    """
    name, entry, fields = _format_case(seed, kind)
    write_repo()
    write_local(entry if isinstance(entry, str) else {name: entry})
    for call in (targets.load, lambda: targets.target(name)):
        text = refusal(call)
        assert str(local_file()) in text, seed.msg(text)
        assert name in text, seed.msg(text)
        assert any(field in text for field in fields), seed.msg((fields, text))


@pytest.mark.parametrize("field", ["token_slot", "merge_gate", "base"])
def test_ac5_repo_check_text_unchanged(layers, seed, field):
    """Отказ `check()` записи слоя репозитория — прежний текст байт в байт.

    Сценарий: в слое репозитория у записи со случайным именем нет поля
    (`token_slot`, `merge_gate` или `base`); файла локального слоя нет.
    `load()` отказывает текстом `<targets.yaml>: target '<имя>': нет поля
    '<поле>'`; тот же текст даёт `check(<имя>, <запись>)` без аргумента
    источника.

    Ловит мутацию: текст отказа записи репозиторного слоя дописан путём
    локального слоя или разделом; умолчание источника `check()` — путь
    локального слоя.
    """
    name = seed.name()
    flat = profile_pair(seed, name)[1]
    del flat[field]
    write_repo({name: flat})
    expected = f"{config.TARGETS}: target '{name}': нет поля '{field}'"
    assert refusal(targets.load) == expected
    assert refusal(lambda: targets.check(name, flat)) == expected


# ------------------------------------------------------------ AC-6

@pytest.mark.parametrize("where", ["description.test_profile.env",
                                   "policy.no_paths",
                                   "description.components.workdir"])
@pytest.mark.parametrize("value", ["/x", "~/x"])
def test_ac6_absolute_value_refused(layers, seed, where, value):
    """Абсолютный путь в разделах `description`/`policy` на любой глубине — отказ требования 4.

    Сценарий: значение `/x` или `~/x` кладётся в значение `env` профиля
    со своим раннером, в элемент `policy.no_paths` (среди годных) или в
    `workdir` единственного компонента со своим раннером. Отказ `load()`
    начинается словами «абсолютный путь в записи <имя>» и называет раздел
    и поле.

    Ловит мутацию: проверка смотрит только верхний уровень раздела (без
    элементов списка и значений `env`) или пропускает `~`; отказ даёт
    прежняя проверка `workdir` другим текстом.
    """
    name = seed.name()
    if where == "policy.no_paths":
        three, _ = profile_pair(seed, name)
        items = three["policy"]["no_paths"]
        items.insert(seed.rng.randrange(len(items) + 1), value)
        section, leaf = "policy", "no_paths"
    elif where == "description.test_profile.env":
        three, _ = profile_pair(seed, name, own_runner=True)
        leaf = "D" + seed.word().upper()
        three["description"]["test_profile"]["env"][leaf] = value
        section = "description"
    else:
        three = component_three(seed, name, "c" + seed.word(),
                                runner="pytest-own", workdir=value)
        section, leaf = "description", "workdir"
    write_repo()
    write_local({name: three})
    text = refusal(targets.load)
    assert f"абсолютный путь в записи {name}" in text, seed.msg(text)
    assert section in text and leaf in text, seed.msg(text)


def test_ac6_machine_absolute_values_accepted(layers, seed):
    """Абсолютные `machine.path` и `machine.url` вида `/tmp/x.git` принимаются.

    Сценарий: запись профиля со своим раннером, `machine.path` —
    `/opt/…:/usr/bin`, `machine.url` — `/tmp/<слово>.git`. `load()` не
    отказывает: `url` записи — тот же путь, `env.PATH` профиля —
    `machine.path`.

    Ловит мутацию: проверка абсолютных путей распространена на раздел
    `machine` — локальный bare-репозиторий и PATH отвергаются.
    """
    name = seed.name()
    path = f"/opt/{seed.word()}/bin:/usr/bin"
    three, _ = profile_pair(seed, name, own_runner=True, path=path)
    url = f"/tmp/{seed.word()}.git"
    three["machine"]["url"] = url
    write_repo()
    write_local({name: three})
    got = targets.load()[name]
    assert got["url"] == url
    assert got["test_profile"]["env"]["PATH"] == path


# ------------------------------------------------------------ AC-7

@pytest.mark.parametrize("where", ["long_lived_dir", "no_paths", "url",
                                   "env не в начале"])
def test_ac7_cache_placeholder_outside_env_refused(layers, seed, where):
    """`<cache>` вне значения `env` раздела `description` (или не в начале значения) — отказ.

    Сценарий: `<cache>/<слово>` в `description.test_profile.long_lived_dir`,
    в элементе `policy.no_paths`, в `machine.url`, либо значение `env`
    вида `<слово>/<cache>`. `load()` отказывает, текст называет `<cache>`.

    Ловит мутацию: `<cache>` подставляется в любом поле записи — каталог
    кэша молча становится запретным путём или адресом репозитория; отказ
    даёт прежняя проверка каталога уже подставленным путём.
    """
    name = seed.name()
    marker = f"<cache>/{seed.word()}"
    three, _ = profile_pair(seed, name, own_runner=where == "env не в начале")
    if where == "long_lived_dir":
        three["description"]["test_profile"]["long_lived_dir"] = marker
    elif where == "no_paths":
        three["policy"]["no_paths"].append(marker)
    elif where == "url":
        three["machine"]["url"] = marker
    else:
        three["description"]["test_profile"]["env"]["CACHE"] = f"{seed.word()}/<cache>"
    write_repo()
    write_local({name: three})
    text = refusal(targets.load)
    assert "<cache>" in text, seed.msg(text)


@pytest.mark.parametrize("shape", ["test_profile", "component"])
def test_ac7_machine_path_without_own_runner_names_machine_path(layers, seed, shape):
    """`machine.path` у профиля или компонента без `runner: pytest-own` — отказ, называющий `machine.path`, а не `env`.

    Сценарий: профиль без раннера и общий `machine.path`, либо
    единственный компонент без раннера и `machine.components.<имя>.path`.
    `load()` отказывает; текст называет `machine.path` (или
    `machine.components.<имя>.path`) и не называет подполе
    `test_profile.env`/поле `env` компонента.

    Ловит мутацию: PATH переносится в `env`, и отказ даёт прежняя проверка
    «`env` допустим только при runner: pytest-own», называющая `env`; либо
    PATH молча не переносится и запись принимается.
    """
    name = seed.name()
    if shape == "test_profile":
        three, _ = profile_pair(seed, name, path="/usr/bin:/bin")
        named = "machine.path"
    else:
        comp = "c" + seed.word()
        three = component_three(seed, name, comp)
        three["machine"]["components"] = {comp: {"path": "/usr/bin:/bin"}}
        named = f"machine.components.{comp}.path"
    write_repo()
    write_local({name: three})
    text = refusal(targets.load)
    assert named in text, seed.msg(text)
    assert "'test_profile.env'" not in text and "поле 'env'" not in text, seed.msg(text)


# ------------------------------------------------------------ AC-8

def test_ac8_merge_order_and_local_wins(layers, seed):
    """Слияние слоёв: общая запись — из локального слоя, порядок имён — по репозиторию, записи только локального слоя — следом в порядке файла.

    Сценарий: слой репозитория — артель, общая запись `shared` с одним
    адресом и запись только репозитория; локальный слой — записи только
    локального слоя (две, случайный порядок) и `shared` с другим адресом
    посередине. `load()` — имена: артель, `shared`, запись репозитория,
    затем локальные в порядке файла; `load()[shared]` и `target(shared)`
    несут адрес локального слоя.

    Ловит мутацию: побеждает запись репозитория; локальные записи идут
    первыми или в порядке, отличном от файла; общая запись переезжает в
    конец по порядку локального слоя.
    """
    shared, repo_only = seed.name(), seed.name()
    local_only = [seed.name(), seed.name()]
    repo_entry = profile_pair(seed, shared)[1]
    write_repo({shared: repo_entry, repo_only: profile_pair(seed, repo_only)[1]})
    local_shared = profile_pair(seed, shared)[0]
    local_shared["machine"]["url"] = f"https://localhost/local/{seed.word()}"
    write_local({local_only[0]: profile_pair(seed, local_only[0])[0],
                 shared: local_shared,
                 local_only[1]: profile_pair(seed, local_only[1])[0]})
    got = targets.load()
    assert list(got) == [config.DEFAULT_TARGET, shared, repo_only, *local_only], seed.msg(list(got))
    assert got[shared]["url"] == local_shared["machine"]["url"]
    assert targets.target(shared)["url"] == local_shared["machine"]["url"]


def test_ac8_broken_repo_copy_still_refused(layers, seed):
    """Сломанная копия записи в слое репозитория при годной локальной — прежний отказ слоя репозитория.

    Сценарий: у записи слоя репозитория нет `token_slot`; в локальном
    слое та же запись годна. `load()` отказывает прежним текстом
    `<targets.yaml>: target '<имя>': нет поля 'token_slot'`.

    Ловит мутацию: запись репозитория, перекрытая локальной, не
    проверяется — сломанный `targets.yaml` проходит молча.
    """
    name = seed.name()
    three, flat = profile_pair(seed, name)
    del flat["token_slot"]
    write_repo({name: flat})
    write_local({name: three})
    assert refusal(targets.load) == (
        f"{config.TARGETS}: target '{name}': нет поля 'token_slot'")


# ------------------------------------------------------------ AC-9

@pytest.mark.parametrize("case,kind", [
    ("табуляция", "не разобран"),
    ("блочный список", "не разобран"),
    ("нет раздела", "нет раздела 'targets:'"),
    ("раздел пуст", "targets:"),
])
def test_ac9_broken_local_layer_refused(layers, seed, case, kind):
    """Сломанный файл локального слоя — `TargetsError` с его путём и видом текста файла репозитория.

    Сценарий: слой репозитория годен; файл `.artel/targets.yaml` —
    с табуляцией в отступе, с блочным списком (оба не разбираются
    `yamlmini`), без корневого `targets:` или с пустым разделом
    `targets:`. `load()` отказывает текстом с путём локального слоя и
    видом причины (`не разобран`, `нет раздела 'targets:'`; у пустого
    раздела — про раздел `targets:`).

    Ловит мутацию: сломанный файл молча считается отсутствующим —
    `load()` отдаёт слой репозитория; отказ называет путь
    `targets.yaml` репозитория.
    """
    name = seed.name()
    text = {"табуляция": f"targets:\n\t{name}:\n",
            "блочный список": f"targets:\n  {name}:\n    - a\n",
            "нет раздела": f"{seed.word()}:\n  {name}: x\n",
            "раздел пуст": "targets:\n"}[case]
    write_repo()
    path = local_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    message = refusal(targets.load)
    assert message.startswith(str(path)), seed.msg(message)
    assert kind in message, seed.msg(message)


# ------------------------------------------------------------ AC-10

def test_ac10_unknown_name_text_tail(layers, seed):
    """Неизвестное имя: прежнее начало текста отказа `target()` и дописка о локальном слое.

    Сценарий: имя, которого нет ни в одном слое. Без файла локального
    слоя текст начинается `<targets.yaml>: target '<имя>' не объявлен
    (есть: ` и дописывает `; локальный слой <путь>: файла нет`, затем
    «— записи внешних проектов лежат в локальном слое». С файлом из
    двух записей — `; локальный слой <путь>: записи ` с их именами, затем
    та же фраза.

    Ловит мутацию: дописка снята или называет путь репозитория; прежнее
    начало текста изменено; при файле печатается «файла нет».
    """
    missing = seed.name()
    write_repo()
    head = f"{config.TARGETS}: target '{missing}' не объявлен (есть: "
    tail = "— записи внешних проектов лежат в локальном слое"
    text = refusal(lambda: targets.target(missing))
    assert text.startswith(head), seed.msg(text)
    absent = f"; локальный слой {local_file()}: файла нет"
    assert absent in text, seed.msg(text)
    assert text.index(tail) > text.index(absent), seed.msg(text)

    names = [seed.name(), seed.name()]
    write_local({name: profile_pair(seed, name)[0] for name in names})
    text = refusal(lambda: targets.target(missing))
    assert text.startswith(head), seed.msg(text)
    listed = f"; локальный слой {local_file()}: записи "
    assert listed in text, seed.msg(text)
    rest = text.split(listed, 1)[1]
    assert all(name in rest.split(tail)[0] for name in names), seed.msg(text)
    assert tail in rest, seed.msg(text)
    assert "файла нет" not in text, seed.msg(text)


# ------------------------------------------------------------ AC-11

def reference(seed: Seed) -> dict:
    return {"modules": [f"src/{seed.word()}.py", f"src/{seed.word()}.py"]}


def artel_with_reference(value: dict) -> str:
    raw = yamlmini.mapping("targets:\n" + artel_target_entry())["targets"]
    entry = dict(raw[config.DEFAULT_TARGET], core_reference=value)
    return entries_text({config.DEFAULT_TARGET: entry})


def test_ac11_core_reference_layer_choice(layers, seed):
    """`core_reference`: артель — из репозитория; внешний проект — из локального слоя, если запись там есть, иначе из репозитория.

    Сценарий: слой репозитория — артель со справочником A, `both` со
    справочником B и `repo_only` со справочником C; локальный слой —
    `both` со справочником D и `local_only` со справочником E (в
    `description.core_reference`). `core_reference` отдаёт A, D, C, E
    соответственно.

    Ловит мутацию: `core_reference` читает только файл репозитория —
    `both` отдаёт B, `local_only` — None.
    """
    both, repo_only, local_only = seed.name(), seed.name(), seed.name()
    refs = {key: reference(seed) for key in "ABCDE"}
    repo_entries = {}
    for name, key in ((both, "B"), (repo_only, "C")):
        repo_entries[name] = dict(profile_pair(seed, name)[1], core_reference=refs[key])
    write_repo(repo_entries, artel=artel_with_reference(refs["A"]))
    local = {}
    for name, key in ((both, "D"), (local_only, "E")):
        three = profile_pair(seed, name)[0]
        three["description"]["core_reference"] = refs[key]
        local[name] = three
    write_local(local)
    assert targets.core_reference(config.DEFAULT_TARGET) == refs["A"]
    assert targets.core_reference(both) == refs["D"], seed.msg(refs)
    assert targets.core_reference(repo_only) == refs["C"], seed.msg(refs)
    assert targets.core_reference(local_only) == refs["E"], seed.msg(refs)


def test_ac11_broken_local_entry_keeps_artel_reference(layers, seed):
    """Сломанная запись другого внешнего проекта в локальном слое не отключает справочник артели.

    Сценарий: артель в слое репозитория со справочником; в локальном
    слое — запись без раздела `machine`. `load()` отказывает (запись
    сломана), а `core_reference("artel")` отдаёт справочник артели.

    Ловит мутацию: `core_reference` проверяет все записи локального слоя
    (через `load()`) — справочник артели отказывает из-за чужой записи.
    """
    value = reference(seed)
    write_repo(artel=artel_with_reference(value))
    name = seed.name()
    three = profile_pair(seed, name)[0]
    del three["machine"]
    write_local({name: three})
    refusal(targets.load)
    assert targets.core_reference(config.DEFAULT_TARGET) == value
