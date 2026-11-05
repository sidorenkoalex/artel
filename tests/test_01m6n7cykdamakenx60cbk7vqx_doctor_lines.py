"""Строки `doctor` записи `github` + `target-human`: `project-ci-file-no-paths-<проект>` проверяет покрытие каталога `.github/workflows/` записями `no_paths` по формуле `config.is_protected_path` для любого имени файла; строки подмодулей и хука есть, строк перезапусков CI и срока токена нет; GitLab — прежние условие и исходы по `.gitlab-ci.yml`.

Группа: долгоживущий
Красен до реализации: строка `project-ci-file-no-paths-<проект>` строится только при компоненте с `full_suite` ci/both, а у записи GitHub такого компонента быть не может — строки нет вовсе; методы GitLab (AC-4) и строк AC-5 зелены с рождения — они закрепляют прежнее поведение.

Связка, которую держит файл: «запись проекта в `targets.yaml` песочницы —
`doctor.project_entry_checks`/`doctor.project_checks.component_checks`/
`doctor.all_checks` — внешние процессы». Песочница — `initialized_tmp_root`
(пути `config` во временном каталоге); внешние процессы, кроме локальных
(`git` без сети, интерпретатор, `ps`), получают отказ запуска — настоящий
`gh` не запускается; признак процесса роли снят. Клон проекта — настоящий
локальный репозиторий без `origin` (`tests.sandbox.make_project_repo`).

Загрузчик не принимает `no_paths` с маской для любой записи одинаково,
поэтому значения `no_paths` подставляются в словарь записи, переданный
строкам прямо (тот же словарь строки получают и из `doctor.all_checks`).

Имена проектов и посторонние пути `no_paths` порождаются модулем `random`
при каждом запуске; зерно печатается и входит в текст провала.
"""
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

from orchestrator import config, doctor, repo_context, runner, store, targets
from tests.sandbox import artel_target_entry, make_project_repo

LETTERS = "abcdefhkmnpqrsvwxyz"
NETWORK_GIT = {"clone", "fetch", "push", "pull", "ls-remote"}
WORKFLOWS = ".github/workflows/"
PUSH_HOOK_LINE = "clone-push-hook"


def word(rng: random.Random, prefix: str, size: int = 7) -> str:
    return prefix + "".join(rng.choice(LETTERS) for _ in range(size))


def local_command(argv) -> bool:
    """Локальный процесс песочницы: `ps`, интерпретатор Python, git без сети."""
    if not isinstance(argv, (list, tuple)) or not argv:
        return False
    words = [os.fsdecode(a) for a in argv]
    name = Path(words[0]).name
    if name == "git":
        return not NETWORK_GIT & set(words[1:])
    return name == "ps" or name.startswith("python") or words[0] == sys.executable


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


@pytest.fixture
def pult(initialized_tmp_root, monkeypatch):
    """Песочница с проинициализированным корнем; внешние процессы не запускаются."""
    real_run, real_popen = subprocess.run, subprocess.Popen

    def run(argv, *args, **kwargs):
        if local_command(argv):
            return real_run(argv, *args, **kwargs)
        empty = b"" if not (kwargs.get("text") or kwargs.get("encoding")
                            or kwargs.get("universal_newlines")) else ""
        return subprocess.CompletedProcess(argv, 127, empty, empty)

    def popen(argv, *args, **kwargs):
        if local_command(argv):
            return real_popen(argv, *args, **kwargs)
        raise FileNotFoundError(f"песочница: внешний процесс {argv!r} не запускается")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(runner, "in_role_environment", lambda env=None: False)
    return initialized_tmp_root


