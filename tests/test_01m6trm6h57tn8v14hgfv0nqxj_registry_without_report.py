"""Запись `full_suite: ci|both` хостинга без `job_test_report` отказывает одинаково в процессе без модуля `ci` и после его импорта — на реестре хостингов, подменённом в процессе теста.

Группа: долгоживущий
Зелёный с рождения: реестр для проверки записи уже берётся импортом `forge` при вызове, а не подстановкой из `ci`; после задачи в настоящем реестре не остаётся хостинга без `job_test_report`, и свойство держится только на подменённом реестре — этот файл сохраняет его.
Заменяет: tests/test_01m6ezxvfgxc6wbda9qjesazrw_hosting_registry.py::test_ac15_full_suite_check_without_ci_module

Стенд — временный `config.TARGETS` песочницы (`tmp_root`) с записью
внешнего проекта из одного компонента (`report`, `full_suite`, `ci_job`),
дописанной к записи артели. Хостинг записи — значение реестра
`forge.IMPLEMENTATIONS`, выбранное зерном из ключей реестра, а не
литералом. Загрузка записи идёт в отдельном процессе `python3`: он ставит
хук импорта, который сразу после исполнения модуля `orchestrator.forge`
заменяет реализацию этого хостинга в реестре классом без
`job_test_report` (сам модуль `ci` хук не импортирует и не трогает),
переводит пути `config` (`tests.sandbox.ALL_CONFIG_ATTRS`) на пути
песочницы и зовёт `targets.load()` — один раз без `orchestrator.ci` в
`sys.modules` до загрузки, другой раз после `import orchestrator.ci`.
Настоящие `targets.yaml` и файл реестра не меняются: подмена живёт только
в памяти дочернего процесса. Имена проекта, компонента и задания — из
`random`, зерно печатается и входит в текст провала.
"""
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from orchestrator import config, forge, targets
from tests.sandbox import ALL_CONFIG_ATTRS, make_project_repo

ALPHABET = "abcdefghijklmnopqrstuvwxyz"
CODE_ROOT = Path(targets.__file__).resolve().parent.parent

LOAD_SCRIPT = """
import importlib.abc, importlib.machinery, json, sys
from pathlib import Path
hosting = sys.argv[3]
state = {"replaced": False}


class NoReport:
    CI_BY_PIPELINE = False


class Hook(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name != "orchestrator.forge":
            return None
        spec = importlib.machinery.PathFinder.find_spec(name, path)
        real_exec = spec.loader.exec_module

        def exec_module(module):
            real_exec(module)
            module.IMPLEMENTATIONS[hosting] = NoReport
            state["replaced"] = True

        spec.loader.exec_module = exec_module
        return spec


sys.meta_path.insert(0, Hook())
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
print(json.dumps({"ci_before": ci_before, "refusal": refusal,
                  "replaced": state["replaced"]}))
"""


@pytest.fixture
def stand(tmp_root):
    """Песочница с зерном, случайными именами и хостингом из реестра."""
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    tmp_root.seed = seed
    tmp_root.project = "p" + "".join(rng.choice(ALPHABET) for _ in range(7))
    tmp_root.component = "".join(rng.choice(ALPHABET) for _ in range(5))
    tmp_root.job = f"suite-{rng.randrange(1, 99)}"
    tmp_root.hosting = rng.choice(sorted(forge.IMPLEMENTATIONS))
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


def load_in_process(stand, with_ci: bool) -> dict:
    """Загрузка записей песочницы в отдельном процессе с подменённым
    реестром: {"ci_before", "refusal", "replaced"}."""
    paths = {name: str(getattr(config, name)) for name in ALL_CONFIG_ATTRS
             if isinstance(getattr(config, name, None), Path)}
    res = subprocess.run(
        [sys.executable, "-c", LOAD_SCRIPT, json.dumps(paths),
         "with-ci" if with_ci else "without-ci", stand.hosting],
        cwd=CODE_ROOT, capture_output=True, text=True, timeout=60,
        start_new_session=True)
    lines = res.stdout.strip().splitlines()
    if res.returncode != 0 or not lines:
        return {"ci_before": None, "refusal": None, "replaced": None,
                "error": f"код {res.returncode}; stderr: {res.stderr[-800:]}"}
    return json.loads(lines[-1])


@pytest.mark.parametrize("mode", ["ci", "both"])
def test_ac9_reportless_hosting_refused_with_and_without_ci(stand, mode):
    """Запись `full_suite: ci|both` хостинга, у которого в подменённом реестре нет `job_test_report`, отказывает `TargetsError` и без модуля `ci`, и после его импорта; тексты одинаковы и называют `full_suite`.

    Сценарий: запись внешнего проекта, компонент с `full_suite` по
    параметру, `ci_job` и `report`; хук дочернего процесса заменил
    реализацию её хостинга в реестре `forge` классом без
    `job_test_report`. Процесс без `orchestrator.ci` (его нет в
    `sys.modules` до загрузки) и процесс после `import orchestrator.ci`.

    Ловит мутацию: реестр подставляется в `targets` при импорте `ci`
    (`targets.hosting_registry = forge.IMPLEMENTATIONS` в `ci.py`, у
    `targets` без `ci` реестра нет) — процесс без `ci` загружает запись без
    отказа (`refusal` — `None`), процесс с `ci` отказывает.
    """
    write_entry(stand, mode)
    without = load_in_process(stand, with_ci=False)
    with_ci = load_in_process(stand, with_ci=True)
    where = (f"зерно: {stand.seed}; хостинг {stand.hosting}; без ci: {without}; "
             f"с ci: {with_ci}")
    assert without["replaced"] is True and with_ci["replaced"] is True, where
    assert without["ci_before"] is False, where
    assert with_ci["refusal"] and "full_suite" in with_ci["refusal"], where
    assert without["refusal"] == with_ci["refusal"], where
