"""Поля записи проекта для доставки через MR: проверка формы при загрузке записи локального слоя, отказ называет поле, плоская запись без новых ключей и `ci_required_jobs` в плоской записи.

Группа: долгоживущий
Красен до реализации: раздел `policy`/`machine` записи локального слоя не знает полей `branch_template`, `ref_pattern`, `freshness`, `squash_before_mr`, `commit_template`, `commit_author`, `co_author`, `push_options`, `push_options_forbidden`, `ci_required_jobs`, `mr_assignee`, `draft_mr`, `max_in_flight` — допустимое значение каждого отказывает «неизвестное поле», и контрольные загрузки падают.

Свойство — чистая проверка записи (`targets.target` над файлом локального
слоя песочницы `tmp_root`), без git и FSM. Каждый отказ проверяется в паре
с контрольной загрузкой той же записи с допустимым значением: так отказ
«неизвестное поле» до реализации не сходит за отказ проверки формы. Имена
проектов порождаются модулем `random` при каждом запуске; зерно печатается
и входит в текст провала.
"""
import random

import pytest

from orchestrator import config, targets

LETTERS = "abcdefghijkmnopqrstuvwxyz"
NEW_KEYS = ("branch_template", "ref_pattern", "freshness", "squash_before_mr",
            "commit_template", "commit_author", "co_author", "push_options",
            "push_options_forbidden", "ci_required_jobs", "mr_assignee",
            "draft_mr", "max_in_flight")
REF_TEMPLATE = {"branch_template": '"feature/{ref}"', "ref_required": "tracker"}
GOOD_AUTHOR = {"name": "X", "email": "x@y"}


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


def project_name(seed: int) -> str:
    rng = random.Random(seed)
    return "r" + "".join(rng.choice(LETTERS) for _ in range(7))


def render(fields: dict, indent: int) -> str:
    """Поля раздела строками YAML: значение-словарь — вложенный блок."""
    pad = " " * indent
    lines = ""
    for key, value in fields.items():
        if isinstance(value, dict):
            lines += f"{pad}{key}:\n" + render(value, indent + 2)
        else:
            lines += f"{pad}{key}: {value}\n"
    return lines


def write_record(name: str, policy: dict | None = None,
                 machine: dict | None = None) -> None:
    """Файл локального слоя с одной записью проекта в трёх разделах."""
    entry = (f"  {name}:\n"
             f"    description:\n      base: {config.MAIN_BRANCH}\n"
             f"      test_profile:\n        command: [python3, -m, pytest]\n"
             f"        long_lived_dir: tests\n"
             f"        long_lived_name: test_<id>_<name>.py\n"
             f"    policy:\n      no_paths: []\n      project_skills: []\n"
             f"      merge_gate: operator\n"
             f"      weakening_scope: [tests/**/*.py]\n"
             f"      mutation_claim_scope: [tests/test_*.py]\n"
             + render(policy or {}, 6)
             + f"    machine:\n      forge: github\n"
             f"      url: https://localhost/team/{name}\n"
             f"      token_slot: {name}-token\n"
             + render(machine or {}, 6))
    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text("targets:\n" + entry, encoding="utf-8")


def load(name: str, policy: dict | None = None, machine: dict | None = None):
    """(плоская запись, None) — загрузилась; (None, текст отказа) — нет."""
    write_record(name, policy, machine)
    try:
        return targets.target(name), None
    except targets.TargetsError as exc:
        return None, str(exc)


def assert_refused_by_field(name: str, field: str, bad: tuple, good: tuple,
                            note: str) -> None:
    """Плохая запись — отказ с именем поля и не «неизвестное поле»;
    контрольная запись с допустимым значением — загружается."""
    entry, error = load(name, *good)
    assert error is None, f"{note}: контрольная запись не загрузилась: {error}"
    entry, error = load(name, *bad)
    assert entry is None, f"{note}: запись загрузилась: {entry}"
    assert field in error, f"{note}: отказ не называет поле {field}: {error}"
    assert "неизвестное" not in error, f"{note}: поле не объявлено: {error}"


# --- AC-1 ---

