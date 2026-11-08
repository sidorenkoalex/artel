"""Перевод тестового файла `suite-run`: константы, уборка, проверка процессов вместо пауз, усиления ac16/ac24.

Группа: разовый
Красен до реализации: тестовый файл suite-run ещё не переведён — в config нет SUITE_RUN_POLL_SEC, копия config.py песочницы его не задаёт, stop_everything ждёт собственный процесс теста (20 с), пределы 15/5 вместо 8/3, у ac16 гейта нет сверки outcome, у ac24 нет «не уложился» и итоговой строки базы, в assert_no_run/ac9/ac20/ac21 стоят паузы time.sleep без снимка /bin/ps; test_ac9 зелёный с рождения — состав и прежние утверждения файла должны сохраниться.

Предмет — сам файл `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py`
рабочей копии задачи: его модуль импортируется (поведение
`stop_everything`, копия `config.py` песочницы, константы классов), а
формы, которые проверяются только по тексту теста (сверка `outcome`
гейта ac16, усиление ac24, порядок «снимок процессов — журналы» в
`assert_no_run`/ac9/ac20/ac21), — разбором AST: вызов метода `self.<имя>`
или функции модуля разворачивается в его тело, так что вынос проверки в
помощник файла законен. Прежний текст файла — с базы ветки
(`DIFF_BASE` помощника пульта), `git show`.
"""
# AC-10: manual — убийство мутаций видно только прогоном пульта `mutation-run --ref base` и `--ref head` по всему файлу suite_run (26 тестов с живыми фоновыми процессами и вложенным pytest, ~250 с на ревизию на каждую мутацию) — это прогон пульта под замком машины, не укладывающийся в предел 120 с теста планки; SPEC сам называет его «прогон пульта mutation-run, не тест набора», таблицу сверяет независимый агент на приёмке.
import ast
import importlib
import json
import os
import random
import subprocess
import sys
import tempfile
import threading
from collections import Counter
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

from orchestrator import acceptance, config  # noqa: E402

REL = "tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py"
MODULE = "tests.test_01m462qaceh29rprd2rzhghqfm_suite_run"
TESTS = (
    ("RunShapeTest", "test_ac1_branch_run_in_workspace_with_profile_and_workers"),
    ("RunShapeTest", "test_ac2_uncommitted_edit_is_seen_by_run"),
    ("ProfileRefusalTest", "test_ac3_project_without_profile_is_refused"),
    ("ProfileRefusalTest", "test_ac4_non_pytest_profile_command_is_refused"),
    ("RoleEnvironmentTest", "test_ac5_runs_have_no_artel_role_in_environment"),
    ("RoleEnvironmentTest", "test_ac22_role_process_is_not_refused"),
    ("BackgroundTest", "test_ac6_returns_before_run_ends_and_run_survives_caller"),
    ("BackgroundTest", "test_ac7_second_launch_reports_running_run"),
    ("BackgroundTest", "test_ac8_wait_reports_finished_or_still_running"),
    ("BackgroundTest", "test_ac9_wait_without_any_run_is_refused"),
    ("BackgroundTest", "test_ac10_wait_above_limit_is_refused_without_waiting"),
    ("TimeoutTest", "test_ac11_branch_run_over_limit_reports_partial_numbers"),
    ("BaseComparisonTest", "test_ac12_failures_split_into_new_and_also_on_base"),
    ("BaseComparisonTest", "test_ac13_gate_full_suite_result_is_reused_as_base"),
    ("BaseComparisonTest", "test_ac14_base_run_in_temporary_copy_at_diff_base"),
    ("BaseComparisonTest", "test_ac15_same_base_is_run_once_across_runs_and_tasks"),
    ("BaseTimeoutTest", "test_ac16_timed_out_base_is_not_saved"),
    ("BaseTimeoutTest", "test_ac16_timed_out_gate_run_saves_nothing"),
    ("ReportTest", "test_ac17_report_numbers_groups_examples_and_log"),
    ("ReportTest", "test_ac18_groups_and_signature_line_are_capped"),
    ("FailedRerunTest", "test_ac19_failed_reruns_exactly_last_failures"),
    ("FailedRerunTest", "test_ac20_failed_without_previous_run_is_refused"),
    ("LockTest", "test_ac21_single_run_lock_refuses_and_releases"),
    ("FootprintTest", "test_ac23_task_state_untouched_and_no_files_outside_state"),
    ("FootprintTest", "test_ac24_base_copy_removed_on_every_outcome"),
    ("MissionTest", "test_ac25_developer_mission_names_suite_run_with_pult_path"),
)
JOURNAL_CALLS = {"calls", "branch_calls", "base_calls", "read_jsonl"}
JOURNAL_ATTRS = {"calls_file", "pytest_file"}
ONE_ARG = {"assertTrue", "assertFalse", "assertIsNone", "assertIsNotNone"}


