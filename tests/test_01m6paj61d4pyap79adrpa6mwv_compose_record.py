"""Запись проекта с `runner: compose`: загрузка и отказы загрузки с именем поля.

Группа: долгоживущий

Вход — текст локального слоя записей (`targets.local_path()`) песочницы
`tmp_root` (пути `config` во временном каталоге): запись в трёх разделах
`description`/`policy`/`machine` с `test_profile` либо с единственным
компонентом `components:`; для правила `env` плоской записи — слой
репозитория (`config.TARGETS`). Читается публичным `targets.load()`, профиль
— `project_profile.component_profiles`. Имена проекта, сервиса, каталогов
дерева и путей контейнера берутся случайно на каждом прогоне; зерно
печатается и входит в текст провала.

Каждый случай отказа сначала загружает ту же запись без правки (контроль:
отказ вызван именно правкой), затем сверяет, что текст `TargetsError`
называет поле. Перечень известных подполей «(известны: …)» из текста
отказа при сверке вырезается: он называет все поля разом.

Красен до реализации: `compose` нет в `targets.PROFILE_RUNNERS`, поля `compose_*` — неизвестные подполя: верная запись `compose` получает `TargetsError` «неизвестное подполе», контрольная загрузка каждого случая отказа падает.
"""
import random
import re
import string

import pytest

from orchestrator import config, project_profile, targets
from tests.sandbox import artel_target_entry

COMPOSE = "compose"
OWN = targets.PROFILE_RUNNER_OWN
LETTERS = string.ascii_lowercase
COMPOSE_FIELDS = ("compose_file", "compose_service", "compose_env_file",
                  "compose_env_template", "compose_mount")
KNOWN_LIST = re.compile(r"\(известны:[^)]*\)")


def word(rng, k: int = 6) -> str:
    return "".join(rng.choices(LETTERS, k=k))


def make_rng():
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    return seed, random.Random(seed)


def layout(rng) -> dict:
    """Случайная раскладка дерева: левая часть монтирования, `workdir` под
    ней, каталог Compose-файла вне её, путь контейнера."""
    left = f"src_{word(rng)}"
    app = f"{left}/app_{word(rng)}"
    deploy = f"deploy_{word(rng)}"
    return {"left": left, "app": app, "deploy": deploy,
            "right": f"/{word(rng)}/{word(rng)}"}


def compose_fields(rng, lay: dict) -> dict:
    """Поля верной записи `compose` (без `command`)."""
    return {
        "runner": COMPOSE,
        "workdir": lay["app"],
        "long_lived_dir": f"{lay['app']}/tests",
        "long_lived_name": "test_<id>_<name>.py",
        "report": "junit-xml",
        "compose_file": f"{lay['deploy']}/compose.yaml",
        "compose_service": f"svc_{word(rng)}",
        "compose_env_file": f"{lay['deploy']}/.env.{word(rng)}",
        "compose_env_template": f"{lay['deploy']}/env.{word(rng)}.template",
        "compose_mount": f"{lay['left']}:{lay['right']}",
    }


def render(fields: dict, indent: int) -> list:
    pad = " " * indent
    lines = []
    for key, value in fields.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            lines += [f'{pad}  {k}: "{v}"' for k, v in value.items()]
        elif isinstance(value, list):
            lines.append(f"{pad}{key}: [{', '.join(value)}]")
        elif isinstance(value, int):
            lines.append(f"{pad}{key}: {value}")
        else:
            lines.append(f'{pad}{key}: "{value}"')
    return lines


def scopes(fields: dict) -> dict:
    lld = fields.get("long_lived_dir", "tests")
    return {"weakening_scope": [f"{lld}/**/*.py"],
            "mutation_claim_scope": [f"{lld}/test_*.py"]}


