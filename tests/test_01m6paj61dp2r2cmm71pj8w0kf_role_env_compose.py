"""Окружение шага роли задачи с профилем `compose` — побайтно как у той же записи с `pytest-own`.

Группа: долгоживущий
Красен до реализации: раннера `compose` в ветке задачи ещё нет (он приходит из main с частью 1) — запись с `runner: compose` не загружается, `runner.role_env` проекта поднимает `TargetsError` или окружение расходится с двойником; случаи без `compose` зелены с рождения — они держат прежнее окружение.

Связка, которую держит файл: «запись проекта локального слоя песочницы —
`runner.role_env`». Песочница — `real_git` (пути `config` во временном
каталоге, карта ролей песочницы); проверка стека подменена заглушкой
`tests.sandbox._stub_check_stack`, как в прочих тестах `role_env`. Запись
проекта — временный дублёр в локальном слое песочницы (`targets.local_path()`);
настоящие файлы пульта не читаются и не меняются. Имена проекта, каталогов,
сервиса, `machine.path` и `commit_author` — из `random` при каждом запуске;
зерно печатается и входит в текст провала.
"""
import random
from unittest import mock

import pytest

from orchestrator import config, idgen, runner, stack, store, targets
from tests.sandbox import _stub_check_stack

LETTERS = "abcdefhkmnpqrsvwxyz"
ROLES = ("developer", "test_author", "reviewer")


def word(rng, prefix: str, size: int = 7) -> str:
    return prefix + "".join(rng.choice(LETTERS) for _ in range(size))


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


@pytest.fixture
def pult(real_git):
    real_git.use_role_map()
    with mock.patch.object(stack, "check_stack", _stub_check_stack):
        yield real_git


def profile_fields(rng, runner_name: str, left: str) -> dict:
    """Поля профиля раннера `runner_name` над одним и тем же деревом."""
    common = {"long_lived_dir": f"{left}/app/tests",
              "long_lived_name": "test_<id>_<name>.py"}
    if runner_name == "compose":
        deploy = word(rng, "deploy")
        return {"runner": "compose", "workdir": f"{left}/app",
                "report": "junit-xml", **common,
                "compose_file": f"{deploy}/compose.yaml",
                "compose_service": word(rng, "svc"),
                "compose_env_file": f"{deploy}/.env",
                "compose_env_template": f"{deploy}/env.template",
                "compose_mount": f"{left}:/{word(rng, 'w')}"}
    if runner_name == targets.PROFILE_RUNNER_OWN:
        return {"runner": runner_name, "workdir": f"{left}/app",
                "report": "junit-xml", **common,
                "command": ["python3", "-m", "pytest"]}
    return {"runner": runner_name, **common,
            "command": ["python3", "-m", "pytest"]}


def render(fields: dict, indent: int) -> list:
    pad = " " * indent
    return [f"{pad}{k}: [{', '.join(v)}]" if isinstance(v, list)
            else f'{pad}{k}: "{v}"' for k, v in fields.items()]


def record(name: str, fields: dict, form: str, comp: str,
           machine_path: str | None, author: tuple | None) -> str:
    lines = [f"  {name}:", "    description:", f"      base: {config.MAIN_BRANCH}"]
    scope = {"weakening_scope": [f"{fields['long_lived_dir']}/**/*.py"],
             "mutation_claim_scope": [f"{fields['long_lived_dir']}/test_*.py"]}
    if form == "test_profile":
        lines += ["      test_profile:"] + render(fields, 8)
    else:
        lines += ["      components:", f"        {comp}:"] + render(fields, 10)
    lines += ["    policy:", "      no_paths: []", "      project_skills: []",
              "      merge_gate: operator"]
    if form == "test_profile":
        lines += render(scope, 6)
    else:
        lines += ["      components:", f"        {comp}:"] + render(scope, 10)
    lines += ["    machine:", "      forge: github",
              f"      url: https://localhost/team/{name}",
              f"      token_slot: {name}-token"]
    if machine_path is not None:
        lines.append(f'      path: "{machine_path}"')
    if author is not None:
        lines += ["      commit_author:", f"        name: {author[0]}",
                  f"        email: {author[1]}"]
    return "\n".join(lines) + "\n"


def write_layer(text: str) -> None:
    path = targets.local_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("targets:\n" + text, encoding="utf-8")


def new_task(rng, name: str) -> str:
    task = idgen.new_task_id()
    store.insert_task(store.db(), task, "Фикстура окружения роли", "in_dev",
                      f"task/{task.lower()}-{word(rng, 's', 5)}", name,
                      config.DEFAULT_BUDGET_USD)
    return task


