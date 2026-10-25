"""Обвязка внешнего проекта в формуле защищённых путей и в его записи: запись `**/<каталог>/`, поле `agent_wrapper`, перечень `protected_paths`, отказ записи по `knowledge` компонента.

Группа: долгоживущий
Красен до реализации: `config.is_protected_path` не понимает запись `**/<каталог>/` — `.claude/rules/x.md` под `**/.claude/` не защищён (AC-3); `targets` отказывает записи с незнакомым полем `agent_wrapper` или теряет его, `protected_paths` внешнего проекта — один `no_paths` без маркеров обвязки (AC-6, AC-7, AC-8); элемент `knowledge`, указывающий в обвязку, загружается молча (AC-14). AC-9 держит прежний перечень артели и зелёный с рождения.

Формула (AC-3) — модульный тест чистой функции, без песочницы. Записи
(AC-6..AC-9, AC-14) — связка «файлы слоёв `targets.yaml` — загрузчик
`targets.load` — `repo_context.resolve`/`protected_paths`» в песочнице
`tmp_root` (`tests.sandbox.TmpRootTest`: `config.TARGETS` во временном
каталоге, признак процесса роли снят); локальный слой —
`targets.local_path()`. Перенос записи (AC-7) — команда `targets-migrate`,
вызванная как из командной строки (`sys.argv` подменён, `artel.main()`).
Имена проекта, компонента, каталогов и записей `no_paths` — от зерна
`random`; зерно печатается и входит в текст провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
константа маркеров, формула `**/<каталог>/`, поле `agent_wrapper` в обоих
слоях и переносе, перечень проекта, отказ `knowledge`, зоны каталога
обвязки, источник подсветки, sparse-checkout рабочей копии с игнором и
уборкой путей обвязки, строка `doctor` — все методы зелёные.
"""
import posixpath
import random
import sys
from unittest import mock

import pytest

from orchestrator import artel, config, repo_context, targets, yamlmini
from tests.sandbox import artel_target_entry

LETTERS = "abcdefghijkmnopqrstuvwxyz"
MARKERS = ("**/.claude/", ".mcp.json", "**/CLAUDE.md", "**/AGENTS.md")
PROFILE = (("command", "[python3, -m, pytest]"),
           ("long_lived_dir", "tests"),
           ("long_lived_name", "test_<id>_<name>.py"),
           ("weakening_scope", "[tests/**/*.py]"),
           ("mutation_claim_scope", "[tests/test_*.py]"))


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


@pytest.fixture
def seed():
    return Seed()


def flow(items) -> str:
    return "[" + ", ".join(items) + "]"


def flat_entry(name: str, no_paths=(), extra: str = "") -> str:
    """Плоская запись внешнего проекта слоя репозитория (отступ записи 2)."""
    return (f"  {name}:\n    forge: github\n"
            f"    url: https://localhost/team/{name}\n    base: main\n"
            f"    token_slot: {name}-token\n    no_paths: {flow(no_paths)}\n"
            f"    project_skills: []\n    merge_gate: operator\n{extra}")


def flat_profile() -> str:
    """Поле `test_profile` плоской записи (отступ записи 2)."""
    return "    test_profile:\n" + "".join(f"      {k}: {v}\n" for k, v in PROFILE)


def local_entry(name: str, policy_extra: str = "") -> str:
    """Запись внешнего проекта локального слоя в трёх разделах."""
    return (f"  {name}:\n"
            f"    description:\n      base: main\n"
            f"      test_profile:\n        command: [python3, -m, pytest]\n"
            f"        long_lived_dir: tests\n"
            f"        long_lived_name: test_<id>_<name>.py\n"
            f"    policy:\n      no_paths: []\n      project_skills: []\n"
            f"      merge_gate: operator\n"
            f"      weakening_scope: [tests/**/*.py]\n"
            f"      mutation_claim_scope: [tests/test_*.py]\n{policy_extra}"
            f"    machine:\n      forge: github\n"
            f"      url: https://localhost/team/{name}\n"
            f"      token_slot: {name}-token\n")


