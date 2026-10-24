"""Планка задачи: уборка `full_suite_lock` без ожидания предела, замер
записью вместо настоящих прогонов в ac8 `doctor_duration`.

Группа: разовый
Красен до реализации: stop_everything отпускает пробник файлом release-tree-<метка>, ac8 делает 17 настоящих прогонов measured_run, в каталоге документов нет PLAN.md и mutation-00N.diff.

Все критерии — факты этой задачи: правка двух тестовых файлов против базы
ветки (`_pult.DIFF_BASE`), PLAN.md и патчи мутаций в ссылке документов
(`_pult.artifact_text`), пути задачи (`_pult.changed_paths`). Поведение
правленых тестов (AC-1, AC-3, AC-6) проверяется исполнением самих методов
из рабочей копии с обёртками, записывающими вызовы.

Валидация стабом: на временной правке рабочей копии (строка отпуска
`self.release(path.name.removeprefix("tree-"))`; ac8 — `measured_run(0.01)`
первым, затем `journal_measurement(1.12)` для калибровки и
`journal_measurement(1.92)` для сигнала) зеленеют test_ac1, test_ac2,
test_ac3, test_ac4 и параметры test_ac6_cleanup_…; правка убрана, не
закоммичена. До правки параметр ac9 test_ac6_cleanup_… уже зелёный:
к снятию групп в нём процессы пульта завершены. Тесты PLAN/патчей
(test_ac5, test_ac6_plan_…, test_ac7) провалидированы подменой `_pult`
синтетическим PLAN в формате `orchestrator/mutation_run.py::_header` и
`_Run.row`: полный вывод двух ref зелёный; без прогона base, с мутацией
«не убита», без строки FAILED и с правленым после прогона патчем —
красный.
"""
import ast
import copy
import hashlib
import importlib
import os
import random
import re
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import (CODE_ROOT, DIFF_BASE, TASK_ID, apply_check,  # noqa: E402
                   artifact_text, changed_paths)

LOCK_FILE = "tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py"
LOCK_MODULE = "tests.test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock"
DURATION_FILE = "tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py"
DURATION_MODULE = "tests.test_01m4araxf7vss5xz8c99bx8de2_doctor_duration"
AC8 = "test_ac8_ack_restarts_calibration_after_signal"
RELEASE_LOOP = "self.probe.glob('tree-*')"
ZONE_PATHS = {LOCK_FILE, DURATION_FILE, "docs/codebase-map.md"}
FOUR_TESTS = ("test_ac6_wait_over_limit_is_not_started_without_pytest",
              "test_ac9_timeout_is_refused_as_timeout_not_as_broken_appendix",
              "test_ac11_not_started_is_refused_with_holder",
              AC8)

_REPO_LOCATING_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                      "GIT_OBJECT_DIRECTORY",
                      "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR",
                      "GIT_NAMESPACE", "GIT_PREFIX")


# --- чтение кода: база ветки и рабочая копия ------------------------------