def local_record(name: str, fields: dict, form: str, comp: str = "",
                 machine_path: str | None = None) -> str:
    """Запись локального слоя в трёх разделах."""
    lines = [f"  {name}:", "    description:", "      base: main"]
    if form == "test_profile":
        lines.append("      test_profile:")
        lines += render(fields, 8)
    else:
        lines += ["      components:", f"        {comp}:"]
        lines += render(fields, 10)
    lines += ["    policy:", "      no_paths: []", "      project_skills: []",
              "      merge_gate: operator"]
    if form == "test_profile":
        lines += render(scopes(fields), 6)
    else:
        lines += ["      components:", f"        {comp}:"]
        lines += render(scopes(fields), 10)
    lines += ["    machine:", "      forge: github",
              f"      url: https://localhost/team/{name}",
              f"      token_slot: {name}-token"]
    if machine_path is not None:
        lines.append(f'      path: "{machine_path}"')
    return "\n".join(lines) + "\n"


def write_local(text: str) -> None:
    path = targets.local_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("targets:\n" + text, encoding="utf-8")


def flat_record(name: str, fields: dict) -> str:
    """Плоская запись слоя репозитория с `test_profile`."""
    lines = [f"  {name}:", "    forge: github",
             f"    url: https://localhost/team/{name}", "    base: main",
             f"    token_slot: {name}-token", "    no_paths: []",
             "    project_skills: []", "    merge_gate: operator",
             "    test_profile:"]
    lines += render(dict(fields, **scopes(fields)), 6)
    return "\n".join(lines) + "\n"


def write_repo(text: str) -> None:
    config.TARGETS.write_text("targets:\n" + artel_target_entry() + text,
                              encoding="utf-8")


def load_error(where: str) -> str:
    with pytest.raises(targets.TargetsError) as caught:
        targets.load()
    text = str(caught.value)
    print(f"{where}: отказ «{text}»")
    return text


def load_ok(where: str) -> dict:
    try:
        return targets.load()
    except targets.TargetsError as exc:
        pytest.fail(f"{where}: верная запись не загружена: {exc}")


def names_field(text: str, field: str) -> bool:
    """Текст отказа называет поле `field` — вне перечня известных полей."""
    rest = KNOWN_LIST.sub("", text)
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(field)}(?![A-Za-z0-9_])",
                     rest) is not None


def entry_fields(entry: dict, form: str, comp: str) -> dict:
    if form == "test_profile":
        return entry[targets.PROFILE_FIELD]
    return entry[targets.COMPONENTS_FIELD][comp]


@pytest.mark.parametrize("form", ["test_profile", "components"])
@pytest.mark.parametrize("with_path", [False, True])
def test_ac1_compose_record_loads_with_default_command(tmp_root, form,
                                                       with_path):
    """Верная запись `compose` загружается в `test_profile` и в `components:`, без `command` — `["pytest"]`.

    Запись с полями требования 1 без `command` (с `machine.path` и без)
    загружается `targets.load()`; в отданной записи `runner` — `compose`,
    поля `compose_*` на месте, `command` — `["pytest"]`; профиль
    `project_profile.component_profiles` несёт команду `("pytest",)`. Та же
    запись с явной `command` отдаёт её как есть. `compose` входит в
    `targets.PROFILE_RUNNERS`.

    Ловит мутацию: умолчание `["pytest"]` не подставлено в отданную копию
    (читатель видит запись без `command`), подставлено поверх явной
    команды, `machine.path` по-прежнему допустим только при `pytest-own`
    (запись с ним отказана) — сверка значения или загрузка падает.
    """
    seed, rng = make_rng()
    where = f"зерно {seed}, форма {form}, machine.path {with_path}"
    assert COMPOSE in targets.PROFILE_RUNNERS, where
    name, comp = f"proj{word(rng)}", f"comp{word(rng)}"
    lay = layout(rng)
    fields = compose_fields(rng, lay)
    path = (f"/opt/{word(rng)}/bin:/opt/{word(rng)}/bin" if with_path
            else None)
    write_local(local_record(name, fields, form, comp, path))
    entry = load_ok(where)[name]
    got = entry_fields(entry, form, comp)
    assert got.get("runner") == COMPOSE, where
    for field in COMPOSE_FIELDS:
        assert got.get(field) == fields[field], f"{where}: поле {field}"
    assert got.get("command") == ["pytest"], f"{where}: {got.get('command')!r}"
    (profile,) = project_profile.component_profiles(name)
    assert tuple(profile.command) == ("pytest",), where
    explicit = ["python3", "-m", "pytest", f"-k{word(rng)}"]
    write_local(local_record(name, dict(fields, command=explicit), form, comp,
                             path))
    got = entry_fields(load_ok(where)[name], form, comp)
    assert got.get("command") == explicit, where


