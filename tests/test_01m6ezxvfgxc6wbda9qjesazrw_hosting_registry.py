"""Проверка записи «`full_suite: ci|both` только для хостинга с чтением отчёта задания» не зависит от того, загружен ли модуль `ci`.

Группа: долгоживущий
Красен до реализации: реестр хостингов подставляет в `targets.hosting_registry` импорт `orchestrator/ci.py` (строка 28) — в процессе без `ci` загрузчик реестра не видит, запись с `full_suite: ci` у хостинга без `job_test_report` загружается без отказа; строка присваивания в `ci.py` есть.

Стенд — временный `config.TARGETS` песочницы (`tmp_root`) с записью
внешнего проекта из одного компонента, дописанной к записи артели (форма —
как в `tests/test_01m5xzskk8gzteca2kwafhe029_component_fields.py`). Хостинг
записи — реализация реестра `forge.IMPLEMENTATIONS` без `job_test_report`,
выбранная из реестра, а не литералом. Загрузка записи идёт в отдельном
процессе `python3`: он импортирует только `orchestrator.config` и
`orchestrator.targets`, переводит пути `config` (`tests.sandbox.
ALL_CONFIG_ATTRS`) на пути песочницы и зовёт `targets.load()` — один раз
без `orchestrator.ci` (сверено по `sys.modules` до загрузки), другой раз
после `import orchestrator.ci`. Имена проекта, компонента и задания — из
`random`, зерно печатается и входит в текст провала.
"""
import ast
import inspect
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from orchestrator import ci, config, forge, targets
from tests.sandbox import ALL_CONFIG_ATTRS, make_project_repo

ALPHABET = "abcdefghijklmnopqrstuvwxyz"
WITHOUT_REPORT = sorted(name for name, impl in forge.IMPLEMENTATIONS.items()
                        if getattr(impl, "job_test_report", None) is None)
CODE_ROOT = Path(targets.__file__).resolve().parent.parent

LOAD_SCRIPT = """
import json, sys
from pathlib import Path
from orchestrator import config
for name, value in json.loads(sys.argv[1]).items():
    setattr(config, name, Path(value))
from orchestrator import targets
ci_before = "orchestrator.ci" in sys.modules
if sys.argv[2] == "with-ci":
    import orchestrator.ci
try:
    targets.load()
    refusal = None
except targets.TargetsError as exc:
    refusal = str(exc)
print(json.dumps({"ci_before": ci_before, "refusal": refusal}))
"""


@pytest.fixture
def stand(tmp_root):
    """Песочница с зерном и случайными именами; запись ещё не написана."""
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    tmp_root.seed = seed
    tmp_root.project = "p" + "".join(rng.choice(ALPHABET) for _ in range(7))
    tmp_root.component = "".join(rng.choice(ALPHABET) for _ in range(5))
    tmp_root.job = f"suite-{rng.randrange(1, 99)}"
    tmp_root.hosting = rng.choice(WITHOUT_REPORT) if WITHOUT_REPORT else ""
    tmp_root.artel_text = config.TARGETS.read_text(encoding="utf-8")
    make_project_repo(tmp_root.project, origin=False)
    return tmp_root


def write_entry(stand, mode: str) -> None:
    """Запись проекта из одного компонента с `full_suite: <mode>`."""
    fields = {
        "command": "[python3, -m, pytest]",
        "long_lived_dir": "tests",
        "long_lived_name": "test_<id>_<name>.py",
        "weakening_scope": "[tests/**]",
        "mutation_claim_scope": "[tests/test_*.py]",
        "report": "junit-xml",
        "full_suite": mode,
        "ci_job": stand.job,
    }
    text = (f"  {stand.project}:\n"
            f"    forge: {stand.hosting}\n"
            f"    url: https://localhost/artel-tests/{stand.project}\n"
            "    base: main\n"
            f"    token_slot: {stand.project}-token\n"
            "    no_paths: []\n"
            "    project_skills: []\n"
            "    merge_gate: operator\n"
            "    components:\n"
            f"      {stand.component}:\n"
            + "".join(f"        {k}: {v}\n" for k, v in fields.items()))
    config.TARGETS.write_text(stand.artel_text.rstrip("\n") + "\n" + text,
                              encoding="utf-8")


def load_in_process(with_ci: bool) -> dict:
    """Загрузка записей песочницы в отдельном процессе: {"ci_before",
    "refusal"}."""
    paths = {name: str(getattr(config, name)) for name in ALL_CONFIG_ATTRS
             if isinstance(getattr(config, name, None), Path)}
    res = subprocess.run(
        [sys.executable, "-c", LOAD_SCRIPT, json.dumps(paths),
         "with-ci" if with_ci else "without-ci"],
        cwd=CODE_ROOT, capture_output=True, text=True, timeout=60)
    lines = res.stdout.strip().splitlines()
    if res.returncode != 0 or not lines:
        return {"ci_before": None, "refusal": None,
                "error": f"код {res.returncode}; stderr: {res.stderr[-800:]}"}
    return json.loads(lines[-1])


@pytest.mark.skipif(not WITHOUT_REPORT,
                    reason="в реестре forge нет хостинга без job_test_report")
@pytest.mark.parametrize("mode", ["ci", "both"])
def test_ac15_full_suite_check_without_ci_module(stand, mode):
    """Запись `full_suite: ci|both` хостинга без `job_test_report` отказывает `TargetsError` в процессе без модуля `ci` так же, как в процессе с ним.

    Сценарий: запись внешнего проекта, компонент с `full_suite` по
    параметру, `ci_job` и `report`, хостинг — реализация реестра без
    `job_test_report`. Процесс без `orchestrator.ci` (его нет в
    `sys.modules` до загрузки) и процесс после `import orchestrator.ci`:
    оба отказывают, текст отказа называет `full_suite` и одинаков.

    Ловит мутацию: реестр хостингов по-прежнему подставляется в
    `targets.hosting_registry` при импорте `ci` — процесс без `ci`
    загружает запись без отказа (`refusal` — `None`), процесс с `ci`
    отказывает.
    """
    write_entry(stand, mode)
    without = load_in_process(with_ci=False)
    with_ci = load_in_process(with_ci=True)
    where = (f"зерно: {stand.seed}; хостинг {stand.hosting}; без ci: {without}; "
             f"с ci: {with_ci}")
    assert without["ci_before"] is False, where
    assert with_ci["refusal"] and "full_suite" in with_ci["refusal"], where
    assert without["refusal"] == with_ci["refusal"], where


def test_ac15_ci_module_does_not_install_registry():
    """В `orchestrator/ci.py` нет присваивания `targets.hosting_registry = …`.

    Сценарий: разбор исходного текста модуля `ci` (`inspect.getsource`):
    ни одного присваивания атрибуту `hosting_registry` объекта `targets`.

    Ловит мутацию: строка подстановки реестра при импорте `ci`
    (`orchestrator/ci.py:28`) оставлена рядом с новым путём реестра —
    присваивание найдено в разборе.
    """
    tree = ast.parse(inspect.getsource(ci))
    found = [ast.unparse(node) for node in ast.walk(tree)
             if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign))
             for target in (node.targets if isinstance(node, ast.Assign)
                            else [node.target])
             if isinstance(target, ast.Attribute)
             and target.attr == "hosting_registry"
             and isinstance(target.value, ast.Name)
             and target.value.id == "targets"]
    assert found == [], found