def git(*args: str) -> str:
    env = {k: v for k, v in os.environ.items() if k not in _REPO_LOCATING_ENV}
    res = subprocess.run(["git", "-C", CODE_ROOT, *args], env=env,
                         capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout


def base_text(rel: str) -> str:
    assert DIFF_BASE, "база диффа задачи не определена при выкладке"
    return git("show", f"{DIFF_BASE}:{rel}")


def code_text(rel: str) -> str:
    return (Path(CODE_ROOT) / rel).read_text(encoding="utf-8")


def method(text: str, cls: str, name: str) -> ast.FunctionDef:
    for node in ast.parse(text).body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == name:
                    return item
    raise LookupError(f"нет метода {cls}.{name}")


def release_loop(fn: ast.FunctionDef) -> ast.For:
    loops = [node for node in ast.walk(fn) if isinstance(node, ast.For)
             and ast.unparse(node.iter) == RELEASE_LOOP]
    assert len(loops) == 1, (f"в {fn.name} ожидался один цикл отпуска по "
                             f"{RELEASE_LOOP}, найдено {len(loops)}")
    return loops[0]


def cleanup_shape(text: str) -> str:
    """Дерево `stop_everything` с телом цикла отпуска, заменённым на pass."""
    fn = copy.deepcopy(method(text, "LockSandbox", "stop_everything"))
    release_loop(fn).body = [ast.Pass()]
    return ast.dump(fn)


def without_release_body(text: str) -> str:
    """Текст файла без строк тела цикла отпуска в `stop_everything`."""
    loop = release_loop(method(text, "LockSandbox", "stop_everything"))
    lines = text.splitlines(keepends=True)
    return "".join(lines[:loop.lineno] + lines[loop.end_lineno:])


def without_method(text: str, cls: str, name: str) -> str:
    fn = method(text, cls, name)
    lines = text.splitlines(keepends=True)
    return "".join(lines[:fn.lineno - 1] + lines[fn.end_lineno:])


def ac8_contract(text: str) -> dict:
    """Докстринг ac8, его утверждения и вызов ack_alert в порядке исходника."""
    fn = method(text, "DoctorDurationTest", AC8)
    calls = sorted((node for node in ast.walk(fn)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and (node.func.attr.startswith("assert")
                         or node.func.attr == "ack_alert")),
                   key=lambda node: (node.lineno, node.col_offset))
    return {"docstring": ast.get_docstring(fn, clean=False),
            "calls": [ast.unparse(node) for node in calls]}


# --- AC-1 -----------------------------------------------------------------

def test_ac1_cleanup_releases_file_the_probe_waits_for(tmp_path):
    """Уборка отпускает каждый пробник тем файлом, который он ждёт.

    На поддельном экземпляре песочницы (каталог пробников с деревьями
    `tree-<метка>` для случайных меток, детей нет) исполняется настоящий
    `LockSandbox.stop_everything` рабочей копии; отпуск записывается
    обёрткой `release`. Записанные пути обязаны совпасть с
    `release_path(<метка>)` — файлом, который ждёт пробник дерева
    `tree-<метка>`. Вторая часть: дерево `stop_everything` вне тела цикла
    отпуска совпадает с базой ветки — сигнал linger, ожидание до 10 с,
    SIGKILL групп и сверка pid не тронуты.

    Ловит мутацию: строка отпуска остаётся `self.release(path.name)` —
    записанные пути `release-tree-<метка>` не совпадут с ожидаемыми; либо
    вместе с ней срок ожидания уборки меняется с 10 с — дерево
    `stop_everything` разойдётся с базой.
    """
    seed = random.randrange(2 ** 32)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    labels = {"".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                      for _ in range(rng.randint(3, 10)))
              for _ in range(rng.randint(1, 5))}
    module = importlib.import_module(LOCK_MODULE)
    cls = module.LockSandbox
    probe = tmp_path / "probe"
    for label in labels:
        (probe / f"tree-{label}").mkdir(parents=True)
    fake = types.SimpleNamespace(probe=probe, children=[],
                                 records=tmp_path / "records.jsonl")
    fake.release_path = lambda label: cls.release_path(fake, label)
    released = []
    fake.release = lambda label: released.append(fake.release_path(label))
    fake.kill_group = cls.kill_group
    cls.stop_everything(fake)
    expected = sorted(cls.release_path(fake, label) for label in labels)
    assert sorted(released) == expected, (
        f"зерно {seed}: уборка отпустила {sorted(p.name for p in released)}, "
        f"пробники ждут {[p.name for p in expected]}")
    assert cleanup_shape(code_text(LOCK_FILE)) == \
        cleanup_shape(base_text(LOCK_FILE)), (
        "stop_everything изменён вне строки отпуска пробников")


# --- AC-2 -----------------------------------------------------------------

def test_ac2_lock_file_unchanged_outside_release_line():
    """Файл full_suite_lock вне тела цикла отпуска совпадает с базой ветки.

    Из текста файла рабочей копии и базы вырезаются строки тела цикла
    `for path in self.probe.glob("tree-*")` в `stop_everything`; остаток —
    все тестовые методы, их утверждения, помощники — обязан совпасть
    побайтно. Зелёный с рождения для неправленого файла.

    Ловит мутацию: разработчик заодно правит утверждение или паузу
    другого теста файла (например ожидание `hold_then_contend`) — остаток
    текста разойдётся с базой.
    """
    assert without_release_body(code_text(LOCK_FILE)) == \
        without_release_body(base_text(LOCK_FILE)), (
        f"{LOCK_FILE} изменён вне строки отпуска в stop_everything")


