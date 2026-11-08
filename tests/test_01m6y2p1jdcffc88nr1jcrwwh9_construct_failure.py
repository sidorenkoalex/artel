"""Падение конструктора песочницы общей фикстуры `tests.sandbox.shared_readonly` выставляет исход построения для всего модуля.

Группа: долгоживущий
Красен до реализации: в `_SharedModuleState.construct` создание песочницы стоит вне `try` — при падении конструктора `failure` не выставляется, и второй и третий тесты образца падают на `AttributeError` снятия отпечатка с песочницы `None`, а не на «построение общей фикстуры упало».

Тест пишет модуль-образец во временный каталог и прогоняет его отдельным
подпроцессом pytest с отчётом junit: исход ошибок подготовки виден только в
отдельном прогоне. Подпроцесс идёт с явным путём файла, с `PYTHONPATH` на
корень дерева, с пределом времени и в своей группе процессов; после
прогона группа снимается целиком.
"""
import os
import random
import signal
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

pytestmark = pytest.mark.size("large")

CODE_ROOT = Path(__file__).resolve().parent.parent
RUN_LIMIT_S = 100
BUILD_FAILED = "построение общей фикстуры упало"

SAMPLE = '''\
from tests.sandbox import TmpDirTest, shared_readonly


class @CLS@(TmpDirTest):
    __test__ = False

    def __init__(self, *args, **kwargs):
        raise RuntimeError(@TOKEN@)


def @BUILD@(sb):
    return sb


@FX@ = shared_readonly(@CLS@, @BUILD@)


def test_1(@FX@):
    pass


def test_2(@FX@):
    pass


def test_3(@FX@):
    pass
'''


def word(rng, length=7):
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                   for _ in range(length))


def run_sample(out: Path, text: str):
    """Пишет образец `out/sample_mod.py`, прогоняет его подпроцессом pytest
    и снимает группу процессов подпроцесса. Отдаёт ({имя теста: тексты
    <error>/<failure>}, {имя теста: теги исходов}, вывод)."""
    sample = out / "sample_mod.py"
    sample.write_text(text, encoding="utf-8")
    (out / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    report = out / "report.xml"
    env = dict(os.environ)
    for name in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTEST_CURRENT_TEST"):
        env.pop(name, None)
    env["PYTHONPATH"] = str(CODE_ROOT)
    proc = subprocess.Popen(
        [sys.executable, "-m", "pytest", str(sample), "-p", "no:cacheprovider",
         "-p", "no:xdist", "-c", str(out / "pytest.ini"), "--rootdir", str(out),
         f"--junitxml={report}", "-q"],
        cwd=str(out), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, start_new_session=True)
    try:
        output, _ = proc.communicate(timeout=RUN_LIMIT_S)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        if proc.poll() is None:
            proc.wait(timeout=10)
    errors: dict[str, str] = {}
    outcomes: dict[str, list[str]] = {}
    if report.is_file():
        for case in ET.parse(report).getroot().iter("testcase"):
            name = case.get("name")
            errors.setdefault(name, "")
            outcomes.setdefault(name, [])
            for child in case:
                if child.tag in ("error", "failure", "skipped"):
                    outcomes[name].append(child.tag)
                    errors[name] += (f"{child.get('message') or ''}\n"
                                     f"{child.text or ''}\n")
    return errors, outcomes, output


@pytest.fixture
def out_dir():
    with tempfile.TemporaryDirectory(prefix="shared-ro-construct-") as tmp:
        yield Path(tmp)


def sample_run(out_dir):
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    token = f"ctor-broke-{rng.randrange(10 ** 9)}"
    text = (SAMPLE.replace("@CLS@", f"Broken{word(rng).capitalize()}Sandbox")
            .replace("@BUILD@", f"build_{word(rng)}")
            .replace("@FX@", f"seeded_{word(rng)}")
            .replace("@TOKEN@", repr(token)))
    errors, outcomes, output = run_sample(out_dir, text)
    return seed, token, errors, outcomes, output


def test_ac5_constructor_failure_marks_build_failed_for_following_tests(out_dir):
    """Конструктор песочницы бросает исключение — второй и третий тесты получают ошибку подготовки «построение общей фикстуры упало», не `AttributeError`.

    Образец: класс песочницы (`TmpDirTest`, `__test__ = False`), чей
    `__init__` бросает `RuntimeError` со случайной меткой; три теста берут
    общую фикстуру над ним. По отчёту junit у `test_2` и `test_3` исход —
    `error`, текст несёт «построение общей фикстуры упало» и не несёт
    `AttributeError`. Имена класса, `build` и фикстуры случайны, зерно
    печатается.

    Ловит мутацию: создание песочницы оставлено вне `try` — `failure` не
    выставлен, второй и третий тесты падают на `AttributeError` снятия
    отпечатка с `None`; либо уборка в `except` зовётся без проверки `sb is
    not None` — исходное исключение подменено `UnboundLocalError`/
    `AttributeError` уборки.
    """
    seed, _token, errors, outcomes, output = sample_run(out_dir)
    assert sorted(outcomes) == ["test_1", "test_2", "test_3"], \
        f"зерно {seed}\n{output}"
    for name in ("test_2", "test_3"):
        assert "error" in outcomes[name], f"зерно {seed}; {name}\n{output}"
        assert BUILD_FAILED in errors[name], \
            f"зерно {seed}; {name}:\n{errors[name]}\n{output}"
        assert "AttributeError" not in errors[name], \
            f"зерно {seed}; {name}:\n{errors[name]}\n{output}"


def test_ac7_constructor_outside_try_mutation_turns_red(out_dir):
    """Мутация «конструктор вне try» краснеет: исход построения у всех трёх тестов несёт исходное исключение конструктора.

    Тот же образец. У `test_1` — `error` с меткой исключения конструктора;
    у `test_2` и `test_3` — `error` «построение общей фикстуры упало» с той
    же меткой: выставленный `failure` называет исходное исключение, а не
    исключение уборки.

    Ловит мутацию: конструктор вне `try` — `failure` не выставлен, у
    `test_2`/`test_3` текст без «построение общей фикстуры упало» и без
    метки; либо `sb = None` не стоит до `try` и уборка падает на неё —
    метки исключения конструктора в тексте нет.
    """
    seed, token, errors, outcomes, output = sample_run(out_dir)
    assert "error" in outcomes.get("test_1", []), f"зерно {seed}\n{output}"
    assert token in errors["test_1"], f"зерно {seed}\n{errors['test_1']}\n{output}"
    for name in ("test_2", "test_3"):
        assert "error" in outcomes.get(name, []), f"зерно {seed}; {name}\n{output}"
        assert BUILD_FAILED in errors[name] and token in errors[name], \
            f"зерно {seed}; {name}:\n{errors[name]}\n{output}"
