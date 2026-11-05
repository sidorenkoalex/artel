"""Проверки записи проекта `github` + `target-human`: отказы полей доставки те же, что у GitLab, источник полного набора `full_suite: ci` отказывает, `policy.ci_required_jobs` — только у хостинга, реализация которого его читает (признак `READS_CI_REQUIRED_JOBS` реестра `forge.IMPLEMENTATIONS`); закрытый список вызовов `gh` отказывает форме `pr create` с лишним хвостом.

Группа: долгоживущий
Красен до реализации: запись `github` + `target-human` с `policy.ci_required_jobs` загружается без отказа, а у реализации GitLab признака `READS_CI_REQUIRED_JOBS` нет — подстановка реализации без признака не меняет исход; методы AC-3 и AC-11 зелены с рождения — они закрепляют прежнее поведение `_check_delivery`, правила `full_suite` и `forge.github_call`.

Свойства — разбор записи (`targets.target`) и ответ `forge.github_call`;
связки «команда — FSM — git» здесь нет. Песочница `tmp_root` (пути
`config` во временном каталоге): записи вымышленных проектов — в
локальном слое (`targets.local_path()`) или в `targets.yaml` песочницы.
Реестр `forge.IMPLEMENTATIONS` подменяется только на время метода
(`monkeypatch.setitem`). `ci.gh` — шпион: настоящего `gh` тест не зовёт.

Имена проектов порождаются модулем `random` при каждом запуске; зерно
печатается и входит в текст провала.
"""
import random
import subprocess
import types

import pytest

from orchestrator import ci, config, forge, gitlab_adapter, targets
from tests.sandbox import artel_target_entry

LETTERS = "abcdefhkmnpqrsvwxyz"

LOCAL_ENTRY = """  {name}:
    description:
      base: {base}
      test_profile:
        command: [python3, -m, pytest]
        long_lived_dir: tests
        long_lived_name: test_<id>_<name>.py
    policy:
      no_paths: []
      project_skills: []
      merge_gate: {gate}
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
{policy}    machine:
      forge: {forge}
      url: "https://localhost/team/{name}"
      token_slot: {name}-token
{machine}"""

# (поле, раздел, значение YAML с отказом `_check_delivery`).
DELIVERY_REFUSALS = [
    ("branch_template", "policy", '"x{bad}"'),
    ("ref_pattern", "policy", '"("'),
    ("squash_before_mr", "policy", '"yes"'),
    ("freshness", "policy", "sideways"),
    ("commit_template", "policy", '"{bad}"'),
    ("commit_author", "machine", "\n        name: avtor"),
    ("co_author", "policy", '"x"'),
    ("push_options", "policy", "[ci.skip]"),
    ("push_options_forbidden", "policy", "5"),
    ("ci_required_jobs", "policy", "5"),
    ("mr_assignee", "policy", '""'),
    ("draft_mr", "policy", '"maybe"'),
    ("max_in_flight", "policy", "0"),
    ("max_awaiting", "policy", "-1"),
    ("awaiting_holds_zones", "policy", '"x"'),
    ("mr_sync_interval_min", "policy", "0"),
]


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


def project_name(rng: random.Random) -> str:
    return "q" + "".join(rng.choice(LETTERS) for _ in range(8))


def write_local(name: str, forge_name: str, gate: str, policy: dict | None = None,
                machine: dict | None = None) -> None:
    """Единственная запись локального слоя; значения полей — текст YAML."""
    def lines(fields: dict | None) -> str:
        return "".join(f"      {key}: {value}\n" for key, value in (fields or {}).items())

    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text("targets:\n" + LOCAL_ENTRY.format(
        name=name, base=config.MAIN_BRANCH, gate=gate, forge=forge_name,
        policy=lines(policy), machine=lines(machine)), encoding="utf-8")


def load_error(name: str) -> str | None:
    """Текст отказа загрузки записи `name`; `None` — запись загрузилась."""
    try:
        targets.target(name)
    except targets.TargetsError as exc:
        return str(exc)
    return None


# ------------------------------------------------------------------- AC-3


@pytest.mark.parametrize("field,section,value", DELIVERY_REFUSALS,
                         ids=[row[0] for row in DELIVERY_REFUSALS])