def component_extra(comp: str, knowledge) -> str:
    """Поле `components:` плоской записи — один компонент с `knowledge`."""
    fields = [*PROFILE, ("knowledge", flow(knowledge))]
    return ("    components:\n" + f"      {comp}:\n"
            + "".join(f"        {k}: {v}\n" for k, v in fields))


def write_layers(repo_entries: str = "", local_entries: str | None = None) -> None:
    config.TARGETS.write_text("targets:\n" + artel_target_entry() + repo_entries,
                              encoding="utf-8")
    local = targets.local_path()
    if local_entries is None:
        if local.exists():
            local.unlink()
        return
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text("targets:\n" + local_entries, encoding="utf-8")


def perimeter(name: str) -> tuple:
    ctx = repo_context.resolve(name)
    assert ctx is not None, f"контекст {name} не разрешён"
    return repo_context.protected_paths(ctx)


# ------------------------------------------------------------ AC-3

@pytest.mark.parametrize("path,protected", [
    (".claude/rules/x.md", True),
    ("frontend/.claude/rules/x.md", True),
    ("frontend/claude/x.md", False),
    ("x.claude", False),
    ("x.claude/y.md", False),
    ("sub/foo.claude/y.md", False),
    ("frontend/.claude", False),
])
def test_ac3_dir_mask_fixed_paths(path, protected):
    """Запись `**/.claude/` покрывает путь с компонентом-каталогом `.claude` на любой глубине и только его.

    Сценарий: пути критерия сверяются с перечнем из одной записи
    `**/.claude/`.

    Ловит мутацию: `**/<каталог>/` сверяется по последнему компоненту, как
    `**/<имя>` — `.claude/rules/x.md` не защищён, а файл `frontend/.claude`
    защищён; сверка подстрокой `.claude/` — защищены `x.claude/y.md` и
    `sub/foo.claude/y.md`.
    """
    assert config.is_protected_path(path, ("**/.claude/",)) is protected


def test_ac3_dir_mask_random_names(seed):
    """Та же формула на каталогах со случайными именами и случайной глубине.

    Сценарий: для случайного имени каталога `d` (с ведущей точкой или без)
    запись `**/d/` покрывает `d/f`, `a/b/d/f`, `d/e/f`, но не `a/d` (файл без
    вложения), `xd/f`, `dx/f`, `a/xd/f`; прежняя запись-маска `**/d` без `/`
    по-прежнему покрывает только последний компонент (`a/d` — да, `d/f` —
    нет).

    Ловит мутацию: компонент сверяется суффиксом или префиксом (`xd/f`,
    `dx/f` защищены); разбор записи теряет завершающий `/` и сверка
    `**/d/` совпала с `**/d` — `a/d` защищён, `d/f` нет.
    """
    for _ in range(5):
        name = seed.rng.choice(("", ".")) + seed.word(seed.rng.randint(2, 6))
        deep = "/".join(seed.word(3) for _ in range(seed.rng.randint(1, 3)))
        mask = (f"**/{name}/",)
        yes = [f"{name}/{seed.word()}.md", f"{deep}/{name}/{seed.word()}",
               f"{name}/{seed.word()}/{seed.word()}.txt"]
        no = [f"{deep}/{name}", f"x{name}/{seed.word()}",
              f"{name}x/{seed.word()}", f"{deep}/x{name}/{seed.word()}"]
        for path in yes:
            assert config.is_protected_path(path, mask), seed.msg(f"{mask} × {path}")
        for path in no:
            assert not config.is_protected_path(path, mask), seed.msg(f"{mask} × {path}")
        assert config.is_protected_path(f"{deep}/{name}", (f"**/{name}",)), seed.msg(name)
        assert not config.is_protected_path(f"{name}/{seed.word()}",
                                            (f"**/{name}",)), seed.msg(name)


# ------------------------------------------------------------ AC-6