# --- разбор файла ------------------------------------------------------------

def head_text() -> str:
    return (Path(CODE_ROOT) / REL).read_text(encoding="utf-8")


def base_text() -> str:
    assert DIFF_BASE, "база диффа задачи не посчитана помощником пульта"
    proc = subprocess.run(
        ["git", "-C", str(CODE_ROOT), "show", f"{DIFF_BASE}:{REL}"],
        capture_output=True, text=True, timeout=60, start_new_session=True)
    assert proc.returncode == 0, f"git show базы: {proc.stderr}"
    return proc.stdout


class Source:
    """AST файла: функции модуля, методы классов, строковые константы."""

    def __init__(self, text: str):
        self.tree = ast.parse(text)
        self.functions = {}
        self.methods = {}
        self.classes = {}
        self.strings = {}
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef):
                self.functions[node.name] = node
            elif isinstance(node, ast.ClassDef):
                self.classes[node.name] = node
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        self.methods.setdefault(item.name, item)
            elif (isinstance(node, ast.Assign) and len(node.targets) == 1
                  and isinstance(node.targets[0], ast.Name)
                  and isinstance(node.value, ast.Constant)
                  and isinstance(node.value.value, str)):
                self.strings[node.targets[0].id] = node.value.value

    def method(self, cls: str, name: str) -> ast.FunctionDef:
        for item in self.classes[cls].body:
            if isinstance(item, ast.FunctionDef) and item.name == name:
                return item
        raise AssertionError(f"{cls}.{name} нет в {REL}")

    def callee(self, call: ast.Call):
        func = call.func
        if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                and func.value.id == "self"):
            return self.methods.get(func.attr)
        if isinstance(func, ast.Name):
            return self.functions.get(func.id)
        return None

    def text_of(self, node) -> str:
        """Строковые константы узла, имена констант модуля — их значением."""
        parts = []
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                parts.append(sub.value)
            elif isinstance(sub, ast.Name) and sub.id in self.strings:
                parts.append(self.strings[sub.id])
        return "\n".join(parts)

    def events(self, func: ast.FunctionDef) -> list:
        """События тела в порядке исполнения, вызовы помощников файла
        развёрнуты: ("cli0", узел) — прямой вызов `self.cli` в самом теле;
        ("ps",) — строка с `/bin/ps`; ("journal",) — чтение журналов
        обёртки/`conftest.py`; ("sleep", глубина) — `time.sleep`."""
        out = []

        def visit(node, depth, stack):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if "/bin/ps" in node.value:
                    out.append(("ps",))
                return
            if isinstance(node, ast.Name) and self.strings.get(node.id, "") \
                    .find("/bin/ps") >= 0:
                out.append(("ps",))
                return
            if isinstance(node, ast.Attribute) and node.attr in JOURNAL_ATTRS:
                out.append(("journal",))
            if isinstance(node, ast.Call):
                for child in [*node.args, *node.keywords]:
                    visit(child, depth, stack)
                func_node = node.func
                if isinstance(func_node, ast.Attribute):
                    visit(func_node.value, depth, stack)
                    if func_node.attr == "sleep" and isinstance(
                            func_node.value, ast.Name) \
                            and func_node.value.id == "time":
                        out.append(("sleep", depth))
                    if func_node.attr in JOURNAL_CALLS:
                        out.append(("journal",))
                    if func_node.attr == "cli" and depth == 0:
                        out.append(("cli0", node))
                if isinstance(func_node, ast.Attribute) and \
                        func_node.attr == "cli":
                    return
                target = self.callee(node)
                if target is not None and target.name not in stack \
                        and len(stack) < 6:
                    for stmt in target.body:
                        visit(stmt, depth + 1, stack | {target.name})
                return
            for child in ast.iter_child_nodes(node):
                visit(child, depth, stack)

        for stmt in func.body:
            visit(stmt, 0, frozenset({func.name}))
        return out

    def closure(self, func: ast.FunctionDef) -> list:
        """Функция и все помощники файла, достижимые из неё вызовами."""
        seen, todo = {}, [func]
        while todo:
            node = todo.pop()
            if node.name in seen:
                continue
            seen[node.name] = node
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    target = self.callee(sub)
                    if target is not None:
                        todo.append(target)
        return list(seen.values())


