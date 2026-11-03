"""Строки `doctor` по записи проекта GitLab и записи с `merge_gate: target-human`: защиты, права токена на CI, правила workflow файла CI, токен, `no_paths` файла CI, перезапуски в `ci_job`, подмодули; строки артели и `github` + `operator` прежние.

Группа: долгоживущий
Красен до реализации: строки записи GitLab идут путём GitHub (`gh api`, Actions, `.github/workflows`, `gh auth token`) — `skip` «gh CLI не найден»/`fail` Actions вместо исходов `forge`, строк `project-ci-file-no-paths-`, `project-ci-reruns-`, `project-submodules-` нет вовсе, у `forge.BranchPipeline` нет поля `http_status` (конструктор падает `TypeError`); тест строк артели и `github` + `operator` (AC-15), строка `project-token` при пустом слоте и без `token_slot` (AC-13), отсутствие новых строк у `operator` (AC-8) зелены с рождения — они держат прежнее поведение.

Связка, которую держит файл: «запись проекта в `targets.yaml` песочницы —
`doctor.project_entry_checks`/`doctor.project_checks.component_checks` —
`forge` — `gitcmd.in_repo` — внешние процессы». Песочница —
`initialized_tmp_root` (пути `config` во временном каталоге, связка ключей —
`tests.sandbox.fake_keychain_token`, признак процесса роли снят); внешние
процессы, кроме локальных (`git` без сети, интерпретатор), получают отказ
запуска. Функции `forge.project_info`, `forge.protections`,
`forge.branch_pipeline` подменены поддельным хостингом, записывающим каждый
вызов; `forge.ci_by_pipeline` настоящий — его истинность даёт запись
`forge: gitlab`. Клон проекта — настоящий локальный репозиторий git в
`repo_context.clone_path(<проект>)` (`tests.sandbox.make_project_repo`):
файлы `.gitlab-ci.yml`/`.gitmodules` лежат в его рабочем дереве. Проба подмодуля — подмена
`gitcmd.in_repo` на вызовах с `ls-remote` (прочие вызовы идут в настоящий).

Загрузчик `targets` требует `token_slot` у плоской записи, поэтому запись
«без `token_slot`» — словарь записи без этого поля, переданный строкам
прямо (тот же словарь строки получают и из `doctor.all_checks`).

Имена проектов, базовые ветки, причины и имена подмодулей порождаются
модулем `random` при каждом запуске; зерно печатается и входит в текст
провала.
"""
import json
import os
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from orchestrator import ci, config, doctor, forge, repo_context, runner, targets
from tests.sandbox import artel_target_entry, make_project_repo

LETTERS = "abcdefghijkmnopqrstuvwxyz"
NETWORK_GIT = {"clone", "fetch", "push", "pull", "ls-remote"}
COMPONENT = "app"
CI_JOB = "tests"
GH_PATH = "/usr/local/bin/gh"
NEW_LINES = ("project-ci-file-no-paths-", "project-ci-reruns-", "project-submodules-")


# --- окружение сценария ---

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


class FakeForge:
    """Поддельный хостинг: ответы `project_info`/`protections`/`branch_pipeline`
    задаёт тест; каждый вызов пишется в `calls`."""

    def __init__(self):
        self.calls: list = []
        self.info = forge.ProjectInfo(config.MAIN_BRANCH, 40)
        self.prot = forge.Protections(["main"], ["v1"])
        self.pipeline = forge.BranchPipeline("a" * 40, forge.GREEN)

    def project_info(self, target):
        self.calls.append(("project_info", target))
        return self.info

    def protections(self, target):
        self.calls.append(("protections", target))
        return self.prot

    def branch_pipeline(self, target, branch):
        self.calls.append(("branch_pipeline", target, branch))
        return self.pipeline


@pytest.fixture
def hosting(pult, monkeypatch):
    fake = FakeForge()
    monkeypatch.setattr(forge, "project_info", fake.project_info)
    monkeypatch.setattr(forge, "protections", fake.protections)
    monkeypatch.setattr(forge, "branch_pipeline", fake.branch_pipeline)
    return fake


class LsRemote:
    """Подмена `gitcmd.in_repo` на вызовах `ls-remote`: код и stderr задаёт тест."""

    def __init__(self, real):
        self.real = real
        self.calls: list = []
        self.code = 0
        self.stderr = ""

    def in_repo(self, repo, *args, **kwargs):
        if "ls-remote" in args:
            self.calls.append((Path(repo), args))
            return subprocess.CompletedProcess(list(args), self.code, "", self.stderr)
        return self.real(repo, *args, **kwargs)


@pytest.fixture
def ls_remote(pult, monkeypatch):
    fake = LsRemote(doctor.gitcmd.in_repo)
    monkeypatch.setattr(doctor.gitcmd, "in_repo", fake.in_repo)
    return fake