# Случаи отказа: (имя случая, форма записи, поле, которое называет отказ).
REFUSALS = [
    ("drop_workdir", "test_profile", "workdir"),
    ("drop_workdir", "components", "workdir"),
    ("drop_report", "test_profile", "report"),
    ("drop_report", "components", "report"),
    ("abs_compose_file", "test_profile", "compose_file"),
    ("dotdot_compose_file", "test_profile", "compose_file"),
    ("abs_compose_env_file", "components", "compose_env_file"),
    ("dotdot_compose_env_file", "test_profile", "compose_env_file"),
    ("abs_compose_env_template", "test_profile", "compose_env_template"),
    ("dotdot_compose_env_template", "components", "compose_env_template"),
    ("abs_mount_left", "test_profile", "compose_mount"),
    ("dotdot_mount_left", "components", "compose_mount"),
    ("relative_mount_right", "test_profile", "compose_mount"),
    ("relative_mount_right", "components", "compose_mount"),
    ("install", "test_profile", "install"),
    ("install", "components", "install"),
    ("tools", "components", "tools"),
    ("checks_local", "components", "checks_local"),
    ("description_env", "test_profile", "env"),
    ("description_env", "components", "env"),
    ("workdir_outside_mount", "test_profile", "workdir|long_lived_dir"),
    ("workdir_outside_mount", "components", "workdir|long_lived_dir"),
    ("long_lived_outside_mount", "test_profile", "long_lived_dir"),
    ("long_lived_outside_mount", "components", "long_lived_dir"),
    ("plank_outside_mount", "test_profile", "long_lived_dir"),
    ("plank_outside_mount", "components", "long_lived_dir"),
    ("plank_layout_outside_mount", "components", "plank_layout"),
    ("reruns_in_report_args", "components", "report_args"),
    ("rerun_plugin_in_select", "components", "select"),
    ("drop_compose_file", "test_profile", "compose_file"),
    ("drop_compose_service", "test_profile", "compose_service"),
    ("drop_compose_env_file", "components", "compose_env_file"),
    ("drop_compose_env_template", "test_profile", "compose_env_template"),
    ("drop_compose_mount", "components", "compose_mount"),
    ("drop_compose_file", "components", "compose_file"),
    ("drop_compose_service", "components", "compose_service"),
    ("drop_compose_env_file", "test_profile", "compose_env_file"),
    ("drop_compose_env_template", "components", "compose_env_template"),
    ("drop_compose_mount", "test_profile", "compose_mount"),
    ("mount_without_pair", "test_profile", "compose_mount"),
    ("mount_two_pairs", "test_profile", "compose_mount"),
    ("mount_two_pairs", "components", "compose_mount"),
    ("mount_list_of_pairs", "components", "compose_mount"),
]