@pytest.mark.parametrize("layer", ["репозиторий", "локальный"])
def test_ac6_agent_wrapper_field_loads_in_both_layers(tmp_root, seed, layer):
    """Запись с `agent_wrapper: [harness/]` загружается в обоих слоях, перечень проекта несёт `harness/`; запись без поля загружается.

    Сценарий: внешний проект со случайным именем — плоской записью слоя
    репозитория с полем `agent_wrapper` либо записью локального слоя с
    полем в разделе `policy`. `targets.load()` не отказывает,
    `protected_paths` контекста проекта содержит `harness/`. Вторая запись
    того же слоя без поля тоже загружается, и `harness/` в её перечне нет.

    Ловит мутацию: поле не внесено в допустимые поля раздела `policy` —
    отказ загрузки локального слоя; `_flatten` не переносит поле из
    `policy` — `harness/` нет в перечне локальной записи; поле сделано
    обязательным — запись без поля отказывает.
    """
    name, bare = "p" + seed.word(), "q" + seed.word()
    if layer == "репозиторий":
        write_layers(flat_entry(name, extra="    agent_wrapper: [harness/]\n")
                     + flat_entry(bare))
    else:
        write_layers(local_entries=local_entry(
            name, "      agent_wrapper: [harness/]\n") + local_entry(bare))
    loaded = targets.load()
    assert name in loaded and bare in loaded, seed.msg(list(loaded))
    assert "harness/" in perimeter(name), seed.msg(perimeter(name))
    assert "harness/" not in perimeter(bare), seed.msg(perimeter(bare))


@pytest.mark.parametrize("layer", ["репозиторий", "локальный"])
@pytest.mark.parametrize("kind", ["строка", "отображение"])
def test_ac6_agent_wrapper_not_list_refused(tmp_root, seed, layer, kind):
    """Запись с `agent_wrapper`, который не список строк, не загружается.

    Сценарий: поле — строка `harness/` или отображение `a: b`; плоская
    запись слоя репозитория либо раздел `policy` записи локального слоя.
    `targets.load()` отказывает `TargetsError`, текст называет поле.

    Ловит мутацию: значение поля не проверяется видом «список строк» —
    строка `harness/` проходит и перечень разбирает её по символам.
    """
    name = "p" + seed.word()
    pad = "    " if layer == "репозиторий" else "      "
    field = (f"{pad}agent_wrapper: harness/\n" if kind == "строка"
             else f"{pad}agent_wrapper:\n{pad}  a: b\n")
    if layer == "репозиторий":
        write_layers(flat_entry(name, extra=field))
    else:
        write_layers(local_entries=local_entry(name, field))
    with pytest.raises(targets.TargetsError, match="agent_wrapper"):
        targets.load()


# ------------------------------------------------------------ AC-7

def test_ac7_targets_migrate_moves_agent_wrapper_to_policy(tmp_root, seed, capsys):
    """`targets-migrate` кладёт `agent_wrapper` плоской записи в раздел `policy` локального слоя.

    Сценарий: слой репозитория — артель и плоская запись внешнего проекта
    с `agent_wrapper: [harness/]`; `targets-migrate <имя>` завершается
    успешно; запись проекта локального слоя несёт поле в разделе `policy`
    (и не в `description`). Затем запись убрана из слоя репозитория:
    действующая запись локального слоя загружается, её перечень несёт
    `harness/`.

    Ловит мутацию: `_split_entry` не знает поля — оно уходит в
    `description`, сверка переноса отказывает или запись теряет поле;
    `_flatten` не переносит поле обратно — перечень без `harness/`.
    """
    name = "p" + seed.word()
    write_layers(flat_entry(name, extra="    agent_wrapper: [harness/]\n"
                            + flat_profile()))
    code = 0
    with mock.patch.object(sys, "argv", ["artel.py", "targets-migrate", name]):
        try:
            artel.main()
        except SystemExit as exc:
            code = exc.code
    out = capsys.readouterr()
    assert code in (0, None), seed.msg(f"{code}\n{out.out}\n{out.err}")
    written = yamlmini.mapping(targets.local_path().read_text(encoding="utf-8"))
    entry = written["targets"][name]
    assert entry["policy"].get("agent_wrapper") == ["harness/"], seed.msg(entry)
    assert "agent_wrapper" not in entry["description"], seed.msg(entry)
    config.TARGETS.write_text("targets:\n" + artel_target_entry(), encoding="utf-8")
    assert "harness/" in perimeter(name), seed.msg(perimeter(name))