def component_block() -> list:
    return ["    components:", f"      {COMPONENT}:",
            "        command: [python3, -m, pytest]",
            "        report: junit-xml",
            "        long_lived_dir: tests",
            "        long_lived_name: test_<id>_<name>.py",
            "        weakening_scope: [tests/**]",
            "        mutation_claim_scope: [tests/test_*.py]",
            "        full_suite: ci",
            f"        ci_job: {CI_JOB}"]


class Scene:
    """Запись внешнего проекта в `targets.yaml` песочницы и её клон."""

    def __init__(self, seed: int, forge_name: str = "gitlab", gate: str = "operator",
                 components: bool = False):
        self.seed = seed
        self.rng = random.Random(seed)
        self.name = word(self.rng, "p")
        self.base = word(self.rng, "base-", 5)
        self.slot = f"{self.name}-token"
        self.url = f"https://localhost/team/{self.name}"
        lines = [f"  {self.name}:", f"    forge: {forge_name}", f"    url: {self.url}",
                 f"    base: {self.base}", f"    token_slot: {self.slot}",
                 "    no_paths: []", "    project_skills: []", f"    merge_gate: {gate}"]
        if components:
            lines += component_block()
        text = "targets:\n" + artel_target_entry()
        config.TARGETS.write_text(text.rstrip("\n") + "\n" + "\n".join(lines) + "\n",
                                  encoding="utf-8")
        self.clone = repo_context.clone_path(self.name)

    def entry(self, **changes) -> dict:
        """Словарь записи с правками; значение `None` — поле убрано."""
        entry = dict(targets.target(self.name))
        for key, value in changes.items():
            if value is None:
                entry.pop(key, None)
            else:
                entry[key] = value
        return entry

    def files(self, files: dict) -> None:
        """Клон — локальный репозиторий git (`make_project_repo`) с файлами
        `files` в рабочем дереве."""
        if not (self.clone / ".git").exists():
            self.clone = make_project_repo(self.name, origin=False)
        for rel, text in files.items():
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def checks(self, entry: dict | None = None) -> dict:
        """Строки `doctor` по записи и её компонентам: имя → строка."""
        entry = self.entry() if entry is None else entry
        found = (list(doctor.project_entry_checks(self.name, entry))
                 + list(doctor.project_checks.component_checks(self.name, entry)))
        return {c.name: c for c in found}

    def note(self, checks: dict, extra: str = "") -> str:
        shown = "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in checks.values())
        return f"зерно: {self.seed}; проект {self.name}; {extra}\n{shown}"


def ci_file(*rules: str) -> str:
    return "workflow:\n  rules:\n" + "".join(rules)


FEATURE_RULE = "    - if: $CI_COMMIT_BRANCH =~ /^feature\\//\n"
TASK_RULE = "    - if: $CI_COMMIT_BRANCH =~ /^task\\//\n"


# --- AC-1, AC-2 ---

def test_ac1_base_protection_low_level_or_reason_skips(hosting, seed):
    """Защиты записи GitLab: Developer (30) и непрочитанные сведения проекта — `skip`, не `fail`.

    Сценарий: запись `forge: gitlab` со случайной базой. Поддельный
    `forge.project_info` отдаёт `access_level` 30 — строка
    `project-base-protection-<имя>` `skip`, в тексте «нужна роль
    Maintainer». Затем `project_info` отдаёт непустую случайную причину —
    строка `skip`, в тексте эта причина.

    Ловит мутацию: строка записи GitLab осталась на `gh api` (текст «gh CLI
    не найден»/«Bad credentials» без «нужна роль Maintainer»); низкий
    уровень доступа даёт `fail` или `ok`; причина `project_info` заменена
    общим текстом либо отказ сведений превращён в `fail`.
    """
    sc = Scene(seed)
    name = f"project-base-protection-{sc.name}"
    hosting.info = forge.ProjectInfo(sc.base, 30)
    checks = sc.checks()
    note = sc.note(checks, "access_level 30")
    assert checks[name].status == "skip", note
    assert "нужна роль Maintainer" in checks[name].detail, note
    reason = word(sc.rng, "причина-", 9)
    hosting.info = forge.ProjectInfo(reason=reason)
    checks = sc.checks()
    note = sc.note(checks, f"причина {reason}")
    assert checks[name].status == "skip", note
    assert reason in checks[name].detail, note


def test_ac2_base_protection_maintainer_lists_protections(hosting, seed):
    """Maintainer (40) и прочитанные защиты — `ok` с именами защищённых веток и тегов.

    Сценарий: `project_info` отдаёт `access_level` 40, `protections` —
    ветки `["main", "release/*"]` и тег `["v*"]`. Строка
    `project-base-protection-<имя>` — `ok`, в тексте `main`, `release/*`,
    `v*`, нет «нужна роль Maintainer».

    Ловит мутацию: порог сравнивается `<=` вместо `<` (40 даст `skip`
    «нужна роль Maintainer»); строка не читает `forge.protections` и
    печатает только уровень доступа (имён защит в тексте нет).
    """
    sc = Scene(seed)
    name = f"project-base-protection-{sc.name}"
    hosting.info = forge.ProjectInfo(sc.base, 40)
    hosting.prot = forge.Protections(["main", "release/*"], ["v*"])
    checks = sc.checks()
    note = sc.note(checks, "access_level 40")
    assert checks[name].status == "ok", note
    for item in ("main", "release/*", "v*"):
        assert item in checks[name].detail, note
    assert "нужна роль Maintainer" not in checks[name].detail, note


