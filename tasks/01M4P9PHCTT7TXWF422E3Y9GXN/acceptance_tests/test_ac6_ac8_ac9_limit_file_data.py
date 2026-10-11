"""AC-6, AC-8, AC-9: данные изменённых методов файла full_suite_limit_runs,
отсутствие запрещённых средств стабилизации, нетронутые `tests/sandbox.py`,
текст `PROBE_TEST` и подмены `config.FULL_SUITE_WORKERS`.

Группа: разовый
Зелёный с рождения: в main пределы методов уже держат N < C < hold и C ≠ 900, повторов, маркеров перезапуска и пропусков в файле нет, а сравнение ветки с main до правки совпадает тождественно; планка держит, что правка задачи этого не нарушила.

Пределы (C, N) и `hold` метода читаются исполнением его тела, а не
разбором текста: генератор `self.rng` заменён «плановым», который на каждом
вызове `randint`/`randrange`/`uniform` отдаёт заданную границу диапазона (и
900, если оно внутри целого диапазона); перебираются все сочетания границ.
Метод гейта мержа идёт без песочницы: `set_config_limit` записывает C,
`prepare` — N (`profile_limit`), а пробник (`probe_test`) — `hold` и
обрывает сценарий до первого обращения к git. Метод `test_ac5_*` идёт в
настоящей песочнице своего класса: `add_project_task` записывает N, пробник —
`hold`, а запуск `suite-run` (`cli`) обрывает сценарий; C у него — предел
копии пульта `COPY_LIMIT`.

Валидация стабом (11.10): поднятые пределы (C 50–60, N 20–25 и т. п.) —
зелено; C `test_ac4_*` 890–910, N ac3_cut 45–55 при C 50–60, N `test_ac5_*`
50–65, `approve` в цикле и `@unittest.skipIf` на методе — каждое названо в
провале.
"""
# AC-1: manual — пять прогонов подряд под нагрузкой (по числу ядер процессов `while 1: pass`) каждого изменённого метода (не меньше трёх методов по десяткам секунд каждый) суммарно превышают предел всего прогона планки на гейте `config.ACCEPTANCE_TIMEOUT_SEC` (300 с), который делят и остальные критерии; повторяемость под нагрузкой — статистическое свойство машины, детерминированным тестом в этом пределе не проверяется. Оператор прогоняет файл под нагрузкой 5 раз на приёмке (нагрузка — `_util.cpu_load`, прогон — `python3 -m pytest tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`).
# AC-2: manual — красноту main под нагрузкой детерминированно не воспроизвести (она зависит от машины и случайных пределов), а запасная ветвь критерия — «причина показана замером в PLAN» — оценка рассуждения по существу; Оператор сверяет PLAN.
# AC-7: manual — сравнение времени файла на ветке и на main без нагрузки требует двух полных прогонов файла (~50 с в main и до ~80 с на ветке) плюс прогоны каждого метода под нагрузкой — сверх предела всего прогона планки `config.ACCEPTANCE_TIMEOUT_SEC` (300 с); время прогона к тому же шумит от загрузки машины гейта. Оператор сверяет замер PLAN и прогон на приёмке.
import ast
import importlib
import inspect
import itertools
import random
import re
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402

if str(_util.ROOT) not in sys.path:
    sys.path.insert(0, str(_util.ROOT))

MAIN_CONFIG_LIMIT = 900
AC5_COPY_CEILING = 60
MAX_COMBOS = 4096


class _Stop(Exception):
    """Сценарий метода дошёл до точки, где все данные уже записаны."""


def _int_candidates(lo: int, hi: int) -> list:
    values = {lo, hi}
    if lo <= MAIN_CONFIG_LIMIT <= hi:
        values.add(MAIN_CONFIG_LIMIT)
    return sorted(values)


