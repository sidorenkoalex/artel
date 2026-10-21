"""Ожидание готовности дескриптора без `select.select`: общая функция нового модуля `tests/`, дескриптор ≥ 1100 в `test_ac9_timeout_kills_group_not_green`, её отдельный тест, неизменные имена `report_outcome` (AC-7…AC-10).

Группа: разовый

Красен до реализации: нового модуля `tests/` с функцией ожидания, которую зовут оба метода, нет — AC-9 падает на её поиске; AC-10 зелёный с рождения — имена и сигнатуры `report_outcome` пока не тронуты, тест держит это на всём пути задачи; AC-7 и AC-8 эскалированы (пометки ниже), их черновики — методы `draft_ac7_…`/`draft_ac8_…`, не собираемые раннером.

Как тест находит функцию ожидания, имени которой SPEC не называет: это
функция модуля `tests/<имя>.py`, которого нет на базе диффа, вызванная в
теле ОБОИХ методов — `VitestReporterTest::test_ac9_timeout_kills_group_not_green`
(`tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`) и
`SeparateSuiteScenarios::test_ac3_timeout_kills_group_and_failure_cleanup_is_bounded`
(`tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py`) — по
импортам файла (`from tests.<имя> import f`, `from tests import <имя>`,
`import tests.<имя> as m`). Номера дескрипторов видит зонд pytest
(`_util.PROBE`): обёртка функции ожидания, `os.read`, `os.close`,
`fcntl.fcntl`, мягкий предел `RLIMIT_NOFILE` на входе и выходе узла.
Мутация «функция вернулась к `select.select`» — зонд подменяет
`selectors.DefaultSelector` (и прочие селекторы) на `SelectSelector`, а
`select.poll` — на обёртку над `select.select` до импорта тестов.
"""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _util import (DIFF_BASE, REPORT_OUTCOME, ROOT, SANDBOX,  # noqa: E402
                   TIMEOUT_INTEGRATIONS, base_source, changed_paths, find_class,
                   find_method, guard_assertions, head_source, new_test_paths,
                   parse, qualified, run_pytest)

REPORT_CLS, REPORT_METHOD = "VitestReporterTest", "test_ac9_timeout_kills_group_not_green"
TIMEOUT_CLS = "SeparateSuiteScenarios"
TIMEOUT_METHOD = "test_ac3_timeout_kills_group_and_failure_cleanup_is_bounded"
REPORT_NODE = f"{REPORT_OUTCOME}::{REPORT_CLS}::{REPORT_METHOD}"
HIGH_FD = 1100
REPORT_MODULE = "tests.test_01m590gjaf0edv4nbc4c99mfvh_report_outcome"
IMPORTERS = ("tests/test_invariants.py", "tests/test_component_report_gates.py")


def imports_of(tree) -> dict:
    """{локальное имя: (модуль, имя в модуле либо None)} по всем импортам."""
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                found[alias.asname or alias.name] = (node.module, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    found[alias.asname] = (alias.name, None)
    return found


def called_functions(func, imports: dict) -> list:
    """(модуль, функция) вызовов в `func`, разрешённых через импорты."""
    out = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        if isinstance(callee, ast.Name) and callee.id in imports:
            mod, name = imports[callee.id]
            out.append(((mod, name), node))
        elif isinstance(callee, ast.Attribute) and isinstance(callee.value, ast.Name) \
                and callee.value.id in imports:
            mod, sub = imports[callee.value.id]
            out.append(((mod if sub is None else f"{mod}.{sub}", callee.attr), node))
    return out


def module_path(mod: str) -> str:
    return mod.replace(".", "/") + ".py"


def method_of(rel: str, cls: str, name: str):
    tree = parse(head_source(rel))
    _c, func = find_method(tree, name, cls)
    return tree, func


def wait_function():
    """(модуль, функция, вызовы в методе report, вызовы в методе timeout)."""
    new = set(new_test_paths())
    r_tree, r_func = method_of(REPORT_OUTCOME, REPORT_CLS, REPORT_METHOD)
    t_tree, t_func = method_of(TIMEOUT_INTEGRATIONS, TIMEOUT_CLS, TIMEOUT_METHOD)
    assert r_func is not None and t_func is not None, "метода нет в голове"
    r_calls = called_functions(r_func, imports_of(r_tree))
    t_calls = called_functions(t_func, imports_of(t_tree))
    common = ({k for k, _n in r_calls} & {k for k, _n in t_calls})
    common = sorted(k for k in common if module_path(k[0]) in new)
    if not common:
        raise AssertionError(
            f"нет функции нового модуля tests/, вызванной в обоих методах; "
            f"новые файлы: {sorted(new)}; вызовы report: {[k for k, _ in r_calls]}; "
            f"timeout: {[k for k, _ in t_calls]}")
    key = common[0]
    return (key[0], key[1], [n for k, n in r_calls if k == key],
            [n for k, n in t_calls if k == key])


def numeric_constants(tree) -> dict:
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out[t.id] = node.value.value
    return out


def arg_values(call, constants: dict) -> list:
    values = []
    for arg in [*call.args, *(k.value for k in call.keywords)]:
        if isinstance(arg, ast.Constant):
            values.append(arg.value)
        elif isinstance(arg, ast.Name) and arg.id in constants:
            values.append(constants[arg.id])
    return values


def select_select_calls(node) -> list:
    return [n for n in ast.walk(node) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute) and n.func.attr == "select"
            and isinstance(n.func.value, ast.Name) and n.func.value.id == "select"]