# --- AC-3, AC-4 ---

@pytest.mark.parametrize("template,status", [(None, "warn"), ("feature/{id}", "ok")],
                         ids=["шаблон по умолчанию", "feature/{id}"])
def test_ac3_workflow_rule_matches_branch_template(hosting, seed, template, status):
    """Правило `workflow:rules` сверяется с веткой по шаблону: мимо правила — `warn`, под правилом — `ok`.

    Сценарий: в клоне записи GitLab `.gitlab-ci.yml` с одним правилом
    `if: $CI_COMMIT_BRANCH =~ /^feature\\//`. При шаблоне ветки по
    умолчанию (`task/{id}-{slug}`) строка `project-ci-pull-request-<имя>`
    — `warn`, в тексте `правило workflow №1 (if: $CI_COMMIT_BRANCH =~
    /^feature\\//)`; при `branch_template: feature/{id}` — `ok`, в тексте
    `правило workflow №1`.

    Ловит мутацию: строка GitLab ищет `pull_request` в `.github/workflows`
    (оба случая — `warn` с текстом о GitHub); шаблон берётся всегда по
    умолчанию, без `branch_template` записи (второй случай — `warn`);
    регулярное выражение сверяется без якоря или поиском подстроки;
    правило в тексте не названо по номеру и выражению.
    """
    sc = Scene(seed)
    sc.files({".gitlab-ci.yml": ci_file(FEATURE_RULE)})
    entry = sc.entry() if template is None else sc.entry(branch_template=template)
    checks = sc.checks(entry)
    line = checks[f"project-ci-pull-request-{sc.name}"]
    note = sc.note(checks, f"шаблон {template}")
    assert line.status == status, note
    if status == "warn":
        assert "правило workflow №1 (if: $CI_COMMIT_BRANCH =~ /^feature\\//)" in line.detail, note
    else:
        assert "правило workflow №1" in line.detail, note


def test_ac4_first_matching_rule_never_decides(hosting, seed):
    """Первое сработавшее правило с `when: never` решает: `warn` с ним, второе правило не упомянуто.

    Сценарий: правила 1) `if: $CI_COMMIT_BRANCH =~ /^task\\//`,
    `when: never`; 2) `if: $CI_COMMIT_BRANCH`. Шаблон по умолчанию: строка
    `project-ci-pull-request-<имя>` — `warn`, в тексте `правило workflow
    №1 (if: $CI_COMMIT_BRANCH =~ /^task\\//)`, нет `правило workflow №2`.

    Ловит мутацию: решает последнее сработавшее правило, а не первое (№2
    без `when` — `ok`); `when: never` не читается (№1 — `ok`); в тексте
    перечислены все правила, а не сработавшее.
    """
    sc = Scene(seed)
    sc.files({".gitlab-ci.yml": ci_file(TASK_RULE, "      when: never\n",
                                        "    - if: $CI_COMMIT_BRANCH\n")})
    checks = sc.checks()
    line = checks[f"project-ci-pull-request-{sc.name}"]
    note = sc.note(checks)
    assert line.status == "warn", note
    assert "правило workflow №1 (if: $CI_COMMIT_BRANCH =~ /^task\\//)" in line.detail, note
    assert "правило workflow №2" not in line.detail, note


def test_ac4_no_workflow_key_is_ok(hosting, seed):
    """Файл CI без `workflow` и без `include` — `ok`: GitLab создаёт конвейер любой ветки.

    Сценарий: `.gitlab-ci.yml` клона — одно задание `tests` со `script`.
    Строка `project-ci-pull-request-<имя>` записи GitLab — `ok`.

    Ловит мутацию: отсутствие `workflow:rules` принято за «ни одно правило
    не сработало» (`warn`); строка GitLab ищет триггер GitHub (`warn`).
    """
    sc = Scene(seed)
    sc.files({".gitlab-ci.yml": "tests:\n  script:\n    - pytest\n"})
    checks = sc.checks()
    assert checks[f"project-ci-pull-request-{sc.name}"].status == "ok", sc.note(checks)