# ------------------------------------------------------------ AC-8

def test_ac8_external_perimeter_fixed_cases(tmp_root, seed):
    """Перечень внешнего проекта — `no_paths`, затем маркеры и `agent_wrapper` без повторов строк.

    Сценарий: три записи критерия — `no_paths: [zz/]` без поля
    `agent_wrapper`; `no_paths: []`; `no_paths: [.claude/, CLAUDE.md]` и
    `agent_wrapper: [harness/, .mcp.json]`. Перечни равны кортежам,
    выведенным из требований 5-6: у третьей `.claude/` и `**/.claude/`
    остаются обе, `.mcp.json` второй раз не добавляется.

    Ловит мутацию: перечень внешнего проекта — один `no_paths` (маркеров
    нет); маркеры идут раньше `no_paths`; повтор `.mcp.json` не убран;
    «дубль» распознан по смыслу записи — `.claude/` поглотила
    `**/.claude/`.
    """
    a, b, c = ("p" + seed.word() for _ in range(3))
    write_layers(flat_entry(a, ["zz/"]) + flat_entry(b, [])
                 + flat_entry(c, [".claude/", "CLAUDE.md"],
                              "    agent_wrapper: [harness/, .mcp.json]\n"))
    assert perimeter(a) == ("zz/", *MARKERS)
    assert perimeter(b) == tuple(config.AGENT_WRAPPER_MARKERS) == MARKERS
    assert perimeter(c) == (".claude/", "CLAUDE.md", *MARKERS, "harness/")


def test_ac8_external_perimeter_random_order_and_duplicates(tmp_root, seed):
    """Порядок и убирание повторов на случайных `no_paths` и `agent_wrapper`.

    Сценарий: `no_paths` — случайные каталоги и файлы с вкраплением маркеров
    обвязки; `agent_wrapper` — случайные пути, повторяющие часть `no_paths`,
    маркеры и друг друга. Перечень — `no_paths` по порядку, затем маркеры и
    элементы `agent_wrapper`, которых в кортеже ещё нет той же строкой.

    Ловит мутацию: повторы убраны через `set` — порядок поплыл; повтор
    внутри `agent_wrapper` не убран; элемент `agent_wrapper`, совпавший с
    `no_paths`, добавлен второй раз.
    """
    for _ in range(4):
        name = "p" + seed.word()
        own = [f"z{seed.word()}/" for _ in range(seed.rng.randint(1, 3))]
        no_paths = own + seed.rng.sample(MARKERS, seed.rng.randint(0, 2))
        seed.rng.shuffle(no_paths)
        fresh = [f"h{seed.word()}/" for _ in range(seed.rng.randint(1, 2))]
        wrapper = fresh + seed.rng.sample(no_paths, 1) + seed.rng.sample(MARKERS, 1)
        wrapper += [seed.rng.choice(wrapper)]
        seed.rng.shuffle(wrapper)
        write_layers(flat_entry(name, no_paths,
                                f"    agent_wrapper: {flow(wrapper)}\n"))
        want = list(no_paths)
        for item in [*MARKERS, *wrapper]:
            if item not in want:
                want.append(item)
        assert perimeter(name) == tuple(want), seed.msg(
            f"no_paths {no_paths}, agent_wrapper {wrapper}")


# ------------------------------------------------------------ AC-9