def assertion_keys(source: Source) -> Counter:
    """Утверждения файла без текста сообщения: имя и проверяемые аргументы;
    свои помощники файла с именем `assert*` утверждениями не считаются."""
    keys = Counter()
    for node in ast.walk(source.tree):
        if isinstance(node, ast.Assert):
            keys[("assert", ast.unparse(node.test))] += 1
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr.startswith("assert")
              and node.func.attr not in source.methods):
            take = 1 if node.func.attr in ONE_ARG else 2
            keys[(node.func.attr,
                  *(ast.unparse(a) for a in node.args[:take]))] += 1
    return keys


def suite_module():
    return importlib.import_module(MODULE)


# --- AC-1 ----------------------------------------------------------------------

def test_ac1_config_poll_step_and_no_own_constant_in_suite_run():
    """В config шаг опроса 1.0, у `suite_run.py` своей константы шага нет.

    Сценарий: `config.SUITE_RUN_POLL_SEC` читается в процессе теста; текст
    `orchestrator/suite_run.py` разбирается AST — среди присваиваний уровня
    модуля нет имени с `POLL` (прежняя `_POLL_SEC = 1.0`).

    Ловит мутацию: константа заведена со значением, отличным от 1.0
    (поведение пульта по умолчанию меняется) — сравнение падает; в
    `suite_run.py` осталась `_POLL_SEC` рядом с новой константой config —
    имя найдено разбором.
    """
    assert getattr(config, "SUITE_RUN_POLL_SEC", None) == 1.0
    tree = ast.parse((Path(CODE_ROOT) / "orchestrator" / "suite_run.py")
                     .read_text(encoding="utf-8"))
    own = []
    for node in tree.body:
        targets = (node.targets if isinstance(node, ast.Assign) else
                   [node.target] if isinstance(node, ast.AnnAssign) else [])
        own += [t.id for t in targets
                if isinstance(t, ast.Name) and "POLL" in t.id.upper()]
    assert own == [], f"собственная константа шага опроса в suite_run.py: {own}"


# --- AC-3 ----------------------------------------------------------------------

def test_ac3_sandbox_config_copy_sets_poll_step():
    """Копия `config.py` песочницы suite-run задаёт `SUITE_RUN_POLL_SEC = 0.1`.

    Сценарий: песочница файла (`SuiteRunSandbox.setUp`) собирается
    по-настоящему во временном каталоге; текст копии
    `<корень песочницы>/orchestrator/config.py` разбирается AST — последнее
    присваивание `SUITE_RUN_POLL_SEC` уровня модуля равно 0.1. Песочница
    убирается своей уборкой.

    Ловит мутацию: дописка песочницы не задаёт шаг — в копии остаётся
    значение пульта 1.0; шаг задан иным значением (`1`, `0.5`) — значение
    не 0.1.
    """
    mod = suite_module()
    box = mod.SuiteRunSandbox()
    try:
        box.setUp()
        text = (box.root / "orchestrator" / "config.py").read_text(
            encoding="utf-8")
    finally:
        box.doCleanups()
    values = []
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "SUITE_RUN_POLL_SEC"
                for t in node.targets):
            values.append(ast.literal_eval(node.value))
    assert values, "копия config.py песочницы не задаёт SUITE_RUN_POLL_SEC"
    assert values[-1] == 0.1, f"значения SUITE_RUN_POLL_SEC в копии: {values}"