def test_ac4_unparsed_form_warns_with_line(hosting, seed):
    """Форма вне разборщика (якорь `&x` в строке 3) — `warn` «.gitlab-ci.yml не разобран:» с номером строки 3.

    Сценарий: `.gitlab-ci.yml` клона, в третьей строке которого —
    скрытое задание с якорем `.tpl: &x`. Строка
    `project-ci-pull-request-<имя>` — `warn`, в тексте `.gitlab-ci.yml не
    разобран:`, а после него — число 3.

    Ловит мутацию: разборщик молча пропускает нераспознанную строку и даёт
    `ok` (ключа `workflow` нет); место в тексте не указано или указан
    номер строки, отсчитанный с нуля (2).
    """
    sc = Scene(seed)
    sc.files({".gitlab-ci.yml": "default:\n  retry: 0\n.tpl: &x\n  script:\n    - pytest\n"})
    checks = sc.checks()
    line = checks[f"project-ci-pull-request-{sc.name}"]
    note = sc.note(checks)
    marker = ".gitlab-ci.yml не разобран:"
    assert line.status == "warn", note
    assert marker in line.detail, note
    assert re.search(r"(?<!\d)3(?!\d)", line.detail.split(marker, 1)[1]), note


# --- AC-5 ---

@pytest.mark.parametrize("no_paths,status", [
    ([], "fail"),
    (["README.md"], "fail"),
    ([".gitlab-ci.yml"], "ok"),
    (["README.md", ".gitlab-ci.yml"], "ok"),
], ids=["пусто", "без файла CI", "файл CI", "файл CI среди прочих"])
def test_ac5_ci_file_covered_by_no_paths(hosting, seed, no_paths, status):
    """Строка `project-ci-file-no-paths-<имя>`: файл CI в `no_paths` — `ok`, иначе `fail`.

    Сценарий: запись GitLab с `merge_gate: target-human` и компонентом
    `full_suite: ci`; в клоне есть `.gitlab-ci.yml` и `README.md`.
    `no_paths` записи — пустой, без файла CI, с файлом CI, с файлом CI
    среди прочих путей.

    Ловит мутацию: строки нет у записи с `target-human`; проверка смотрит
    на наличие файла в клоне, а не на `no_paths` (все случаи — `ok`);
    отсутствие файла CI в `no_paths` даёт `warn` вместо `fail`; сверяется
    только первый элемент `no_paths`.
    """
    sc = Scene(seed, gate="target-human", components=True)
    sc.files({".gitlab-ci.yml": "tests:\n  script:\n    - pytest\n", "README.md": "x\n"})
    checks = sc.checks(sc.entry(no_paths=no_paths))
    name = f"project-ci-file-no-paths-{sc.name}"
    note = sc.note(checks, f"no_paths {no_paths}")
    assert name in checks, note
    assert checks[name].status == status, note


# --- AC-6 ---

RERUN_TABLE = [
    ("1", "tests:\n  script:\n    - pytest\n  retry: 2\n", "warn", "retry"),
    ("2", "default:\n  retry: 1\ntests:\n  script:\n    - pytest\n", "warn", "retry"),
    ("3", ".base:\n  retry: 2\ntests:\n  extends: .base\n  script:\n    - pytest\n",
     "warn", "retry"),
    ("4", "tests:\n  script:\n    - pytest --reruns 2\n", "warn", "--reruns"),
    ("5-задание", "tests:\n  variables:\n    PYTEST_ADDOPTS: \"--reruns 3\"\n"
                  "  script:\n    - pytest\n", "warn", "--reruns"),
    ("5-верхний", "variables:\n  PYTEST_ADDOPTS: \"-p rerunfailures\"\n"
                  "tests:\n  script:\n    - pytest\n", "warn", "rerunfailures"),
    ("6", "tests:\n  script:\n    - pytest -p rerunfailures\n", "warn", "rerunfailures"),
    ("7", "tests:\n  before_script:\n    - pip install pytest-rerunfailures\n"
          "  script:\n    - pytest\n", "warn", "rerunfailures"),
    ("retry-0", "tests:\n  script:\n    - pytest\n  retry: 0\n", "ok", None),
    ("retry-чужого", "lint:\n  script:\n    - ruff\n  retry: 2\n"
                     "tests:\n  script:\n    - pytest\n", "ok", None),
]


@pytest.mark.parametrize("form,text,status,finding", RERUN_TABLE,
                         ids=[row[0] for row in RERUN_TABLE])
def test_ac6_reruns_in_ci_job(hosting, seed, form, text, status, finding):
    """Строка `project-ci-reruns-<имя>-<компонент>` по таблице AC-6: каждая форма перезапуска — `warn` со ссылкой на инвариант 41.

    Сценарий: запись GitLab с `target-human` и компонентом `full_suite:
    ci`, `ci_job: tests`; `.gitlab-ci.yml` клона в блочной форме YAML —
    строка таблицы AC-6. Формы 1–7 — `warn`, в тексте ссылка на инвариант
    41 и сама находка (`retry`, `--reruns`, `rerunfailures`); `retry: 0`
    задания и `retry` у чужого задания — `ok`.

    Ловит мутацию: не читается наследование из `default:` (форма 2) или по
    `extends:` (форма 3); переменные верхнего уровня не просматриваются
    (5-верхний); `before_script` не просматривается (форма 7); `retry: 0`
    считается перезапуском; `retry` любого задания файла засчитан
    `ci_job` (строка «retry-чужого» — `warn`); `warn` без ссылки на
    инвариант 41.
    """
    sc = Scene(seed, gate="target-human", components=True)
    sc.files({".gitlab-ci.yml": text})
    checks = sc.checks()
    name = f"project-ci-reruns-{sc.name}-{COMPONENT}"
    note = sc.note(checks, f"форма {form}\n{text}")
    assert name in checks, note
    assert checks[name].status == status, note
    if status == "warn":
        assert re.search(r"инвариант\w*\s+(?:№\s*)?41\b", checks[name].detail), note
        assert finding in checks[name].detail, note