class WaitFunctionTest(unittest.TestCase):

    maxDiff = None

# AC-7: escalate — на macOS (машина пульта, где идут планка и полный набор пульта) select.poll и kqueue (selectors.DefaultSelector) не сообщают EOF именованного канала (FIFO) — проверено: после закрытия писателя poll/kqueue пусты, select.select видит готовность; test_ac9_timeout_kills_group_not_green ждёт именно EOF FIFO, и с ожиданием через poll/DefaultSelector он локально красен «потомок раннера пережил таймаут» при любой реализации. Как быть: (A) на Darwin test_ac9 ждёт прежним select.select на исходном дескрипторе, а poll/DefaultSelector и перенос на ≥ 1100 — вне Darwin (свойство держит CI Linux; AC-7/AC-8 уточняются «вне Darwin»); (B) test_ac9 на Darwin пропускается (skipIf) с причиной; (C) канал test_ac9 меняется с FIFO на иной (правка фикстуры ReportSandbox без смены имён и сигнатур AC-10)? Дефолт — (A).
    def draft_ac7_both_methods_wait_through_new_module_without_select(self):
        """Оба метода ждут готовности через функцию нового модуля `tests/` на `DefaultSelector`/`poll`, без `select.select`, с пределами 30 и 10 с; утверждения прежние; `tests/sandbox.py` не тронут.

        Сценарий: разбор голов обоих файлов — в методах нет вызова
        `select.select`; функция ожидания найдена (докстринг модуля);
        модуль функции называет `DefaultSelector` или `select.poll` и не
        зовёт `select.select`; вызов функции в методе report несёт 30
        (`CHILD_GUARD_SEC` = 30), в методе timeout — 10; гейт неослабления
        (`guard.changed_test_assertions`) не находит потерь по обоим
        методам; `tests/sandbox.py` не входит в `changed_paths()` и не
        отличается от базы.

        Ловит мутацию: функция ожидания заведена только в одном файле
        (второй остался на `select.select`); функция внутри построена на
        `select.select`; предел ожидания поднят до 60 с «для надёжности»;
        утверждение `assertTrue(ready, …)` снято при переходе на функцию.
        """
        for rel, cls, name in ((REPORT_OUTCOME, REPORT_CLS, REPORT_METHOD),
                               (TIMEOUT_INTEGRATIONS, TIMEOUT_CLS, TIMEOUT_METHOD)):
            _tree, func = method_of(rel, cls, name)
            self.assertIsNotNone(func, f"{rel}::{cls}::{name} нет")
            self.assertEqual([ast.unparse(c) for c in select_select_calls(func)], [],
                             f"{name}: select.select")
        mod, fname, r_calls, t_calls = wait_function()
        mod_tree = parse(head_source(module_path(mod)))
        names = {n.attr for n in ast.walk(mod_tree) if isinstance(n, ast.Attribute)} | \
                {n.id for n in ast.walk(mod_tree) if isinstance(n, ast.Name)} | \
                {a.name for n in ast.walk(mod_tree) if isinstance(n, ast.ImportFrom)
                 for a in n.names}
        polls = [n for n in ast.walk(mod_tree) if isinstance(n, ast.Attribute)
                 and n.attr == "poll" and isinstance(n.value, ast.Name)
                 and n.value.id == "select"]
        self.assertTrue("DefaultSelector" in names or polls,
                        f"{mod}: ни DefaultSelector, ни select.poll")
        self.assertEqual(select_select_calls(mod_tree), [], f"{mod}: select.select")

        r_const = numeric_constants(parse(head_source(REPORT_OUTCOME)))
        self.assertEqual(r_const.get("CHILD_GUARD_SEC"), 30)
        self.assertTrue(all(30 in arg_values(c, r_const) for c in r_calls),
                        f"предел report: {[ast.unparse(c) for c in r_calls]}")
        t_const = numeric_constants(parse(head_source(TIMEOUT_INTEGRATIONS)))
        self.assertTrue(all(10 in arg_values(c, t_const) for c in t_calls),
                        f"предел timeout: {[ast.unparse(c) for c in t_calls]}")

        for rel, cls, name in ((REPORT_OUTCOME, REPORT_CLS, REPORT_METHOD),
                               (TIMEOUT_INTEGRATIONS, TIMEOUT_CLS, TIMEOUT_METHOD)):
            base, head, lost = guard_assertions(rel)
            qual = qualified(head or {}, name, cls)
            self.assertIsNotNone(qual, f"гейт не видит {name}")
            self.assertEqual(lost.get(qual, []), [], f"{name}: потери утверждений")
            self.assertGreaterEqual(len(head[qual]), len(base[qualified(base, name, cls)]))

        self.assertNotIn(SANDBOX, changed_paths())
        diff = subprocess.run(["git", "-C", str(ROOT), "diff", DIFF_BASE, "--", SANDBOX],
                              capture_output=True, text=True)
        self.assertEqual((diff.returncode, diff.stdout), (0, ""), "tests/sandbox.py изменён")