def mutated(case: str, fields: dict, lay: dict, rng) -> dict:
    """Запись случая `case` из верной записи `fields`."""
    out = dict(fields)
    if case.startswith("drop_"):
        out.pop(case[len("drop_"):])
    elif case.startswith("abs_compose_"):
        field = case[len("abs_"):]
        out[field] = f"/{word(rng)}/{fields[field]}"
    elif case.startswith("dotdot_compose_"):
        field = case[len("dotdot_"):]
        out[field] = f"{lay['deploy']}/../../{word(rng)}/{word(rng)}.yaml"
    elif case == "abs_mount_left":
        out["compose_mount"] = f"/{lay['left']}:{lay['right']}"
    elif case == "dotdot_mount_left":
        out["compose_mount"] = f"{lay['left']}/..:{lay['right']}"
    elif case == "relative_mount_right":
        out["compose_mount"] = f"{lay['left']}:{lay['right'].lstrip('/')}"
    elif case == "install":
        out["install"] = ["make", f"deps_{word(rng)}"]
    elif case == "tools":
        out["tools"] = {"pytest": f"8.{rng.randrange(10)}"}
    elif case == "checks_local":
        out["checks_local"] = ["make", f"check_{word(rng)}"]
    elif case == "description_env":
        out["env"] = {f"PROBE_{word(rng).upper()}": word(rng)}
    elif case == "workdir_outside_mount":
        # `workdir` вне монтирования тянет за собой `long_lived_dir` вне него
        # (или вне `workdir`): отказ называет одно из двух полей.
        out["workdir"] = f"other_{word(rng)}"
        out["long_lived_dir"] = f"{out['workdir']}/tests"
    elif case == "long_lived_outside_mount":
        out["long_lived_dir"] = f"other_{word(rng)}/tests"
    elif case == "plank_outside_mount":
        # `long_lived_dir` под монтированием, но вне `workdir`: планка лежит
        # без раскладки в каталоге задачи от корня дерева — не под левой
        # частью `src_…`.
        out["long_lived_dir"] = f"{lay['left']}/qa_{word(rng)}"
    elif case == "plank_layout_outside_mount":
        out["plank_layout"] = f"other_{word(rng)}/.plank/<id>"
    elif case == "reruns_in_report_args":
        out["report_args"] = ["--junitxml", "--reruns=3"]
    elif case == "rerun_plugin_in_select":
        out["select"] = ["-p", "rerunfailures"]
    elif case == "mount_without_pair":
        out["compose_mount"] = lay["left"]
    elif case == "mount_two_pairs":
        out["compose_mount"] = (f"{lay['left']}:{lay['right']}:"
                                f"lib_{word(rng)}:/lib_{word(rng)}")
    elif case == "mount_list_of_pairs":
        out["compose_mount"] = [f"{lay['left']}:{lay['right']}",
                                f"lib_{word(rng)}:/lib_{word(rng)}"]
    else:
        raise AssertionError(f"неизвестный случай {case}")
    return out


@pytest.mark.parametrize("case, form, field", REFUSALS)
def test_ac2_compose_record_refused_naming_field(tmp_root, case, form, field):
    """Правка верной записи `compose` — отказ загрузки, текст называет поле.

    Сначала верная запись той же формы загружается (контроль). Затем
    запись с правкой случая (нет поля, абсолютный путь или `..`, правая
    часть монтирования не абсолютна, `install`/`tools`/`checks_local`,
    `env` в разделе `description`, `workdir`/`long_lived_dir` вне левой
    части `compose_mount`, `long_lived_dir` вне `workdir` при каталоге
    планки задачи не под монтированием, `plank_layout` вне монтирования,
    повторы в `report_args`/`select` при команде по умолчанию, монтирование
    без пары или с двумя парами) получает `TargetsError`, называющий поле
    случая.

    Ловит мутацию: пропущена проверка одного поля (нет `workdir` — молчаливое
    `.`; нет `compose_mount` — прогон без монтирования; `..` в пути
    принят; вторая пара монтирования отброшена молча), умолчание
    `["pytest"]` не участвует в запрете повторов, планка вне
    монтирования не проверена — запись загружается без отказа или отказ
    называет другое поле.
    """
    seed, rng = make_rng()
    where = f"зерно {seed}, случай {case}, форма {form}"
    name, comp = f"proj{word(rng)}", f"comp{word(rng)}"
    lay = layout(rng)
    fields = compose_fields(rng, lay)
    write_local(local_record(name, fields, form, comp))
    load_ok(f"{where} (контроль)")
    write_local(local_record(name, mutated(case, fields, lay, rng), form,
                             comp))
    text = load_error(where)
    assert any(names_field(text, one) for one in field.split("|")), \
        f"{where}: отказ не называет {field}: {text}"


@pytest.mark.parametrize("form", ["test_profile", "components"])
def test_ac2_long_lived_outside_workdir_loads_when_plank_under_mount(tmp_root,
                                                                    form):
    """`long_lived_dir` вне `workdir` при монтировании корня дерева (`.`) загружается.

    Запись `compose` с `compose_mount` `.:<путь>`, `workdir` и
    `long_lived_dir` в разных каталогах: каталог планки задачи лежит под
    корнем дерева — отказа нет. Пара к случаю `plank_outside_mount`.

    Ловит мутацию: `long_lived_dir` вне `workdir` отказан всегда, без
    сверки каталога планки с левой частью монтирования — верная запись
    получает отказ.
    """
    seed, rng = make_rng()
    where = f"зерно {seed}, форма {form}"
    name, comp = f"proj{word(rng)}", f"comp{word(rng)}"
    lay = layout(rng)
    fields = compose_fields(rng, lay)
    fields["long_lived_dir"] = f"{lay['left']}/qa_{word(rng)}"
    fields["compose_mount"] = f".:{lay['right']}"
    write_local(local_record(name, fields, form, comp))
    load_ok(where)