# --- AC-7 ---

def submodule_scene(seed: int, gate: str = "target-human") -> tuple:
    sc = Scene(seed, gate=gate, components=True)
    sub = word(sc.rng, "lib", 5)
    address = f"https://localhost/team/{sub}.git"
    sc.files({".gitmodules": f'[submodule "libs/{sub}"]\n\tpath = libs/{sub}\n'
                             f"\turl = {address}\n",
              ".gitlab-ci.yml": "tests:\n  script:\n    - pytest\n"})
    return sc, address


def test_ac7_submodule_probe_failure_and_success(hosting, ls_remote, seed):
    """Подмодуль на том же хосте: `ls-remote` с кодом 128 — `fail` с адресом и stderr, код 0 — `ok`.

    Сценарий: запись GitLab с `target-human` и `token_slot`; в
    `.gitmodules` клона — подмодуль `https://localhost/team/<имя>.git`
    (хост записи). Подменённый `gitcmd.in_repo` на `ls-remote` этого
    адреса отвечает кодом 128 и stderr `fatal: Authentication failed` —
    строка `project-submodules-<имя>` `fail`, в тексте адрес и
    `Authentication failed`; затем кодом 0 — `ok`. Проба шла по адресу
    подмодуля.

    Ловит мутацию: строки нет; проба идёт не через `gitcmd.in_repo` (без
    токена слота — подмена не видит вызова, код 0 даёт не `ok`); отказ
    пробы даёт `warn`; stderr git не попадает в текст; подмодуль хоста
    записи сочтён чужим и не проверен.
    """
    sc, address = submodule_scene(seed)
    name = f"project-submodules-{sc.name}"
    ls_remote.code, ls_remote.stderr = 128, "fatal: Authentication failed"
    checks = sc.checks()
    note = sc.note(checks, f"адрес {address}; пробы {ls_remote.calls}")
    assert name in checks, note
    assert checks[name].status == "fail", note
    assert address in checks[name].detail, note
    assert "Authentication failed" in checks[name].detail, note
    assert any(address in args for _repo, args in ls_remote.calls), note
    ls_remote.code, ls_remote.stderr = 0, ""
    checks = sc.checks()
    assert checks[name].status == "ok", sc.note(checks, f"код 0; пробы {ls_remote.calls}")


def test_ac7_submodules_in_role_skip_without_probe(hosting, ls_remote, monkeypatch, seed):
    """В процессе роли строка подмодулей — `skip`, проба `ls-remote` не запускается.

    Сценарий: тот же клон с подмодулем; признак процесса роли выставлен
    (`runner.in_role_environment` истинно). Строка
    `project-submodules-<имя>` — `skip`, подменённый `gitcmd.in_repo` не
    видел ни одного `ls-remote`.

    Ловит мутацию: строка не проверяет признак роли и пробует подмодуль
    (вызов `ls-remote` есть, исход — `ok`/`fail`).
    """
    sc, _address = submodule_scene(seed)
    monkeypatch.setattr(runner, "in_role_environment", lambda env=None: True)
    checks = sc.checks()
    name = f"project-submodules-{sc.name}"
    note = sc.note(checks, f"пробы {ls_remote.calls}")
    assert name in checks, note
    assert checks[name].status == "skip", note
    assert ls_remote.calls == [], note


# --- AC-8 ---

@pytest.mark.parametrize("gate,present", [("operator", False), ("target-human", True)])
def test_ac8_new_lines_only_for_target_human(hosting, ls_remote, seed, gate, present):
    """Новые строки (`no_paths` файла CI, перезапуски, подмодули) есть только у записи с `target-human`.

    Сценарий: запись GitLab с компонентом `full_suite: ci` и подмодулем в
    `.gitmodules`; `merge_gate` — `operator` либо `target-human`. При
    `operator` строк `project-ci-file-no-paths-<имя>`,
    `project-ci-reruns-<имя>-*`, `project-submodules-<имя>` нет; при
    `target-human` есть все три.

    Ловит мутацию: новые строки выбираются по `forge.ci_by_pipeline`
    (запись GitLab с `operator` их получит); выбор перевёрнут; одна из
    трёх строк не добавлена.
    """
    sc, _address = submodule_scene(seed, gate=gate)
    checks = sc.checks()
    note = sc.note(checks, f"merge_gate {gate}")
    found = [prefix for prefix in NEW_LINES
             if any(n.startswith(f"{prefix}{sc.name}") for n in checks)]
    assert found == (list(NEW_LINES) if present else []), note