def envs(task: str, project: str | None) -> dict:
    return {role: runner.role_env(role, task, project=project) for role in ROLES}


def diff(a: dict, b: dict) -> str:
    out = []
    for role in a:
        keys = set(a[role]) | set(b[role])
        out += [f"{role}.{k}: {a[role].get(k)!r} != {b[role].get(k)!r}"
                for k in sorted(keys) if a[role].get(k) != b[role].get(k)]
    return "; ".join(out[:10])


@pytest.mark.parametrize("form", ["test_profile", "components"])
@pytest.mark.parametrize("with_path", [False, True])
def test_ac1_compose_role_env_equals_pytest_own_twin(pult, seed, form, with_path):
    """Окружение `role_env` задачи проекта с `compose` побайтно равно окружению той же записи с `pytest-own`.

    Сценарий: в локальном слое песочницы — запись проекта со случайными
    именами, `commit_author` и (по параметру) `machine.path`; профиль —
    `compose` в `test_profile` или в единственном компоненте. Для задачи
    этого проекта `runner.role_env` трёх ролей сравнивается с окружением
    после замены профиля двойником `pytest-own` над тем же деревом (прочие
    поля записи те же): словари равны целиком, ключ в ключ и значение в
    значение.

    Ловит мутацию: шагу роли задачи `compose` добавлены `DOCKER_HOST`,
    `DOCKER_CONFIG` или каталог `docker` в `PATH`; окружение для `compose`
    строится иной веткой (без `GIT_CONFIG_NOSYSTEM` или без `commit_author`)
    — словари расходятся на этом ключе.
    """
    rng = random.Random(seed)
    name, comp, left = word(rng, "p"), word(rng, "c", 5), word(rng, "src")
    path = f"/opt/{word(rng, 'm', 5)}/bin" if with_path else None
    author = (word(rng, "a"), f"{word(rng, 'e')}@example.invalid")
    task = new_task(rng, name)
    write_layer(record(name, profile_fields(rng, "compose", left), form, comp,
                       path, author))
    targets.load()
    got = envs(task, name)
    write_layer(record(name, profile_fields(rng, targets.PROFILE_RUNNER_OWN,
                                            left), form, comp, path, author))
    twin = envs(task, name)
    assert got == twin, f"зерно: {seed}; {diff(got, twin)}"


def test_ac1_non_compose_role_env_unchanged(pult, seed):
    """Окружение `role_env` у `pytest-own`, `pult-pytest`, артели, вызова без проекта и при непрочитанной записи — прежнее, исключения нет.

    Сценарий: запись проекта без `machine.path` и без `commit_author` с
    профилем `pult-pytest`, затем `pytest-own`, затем `compose` над тем же
    деревом — окружение задачи проекта одно и то же у всех трёх. Окружение
    артели и вызова без проекта не меняется от того, есть ли в слое проект
    `compose`. Слой проектов испорчен (неразбираемая запись) — `role_env`
    задачи проекта не поднимает исключения и равен окружению той же задачи
    при годной записи `pytest-own`.

    Ловит мутацию: `role_env` читает профиль проекта для решения о Docker и
    на непрочитанном слое поднимает `TargetsError`; окружение артели или
    вызова без проекта меняется, когда в слое есть проект `compose`;
    раннер `pult-pytest`/`pytest-own` получает иную ветку окружения.
    """
    rng = random.Random(seed)
    name, left = word(rng, "p"), word(rng, "src")
    task = new_task(rng, name)
    artel_task = new_task(rng, config.DEFAULT_TARGET)
    seen = {}
    for runner_name in (targets.PROFILE_RUNNER_DEFAULT, targets.PROFILE_RUNNER_OWN,
                        "compose"):
        write_layer(record(name, profile_fields(rng, runner_name, left),
                           "test_profile", "", None, None))
        targets.load()
        seen[runner_name] = (envs(task, name), envs(artel_task, config.DEFAULT_TARGET),
                             envs(artel_task, None))
    note = f"зерно: {seed}"
    own = seen[targets.PROFILE_RUNNER_OWN]
    for runner_name, got in seen.items():
        for index, label in enumerate(("проект", "артель", "без проекта")):
            assert got[index] == own[index], \
                f"{note}; {runner_name}, {label}: {diff(got[index], own[index])}"
    write_layer(f"  {name}:\n    description: [не запись\n")
    with pytest.raises(targets.TargetsError):
        targets.load()
    broken = envs(task, name)
    assert broken == own[0], f"{note}; слой испорчен: {diff(broken, own[0])}"