@pytest.mark.parametrize("field", [*COMPOSE_FIELDS, "compose_up_down_sec"])
def test_ac2_compose_field_with_other_runner_refused(tmp_root, field):
    """Поле `compose_*` у записи `pytest-own` — отказ загрузки с именем поля.

    Контроль: запись `pytest-own` (своя команда, `workdir`, `report`)
    загружается; та же запись с одним полем `compose_*` (значение — из
    верной записи `compose`, у `compose_up_down_sec` — целое) получает
    `TargetsError`, называющий это поле.

    Ловит мутацию: поля `compose_*` приняты у любого раннера (проверка
    только при `compose`) — запись `pytest-own` с ним загружается.
    """
    seed, rng = make_rng()
    where = f"зерно {seed}, поле {field}"
    name = f"proj{word(rng)}"
    lay = layout(rng)
    compose = compose_fields(rng, lay)
    own = {"runner": OWN, "command": ["python3", "-m", "pytest"],
           "workdir": lay["app"], "long_lived_dir": f"{lay['app']}/tests",
           "long_lived_name": "test_<id>_<name>.py", "report": "junit-xml"}
    write_local(local_record(name, own, "test_profile"))
    load_ok(f"{where} (контроль)")
    value = rng.randrange(1, 900) if field == "compose_up_down_sec" \
        else compose[field]
    write_local(local_record(name, dict(own, **{field: value}),
                             "test_profile"))
    text = load_error(where)
    assert names_field(text, field), f"{where}: {text}"


def test_ac2_flat_repo_record_compose_env_refused(tmp_root):
    """Поле `env` у плоской записи `compose` слоя репозитория — отказ с именем `env`.

    Контроль: плоская запись `compose` (в `config.TARGETS` рядом с записью
    артели) без `env` загружается; та же запись с `env` в `test_profile`
    получает `TargetsError`, называющий `env`.

    Ловит мутацию: запрет `env` проверяется только по разделу
    `description` локального слоя — плоская запись слоя репозитория с
    `env` загружается.
    """
    seed, rng = make_rng()
    where = f"зерно {seed}"
    name = f"proj{word(rng)}"
    fields = compose_fields(rng, layout(rng))
    write_repo(flat_record(name, fields))
    entry = load_ok(f"{where} (контроль)")[name]
    assert entry[targets.PROFILE_FIELD].get("runner") == COMPOSE, where
    write_repo(flat_record(name, dict(
        fields, env={f"PROBE_{word(rng).upper()}": word(rng)})))
    text = load_error(where)
    assert names_field(text, "env"), f"{where}: {text}"


def test_ac2_pytest_own_without_command_still_refused(tmp_root):
    """Профиль `pytest-own` без `command` — по-прежнему отказ «нет подполя».

    Контроль: запись `pytest-own` с командой загружается; без `command` —
    `TargetsError` с «нет подполя» и `command`. Умолчание `["pytest"]`
    действует только у `compose`.

    Ловит мутацию: умолчание команды подставлено любому раннеру (или до
    проверки обязательных подполей) — запись `pytest-own` без `command`
    загружается с командой `pytest`.
    """
    seed, rng = make_rng()
    where = f"зерно {seed}"
    name = f"proj{word(rng)}"
    app = f"app_{word(rng)}"
    own = {"runner": OWN, "command": ["python3", "-m", "pytest"],
           "workdir": app, "long_lived_dir": f"{app}/tests",
           "long_lived_name": "test_<id>_<name>.py", "report": "junit-xml"}
    write_local(local_record(name, own, "test_profile"))
    load_ok(f"{where} (контроль)")
    own.pop("command")
    write_local(local_record(name, own, "test_profile"))
    text = load_error(where)
    assert "нет подполя" in text and names_field(text, "command"), \
        f"{where}: {text}"