# --- AC-9, AC-10 ---

@pytest.fixture
def gh_spy(pult, monkeypatch):
    """`gh` «установлен» (`shutil.which("gh")` — путь); каждый вызов `gh`
    процессом и через `ci.gh` записывается и получает отказ 401."""
    calls: list = []
    inner = subprocess.run
    real_which = shutil.which

    def run(argv, *args, **kwargs):
        if (isinstance(argv, (list, tuple)) and argv
                and Path(os.fsdecode(argv[0])).name == "gh"):
            calls.append(["subprocess.run", *argv])
            return subprocess.CompletedProcess(argv, 1, "", "gh: Bad credentials (HTTP 401)")
        return inner(argv, *args, **kwargs)

    def gh(*args, **kwargs):
        calls.append(["ci.gh", *args])
        return subprocess.CompletedProcess(["gh", *args], 1, "", "gh: Bad credentials (HTTP 401)")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(ci, "gh", gh)
    monkeypatch.setattr(shutil, "which",
                        lambda cmd, *a, **k: GH_PATH if cmd == "gh" else real_which(cmd, *a, **k))
    return calls


@pytest.mark.parametrize("gate", ["operator", "target-human"])
def test_ac9_gitlab_lines_never_call_gh(hosting, ls_remote, gh_spy, seed, gate):
    """За прогон всех строк `project-*-<имя>` записи GitLab шпион `gh` не видит ни одного вызова, даже когда `gh` установлен.

    Сценарий: запись GitLab (с `operator` и с `target-human`) на
    подменённом `forge`, клон с файлом CI и подмодулем, слот токена
    заполнен; `shutil.which("gh")` возвращает путь. Шпион
    `subprocess.run` с `gh` первым аргументом и `ci.gh` после прогона
    строк записи и её компонентов пуст.

    Ловит мутацию: строка защит, прав токена на CI или токена записи
    GitLab выбрана по `hasattr(..., "pipeline_status")` либо осталась на
    пути GitHub (`gh api`, `gh auth token`) — шпион запишет вызов.
    """
    sc, _address = submodule_scene(seed, gate=gate)
    sc.files({".gitlab-ci.yml": ci_file(TASK_RULE)})
    checks = sc.checks()
    note = sc.note(checks, f"merge_gate {gate}; вызовы gh {gh_spy}")
    assert any(n.startswith("project-") for n in checks), note
    assert gh_spy == [], note


def test_ac10_gitlab_data_gives_ok_without_github_words(hosting, gh_spy, seed):
    """Данные GitLab — четыре строки `ok`, ни одна не несёт «gh:», «Bad credentials», «Actions», «pull_request».

    Сценарий: запись GitLab, `access_level` 40, защиты прочитаны,
    `branch_pipeline` базы — `green`, в `.gitlab-ci.yml` правило
    `if: $CI_COMMIT_BRANCH =~ /^task\\//` (ветка по шаблону по умолчанию
    под ним), слот токена заполнен. Строки `project-base-protection`,
    `project-ci-token`, `project-ci-pull-request`, `project-token` — `ok`,
    в их текстах нет слов пути GitHub.

    Ловит мутацию: любая из четырёх строк осталась на пути GitHub (`skip`
    «gh: Bad credentials», `fail` «запуски Actions недоступны», `warn` о
    триггере `pull_request`, сверка с `gh auth token`).
    """
    sc = Scene(seed)
    sc.files({".gitlab-ci.yml": ci_file(TASK_RULE)})
    hosting.info = forge.ProjectInfo(sc.base, 40)
    hosting.prot = forge.Protections([sc.base], ["v*"])
    hosting.pipeline = forge.BranchPipeline("b" * 40, forge.GREEN)
    checks = sc.checks()
    note = sc.note(checks)
    for kind in ("base-protection", "ci-token", "ci-pull-request", "token"):
        line = checks[f"project-{kind}-{sc.name}"]
        assert line.status == "ok", f"{kind}; {note}"
        for bad in ("gh:", "Bad credentials", "Actions", "pull_request"):
            assert bad not in line.detail, f"{kind}: {bad}; {note}"


# --- AC-11 ---

def ci_token_cases():
    return [
        ("отказ-403", lambda: forge.BranchPipeline(reason="отказ", http_status=403), "fail", None),
        ("отказ-503", lambda: forge.BranchPipeline(reason="отказ", http_status=503), "skip", None),
        ("отказ-None", lambda: forge.BranchPipeline(reason="отказ", http_status=None), "skip", None),
        ("none", lambda: forge.BranchPipeline(verdict="none"), "ok", "none"),
        ("red", lambda: forge.BranchPipeline(verdict="red"), "ok", "red"),
    ]


@pytest.mark.parametrize("case,make,status,word_in_text", ci_token_cases(),
                         ids=[c[0] for c in ci_token_cases()])