# AC-8: escalate — тот же вопрос, что AC-7: на macOS ожидание EOF FIFO через poll/kqueue на дескрипторе ≥ 1100 не наступает (select.select на ≥ 1024 — ValueError), test_ac9 при выполненном AC-8 красен на машине пульта; черновик теста ниже (draft_ac8_…) прогнан стабом — красен именно этим. Применять AC-8 только вне Darwin (дефолт, вариант (A) AC-7), пропускать test_ac9 на Darwin (B) или сменить канал (C)?
    def draft_ac8_report_waits_and_reads_on_duplicated_high_fd(self):
        """`test_ac9_timeout_kills_group_not_green` переносит канал на дескриптор ≥ 1100, ждёт и читает по нему, исходный закрывает до ожидания; мягкий предел возвращён.

        Сценарий: прогон узла с зондом. Узел зелёный; метод несёт
        `fcntl.F_DUPFD`; зонд видел `fcntl(fd, F_DUPFD, n ≥ 1100)` с
        результатом ≥ 1100; функция ожидания получила этот дескриптор;
        `os.read` шёл по нему же; `os.close` исходного дескриптора — после
        переноса и раньше первого ожидания; мягкий `RLIMIT_NOFILE` на
        выходе узла равен входному.

        Ловит мутацию: перенос сделан, но ожидание и чтение остались на
        исходном `reader` (номер < 1100 — свойство «больше 1024» не
        держится); исходный дескриптор не закрыт; поднятый предел не
        возвращён в `addCleanup`.
        """
        _tree, func = method_of(REPORT_OUTCOME, REPORT_CLS, REPORT_METHOD)
        self.assertTrue([n for n in ast.walk(func) if isinstance(n, ast.Attribute)
                         and n.attr == "F_DUPFD"], "в методе нет fcntl.F_DUPFD")
        mod, fname, _r, _t = wait_function()
        run = run_pytest([REPORT_NODE], env={"ARTEL_PROBE_WAIT": f"{mod}:{fname}"})
        self.assertEqual(run.code, 0, run.tail())
        node = REPORT_METHOD
        events = [r for r in run.probe if node in r.get("node", "")]
        dups = [(i, r) for i, r in enumerate(events) if r["kind"] == "dupfd"
                and isinstance(r.get("arg"), int) and r["arg"] >= HIGH_FD
                and isinstance(r.get("result"), int) and r["result"] >= HIGH_FD]
        self.assertTrue(dups, f"переноса на ≥ {HIGH_FD} нет: "
                              f"{[r for r in events if r['kind'] == 'dupfd']}")
        i_dup, dup = dups[0]
        high, orig = dup["result"], dup["fd"]
        waits = [(i, r) for i, r in enumerate(events) if r["kind"] == "wait"]
        self.assertTrue(waits, "функция ожидания не вызвана")
        self.assertTrue(all(high in r["fds"] for _i, r in waits),
                        f"ожидание не на {high}: {[r['fds'] for _i, r in waits]}")
        reads = [r["fd"] for r in events if r["kind"] == "read"]
        self.assertIn(high, reads, f"чтение не по {high}: {reads}")
        first_wait = waits[0][0]
        closes = [i for i, r in enumerate(events) if r["kind"] == "close"
                  and r["fd"] == orig and i_dup < i < first_wait]
        self.assertTrue(closes, f"исходный {orig} не закрыт до ожидания")
        limits = {r["phase"]: r["soft"] for r in events if r["kind"] == "rlimit"}
        self.assertEqual(limits.get("setup"), limits.get("teardown"), limits)

    def test_ac9_separate_wait_test_green_and_red_on_select(self):
        """Отдельный новый файл `tests/` проверяет функцию ожидания на дескрипторе ≥ 1100 и краснеет `ValueError`, когда она построена на `select.select`.

        Сценарий: новый файл `tests/test_*.py` (нет на базе диффа, не
        `report_outcome`/`timeout_integrations`), импортирующий модуль
        функции ожидания (или сам этот модуль). Прогон с зондом — зелёный,
        функция ожидания вызвана с дескриптором ≥ 1100. Прогон с зондом,
        подменившим `selectors.DefaultSelector` на `SelectSelector` и
        `select.poll` на обёртку над `select.select`, — красный, в выводе
        `ValueError`.

        Ловит мутацию: тест функции ждёт на дескрипторе исходного номера
        (< 1024) — `select.select` его принимает, мутант зелёный; либо
        отдельного теста нет.
        """
        mod, fname, _r, _t = wait_function()
        mod_rel = module_path(mod)
        candidates = []
        for rel in new_test_paths():
            if not Path(rel).name.startswith("test_") or rel in (
                    REPORT_OUTCOME, TIMEOUT_INTEGRATIONS):
                continue
            if rel == mod_rel or any(m == mod or m.startswith(mod + ".") or
                                     f"{m}.{n}" == mod
                                     for m, n in imports_of(parse(head_source(rel))).values()):
                candidates.append(rel)
        self.assertTrue(candidates, f"нового файла теста функции {mod}.{fname} нет")
        ok = []
        for rel in candidates:
            run = run_pytest([rel], env={"ARTEL_PROBE_WAIT": f"{mod}:{fname}"})
            high = [f for r in run.probe_of("wait") for f in r["fds"] if f >= HIGH_FD]
            if run.code != 0 or not high:
                continue
            mutant = run_pytest([rel], env={"ARTEL_PROBE_SELECT": "1"})
            if mutant.code != 0 and "ValueError" in mutant.out:
                ok.append(rel)
        self.assertTrue(ok, f"ни один из {candidates} не зелёный на ≥ {HIGH_FD} "
                            f"и красный ValueError на select.select")

    def test_ac10_report_outcome_imported_names_and_signatures_unchanged(self):
        """Имена, которые `tests/test_invariants.py` и `tests/test_component_report_gates.py` берут из `report_outcome`, есть с прежними сигнатурами и импортируются.

        Сценарий: имена импортов из `report_outcome` в обоих файлах; для
        функции — `ast.dump` аргументов базы и головы равны; для класса —
        прежние базовые классы и каждый метод базы есть с прежними
        аргументами; прочее имя есть на верхнем уровне головы. Чистый
        интерпретатор импортирует все имена из головы.

        Ловит мутацию: функция ожидания добавлена параметром в `vitest_test`
        или `ReportSandbox.full_vitest`; `junit` переименован при выносе
        общего кода — импорт `test_invariants` падает.
        """
        wanted = set()
        for rel in IMPORTERS:
            for node in ast.walk(parse(head_source(rel))):
                if isinstance(node, ast.ImportFrom) and node.module == REPORT_MODULE:
                    wanted |= {a.name for a in node.names}
        self.assertTrue({"ReportSandbox", "junit", "vitest_report", "vitest_test"} <= wanted,
                        wanted)
        base_tree = parse(base_source(REPORT_OUTCOME))
        head_tree = parse(head_source(REPORT_OUTCOME))

        def top(tree):
            out = {}
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                    out[node.name] = node
                elif isinstance(node, ast.Assign):
                    out.update({t.id: node for t in node.targets if isinstance(t, ast.Name)})
            return out

        base, head = top(base_tree), top(head_tree)
        for name in sorted(wanted):
            with self.subTest(name=name):
                self.assertIn(name, head)
                b, h = base[name], head[name]
                if isinstance(b, ast.FunctionDef):
                    self.assertEqual(ast.dump(b.args), ast.dump(h.args))
                elif isinstance(b, ast.ClassDef):
                    self.assertEqual([ast.dump(x) for x in b.bases],
                                     [ast.dump(x) for x in h.bases])
                    hm = {n.name: n for n in h.body if isinstance(n, ast.FunctionDef)}
                    for m in b.body:
                        if isinstance(m, ast.FunctionDef):
                            self.assertIn(m.name, hm, f"{name}.{m.name}")
                            self.assertEqual(ast.dump(m.args), ast.dump(hm[m.name].args),
                                             f"{name}.{m.name}")
        code = f"from {REPORT_MODULE} import {', '.join(sorted(wanted))}"
        res = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0, res.stderr)


if __name__ == "__main__":
    unittest.main()