# (вариант, поле отказа, policy плохой записи, policy контрольной записи)
AC1_CASES = [
    ("ref-without-ref-required", "branch_template",
     {"branch_template": '"feature/{ref}"'}, REF_TEMPLATE),
    ("commit-template-without-squash", "commit_template",
     {"commit_template": '"{ref}: {text}"'},
     {"commit_template": '"{ref}: {text}"', "squash_before_mr": "true"}),
    ("rebase-without-squash", "freshness",
     {"freshness": "rebase"},
     {"freshness": "rebase", "squash_before_mr": "true"}),
    ("ci-skip", "push_options",
     {"push_options": "[ci.skip]"},
     {"push_options": "[ci.variable=OTHER=1]"}),
    ("forbidden-ci-variable", "push_options",
     {"push_options": "[ci.variable=SECRET=1]", "push_options_forbidden": "[SECRET]"},
     {"push_options": "[ci.variable=OTHER=1]", "push_options_forbidden": "[SECRET]"}),
    ("forbidden-plain", "push_options",
     {"push_options": "[SECRET=1]", "push_options_forbidden": "[SECRET]"},
     {"push_options": "[ci.variable=OTHER=1]", "push_options_forbidden": "[SECRET]"}),
    ("no-equals", "push_options",
     {"push_options": "[novalue]"},
     {"push_options": "[ci.variable=OTHER=1]"}),
    ("merge-request", "push_options",
     {"push_options": "[merge_request.target=main]"},
     {"push_options": "[ci.variable=OTHER=1]"}),
    ("ref-pattern-without-ref", "ref_pattern",
     {"ref_pattern": r"PROJ-\d+"},
     dict(REF_TEMPLATE, ref_pattern=r"PROJ-\d+")),
]


@pytest.mark.parametrize("case,field,bad,good", AC1_CASES,
                         ids=[c[0] for c in AC1_CASES])
def test_ac1_record_rule_refused_with_field_name(tmp_root, seed, case, field, bad, good):
    """Нарушение правила записи — отказ загрузки с именем своего поля.

    Сценарий: запись локального слоя со случайным именем сначала
    загружается в контрольном виде (правило соблюдено: `ref_required` при
    `{ref}`, `squash_before_mr: true` при своём `commit_template` и при
    `rebase`, `ci.variable=OTHER=1` при `push_options_forbidden: [SECRET]`,
    `ref_pattern` при шаблоне с `{ref}`), затем — с нарушением:
    `targets.target` поднимает `TargetsError`, текст называет поле
    (`branch_template`, `commit_template`, `freshness`, `push_options`,
    `ref_pattern`) и не говорит «неизвестное поле».

    Ловит мутацию: проверки `{ref}` без `ref_required` нет — запись с
    `feature/{ref}` загрузится; `push_options` проверяет запрещённые имена
    только у формы `ИМЯ=значение`, а не у `ci.variable=ИМЯ=значение` (или
    наоборот); `merge_request.*` отказывается только при непустом
    `push_options_forbidden`; элемент без `=` принят; `ref_pattern` без
    `{ref}` молча игнорируется; отказ называет не то поле (`squash_before_mr`
    вместо `freshness`).
    """
    name = project_name(seed)
    note = f"зерно: {seed}; {case}; проект {name}"
    assert_refused_by_field(name, field, (bad, None), (good, None), note)


# --- AC-2 ---

# (вариант, поле, раздел, плохое значение, допустимое значение, общие поля policy)
AC2_CASES = [
    ("freshness", "freshness", "policy", "squash", "merge", {}),
    ("ref_pattern", "ref_pattern", "policy", '"PROJ-("', r"PROJ-\d+", REF_TEMPLATE),
    ("commit_author-no-email", "commit_author", "machine",
     {"name": "X"}, GOOD_AUTHOR, {}),
    ("commit_author-empty-name", "commit_author", "machine",
     {"name": '""', "email": "x@y"}, GOOD_AUTHOR, {}),
    ("commit_author-string", "commit_author", "machine",
     '"X <x@y>"', GOOD_AUTHOR, {}),
    ("co_author", "co_author", "policy",
     '"Reviewed-by: X"', '"Co-authored-by: X <x@y>"', {}),
    ("mr_assignee", "mr_assignee", "policy", '""', "alice", {}),
    ("draft_mr", "draft_mr", "policy", "yes", "false", {}),
    ("max_in_flight", "max_in_flight", "policy", "0", "3", {}),
    ("ci_required_jobs", "ci_required_jobs", "policy", "build", "[build]", {}),
    ("push_options_forbidden", "push_options_forbidden", "policy",
     "SECRET", "[SECRET]", {}),
]