def test_ac11_ci_token_by_verdict_and_http_status(hosting, seed, case, make, status, word_in_text):
    """Строка `project-ci-token-<имя>` записи GitLab различает отказ правами и временный отказ по `http_status`.

    Сценарий: подменённый `forge.branch_pipeline` отдаёт
    `BranchPipeline(reason="отказ", http_status=403)` — строка `fail` с
    текстом «статус CI проекта пульт не увидит»; тот же `reason` с
    `http_status` 503 и `None` — `skip`; `verdict` `none` и `red` — `ok`,
    значение итога в тексте.

    Ловит мутацию: различение по тексту `reason` (у всех трёх отказов он
    одинаков — исходы совпадут); всякий отказ — `fail` (503/None не
    `skip`); итог `red` принят за отказ (`fail`); строка осталась на
    Actions (`gh`).
    """
    sc = Scene(seed)
    hosting.pipeline = make()
    checks = sc.checks()
    line = checks[f"project-ci-token-{sc.name}"]
    note = sc.note(checks, case)
    assert line.status == status, note
    if status == "fail":
        assert "статус CI проекта пульт не увидит" in line.detail, note
    if word_in_text:
        assert re.search(rf"\b{word_in_text}\b", line.detail), note


# --- AC-13 ---

@pytest.mark.parametrize("how,status", [("нет поля", "warn"), ("слот пуст", "fail"),
                                        ("слот заполнен", "ok")])
def test_ac13_project_token_gitlab(hosting, gh_spy, monkeypatch, seed, how, status):
    """Строка `project-token-<имя>` записи GitLab: без `token_slot` — `warn`, пустой слот — `fail`, заполненный — `ok` с оговоркой о несделанной сверке с `gh`.

    Сценарий: запись GitLab; `token_slot` убран из словаря записи, слот в
    связке ключей пуст либо заполнен. Статусы — `warn`, `fail`, `ok`; у
    `ok` текст называет, что сверка с токеном `gh` Оператора не делалась
    (а не «отличен от токена gh Оператора»).

    `gh` установлен (шпион `gh`), и ни одного вызова `gh auth token` нет.

    Ловит мутацию: заполненный слот сверяется с `gh auth token` (текст
    «отличен от токена gh Оператора», шпион видит `gh auth token`); пустой
    слот — `warn`; текст `ok` молчит о несделанной сверке.
    """
    sc = Scene(seed)
    entry = sc.entry(token_slot=None) if how == "нет поля" else sc.entry()
    if how == "слот пуст":
        monkeypatch.setattr(doctor.keychain, "token", lambda slot: "")
    checks = sc.checks(entry)
    line = checks[f"project-token-{sc.name}"]
    note = sc.note(checks, f"{how}; вызовы gh {gh_spy}")
    assert line.status == status, note
    if status == "ok":
        assert "gh" in line.detail and "сверк" in line.detail.lower(), note
        assert re.search(r"\bне\b", line.detail), note
        assert "отличен от токена gh" not in line.detail, note
    assert not [c for c in gh_spy if "auth" in c[1:3]], note


def test_ac13_no_token_slot_skips_without_hosting(hosting, ls_remote, seed):
    """Запись GitLab с `target-human` без `token_slot`: строки хостинга — `skip` «нет token_slot» без единого обращения.

    Сценарий: клон с подмодулем на хосте записи; словарь записи без
    `token_slot`. Строки `project-base-protection-<имя>`,
    `project-ci-token-<имя>`, `project-submodules-<имя>` — `skip`, в
    тексте `нет token_slot`; поддельный `forge` не видел вызовов
    `project_info`/`protections`/`branch_pipeline`, подменённый
    `gitcmd.in_repo` — ни одного `ls-remote`.

    Ловит мутацию: запрос уходит с авторизацией Оператора (вызов `forge`
    или пробы есть); отсутствие слота даёт `warn`/`fail`; строка
    подмодулей без слота пробует адреса.
    """
    sc, _address = submodule_scene(seed)
    checks = sc.checks(sc.entry(token_slot=None))
    note = sc.note(checks, f"forge {hosting.calls}; пробы {ls_remote.calls}")
    for kind in ("base-protection", "ci-token", "submodules"):
        line = checks[f"project-{kind}-{sc.name}"]
        assert line.status == "skip", f"{kind}; {note}"
        assert "нет token_slot" in line.detail, f"{kind}; {note}"
    assert hosting.calls == [], note
    assert ls_remote.calls == [], note


# --- AC-15 ---

PROTECTION = {"required_pull_request_reviews": {"required_approving_review_count": 1},
              "enforce_admins": {"enabled": True},
              "required_status_checks": {"contexts": ["ci"]}}