def test_ac3_delivery_refusal_same_text_for_github_and_gitlab(tmp_root, seed,
                                                              field, section, value):
    """Отказ поля доставки у записи `github` + `target-human` — тот же текст, что у `gitlab` + `target-human`.

    Сценарий: запись локального слоя со случайным именем и негодным
    значением поля по параметру (16 полей `_check_delivery`); та же запись
    сначала с `forge: github`, затем с `forge: gitlab`. Обе отказывают при
    загрузке, текст отказа называет поле в его разделе, и тексты двух
    хостингов равны.

    Ловит мутацию: для GitHub введено своё исключение в проверке поля
    (отказ пропущен или с иным текстом, например отказ
    `ci_required_jobs` по хостингу поставлен раньше проверки формы и
    подменил текст «не список строк»).
    """
    name = project_name(random.Random(seed))
    texts = {}
    for forge_name in ("github", "gitlab"):
        if section == "machine":
            write_local(name, forge_name, "target-human", machine={field: value})
        else:
            write_local(name, forge_name, "target-human", policy={field: value})
        texts[forge_name] = load_error(name)
    note = f"зерно: {seed}; {name}; {field}: {texts}"
    assert texts["gitlab"] is not None and texts["github"] is not None, note
    assert f"'{section}.{field}'" in texts["github"], note
    assert texts["github"] == texts["gitlab"], note