# --- AC-3 -----------------------------------------------------------------

def per_test(call: tuple) -> float:
    _, args, kwargs = call
    duration = args[0] if args else kwargs["duration"]
    tests = args[1] if len(args) > 1 else kwargs.get("tests", 4)
    return duration / tests


def test_ac3_ac8_keeps_one_real_run_first():
    """В ac8 настоящий прогон один и первый, остальное — записи замера.

    Метод ac8 рабочей копии исполняется целиком; `measured_run` и
    `journal_measurement` обёрнуты записью вызова (с передачей настоящей
    реализации). Ожидаемая последовательность при k =
    `config.SUITE_DURATION_CALIBRATION_RUNS`: первый вызов —
    `measured_run(0.01)`, других `measured_run` нет; далее k − 1
    калибровочных `journal_measurement` по образцу `1.12` (0,28 с на
    тест), сигнальная запись по образцу `1.92` или выше (от 0,48 с на
    тест), затем k калибровочных записей; сам тест проходит.

    Ловит мутацию: сигнальный вызов остаётся настоящим `measured_run(4.0)`
    либо настоящий прогон переезжает с первой позиции — число или порядок
    вызовов `measured_run` в записи разойдутся с ожидаемыми; калибровка
    записью с другой длительностью на тест — разойдутся значения.
    """
    from orchestrator import config

    module = importlib.import_module(DURATION_MODULE)
    cls = module.DoctorDurationTest
    calls = []
    real_measured, real_journal = cls.measured_run, cls.journal_measurement

    def measured(self, *args, **kwargs):
        calls.append(("measured_run", args, kwargs))
        return real_measured(self, *args, **kwargs)

    def journal(self, *args, **kwargs):
        calls.append(("journal_measurement", args, kwargs))
        return real_journal(self, *args, **kwargs)

    result = unittest.TestResult()
    with mock.patch.object(cls, "measured_run", measured), \
            mock.patch.object(cls, "journal_measurement", journal):
        cls(AC8).run(result)
    assert result.wasSuccessful(), [text for _, text in
                                    result.errors + result.failures]
    k = config.SUITE_DURATION_CALIBRATION_RUNS
    names = [name for name, _, _ in calls]
    assert names.count("measured_run") == 1, names
    assert calls[0] == ("measured_run", (0.01,), {}), calls[0]
    assert len(calls) == 2 * k + 1, names
    assert set(names[1:]) == {"journal_measurement"}, names
    calibration = calls[1:k] + calls[k + 1:]
    assert all(per_test(call) == pytest.approx(1.12 / 4)
               for call in calibration), calibration
    assert per_test(calls[k]) >= 1.92 / 4 - 1e-9, calls[k]


# --- AC-4 -----------------------------------------------------------------

def test_ac4_ac8_assertions_and_rest_of_file_unchanged():
    """Утверждения и докстринг ac8 прежние, файл вне ac8 не тронут.

    Сравниваются база ветки и рабочая копия `doctor_duration`: докстринг
    ac8 (с «Ловит мутацию»), последовательность вызовов `self.assert*` и
    `store.ack_alert` в теле ac8 в порядке исходника, и текст файла без
    строк метода ac8 — побайтно. Зелёный с рождения для неправленого
    файла.

    Ловит мутацию: при замене вызовов разработчик ослабляет
    `assertEqual(len(found), 1)` до `assertTrue(found)`, убирает
    проверку после ack или правит соседний тест файла — список
    утверждений или остаток текста разойдутся с базой.
    """
    now, base = code_text(DURATION_FILE), base_text(DURATION_FILE)
    assert ac8_contract(now) == ac8_contract(base)
    assert without_method(now, "DoctorDurationTest", AC8) == \
        without_method(base, "DoctorDurationTest", AC8), (
        f"{DURATION_FILE} изменён вне тела {AC8}")


# --- AC-5 -----------------------------------------------------------------