class PlannedRandom:
    """Генератор с заданным выбором границы на каждом вызове
    `randint`/`randrange`/`uniform`; прочее — настоящему `random.Random`."""

    def __init__(self, plan: tuple | None, seed: int = 0):
        self._real = random.Random(seed)
        self.plan = plan
        self.draws = []

    def _draw(self, kind: str, candidates: list):
        index = len(self.draws)
        self.draws.append((kind, tuple(candidates)))
        if self.plan is None or index >= len(self.plan):
            return candidates[0]
        return candidates[self.plan[index]]

    def randint(self, a, b):
        return self._draw("randint", _int_candidates(a, b))

    def randrange(self, start, stop=None, step=1):
        lo, hi = (0, start - 1) if stop is None else (start, stop - 1)
        return self._draw("randrange", _int_candidates(lo, hi))

    def uniform(self, a, b):
        return self._draw("uniform", sorted({a, b}))

    def __getattr__(self, name):
        return getattr(self._real, name)


def _bind(func, inst, args, kwargs) -> dict:
    bound = inspect.signature(func).bind(inst, *args, **kwargs)
    bound.apply_defaults()
    return dict(bound.arguments)


def _limit_module():
    return importlib.import_module(_util.LIMIT_MODULE)


def _gate_values(mod, key: str, plan) -> tuple:
    """(записанные значения, генератор) одного прогона тела метода гейта."""
    cls_name, name = _util.LIMIT_METHODS[key]
    cls = getattr(mod, cls_name)
    inst = cls(name)
    inst.seed = 0
    rng = PlannedRandom(plan)
    inst.rng = rng
    rec = {}

    def set_config_limit(*args, **kwargs):
        rec["C"] = _bind(cls.set_config_limit, inst, args, kwargs)["seconds"]

    def prepare(*args, **kwargs):
        rec["N"] = _bind(cls.prepare, inst, args, kwargs)["profile_limit"]
        return cls.prepare(inst, *args, **kwargs)

    def probe_test(*args, **kwargs):
        rec["hold"] = _bind(cls.probe_test, inst, args, kwargs)["hold"]
        raise _Stop

    def approve(*args, **kwargs):
        raise _Stop

    inst.set_config_limit = set_config_limit
    inst.prepare = prepare
    inst.probe_test = probe_test
    inst.approve = approve
    fake_random = types.SimpleNamespace(
        randint=rng.randint, randrange=rng.randrange, uniform=rng.uniform,
        choice=rng.choice, Random=random.Random)
    with mock.patch.object(mod, "random", fake_random):
        try:
            getattr(inst, name)()
        except _Stop:
            pass
    return rec, rng


def _plans(discovery: PlannedRandom):
    sizes = [len(candidates) for _, candidates in discovery.draws]
    combos = 1
    for size in sizes:
        combos *= size
    if combos > MAX_COMBOS:
        raise AssertionError(f"сочетаний границ {combos} > {MAX_COMBOS}")
    return list(itertools.product(*[range(size) for size in sizes]))


def _calls_named(node, names: set) -> list:
    found = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            label = (func.attr if isinstance(func, ast.Attribute)
                     else func.id if isinstance(func, ast.Name) else None)
            if label in names:
                found.append(label)
    return found


def _loops(node) -> list:
    return [sub for sub in ast.walk(node)
            if isinstance(sub, (ast.For, ast.AsyncFor, ast.While, ast.ListComp,
                                ast.SetComp, ast.DictComp, ast.GeneratorExp))]


def _probe_test_value(source: str) -> str | None:
    for node in ast.parse(source).body:
        if (isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "PROBE_TEST"
                        for t in node.targets)
                and isinstance(node.value, ast.Constant)):
            return node.value.value
    return None