# --- AC-4 ----------------------------------------------------------------------

def test_ac4_stop_everything_waits_children_but_not_own_process():
    """Уборка ждёт смерти записанных потомков, но не процесса теста.

    Сценарий: журнал обёртки несёт только `os.getpid()` и одноразовые
    дочерние `/bin/sleep` самого теста (одни — в поле `pid`, другие — в
    поле `ppid`), паузы потомков — доли секунды от зерна; каждого потомка
    пожинает свой поток. `SuiteRunSandbox.stop_everything` экземпляра с этим
    журналом проверяет живость (обёрнутая `pid_alive` модуля записывает
    каждый проверенный pid): каждый потомок проверялся, `os.getpid()` — ни
    разу; потомки завершились сами (код 0), а не добиты SIGKILL.

    Ловит мутацию: `os.getpid()` не исключён из ожидания (прежний код) —
    его pid среди проверенных, уборка ждёт 20 с; вместе с процессом теста
    отброшены записи `ppid` или все потомки — их pid не проверялся, и
    они остаются жить; ожидание без потомков, а добивание с ними — код
    потомка -9.
    """
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    mod = suite_module()
    probe = Path(tempfile.mkdtemp(prefix="artel-ac4-probe-")).resolve()
    children, reapers = [], []
    try:
        for _ in range(2 + rng.randrange(3)):
            proc = subprocess.Popen(
                ["/bin/sleep", f"{rng.uniform(0.2, 0.9):.2f}"],
                start_new_session=True)
            children.append(proc)
            reaper = threading.Thread(target=proc.wait, daemon=True)
            reaper.start()
            reapers.append(reaper)
        me = os.getpid()
        lines = []
        for index, proc in enumerate(children):
            row = ({"pid": proc.pid, "ppid": me} if index % 2 == 0 else
                   {"pid": me, "ppid": proc.pid})
            lines.append(json.dumps(row))
        calls = probe / "calls.jsonl"
        calls.write_text("\n".join(lines) + "\n", encoding="utf-8")
        box = mod.SuiteRunSandbox()
        box.probe = probe
        box.calls_file = calls
        box.release_file = probe / "release"
        box.pytest_file = probe / "pytest.jsonl"
        checked = []
        real = mod.pid_alive

        def watched(pid):
            checked.append(pid)
            return real(pid)

        with mock.patch.object(mod, "pid_alive", watched):
            mod.SuiteRunSandbox.stop_everything(box)
        for reaper in reapers:
            reaper.join(10)
        assert me not in checked, (f"процесс теста {me} в ожидании уборки; "
                                   f"зерно: {seed}")
        for proc in children:
            assert proc.pid in checked, (f"потомок {proc.pid} выпал из "
                                         f"ожидания; зерно: {seed}")
            assert proc.returncode == 0, (f"потомок {proc.pid}: код "
                                          f"{proc.returncode} — не дождались; "
                                          f"зерно: {seed}")
    finally:
        for proc in children:
            if proc.poll() is None:
                proc.kill()
                proc.wait(10)


# --- AC-5 ----------------------------------------------------------------------

def gate_timeout_values(source: Source, mod) -> list:
    """Значения `FULL_SUITE_TIMEOUT_SEC` в `mock.patch.object` ac16 гейта."""
    func = source.method("BaseTimeoutTest",
                         "test_ac16_timed_out_gate_run_saves_nothing")
    values = []
    for node in ast.walk(func):
        if not (isinstance(node, ast.Call) and len(node.args) >= 3
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "FULL_SUITE_TIMEOUT_SEC"):
            continue
        arg = node.args[2]
        if isinstance(arg, ast.Constant):
            values.append(arg.value)
        elif isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name) \
                and arg.value.id in ("self", "BaseTimeoutTest"):
            values.append(getattr(mod.BaseTimeoutTest, arg.attr))
        elif isinstance(arg, ast.Name):
            values.append(getattr(mod, arg.id))
        else:
            values.append(ast.unparse(arg))
    return values