def run_blocks(plan: str) -> list:
    """Шапки и строки таблиц вывода mutation-run этой задачи в тексте PLAN."""
    blocks = []
    head = re.compile(rf"^\s*#\s*mutation-run №\S+ задачи {TASK_ID}\b")
    for line in plan.splitlines():
        if head.match(line):
            blocks.append({"ref": None, "sha": None, "tests": "",
                           "patches": {}, "killed": {}})
            continue
        if not blocks:
            continue
        block = blocks[-1]
        if m := re.match(r"^\s*#\s*ревизия прогона:\s*(\S+)\s+([0-9a-f]{7,40})",
                         line):
            block["ref"], block["sha"] = m.group(1), m.group(2)
        elif m := re.match(r"^\s*#\s*тесты:\s*(.*)$", line):
            block["tests"] = m.group(1)
        elif m := re.match(r"^\s*#\s*патч\s+(\d+)\s+(\S+)\s+sha256\s+"
                           r"([0-9a-f]{64})", line):
            block["patches"][m.group(2)] = m.group(3)
        elif m := re.match(r"^\s*(\d+)[\t ]+убита[\t ]+(.*)$", line):
            block["killed"][int(m.group(1))] = m.group(2)
    return blocks


def diff_paths(diff: str) -> set:
    return {m.group(1) for m in re.finditer(r"^\+\+\+ b/(\S+)", diff, re.M)} | \
        {m.group(1) for m in re.finditer(r"^--- a/(\S+)", diff, re.M)}


def test_ac5_mutations_killed_by_ac8_on_base_and_worktree():
    """Патчи мутаций лежат в документах, PLAN приводит их убийство ac8.

    Из ссылки документов читаются `mutation-001.diff`, `mutation-002.diff`
    (мутируют только `orchestrator/` и применяются к дереву HEAD) и
    PLAN.md. В PLAN ищутся шапки вывода `mutation-run` этой задачи с
    `--tests` doctor_duration: прогон ref `base` и прогон ref `worktree`,
    в каждом — sha256 обоих патчей, равные sha256 файлов документов, и
    строки «1 убита …», «2 убита …» с узлом ac8. Дерево `orchestrator/`
    ревизий двух прогонов совпадает; в PLAN есть строка падения ac8 из
    лога (FAILED с именем теста).

    Ловит мутацию: в PLAN приведён только прогон `--ref worktree`, либо
    мутация 002 «не убита» или убита другим тестом, либо патч в
    документах правлен после прогона — шапки или таблица разойдутся с
    ожидаемыми.
    """
    plan = artifact_text("PLAN.md")
    assert plan is not None, "в документах задачи нет PLAN.md"
    sums = {}
    for name in ("mutation-001.diff", "mutation-002.diff"):
        diff = artifact_text(name)
        assert diff is not None, f"в документах задачи нет {name}"
        paths = diff_paths(diff)
        assert paths and all(p.startswith("orchestrator/") for p in paths), (
            f"{name} мутирует не только orchestrator/: {sorted(paths)}")
        assert apply_check(diff) == "", f"{name} не применяется к HEAD"
        sums[name] = hashlib.sha256(diff.encode("utf-8")).hexdigest()

    def proves(block: dict) -> bool:
        return (DURATION_FILE in block["tests"]
                and all(block["patches"].get(n) == s for n, s in sums.items())
                and all(AC8 in block["killed"].get(i, "") for i in (1, 2)))

    blocks = run_blocks(plan)
    by_ref = {ref: [b for b in blocks if b["ref"] == ref and proves(b)]
              for ref in ("base", "worktree")}
    assert by_ref["base"], ("в PLAN нет вывода mutation-run --ref base с "
                            "обеими мутациями, убитыми ac8, и sha256 патчей "
                            f"документов; шапки: {blocks}")
    assert by_ref["worktree"], ("в PLAN нет вывода mutation-run --ref "
                                "worktree с обеими мутациями, убитыми ac8, и "
                                f"sha256 патчей документов; шапки: {blocks}")
    trees = {git("rev-parse", f"{b['sha']}:orchestrator").strip()
             for ref in by_ref for b in by_ref[ref]}
    assert len(trees) == 1, f"дерево orchestrator/ прогонов разное: {trees}"
    assert any(AC8 in line and "FAILED" in line
               for line in plan.splitlines()), (
        "в PLAN нет строки падения ac8 из лога mutation-run")