def flat_with_ci_component(name: str, forge_name: str) -> None:
    lines = [f"  {name}:", f"    forge: {forge_name}",
             f"    url: https://localhost/team/{name}",
             f"    base: {config.MAIN_BRANCH}", f"    token_slot: {name}-token",
             "    no_paths: []", "    project_skills: []",
             "    merge_gate: target-human",
             "    components:", "      app:",
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


def test_ac3_github_people_full_suite_ci_refused(tmp_root, seed):
    """Запись `github` + `target-human` с компонентом `full_suite: ci` отказывает при загрузке, отказ называет `full_suite`.

    Сценарий: в `targets.yaml` песочницы — запись `github` +
    `target-human` со случайным именем и компонентом `full_suite: ci`
    (`ci_job`, `report` заданы). `targets.target` поднимает `TargetsError`,
    текст несёт `full_suite`.

    Ловит мутацию: правило источника полного набора пропускает GitHub
    проекта людей (исключение по паре или по `merge_gate`) — запись
    загружается.
    """
    name = project_name(random.Random(seed))
    flat_with_ci_component(name, "github")
    text = load_error(name)
    assert text is not None and "full_suite" in text, f"зерно: {seed}; {name}: {text}"


# ------------------------------------------------------------------- AC-8


def test_ac8_github_people_ci_required_jobs_refused(tmp_root, seed):
    """Запись `github` + `target-human` с `policy.ci_required_jobs` отказывает при загрузке; отказ называет поле и хостинг `github`.

    Сценарий: запись локального слоя со случайным именем и непустым
    списком `ci_required_jobs` из случайных имён заданий. `targets.target`
    поднимает `TargetsError`, текст несёт `ci_required_jobs` и `github`.

    Ловит мутацию: отказ не введён (запись грузится, поле молча не
    читается `_GitHub`); отказ без имени хостинга или поля.
    """
    rng = random.Random(seed)
    name = project_name(rng)
    jobs = "[" + ", ".join(f"job{rng.randrange(100)}" for _ in range(rng.randint(1, 3))) + "]"
    write_local(name, "github", "target-human", policy={"ci_required_jobs": jobs})
    text = load_error(name)
    note = f"зерно: {seed}; {name}; {jobs}: {text}"
    assert text is not None, note
    assert "ci_required_jobs" in text and "github" in text, note


@pytest.mark.parametrize("forge_name,gate", [("gitlab", "target-human"),
                                             ("github", "operator")],
                         ids=["gitlab-target-human", "github-operator"])
def test_ac8_gitlab_and_operator_entries_with_jobs_load(tmp_root, seed, forge_name, gate):
    """Запись `gitlab` + `target-human` и запись `github` + `operator` с `policy.ci_required_jobs` загружаются.

    Сценарий: та же запись с непустым `ci_required_jobs`, но `forge:
    gitlab` (людей проекта) либо `merge_gate: operator` (GitHub).
    `targets.target` отдаёт запись без исключения, список полей — тот же.

    Ловит мутацию: отказ поставлен по полю для любого хостинга или любой
    записи (без признака проекта людей) — запись GitLab или `operator`
    отказывает.
    """
    name = project_name(random.Random(seed))
    write_local(name, forge_name, gate, policy={"ci_required_jobs": "[tests, lint]"})
    text = load_error(name)
    assert text is None, f"зерно: {seed}; {name}: {text}"
    assert targets.target(name).get("ci_required_jobs") == ["tests", "lint"], \
        f"зерно: {seed}; {name}"


def test_ac8_registry_attribute_decides_not_literal(tmp_root, seed, monkeypatch):
    """Решение — признак `READS_CI_REQUIRED_JOBS` реализации в `forge.IMPLEMENTATIONS`, не литерал хостинга и не `CI_BY_PIPELINE`.

    Сценарий: (1) под ключом `github` реестра — подкласс прежней
    реализации GitHub с `READS_CI_REQUIRED_JOBS = True` (`CI_BY_PIPELINE`
    прежний, ложный): запись `github` + `target-human` с непустым
    `ci_required_jobs` загружается. (2) Под ключом `gitlab` — пространство
    имён с атрибутами модуля `gitlab_adapter`, но `READS_CI_REQUIRED_JOBS =
    False` и `CI_BY_PIPELINE = True`: запись `gitlab` + `target-human` с
    тем же полем отказывает, текст несёт `ci_required_jobs` и `gitlab`.

    Ловит мутацию: отказ решается сравнением `forge` с `"github"` (подмена
    (1) не снимает отказ) или по `CI_BY_PIPELINE` (подмена (2) с
    истинным `CI_BY_PIPELINE` не даёт отказа).
    """
    rng = random.Random(seed)
    name = project_name(rng)
    github_impl = forge.IMPLEMENTATIONS["github"]
    reading = type("ReadingGitHub", (github_impl,), {"READS_CI_REQUIRED_JOBS": True})
    monkeypatch.setitem(forge.IMPLEMENTATIONS, "github", reading)
    assert reading.CI_BY_PIPELINE is False
    write_local(name, "github", "target-human", policy={"ci_required_jobs": "[tests]"})
    text = load_error(name)
    assert text is None, f"зерно: {seed}; {name}: подкласс с признаком: {text}"

    fields = {k: v for k, v in vars(gitlab_adapter).items() if not k.startswith("__")}
    fields.update(READS_CI_REQUIRED_JOBS=False, CI_BY_PIPELINE=True)
    monkeypatch.setitem(forge.IMPLEMENTATIONS, "gitlab", types.SimpleNamespace(**fields))
    write_local(name, "gitlab", "target-human", policy={"ci_required_jobs": "[tests]"})
    text = load_error(name)
    note = f"зерно: {seed}; {name}: gitlab без признака: {text}"
    assert text is not None, note
    assert "ci_required_jobs" in text and "gitlab" in text, note


# ------------------------------------------------------------------ AC-11


class GhSpy:
    def __init__(self):
        self.calls: list = []

    def __call__(self, *args, **kwargs):
        self.calls.append(([str(a) for a in args], dict(kwargs)))
        return subprocess.CompletedProcess(list(args), 0, "", "")


def create_argv(rng: random.Random) -> list:
    return ["pr", "create", "--head", f"task/{project_name(rng)}", "--base",
            config.MAIN_BRANCH, "--title", f"Заголовок {rng.randrange(10 ** 6)}",
            "--body", f"Текст {rng.randrange(10 ** 6)}"]


@pytest.mark.parametrize("tail", [[], ["--draft"], ["--assignee=alice"],
                                  ["--draft", "--assignee=alice"]],
                         ids=["хвост", "draft", "assignee", "draft-assignee"])
def test_ac11_pr_create_extra_argument_refused_without_gh(tmp_root, seed, monkeypatch, tail):
    """`forge.github_call` с формой `pr create`, у которой после разрешённого хвоста лишний аргумент, — отказ без вызова `gh`.

    Сценарий: запись `github` + `target-human` локального слоя с https-
    `url` (контекст разрешается — без закрытого списка вызов дошёл бы до
    `ci.gh`). Разрешённая форма `pr create --head … --base … --title …
    --body …` с хвостом по параметру уходит в шпион `ci.gh` (контроль); та
    же форма с лишним случайным аргументом в конце — ответ код 1, stderr
    начинается с `forge.GH_CALL_REFUSAL`, шпион нового вызова не видел.

    Ловит мутацию: `return rest == []` → `return True` в разборе формы
    `pr create` — лишний аргумент проходит в `ci.gh`.
    """
    rng = random.Random(seed)
    name = project_name(rng)
    write_local(name, "github", "target-human")
    spy = GhSpy()
    monkeypatch.setattr(ci, "gh", spy)
    allowed = create_argv(rng) + tail
    res = forge.github_call(name, *allowed)
    note = f"зерно: {seed}; {name}; {spy.calls}"
    assert len(spy.calls) == 1 and spy.calls[0][0] == allowed, note
    extra = allowed + [rng.choice(["--web", "--fill", f"x{rng.randrange(100)}",
                                   "--label=bug"])]
    res = forge.github_call(name, *extra)
    note = f"зерно: {seed}; {name}; argv {extra}; ответ {res!r}; {spy.calls}"
    assert res.returncode == 1, note
    assert str(res.stderr).startswith(forge.GH_CALL_REFUSAL), note
    assert len(spy.calls) == 1, note