def test_ac5_limits_are_eight_and_three_seconds():
    """Пределы классов — 8 с, предел гейта ac16 — 3 с.

    Сценарий: модуль тестового файла импортирован; `TIMEOUT_SEC` у
    `FootprintTest`, `BaseTimeoutTest`, `TimeoutTest` сверяются с 8; в
    `test_ac16_timed_out_gate_run_saves_nothing` значение, подставляемое
    `mock.patch.object(config, "FULL_SUITE_TIMEOUT_SEC", …)` (литерал или
    константа класса/модуля), — 3.

    Ловит мутацию: у одного из классов остался прежний предел 15 или взят
    иной (10) — сравнение падает; предел гейта оставлен 5 — значение не 3.
    """
    mod = suite_module()
    for name in ("FootprintTest", "BaseTimeoutTest", "TimeoutTest"):
        assert getattr(mod, name).TIMEOUT_SEC == 8, (
            f"{name}.TIMEOUT_SEC = {getattr(mod, name).TIMEOUT_SEC}")
    values = gate_timeout_values(Source(head_text()), mod)
    assert values == [3], f"предел гейта ac16: {values}"


# --- AC-6 ----------------------------------------------------------------------

def mentions(node, base: str, attr: str) -> bool:
    return any(isinstance(n, ast.Attribute) and n.attr == attr
               and isinstance(n.value, ast.Name) and n.value.id == base
               for n in ast.walk(node))


def test_ac6_gate_timeout_outcome_is_asserted():
    """ac16 гейта сверяет `result.outcome` с `acceptance.FULL_SUITE_TIMEOUT`.

    Сценарий: тело `test_ac16_timed_out_gate_run_saves_nothing` разбирается
    AST. Среди утверждений есть равенство (`assertEqual`/`assertIs` или
    `assert … ==`), связывающее `result.outcome` и
    `acceptance.FULL_SUITE_TIMEOUT`; прежнее `assertFalse(result.green, …)`
    на месте. Константа `acceptance.FULL_SUITE_TIMEOUT` существует.

    Ловит мутацию: усиление не добавлено или сверяет иное поле
    (`result.detail`) либо иную константу (`FULL_SUITE_NOT_STARTED`) —
    равенства с `FULL_SUITE_TIMEOUT` нет; прежняя проверка `green` снята.
    """
    assert hasattr(acceptance, "FULL_SUITE_TIMEOUT")
    func = Source(head_text()).method(
        "BaseTimeoutTest", "test_ac16_timed_out_gate_run_saves_nothing")
    equal, green = False, False
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("assertEqual", "assertIs") and \
                    len(node.args) >= 2:
                pair = ast.Tuple(elts=node.args[:2])
                equal |= (mentions(pair, "result", "outcome") and
                          mentions(pair, "acceptance", "FULL_SUITE_TIMEOUT"))
            if node.func.attr == "assertFalse" and node.args and \
                    ast.unparse(node.args[0]) == "result.green":
                green = True
        if isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare) \
                and isinstance(node.test.ops[0], (ast.Eq, ast.Is)):
            equal |= (mentions(node.test, "result", "outcome") and
                      mentions(node.test, "acceptance", "FULL_SUITE_TIMEOUT"))
    assert equal, "нет сверки result.outcome == acceptance.FULL_SUITE_TIMEOUT"
    assert green, "прежнее assertFalse(result.green) снято"


# --- AC-7 ----------------------------------------------------------------------