class ChangedMethodLimitsTest(unittest.TestCase):

    def test_ac6_gate_methods_keep_n_below_c_below_hold_over_whole_range(self):
        """Методы гейта мержа: N < C < hold (без N — C < hold), C ≠ 900.

        Сценарий: для каждого изменённого метода гейта (ac3_cut,
        `test_ac4_*`, изменённые `test_ac6_*`/`test_ac7_*`) тело исполняется
        на каждом сочетании границ диапазонов генератора; записанные C, N и
        `hold` сверяются с неравенствами критерия.

        Ловит мутацию: подъём пределов вывел их за рамку — например, N
        ac3_cut поднят до диапазона, пересекающего C (`randint(40, 60)` при C
        40–50), или C `test_ac4_*` поднят выше `hold`, или диапазон C задел
        900 — на границе диапазона неравенство нарушено, тест называет метод
        и значения.
        """
        mod = _limit_module()
        problems = []
        for key in _util.changed_limit_methods():
            if key == "ac5":
                continue
            _, discovery = _gate_values(mod, key, None)
            for plan in _plans(discovery):
                rec, rng = _gate_values(mod, key, plan)
                if [d for d, _ in rng.draws] != [d for d, _ in discovery.draws]:
                    problems.append(f"{key}: порядок вызовов генератора "
                                    f"меняется от значений")
                    break
                c, n, hold = rec.get("C"), rec.get("N"), rec.get("hold")
                if c is None or hold is None:
                    problems.append(f"{key}: сценарий не записал C или hold "
                                    f"({rec})")
                    break
                bad = []
                if n is not None and not n < c:
                    bad.append("N < C")
                if not c < hold:
                    bad.append("C < hold")
                if c == MAIN_CONFIG_LIMIT:
                    bad.append("C ≠ 900")
                if bad:
                    problems.append(f"{key}: нарушено {', '.join(bad)} при "
                                    f"C={c}, N={n}, hold={hold}")
        self.assertFalse(problems, "\n".join(problems))

    def test_ac6_suite_run_method_keeps_n_below_copy_limit_and_60(self):
        """`test_ac5_*`: N < 60, N < C (`COPY_LIMIT`) < hold, C ≠ 900.

        Сценарий: настоящая песочница класса `SuiteRunProfileLimitTest`;
        тело метода исполняется на каждом сочетании границ генератора до
        запуска `suite-run`; N — аргумент `add_project_task`, `hold` —
        аргумент пробника ветки задачи.

        Ловит мутацию: N `test_ac5_*` поднят до 60 и выше (`randint(50, 65)`)
        либо `hold` пробника оставлен ниже предела копии — на границе
        диапазона неравенство нарушено, тест называет значения.
        """
        mod = _limit_module()
        cls_name, name = _util.LIMIT_METHODS["ac5"]
        cls = getattr(mod, cls_name)
        inst = cls(name)
        inst.setUp()
        problems = []
        try:
            c = inst.COPY_LIMIT

            def once(plan, seed):
                rng = PlannedRandom(plan, seed)
                inst.rng = rng
                rec = {}
                real_add, real_probe = cls.add_project_task, cls.probe_test

                def add_project_task(*args, **kwargs):
                    rec["N"] = _bind(real_add, inst, args, kwargs)["limit"]
                    return real_add(inst, *args, **kwargs)

                def probe_test(*args, **kwargs):
                    rec["hold"] = _bind(real_probe, inst, args, kwargs)["hold"]
                    return real_probe(inst, *args, **kwargs)

                def cli(*args, **kwargs):
                    raise _Stop

                with mock.patch.object(inst, "add_project_task",
                                       add_project_task, create=True), \
                        mock.patch.object(inst, "probe_test", probe_test,
                                          create=True), \
                        mock.patch.object(inst, "cli", cli, create=True):
                    try:
                        getattr(inst, name)()
                    except _Stop:
                        pass
                return rec, rng

            _, discovery = once(None, 1)
            for index, plan in enumerate(_plans(discovery)):
                rec, _ = once(plan, index + 2)
                n, hold = rec.get("N"), rec.get("hold")
                if n is None or hold is None:
                    problems.append(f"сценарий не записал N или hold ({rec})")
                    break
                bad = []
                if not n < AC5_COPY_CEILING:
                    bad.append("N < 60")
                if not n < c:
                    bad.append("N < C")
                if not c < hold:
                    bad.append("C < hold")
                if c == MAIN_CONFIG_LIMIT:
                    bad.append("C ≠ 900")
                if bad:
                    problems.append(f"нарушено {', '.join(bad)} при N={n}, "
                                    f"C={c}, hold={hold}")
        finally:
            inst.tearDown()
            inst.doCleanups()
        self.assertFalse(problems, "test_ac5_*: " + "\n".join(problems))

    def test_ac6_no_repeat_rerun_skip_or_foreign_start_record(self):
        """Ни повтора сценария, ни маркеров перезапуска, ни пропуска, ни
        записи «start» не пробником.

        Сценарий: разбор файла ветки против main — (1) в изменённых методах
        вызовы `approve`/`prepare`/`cli`/`add_project_task`/`cmd_approve` не
        стоят в цикле, а в помощниках `approve`/`prepare`/`cli`/
        `add_project_task` циклов не больше, чем в main; (2) новых имён
        `skip*`/`flaky`/`rerun*`/`retry*` и новых декораторов у методов
        нет; (3) вне `PROBE_TEST` нет записи в журнал пробника
        (`self.records`) и литерала события «start» вне `events(...)`.

        Ловит мутацию: стабилизация повтором — `for _ in range(3): out, _ =
        self.approve()` — или `@unittest.skipIf(...)`/`@pytest.mark.flaky`
        на методе, или `self.records.write_text('{"event": "start"…')` в
        тесте — тест называет нарушение и место.
        """
        main_src = _util.main_text(_util.LIMIT_FILE)
        branch_src = _util.branch_text(_util.LIMIT_FILE)
        problems = []
        scenario = {"approve", "prepare", "cli", "add_project_task",
                    "cmd_approve", "set_config_limit", "set_profile_limit"}
        for key in _util.changed_limit_methods():
            cls_name, name = _util.LIMIT_METHODS[key]
            node = _util.method_node(branch_src, cls_name, name)
            if node is None:
                problems.append(f"{key}: метода {cls_name}.{name} нет")
                continue
            for loop in _loops(node):
                inside = _calls_named(loop, scenario)
                if inside:
                    problems.append(f"{key}: сценарий в цикле (строка "
                                    f"{loop.lineno}): {sorted(set(inside))}")
            main_node = _util.method_node(main_src, cls_name, name)
            main_decos = ([ast.dump(d) for d in main_node.decorator_list]
                          if main_node else [])
            new_decos = [ast.unparse(d) for d in node.decorator_list
                         if ast.dump(d) not in main_decos]
            if new_decos:
                problems.append(f"{key}: новые декораторы {new_decos}")
        for cls_name, helper in (("MergeGateLimitSandbox", "approve"),
                                 ("MergeGateLimitSandbox", "prepare"),
                                 ("SuiteRunLimitSandbox", "cli"),
                                 ("SuiteRunLimitSandbox", "add_project_task"),
                                 ("ProbeSandbox", "probe_test"),
                                 ("ProbeSandbox", "events")):
            before = _util.method_node(main_src, cls_name, helper)
            after = _util.method_node(branch_src, cls_name, helper)
            if after is not None and before is not None and \
                    len(_loops(after)) > len(_loops(before)):
                problems.append(f"{cls_name}.{helper}: новый цикл")

        banned = re.compile(r"(?i)skip|flaky|rerun|retry")

        def names(source):
            found = set()
            for sub in ast.walk(ast.parse(source)):
                if isinstance(sub, ast.Name) and banned.search(sub.id):
                    found.add(sub.id)
                elif isinstance(sub, ast.Attribute) and banned.search(sub.attr):
                    found.add(sub.attr)
                elif (isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                      and re.search(r"(?i)\b(flaky|reruns?)\b", sub.value)):
                    found.add(sub.value[:60])
            return found

        new_names = names(branch_src) - names(main_src)
        if new_names:
            problems.append(f"новые имена пропуска/перезапуска: "
                            f"{sorted(new_names)}")

        tree = ast.parse(branch_src)
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                child.parent = parent
        probe = None
        for node in tree.body:
            if (isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "PROBE_TEST"
                            for t in node.targets)):
                probe = node
        probe_nodes = set(map(id, ast.walk(probe))) if probe else set()
        for sub in ast.walk(tree):
            if id(sub) in probe_nodes:
                continue
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                if re.search(r"""["']?event["']?\s*:\s*["']?start""", sub.value):
                    problems.append(f"строка {sub.lineno}: литерал события "
                                    f"start вне PROBE_TEST")
                elif sub.value == "start":
                    call = getattr(sub, "parent", None)
                    func = getattr(call, "func", None)
                    if not (isinstance(call, ast.Call)
                            and isinstance(func, ast.Attribute)
                            and func.attr == "events"):
                        problems.append(f"строка {sub.lineno}: «start» вне "
                                        f"events(...)")
            if isinstance(sub, ast.Attribute) and sub.attr == "records":
                parent = getattr(sub, "parent", None)
                if isinstance(parent, ast.Attribute) and parent.attr in (
                        "write_text", "write_bytes", "open"):
                    problems.append(f"строка {sub.lineno}: запись в журнал "
                                    f"пробника вне PROBE_TEST")
                if (isinstance(parent, ast.Call)
                        and isinstance(parent.func, ast.Name)
                        and parent.func.id == "open"):
                    problems.append(f"строка {sub.lineno}: open() журнала "
                                    f"пробника вне PROBE_TEST")
        self.assertFalse(problems, "\n".join(problems))