def test_ac9_artel_perimeter_is_protected_paths(tmp_root, seed):
    """Перечень артели — `config.PROTECTED_PATHS`, маркеры обвязки в него не дописываются.

    Сценарий: `protected_paths(resolve(config.DEFAULT_TARGET))` равен
    `tuple(config.PROTECTED_PATHS)` — и на текущем перечне, и при подмене
    перечня случайной добавочной записью.

    Ловит мутацию: маркеры обвязки дописаны в перечень любого проекта,
    включая артель, — у артели в перечне `**/.claude/`; перечень артели
    снят снимком при загрузке модуля — подмена его не меняет.
    """
    write_layers()
    ctx = repo_context.resolve(config.DEFAULT_TARGET)
    assert repo_context.protected_paths(ctx) == tuple(config.PROTECTED_PATHS)
    patched = tuple(config.PROTECTED_PATHS) + (f"z{seed.word()}/",)
    with mock.patch.object(config, "PROTECTED_PATHS", patched):
        assert repo_context.protected_paths(
            repo_context.resolve(config.DEFAULT_TARGET)) == patched, seed.msg(patched)


# ------------------------------------------------------------ AC-14

@pytest.mark.parametrize("item,entry", [
    (".claude/rules/", "**/.claude/"),
    ("./.claude/rules/", "**/.claude/"),
    ("sub/CLAUDE.md", "**/CLAUDE.md"),
    ("sub/AGENTS.md", "**/AGENTS.md"),
    (".mcp.json", ".mcp.json"),
    ("./.mcp.json", ".mcp.json"),
    ("harness/a.md", "harness/"),
    ("./harness/a.md", "harness/"),
])
def test_ac14_knowledge_into_wrapper_refused(tmp_root, seed, item, entry):
    """Элемент `knowledge` компонента, указывающий в обвязку проекта, — отказ загрузки записи с компонентом, элементом и путём обвязки.

    Сценарий: плоская запись внешнего проекта со случайным именем,
    `agent_wrapper: [harness/]` и одним компонентом со случайным именем, чей
    `knowledge` — один элемент критерия. `targets.load()` отказывает
    `TargetsError`; текст называет компонент, элемент (как записан или
    нормализованным) и запись обвязки, под которую он попал.

    Ловит мутацию: элемент сверяется без нормализации — `./.claude/rules/`
    и `./harness/a.md` проходят; элемент-каталог сверяется формулой путей
    файлов, а не как зона — `.claude/rules/` проходит; сверка только по
    маркерам — `harness/a.md` проходит.
    """
    name, comp = "p" + seed.word(), "k" + seed.word()
    write_layers(flat_entry(name, [], "    agent_wrapper: [harness/]\n"
                            + component_extra(comp, [item])))
    with pytest.raises(targets.TargetsError) as caught:
        targets.load()
    text = str(caught.value)
    normalized = posixpath.normpath(item)
    assert comp in text, seed.msg(text)
    assert item in text or normalized in text, seed.msg(text)
    assert entry in text, seed.msg(text)


@pytest.mark.parametrize("item", ["CLAUDE.md", "./CLAUDE.md", "AGENTS.md",
                                  "docs/arch.md", "docs/", "./"])
def test_ac14_knowledge_outside_wrapper_loads(tmp_root, seed, item):
    """Корневые `CLAUDE.md`/`AGENTS.md`, файл и каталог вне обвязки и каталог-предок в `knowledge` загружаются.

    Сценарий: та же запись с `agent_wrapper: [harness/]`, `knowledge` — один
    элемент критерия; `targets.load()` отдаёт запись проекта.

    Ловит мутацию: исключение корневых `CLAUDE.md`/`AGENTS.md` не сделано —
    `[CLAUDE.md]` под `**/CLAUDE.md` отказывает; исключение не видит
    нормализации — `./CLAUDE.md` отказывает; элемент-предок сверяется «в
    обратную сторону» (обвязка внутри элемента) — `./` и `docs/`
    отказывают.
    """
    name, comp = "p" + seed.word(), "k" + seed.word()
    write_layers(flat_entry(name, [], "    agent_wrapper: [harness/]\n"
                            + component_extra(comp, [item])))
    assert name in targets.load(), seed.msg(item)