def test_ac7_ac24_asserts_no_timeout_and_base_summary():
    """ac24 сверяет отчёт без «не уложился» и итоговую строку лога базы.

    Сценарий: `test_ac24_base_copy_removed_on_every_outcome` и его
    помощники файла разбираются AST. Отчёт берётся как в ac11 — вызовом
    `self.report(…)`; есть отрицательное утверждение (`assertNotIn`/
    `assertNotRegex`/`assert … not in`) с «не уложился»; лог базы
    находится правилом имени пульта — суффикс `-base` — и сверяется с
    итоговой строкой pytest (в тексте проверки — `passed` и `failed`);
    прежние утверждения о копии базы (одна запись базы, каталога нет,
    клон её не числит) на месте.

    Ловит мутацию: усиление отчёта не добавлено или сделано положительным
    (`assertIn`) — отрицательного утверждения нет; лог базы не читается
    либо ищется не по `-base` — суффикса нет; итоговая строка сверяется
    только словом `passed` — у красной базы её не найти, `failed` в
    проверке нет; прежняя проверка копии снята.
    """
    source = Source(head_text())
    func = source.method("FootprintTest",
                         "test_ac24_base_copy_removed_on_every_outcome")
    nodes = source.closure(func)
    calls = [n for f in nodes for n in ast.walk(f) if isinstance(n, ast.Call)]
    assert any(isinstance(c.func, ast.Attribute) and c.func.attr == "report"
               and isinstance(c.func.value, ast.Name)
               and c.func.value.id == "self" for c in calls), \
        "ac24 не читает отчёт self.report(…)"
    negative = False
    for f in nodes:
        for node in ast.walk(f):
            if isinstance(node, ast.Call) and isinstance(node.func,
                                                         ast.Attribute) \
                    and node.func.attr in ("assertNotIn", "assertNotRegex"):
                negative |= "не уложился" in source.text_of(node)
            if isinstance(node, ast.Assert) and any(
                    isinstance(sub, ast.Compare) and any(
                        isinstance(op, ast.NotIn) for op in sub.ops)
                    for sub in ast.walk(node.test)):
                negative |= "не уложился" in source.text_of(node)
    assert negative, "нет утверждения об отсутствии «не уложился» в отчёте"
    text = "\n".join(source.text_of(f) for f in nodes)
    assert "-base" in text, "лог базы не ищется по суффиксу -base"
    for word in ("passed", "failed"):
        assert word in text, f"итоговая строка pytest базы без «{word}»"
    keys = assertion_keys(Source(ast.unparse(func)))
    for key in (("assertEqual", "len(bases)", "1"),
                ("assertFalse", "os.path.exists(place)"),
                ("assertNotIn", "place", "listed")):
        assert keys[key] >= 1, f"прежнее утверждение ac24 {key} снято"


# --- AC-8 ----------------------------------------------------------------------

def ordered_after_command(source: Source, func: ast.FunctionDef,
                          label: str) -> None:
    events = source.events(func)
    starts = [i for i, e in enumerate(events) if e[0] == "cli0"]
    start = starts[0] + 1 if starts else 0
    tail = events[start:]
    kinds = [e[0] for e in tail]
    assert "ps" in kinds, f"{label}: после команды нет снимка /bin/ps"
    first_ps = kinds.index("ps")
    assert "journal" not in kinds[:first_ps], (
        f"{label}: журналы читаются раньше снимка процессов")
    assert "journal" in kinds[first_ps:], (
        f"{label}: после снимка процессов журналы не читаются")
    assert "sleep" not in kinds[:first_ps], (
        f"{label}: пауза time.sleep между командой и снимком процессов")