# --- AC-6 -----------------------------------------------------------------

def test_ac6_plan_names_times_of_four_tests():
    """PLAN называет все четыре теста, время которых замерено до и после.

    Ловит мутацию: в PLAN приведены замеры только `full_suite_lock` без
    ac8 `doctor_duration` — имени ac8 в тексте PLAN не окажется.
    """
    plan = artifact_text("PLAN.md")
    assert plan is not None, "в документах задачи нет PLAN.md"
    missing = [name for name in FOUR_TESTS if name not in plan]
    assert not missing, f"PLAN не приводит время тестов: {missing}"


@pytest.mark.parametrize("cls_name,name", [
    ("WaitLimitTest", "test_ac6_wait_over_limit_is_not_started_without_pytest"),
    ("MergeGateOutcomesTest",
     "test_ac9_timeout_is_refused_as_timeout_not_as_broken_appendix"),
    ("MergeGateOutcomesTest", "test_ac11_not_started_is_refused_with_holder"),
])
def test_ac6_cleanup_does_not_wait_out_limit(cls_name, name):
    """Уборка теста full_suite_lock не ждёт предел и не снимает живых.

    Тест рабочей копии исполняется целиком; `LockSandbox.stop_everything`
    обёрнут наблюдением: к первому снятию группы `kill_group` ни один
    дочерний процесс пульта не должен ещё работать (цикл ожидания
    закончился сам, а не по пределу 10 с), и сверка записей pid пробника
    (`pid_alive`) не находит живых процессов для SIGKILL. Сам тест
    проходит.

    Ловит мутацию: уборка отпускает пробник не тем файлом
    (`release-tree-<метка>`) — пробник висит, процессы пульта к снятию
    групп ещё работают, наблюдение их перечислит.
    """
    module = importlib.import_module(LOCK_MODULE)
    sandbox = module.LockSandbox
    real_stop = sandbox.stop_everything
    real_pid_alive = module.pid_alive
    seen = {"running": None, "alive": []}

    def observed(self):
        real_kill = type(self).kill_group

        def kill_group(pgid):
            if seen["running"] is None:
                seen["running"] = [c.label for c in self.children
                                   if c.proc.poll() is None]
            real_kill(pgid)

        def pid_alive(pid):
            alive = real_pid_alive(pid)
            if alive:
                seen["alive"].append(pid)
            return alive

        self.kill_group = kill_group
        with mock.patch.object(module, "pid_alive", pid_alive):
            real_stop(self)

    result = unittest.TestResult()
    with mock.patch.object(sandbox, "stop_everything", observed):
        getattr(module, cls_name)(name).run(result)
    assert result.wasSuccessful(), [text for _, text in
                                    result.errors + result.failures]
    assert not seen["running"], (
        f"уборка дождалась предела: к снятию групп работали {seen['running']}")
    assert not seen["alive"], f"уборка сняла живые процессы {seen['alive']}"


# --- AC-7 -----------------------------------------------------------------

def test_ac7_no_temporary_files_in_working_copy():
    """Пути задачи — только файлы зоны; замок ждали через --wait-lock.

    Пути задачи по правилу гейта зон (`changed_paths`: закоммиченный дифф
    от базы и неотслеживаемые файлы вне `tasks/<id>/`) обязаны лежать в
    {два тестовых файла, docs/codebase-map.md}; PLAN, приводящий команды
    mutation-run, называет флаг `--wait-lock`.

    Ловит мутацию: шаг оставил в рабочей копии файл замера (например
    `timing.txt` или `mutation-001.diff` в корне) — он появится среди
    путей задачи вне зоны.
    """
    extra = sorted(set(changed_paths()) - ZONE_PATHS)
    assert not extra, f"в рабочей копии файлы вне зоны задачи: {extra}"
    plan = artifact_text("PLAN.md")
    assert plan is not None, "в документах задачи нет PLAN.md"
    assert "--wait-lock" in plan, "PLAN не показывает ожидание замка --wait-lock"