def sections(section: str, field: str, value, common: dict) -> tuple:
    """(policy, machine) записи с полем `field` в разделе `section`."""
    if section == "machine":
        return dict(common), {field: value}
    return dict(common, **{field: value}), None


@pytest.mark.parametrize("case,field,section,bad,good,common", AC2_CASES,
                         ids=[c[0] for c in AC2_CASES])
def test_ac2_field_form_refused_with_field_name(tmp_root, seed, case, field,
                                                section, bad, good, common):
    """Значение поля не своей формы — отказ с именем поля; допустимое — загружается.

    Сценарий: запись локального слоя со случайным именем с допустимым
    значением поля (`merge`, `PROJ-\\d+`, `{name: X, email: x@y}`,
    `Co-authored-by: …`, непустой `mr_assignee`, булево `draft_mr`,
    `max_in_flight: 3`, списки `ci_required_jobs`/`push_options_forbidden`)
    загружается; та же запись с плохим значением (`squash`, `PROJ-(`,
    `commit_author` без email, с пустым `name`, строкой, `Reviewed-by: X`,
    пустой `mr_assignee`, `draft_mr: yes`, `max_in_flight: 0`, строка
    вместо списка) — `TargetsError` с именем поля, не «неизвестное поле».

    Ловит мутацию: `ref_pattern` не компилируется при загрузке (`re.compile`
    не вызван) — `PROJ-(` загрузится; `commit_author` проверяет только
    наличие ключей, а не непустоту — `name: ""` пройдёт; строка вместо
    отображения принята; `co_author` проверяется подстрокой, а не началом
    `Co-authored-by: `; `max_in_flight` сравнивается `>= 0`; `draft_mr`
    приводится `bool(...)` — `yes` пройдёт; строка `build` принята за список.
    """
    name = project_name(seed)
    note = f"зерно: {seed}; {case}; проект {name}"
    assert_refused_by_field(name, field, sections(section, field, bad, common),
                            sections(section, field, good, common), note)


def test_ac2_record_without_new_fields_keeps_flat_shape(tmp_root, seed):
    """Запись без новых полей загружается, и в её плоской записи нет ни одного нового ключа.

    Сценарий: запись локального слоя со случайным именем без новых полей;
    `targets.target` возвращает запись, среди её ключей нет ни
    `branch_template`, ни прочих новых полей — значения по умолчанию в
    плоскую запись не подставляются.

    Ловит мутацию: `targets._flatten` дописывает значения по умолчанию
    (`branch_template: task/{id}-{slug}`, `push_options: []`,
    `draft_mr: true`) в каждую плоскую запись — у записи появятся новые
    ключи.
    """
    name = project_name(seed)
    entry, error = load(name)
    note = f"зерно: {seed}; проект {name}"
    assert error is None, f"{note}: {error}"
    assert sorted(set(entry) & set(NEW_KEYS)) == [], f"{note}: {sorted(entry)}"


def test_ac2_ci_required_jobs_in_flat_record(tmp_root, seed):
    """`policy.ci_required_jobs` попадает в плоскую запись списком; без поля ключа нет.

    Сценарий: запись локального слоя со случайным именем и
    `ci_required_jobs: [build, test]` — `targets.target(name)` несёт ключ
    `ci_required_jobs` со значением `["build", "test"]`. Та же запись без
    поля — ключа нет, `.get("ci_required_jobs") or []` даёт `[]`.

    Ловит мутацию: поле объявлено и проверено, но не перенесено
    `targets._flatten` в плоскую запись — ключа не будет; переносится
    всегда, со значением по умолчанию `[]` — у записи без поля ключ
    появится.
    """
    name = project_name(seed)
    note = f"зерно: {seed}; проект {name}"
    entry, error = load(name, {"ci_required_jobs": "[build, test]"})
    assert error is None, f"{note}: {error}"
    assert entry.get("ci_required_jobs") == ["build", "test"], f"{note}: {entry}"
    entry, error = load(name)
    assert error is None, f"{note}: {error}"
    assert "ci_required_jobs" not in entry, f"{note}: {entry}"
    assert (entry.get("ci_required_jobs") or []) == [], f"{note}: {entry}"