def declare(rng: random.Random, forge_name: str, components: bool = False) -> str:
    """Плоская запись проекта `<forge>` + `target-human` в `targets.yaml`
    песочницы и клон; имя проекта."""
    name = word(rng, "p")
    lines = [f"  {name}:", f"    forge: {forge_name}",
             f"    url: https://localhost/team/{name}",
             f"    base: {config.MAIN_BRANCH}", f"    token_slot: {name}-token",
             "    no_paths: []", "    project_skills: []",
             "    merge_gate: target-human"]
    if components:
        lines += ["    components:", "      app:",
                  "        command: [python3, -m, pytest]",
                  "        report: junit-xml",
                  "        long_lived_dir: tests",
                  "        long_lived_name: test_<id>_<name>.py",
                  "        weakening_scope: [tests/**]",
                  "        mutation_claim_scope: [tests/test_*.py]",
                  "        full_suite: ci",
                  "        ci_job: tests"]
    config.TARGETS.write_text("targets:\n" + artel_target_entry().rstrip("\n")
                              + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    make_project_repo(name, origin=False)
    return name


def lines_of(name: str, no_paths: list) -> dict:
    entry = dict(targets.target(name))
    entry["no_paths"] = list(no_paths)
    found = (list(doctor.project_entry_checks(name, entry))
             + list(doctor.project_checks.component_checks(name, entry)))
    return {c.name: c for c in found}


def shown(checks: dict) -> str:
    return "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in checks.values())


# ------------------------------------------------------------------- AC-4

COVERING = [".github/workflows/", ".github/", ".github", "**/workflows/", "**/.github/"]
NOT_COVERING = [None, ".github/*", "**/", "**/ci.yml", "**/x", "**/a", "**/main.yml",
                ".github/workflows/c", ".github/workflows/ci.yml",
                ".github/workflows/x", ".github/workflows/a"]


@pytest.mark.parametrize("entry,status",
                         [(e, "ok") for e in COVERING] + [(e, "fail") for e in NOT_COVERING],
                         ids=[f"ok {e}" for e in COVERING]
                         + [f"fail {e or 'без записи'}" for e in NOT_COVERING])
def test_ac4_github_workflows_dir_covered_by_no_paths(pult, seed, entry, status):
    """Строка `project-ci-file-no-paths-<проект>` записи `github` + `target-human` есть без компонента `full_suite` и решает покрытие всего каталога `.github/workflows/`.

    Сценарий: запись GitHub людей проекта без компонентов; `no_paths` —
    запись по параметру среди случайных посторонних путей (или только
    посторонние). Строка есть; при записях `.github/workflows/`,
    `.github/`, `.github`, `**/workflows/`, `**/.github/` — `ok`; без
    подходящей записи, при маске `.github/*`, при `**/`, при записях на
    отдельный файл (`**/ci.yml`, `**/x`, `**/a`, `**/main.yml`,
    `.github/workflows/ci.yml`, `.github/workflows/x`,
    `.github/workflows/a`) и при префиксе длиннее каталога
    (`.github/workflows/c`) — `fail`, текст называет `.github/workflows/`.

    Ловит мутацию: строка строится по-прежнему только при компоненте
    `full_suite` ci/both (у GitHub её нет); покрытие пробуется путём самого
    каталога (`**/` даёт `ok`) или одним фиксированным именем файла
    (`ci.yml` даёт `ok` записи `**/ci.yml`, `x`/`a` — записям `**/x`,
    `**/a`, `.github/workflows/x`, `.github/workflows/a`, `c…` — префиксу
    `.github/workflows/c`); маска `*` принимается по `mask_matches`;
    сравнение литералом `forge == "github"` вместо `forge.ci_by_pipeline`
    здесь не наблюдается — его ловит сторож литералов.
    """
    rng = random.Random(seed)
    name = declare(rng, "github")
    others = [f"{word(rng, 'd', 4)}/{word(rng, 'f', 3)}.txt" for _ in range(rng.randint(0, 2))]
    no_paths = others + ([entry] if entry else [])
    rng.shuffle(no_paths)
    checks = lines_of(name, no_paths)
    line = checks.get(f"project-ci-file-no-paths-{name}")
    note = f"зерно: {seed}; no_paths {no_paths}\n{shown(checks)}"
    assert line is not None, note
    assert line.status == status, note
    if status == "fail":
        assert WORKFLOWS in line.detail, note


@pytest.mark.parametrize("components,no_paths,status", [
    (True, [".gitlab-ci.yml"], "ok"),
    (True, ["README.md"], "fail"),
    (True, [], "fail"),
    (False, [".gitlab-ci.yml"], None),
], ids=["ci-файл покрыт", "ci-файл не покрыт", "пусто", "без компонента ci"])
def test_ac4_gitlab_ci_file_line_unchanged(pult, seed, components, no_paths, status):
    """Запись `gitlab` + `target-human`: строка `project-ci-file-no-paths-<проект>` — прежнее условие (компонент `full_suite` ci/both) и прежние исходы по `.gitlab-ci.yml`.

    Сценарий: запись GitLab людей проекта с компонентом `full_suite: ci`
    либо без компонентов; `no_paths` по параметру. С компонентом:
    `.gitlab-ci.yml` в `no_paths` — `ok`, иначе — `fail`, текст называет
    `.gitlab-ci.yml`. Без компонента — строки нет.

    Ловит мутацию: строка «всегда» распространена на хостинг с конвейерами
    (у GitLab без компонента строка появилась); для GitLab проверяется
    каталог `.github/workflows/` вместо `.gitlab-ci.yml`.
    """
    rng = random.Random(seed)
    name = declare(rng, "gitlab", components=components)
    checks = lines_of(name, no_paths)
    line = checks.get(f"project-ci-file-no-paths-{name}")
    note = f"зерно: {seed}; no_paths {no_paths}\n{shown(checks)}"
    if status is None:
        assert line is None, note
        return
    assert line is not None and line.status == status, note
    if status == "fail":
        assert ".gitlab-ci.yml" in line.detail, note


# ------------------------------------------------------------------- AC-5


def test_ac5_github_people_doctor_lines_present_and_absent(pult, seed):
    """`doctor` по записи `github` + `target-human`: строки `project-submodules-<проект>` и хука (`clone-push-hook`) есть, строк `project-ci-reruns-<проект>-…` и `token-expiry-<проект>` нет.

    Сценарий: в `targets.yaml` песочницы — артель и одна запись GitHub
    людей проекта со случайным именем, клон заведён. Среди строк
    `doctor.all_checks` есть `project-submodules-<проект>` и
    `clone-push-hook`; ни одна строка не начинается с
    `project-ci-reruns-<проект>-` и не равна `token-expiry-<проект>`.

    Ловит мутацию: строки подмодулей или хука клонов выбраны по хостингу с
    конвейерами (`forge.ci_by_pipeline`) вместо `merged_by_project_people`
    — у GitHub их нет; реализации GitHub добавлена функция `token_expiry`
    или строка перезапусков CI построена для GitHub — лишняя строка.
    """
    rng = random.Random(seed)
    name = declare(rng, "github")
    assert repo_context.clone_path(name).exists()
    checks = {c.name: c for c in doctor.all_checks(store.db())}
    note = f"зерно: {seed}; проект {name}\n{shown(checks)}"
    assert f"project-submodules-{name}" in checks, note
    assert PUSH_HOOK_LINE in checks, note
    assert not [n for n in checks if n.startswith(f"project-ci-reruns-{name}-")], note
    assert f"token-expiry-{name}" not in checks, note