@pytest.fixture
def github_world(pult, monkeypatch):
    """`gh` установлен и отвечает: защита ветки, токен Оператора, пустые
    check-runs и запуски Actions; git клона — без сети (origin = `url`)."""
    state = {"url": ""}
    inner = subprocess.run
    real_which = shutil.which

    def gh_reply(args):
        if args[:2] == ["auth", "token"]:
            return 0, "operator-token\n"
        if args[:1] == ["api"] and args[1].endswith("/protection"):
            return 0, json.dumps(PROTECTION)
        if args[:1] == ["api"] and "/check-runs" in args[1]:
            return 0, json.dumps({"check_runs": []})
        if args[:1] == ["api"] and "/actions/runs" in args[1]:
            return 0, json.dumps({"workflow_runs": []})
        return 1, ""

    def run(argv, *args, **kwargs):
        if (isinstance(argv, (list, tuple)) and argv
                and Path(os.fsdecode(argv[0])).name == "gh"):
            code, out = gh_reply([os.fsdecode(a) for a in argv[1:]])
            return subprocess.CompletedProcess(argv, code, out, "")
        return inner(argv, *args, **kwargs)

    def in_repo(repo, *args, **kwargs):
        if args[:2] == ("remote", "get-url"):
            return subprocess.CompletedProcess(list(args), 0, state["url"] + "\n", "")
        return subprocess.CompletedProcess(list(args), 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(doctor.gitcmd, "in_repo", in_repo)
    monkeypatch.setattr(shutil, "which",
                        lambda cmd, *a, **k: GH_PATH if cmd == "gh" else real_which(cmd, *a, **k))
    return state


ARTEL_NAMES = ("clone", "artifacts-push", "ci-pull-request", "base-protection",
               "token", "ci-token", "no-paths", "skills")
ARTEL_TEXT = "неприменимо: запись артели — проверка внешнего проекта"


@pytest.mark.parametrize("with_slot", [True, False], ids=["token_slot", "без token_slot"])
def test_ac15_github_operator_and_artel_lines_unchanged(github_world, seed, with_slot):
    """Строки записи `github` + `operator` и артели — прежние имена, статусы и тексты.

    Сценарий: запись `forge: github`, `merge_gate: operator`, клон с
    `.github/workflows/ci.yml` (`on: [pull_request]`); `gh` установлен и
    отвечает защитой ветки, токеном Оператора, пустыми check-runs и
    запусками Actions. Строки записи (со слотом и без `token_slot`) и её
    компонентов — ровно прежний список (имя, статус, текст); у артели —
    восемь строк `skip` «неприменимо…» и никаких новых строк.

    Ловит мутацию: выбор пути GitLab сделан по `hasattr(...,
    "pipeline_status")` (у `_GitHub` он есть — строки GitHub уйдут в
    `forge`); новые строки (`no_paths` файла CI, перезапуски, подмодули)
    добавлены всем записям; текст строки токена GitHub заменён текстом
    GitLab о несделанной сверке.
    """
    sc = Scene(seed, forge_name="github")
    github_world["url"] = sc.url
    sc.files({".github/workflows/ci.yml": "on: [pull_request]\njobs: {}\n"})
    entry = sc.entry() if with_slot else sc.entry(token_slot=None)
    got = [(c.name, c.status, c.detail) for c in sc.checks(entry).values()]
    n = sc.name
    token = ((f"project-token-{n}", "ok",
              f"токен проекта есть в слоте {sc.slot}, отличен от токена gh Оператора")
             if with_slot else
             (f"project-token-{n}", "warn",
              "нет токена проекта: поле token_slot записи не задано — операции "
              "хостинга идут с авторизацией Оператора"))
    expected = [
        (f"project-clone-{n}", "warn",
         f"клон ещё не обновлялся пультом ({sc.clone}); fetch прошёл"),
        (f"project-artifacts-push-{n}", "ok", "пробный push --dry-run в refs/artifacts/* прошёл"),
        (f"project-ci-pull-request-{n}", "ok", "триггер pull_request: ci.yml"),
        (f"project-base-protection-{n}", "ok",
         f"защита базовой ветки {sc.base}: одобрений требуется: 1, enforce_admins: "
         f"True, обязательные проверки: ci"),
        token,
        (f"project-ci-token-{n}", "ok",
         f"токен проекта читает check-runs вершины {sc.base} и запуски Actions"),
        (f"project-no-paths-{n}", "ok", "все пути no_paths есть в дереве клона"),
        (f"project-skills-{n}", "ok", "project_skills записи годны"),
    ]
    note = f"зерно: {seed}; со слотом {with_slot}\n" + "\n".join(map(str, got))
    assert got == expected, note
    artel = config.DEFAULT_TARGET
    artel_entry = targets.target(artel)
    got = [(c.name, c.status, c.detail) for c in
           list(doctor.project_entry_checks(artel, artel_entry))
           + list(doctor.project_checks.component_checks(artel, artel_entry))]
    assert got == [(f"project-{k}-{artel}", "skip", ARTEL_TEXT) for k in ARTEL_NAMES], \
        f"зерно: {seed}\n" + "\n".join(map(str, got))