def test_ac8_process_snapshot_replaces_pauses():
    """Паузы сменены снимком `/bin/ps` сразу после команды, затем журналы.

    Сценарий: AST `assert_no_run`, тестов ac3, ac4, ac9, ac20, ac21 и
    достижимых из них помощников файла. В телах `assert_no_run`, ac9,
    ac20, ac21 нет `time.sleep`. В порядке исполнения после прямого вызова
    команды (`self.cli`) первым идёт снимок процессов (строка `/bin/ps`),
    до него нет ни чтения журналов обёртки/`conftest.py`, ни паузы, после
    него журналы читаются. Снимок — `/bin/ps -axww -o
    pid=,ppid=,command=`, его успешность сверяется с `os.getpid()`, отказ —
    текстом «снимок процессов не получен»; журналы по-прежнему
    утверждаются пустыми.

    Ловит мутацию: пауза оставлена (или перенесена перед снимком) —
    `time.sleep` найден; журналы читаются до снимка — порядок нарушен;
    снимок другим форматом (`ps aux`) — нет `pid=,ppid=,command=`; пустой
    снимок проходит молча — нет сверки с `os.getpid()`.
    """
    source = Source(head_text())
    targets = {
        "assert_no_run": source.method("ProfileRefusalTest", "assert_no_run"),
        "ac9": source.method("BackgroundTest",
                             "test_ac9_wait_without_any_run_is_refused"),
        "ac20": source.method(
            "FailedRerunTest", "test_ac20_failed_without_previous_run_is_refused"),
        "ac21": source.method("LockTest",
                              "test_ac21_single_run_lock_refuses_and_releases"),
    }
    for label, func in targets.items():
        own = [e for e in source.events(func) if e[0] == "sleep" and e[1] == 0]
        assert own == [], f"{label}: в теле осталась пауза time.sleep"
        ordered_after_command(source, func, label)
        text = "\n".join(source.text_of(f) for f in source.closure(func))
        for needle in ("/bin/ps", "-axww", "pid=,ppid=,command=",
                       "снимок процессов не получен"):
            assert needle in text, f"{label}: в проверке процессов нет «{needle}»"
        assert any(mentions(f, "os", "getpid") for f in source.closure(func)), \
            f"{label}: снимок процессов не сверяется с os.getpid()"
    for cls, name in (("ProfileRefusalTest",
                       "test_ac3_project_without_profile_is_refused"),
                      ("ProfileRefusalTest",
                       "test_ac4_non_pytest_profile_command_is_refused")):
        ordered_after_command(source, source.method(cls, name), name)
    keys = assertion_keys(source)
    for key in (("assertEqual", "self.calls()", "[]"),
                ("assertEqual", "self.read_jsonl(self.pytest_file)", "[]"),
                ("assertEqual", "self.branch_calls(wt_b)", "[]")):
        assert keys[key] >= 1, f"утверждение пустого журнала {key} снято"


# --- AC-9 ----------------------------------------------------------------------

def test_ac9_tests_composition_assertions_and_kept_pauses():
    """Состав тестов прежний, без skip, прежние утверждения и паузы ac6/ac8.

    Сценарий: AST файла рабочей копии и того же файла на базе ветки.
    Методы `test_*` по классам — ровно 26 прежних имён; ни декоратора с
    `skip`, ни вызова `skipTest`/`skip*` в классах тестов; каждое
    утверждение базы (имя `assert*` с проверяемыми аргументами, без
    текста сообщения, либо `assert`) встречается в новом тексте не реже;
    `time.sleep(1)` в ac6 и `time.sleep(2)` в ac8 на месте.

    Ловит мутацию: тест переименован, удалён или помечен skip ради
    скорости — состав расходится или skip найден; утверждение снято вместе
    с паузой (`assertEqual(self.calls(), [])`) — счёт утверждения на ветке
    меньше базы; пауза ac6 или ac8 убрана или сокращена — `time.sleep`
    с прежним значением не найден.
    """
    head = Source(head_text())
    base = Source(base_text())
    found = Counter()
    for cls_name, cls in head.classes.items():
        for item in cls.body:
            if isinstance(item, ast.FunctionDef) and item.name.startswith("test"):
                found[(cls_name, item.name)] += 1
    assert found == Counter(TESTS), (
        f"лишние: {sorted(found - Counter(TESTS))}; "
        f"недостающие: {sorted(Counter(TESTS) - found)}")
    for node in ast.walk(head.tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            for deco in node.decorator_list:
                assert "skip" not in ast.unparse(deco).lower(), (
                    f"{node.name}: декоратор {ast.unparse(deco)}")
        if isinstance(node, ast.Call):
            name = (node.func.attr if isinstance(node.func, ast.Attribute)
                    else getattr(node.func, "id", ""))
            assert name not in ("skipTest", "skip", "skipIf", "skipUnless"), (
                f"вызов {ast.unparse(node)[:80]}")
    missing = assertion_keys(base) - assertion_keys(head)
    assert not missing, f"прежние утверждения сняты: {sorted(missing)}"
    for cls, name, seconds in (
            ("BackgroundTest",
             "test_ac6_returns_before_run_ends_and_run_survives_caller", 1),
            ("BackgroundTest",
             "test_ac8_wait_reports_finished_or_still_running", 2)):
        sleeps = [ast.unparse(n) for n in ast.walk(head.method(cls, name))
                  if isinstance(n, ast.Call) and ast.unparse(n.func) ==
                  "time.sleep"]
        assert sleeps == [f"time.sleep({seconds})"], f"{name}: {sleeps}"