class SandboxUnchangedTest(unittest.TestCase):

    def test_ac8_sandbox_matches_main(self):
        """`tests/sandbox.py` ветки побайтно равен main.

        Сценарий: текст файла в рабочей копии сравнивается с текстом в базе
        диффа задачи.

        Ловит мутацию: стабилизация через помощник песочницы — например,
        `wait_processes_gone` с бо́льшим сроком или новый параметр
        `RealGitSandbox` — текст расходится с main, тест покраснеет.
        """
        self.assertEqual(_util.branch_text(_util.SANDBOX_FILE),
                         _util.main_text(_util.SANDBOX_FILE),
                         "tests/sandbox.py на ветке отличается от main")


class ProbeAndWorkersUnchangedTest(unittest.TestCase):

    def test_ac9_probe_text_and_workers_substitutions_match_main(self):
        """`PROBE_TEST` и обе подмены `FULL_SUITE_WORKERS` — как в main.

        Сценарий: значение константы `PROBE_TEST` (с местом `note("start")`
        первой строкой тела `test_{name}`) на ветке и в main сравнивается
        дословно; строки файла, называющие `FULL_SUITE_WORKERS`, на ветке и
        в main совпадают, и среди них есть
        `mock.patch.object(config, "FULL_SUITE_WORKERS", "1")` и дописка
        `FULL_SUITE_WORKERS = '1'` в `config.py` копии пульта.

        Ловит мутацию: `note("start")` перенесён до цикла импорта/в начало
        модуля пробника или подмена воркеров снята («-n 1» → без
        `FULL_SUITE_WORKERS`) ради быстрого старта — текст расходится с
        main, тест покраснеет.
        """
        main_src = _util.main_text(_util.LIMIT_FILE)
        branch_src = _util.branch_text(_util.LIMIT_FILE)
        main_probe = _probe_test_value(main_src)
        self.assertIsNotNone(main_probe, "PROBE_TEST в main не найден")
        self.assertIn('def test_{name}():\n    note("start")\n', main_probe)
        self.assertEqual(_probe_test_value(branch_src), main_probe,
                         "текст PROBE_TEST на ветке отличается от main")

        def workers(source):
            return [line.strip() for line in source.splitlines()
                    if "FULL_SUITE_WORKERS" in line
                    and not line.strip().startswith("#")]

        self.assertEqual(workers(branch_src), workers(main_src),
                         "строки с FULL_SUITE_WORKERS отличаются от main")
        self.assertIn('mock.patch.object(config, "FULL_SUITE_WORKERS", "1")',
                      branch_src)
        self.assertIn("\"FULL_SUITE_WORKERS = '1'\\n\"", branch_src)


if __name__ == "__main__":
    unittest.main()
