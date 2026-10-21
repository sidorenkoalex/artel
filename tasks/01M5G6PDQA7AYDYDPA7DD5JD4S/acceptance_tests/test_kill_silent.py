"""`SilentHostingTest` держит предел `kill` без часов: аргументы предела у пуша и `gh pr close`, флаг истечения молчания хостинга, ровно по одному вызову; сравнение настенного времени удалено (AC-13…AC-17).

Группа: разовый

Красен до реализации: в `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py` ещё стоит `assertLessEqual(elapsed, limit, …)` и описание про допуск времени; сценария с `config.GH_TIMEOUT_SEC` из 7…300 и перехватом `subprocess.run` нет; у `Silence` нет флага истечения молчания, `Silence.limit` = 19 с; утверждений `silence.hits == 1` и одного `gh pr close` нет.

Как тест находит то, чего SPEC не называет:
- сценарий перехвата (AC-14) — узел `SilentHostingTest`, в котором зонд
  pytest (`_util.PROBE`, обёртка присваиваний атрибутов модуля
  `orchestrator.config`) видел `config.GH_TIMEOUT_SEC` из 7…300, отличный
  от исходного и от 2; сквозной сценарий (AC-15) — узел, где
  `GH_TIMEOUT_SEC` выставлен в 2; `Silence.limit` — присваивание атрибута
  `limit` экземпляру `Silence`, которое видит тот же зонд;
- флаг истечения молчания — атрибут `silence.<имя>` (не `hits`), который
  `GitHttpHosting.serve` головы присваивает в ветке правила молчания;
  утверждение о флаге — `self.assert…` сквозного метода, чей текст несёт
  `.<имя>`.
Мутации кода пульта (`orchestrator/cleanup.py`, `orchestrator/ci.py` —
вне зон задачи, текст стабилен) вносятся текстовой правкой во временной
копии рабочей копии; в прогонах мутаций зонд урезает `Silence.limit` до
8 с, чтобы мутант укладывался в таймаут теста, — истечение молчания тогда
наступает раньше, и красноту даёт утверждение о флаге, а не таймаут.
"""
import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _util import (KILL_CLEANUP, assertion_texts, base_source,  # noqa: E402
                   class_methods, find_class, find_method, guard_assertions,
                   head_source, missing, parse, qualified, run_mutant,
                   run_pytest, self_calls)

CLASS = "SilentHostingTest"
METHOD = "test_ac6_silent_gh_and_origin_bounded_and_noted"
NODE = f"{KILL_CLEANUP}::{CLASS}"
CLAMP = {"ARTEL_PROBE_CLAMP": "8"}
CLEANUP_PY = "orchestrator/cleanup.py"
CI_PY = "orchestrator/ci.py"

MUTATIONS = {
    "push_no_c": {CLEANUP_PY: [(
        '    return gitcmd.in_repo(repo, "-c", "http.lowSpeedLimit=1", "-c",\n'
        '                          f"http.lowSpeedTime={config.GH_TIMEOUT_SEC}", *args)',
        '    return gitcmd.in_repo(repo, *args)')]},
    "push_limit_number": {CLEANUP_PY: [(
        'f"http.lowSpeedTime={config.GH_TIMEOUT_SEC}"', 'f"http.lowSpeedTime={60}"')]},
    "gh_timeout_number": {CI_PY: [(
        "timeout_sec = config.GH_TIMEOUT_SEC if timeout is None else timeout",
        "timeout_sec = 60 if timeout is None else timeout")]},
    "note_limit_number": {CLEANUP_PY: [(
        'return f"{what} не ответил за {config.GH_TIMEOUT_SEC} с ({text})"',
        'return f"{what} не ответил за {60} с ({text})"')]},
    "silent_as_refusal": {CLEANUP_PY: [(
        "    if silent:\n        return f\"{what} не ответил",
        "    if False:\n        return f\"{what} не ответил")]},
    "push_twice": {CLEANUP_PY: [(
        "        notes.append(_delete_origin_branch(workspace.task_repo(task_id), branch))",
        "        _delete_origin_branch(workspace.task_repo(task_id), branch); "
        "notes.append(_delete_origin_branch(workspace.task_repo(task_id), branch))")]},
    "gh_twice": {CLEANUP_PY: [(
        "            notes.append(_close_project_pr(branch, ctx.remote, task_id))",
        "            _close_project_pr(branch, ctx.remote, task_id); "
        "notes.append(_close_project_pr(branch, ctx.remote, task_id))")]},
}

_RUNS: dict = {}


def normal_run():
    if "normal" not in _RUNS:
        _RUNS["normal"] = run_pytest([NODE])
    return _RUNS["normal"]


def mutant_run(name: str):
    if name not in _RUNS:
        _RUNS[name] = run_mutant(MUTATIONS[name], [NODE], env=CLAMP)
    return _RUNS[name]


def gh_values(run) -> dict:
    """{узел: [значения GH_TIMEOUT_SEC, присвоенные в узле]}."""
    values: dict = {}
    for rec in run.probe_of("gh_timeout"):
        if rec.get("node"):
            values.setdefault(rec["node"], []).append(rec["value"])
    return values


def initial_gh(run):
    found = run.probe_of("gh_timeout_initial")
    return found[0]["value"] if found else None


def intercept_nodes(run) -> list:
    initial = initial_gh(run)
    return sorted(node for node, vals in gh_values(run).items()
                  if any(isinstance(v, (int, float)) and 7 <= v <= 300
                         and v != initial and v != 2 for v in vals))


def e2e_nodes(run) -> list:
    return sorted(node for node, vals in gh_values(run).items() if 2 in vals)


def case_key(node: str) -> str:
    """Ключ исхода junit (`модуль.Класс.метод`) по id узла pytest."""
    path, cls, meth = node.split("::")
    return f"{path[:-3].replace('/', '.')}.{cls}.{meth}"


def head_tree():
    return parse(head_source(KILL_CLEANUP))


def base_tree():
    return parse(base_source(KILL_CLEANUP))


def _is_silence_attr(node) -> bool:
    return (isinstance(node, ast.Attribute)
            and ast.unparse(node.value).split(".")[-1] == "silence")


def silence_block(serve: ast.FunctionDef):
    """`if` правила молчания в `serve` — тот, в чьём теле `silence.hits += 1`."""
    for node in ast.walk(serve):
        if isinstance(node, ast.If) and any(
                isinstance(s, ast.AugAssign) and _is_silence_attr(s.target)
                and s.target.attr == "hits" for s in ast.walk(node)):
            return node
    return None


def flag_names(serve: ast.FunctionDef) -> list:
    block = silence_block(serve)
    if block is None:
        return []
    names = []
    for node in ast.walk(block):
        targets = (node.targets if isinstance(node, ast.Assign) else
                   [node.target] if isinstance(node, (ast.AugAssign, ast.AnnAssign))
                   else [])
        for t in targets:
            if _is_silence_attr(t) and t.attr not in ("hits", "pattern", "limit",
                                                      "release"):
                names.append(t.attr)
    return sorted(set(names))


def serve_of(tree) -> ast.FunctionDef | None:
    _cls, serve = find_method(tree, "serve", "GitHttpHosting")
    return serve


def method_and_helpers(tree, cls_name: str, method: str) -> list:
    """Метод класса и его помощники первого уровня `self.<имя>` своего
    класса и базовых классов файла."""
    cls = find_class(tree, cls_name)
    chain = []
    while cls is not None:
        chain.append(cls)
        base = cls.bases[0] if cls.bases else None
        cls = find_class(tree, base.id) if isinstance(base, ast.Name) else None
    funcs = {}
    for c in reversed(chain):
        funcs.update(class_methods(c))
    func = funcs.get(method)
    if func is None:
        return []
    return [func] + [funcs[n] for n in set(self_calls(func))
                     if n in funcs and not n.startswith("test")]


def class_assertions(tree, cls_name: str) -> list:
    cls = find_class(tree, cls_name)
    out = []
    for name in class_methods(cls) if cls else {}:
        for func in method_and_helpers(tree, cls_name, name):
            out += assertion_texts(func)
    return out


def failure_lines(text: str) -> list:
    name = Path(KILL_CLEANUP).name
    return [int(m) for m in re.findall(re.escape(name) + r":(\d+)", text)]


class KillSilentHostingTest(unittest.TestCase):

    maxDiff = None

    def test_ac13_only_wallclock_assertion_removed(self):
        """Относительно базы в `test_ac6_silent_gh_and_origin_bounded_and_noted` пропало только `assertLessEqual(elapsed, limit, …)`.

        Сценарий: утверждения `self.assert…` метода на базе диффа (без
        `assertLessEqual` над `elapsed`) стоят дословно (`ast.unparse`) в
        методе головы или его помощниках первого уровня; сравнения
        `elapsed` в голове нет; гейт неослабления (`guard.test_assertions` +
        `guard.changed_test_assertions`) находит по методу ровно одну
        потерю — это `assertLessEqual` над `elapsed`.

        Ловит мутацию: правка сняла вместе со сравнением времени ещё и
        `assertGreaterEqual(self.silence.hits, 1, …)` или одну из заметок
        `SILENT` (переписала её через другую константу) — гейт видит вторую
        потерю, дословного утверждения в голове нет.
        """
        base_cls, base_m = find_method(base_tree(), METHOD, CLASS)
        self.assertIsNotNone(base_m, "метода нет на базе диффа")
        kept = [t for t in assertion_texts(base_m)
                if not ("assertLessEqual" in t and "elapsed" in t)]
        self.assertEqual(len(kept), 4, f"утверждения базы: {kept}")
        tree = head_tree()
        funcs = method_and_helpers(tree, CLASS, METHOD)
        self.assertTrue(funcs, "метода нет в голове")
        head = [t for f in funcs for t in assertion_texts(f)]
        self.assertEqual(missing(kept, head), [], "утверждения не дословно")
        self.assertFalse([t for t in assertion_texts(funcs[0]) if "elapsed" in t],
                         "сравнение elapsed осталось")
        _base, gh, lost = guard_assertions(KILL_CLEANUP)
        name = qualified(gh or {}, METHOD, CLASS)
        self.assertIsNotNone(name, "гейт не видит метода в голове")
        texts = lost.get(name, [])
        self.assertEqual(len(texts), 1, f"потери гейта: {texts}")
        self.assertIn("assertLessEqual", texts[0])
        self.assertIn("elapsed", texts[0])

    def test_ac14_intercept_scenario_present_and_green(self):
        """В `SilentHostingTest` есть зелёный узел с `config.GH_TIMEOUT_SEC` из 7…300, отличным от исходного и от 2.

        Сценарий: прогон класса `SilentHostingTest` с зондом; зонд пишет
        каждое присваивание `config.GH_TIMEOUT_SEC` с узлом pytest. Класс
        зелёный; есть узел, где присвоено значение из 7…300, не равное
        исходному `config.GH_TIMEOUT_SEC` и не равное 2.

        Ловит мутацию: сценарий перехвата подменяет предел значением
        `random.choice((2, config.GH_TIMEOUT_SEC))` либо литералом вне
        7…300 — узла с допустимым значением нет.
        """
        run = normal_run()
        self.assertEqual(run.failed(CLASS), {}, run.tail())
        self.assertEqual(run.code, 0, run.tail())
        nodes = intercept_nodes(run)
        self.assertTrue(nodes, f"узла перехвата нет: {gh_values(run)}\n"
                               f"исходный {initial_gh(run)}")
        for node in nodes:
            self.assertIn(case_key(node), run.passed(), node)

    def _intercept_red(self, mutation: str) -> None:
        nodes = intercept_nodes(normal_run())
        self.assertTrue(nodes, "узла перехвата нет")
        run = mutant_run(mutation)
        red = [n for n in nodes if case_key(n) in run.failed()]
        self.assertTrue(red, f"мутация {mutation}: узел перехвата зелёный\n"
                             f"{run.cases}\n{run.tail()}")

    def test_ac14_push_without_low_speed_pairs_reddens_intercept(self):
        """Пуш удаления без пар `-c http.lowSpeedLimit=1 -c http.lowSpeedTime=…` краснит сценарий перехвата.

        Сценарий: во временной копии `cleanup._bounded` зовёт git без пар
        `-c`; прогон `SilentHostingTest` — узел перехвата красный.

        Ловит мутацию: сценарий перехвата не сверяет аргументы пуша
        удаления — мутант зелёный.
        """
        self._intercept_red("push_no_c")

    def test_ac14_push_limit_number_reddens_intercept(self):
        """Предел пуша, зашитый числом 60 вместо `config.GH_TIMEOUT_SEC`, краснит сценарий перехвата.

        Сценарий: во временной копии `http.lowSpeedTime=60`; узел перехвата
        (значение предела случайно и не равно исходному 60) — красный.

        Ловит мутацию: сценарий проверяет только наличие `http.lowSpeedTime`
        без значения либо держит исходный предел — мутант зелёный.
        """
        self._intercept_red("push_limit_number")

    def test_ac14_gh_timeout_number_reddens_intercept(self):
        """`gh` с `timeout=60` вместо `config.GH_TIMEOUT_SEC` краснит сценарий перехвата.

        Сценарий: во временной копии `ci.gh` берёт предел числом 60; узел
        перехвата — красный.

        Ловит мутацию: сценарий не сверяет `timeout=` вызова `gh pr close` —
        мутант зелёный.
        """
        self._intercept_red("gh_timeout_number")

    def test_ac14_note_limit_number_reddens_intercept(self):
        """Заметка «не ответил за 60 с» вместо значения предела краснит сценарий перехвата.

        Сценарий: во временной копии `_left_reason` пишет число 60; узел
        перехвата — красный.

        Ловит мутацию: сценарий сверяет только «не ответил», без значения
        предела в тексте заметки — мутант зелёный.
        """
        self._intercept_red("note_limit_number")

    def test_ac15_end_to_end_limit_flag_and_green(self):
        """Сквозной узел: предел 2 с, `Silence.limit` в [60, 120), флаг ставится по истечении `release.wait`, узел зелёный.

        Сценарий: прогон `SilentHostingTest` с зондом — есть узел с
        `config.GH_TIMEOUT_SEC = 2`, он зелёный, в нём `Silence.limit`
        присвоено значение не меньше 60 и меньше 120. `serve` головы в
        ветке правила молчания присваивает флаг `silence.<имя>`, и это
        присваивание зависит от результата `release.wait(…)`; сквозной
        метод утверждает этот флаг.

        Ловит мутацию: срок молчания оставлен `limit + 5` (19 с) или поднят
        до 120 с; флаг ставится безусловно после `wait` (не по его
        результату); утверждения о флаге в сквозном методе нет.
        """
        run = normal_run()
        nodes = e2e_nodes(run)
        self.assertTrue(nodes, f"сквозного узла с пределом 2 нет: {gh_values(run)}")
        for node in nodes:
            self.assertIn(case_key(node), run.passed(), run.tail())
            limits = [r["value"] for r in run.probe_of("silence_limit", node)
                      if r["value"]]
            self.assertTrue(limits, f"{node}: Silence.limit не присвоен")
            for value in limits:
                self.assertGreaterEqual(value, 60, node)
                self.assertLess(value, 120, node)

        serve = serve_of(head_tree())
        flags = flag_names(serve)
        self.assertTrue(flags, "serve не ставит флаг истечения молчания")
        block = silence_block(serve)
        waits = [n for n in ast.walk(block) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == "wait"]
        self.assertTrue(waits, "release.wait в правиле молчания нет")
        wait_names = set()
        for n in ast.walk(block):
            if isinstance(n, ast.Assign) and any(w in ast.walk(n.value) for w in waits):
                wait_names |= {t.id for t in n.targets if isinstance(t, ast.Name)}

        def depends(node) -> bool:
            return any(w in ast.walk(node) for w in waits) or any(
                isinstance(x, ast.Name) and x.id in wait_names for x in ast.walk(node))

        guarded = False
        for n in ast.walk(block):
            if isinstance(n, ast.If) and depends(n.test):
                guarded |= any(isinstance(t, ast.Attribute) and t.attr in flags
                               for s in n.body for x in ast.walk(s)
                               if isinstance(x, ast.Assign) for t in x.targets)
            if isinstance(n, ast.Assign) and depends(n.value):
                guarded |= any(isinstance(t, ast.Attribute) and t.attr in flags
                               for t in n.targets)
        self.assertTrue(guarded, f"флаг {flags} ставится не по результату wait")

        tree = head_tree()
        for node in nodes:
            meth = node.split("::")[-1]
            texts = [t for f in method_and_helpers(tree, CLASS, meth)
                     for t in assertion_texts(f)]
            self.assertTrue([t for t in texts if any(f".{fl}" in t for fl in flags)],
                            f"{meth}: утверждения о флаге {flags} нет")

    def test_ac15_push_without_pairs_red_by_flag_assertion(self):
        """Под мутацией «пуш без `-c`» сквозной узел красен утверждением о флаге истечения молчания, а не таймаутом.

        Сценарий: во временной копии пуш удаления без пар `-c`; срок
        молчания урезан зондом до 8 с. Сквозной узел красный, строка
        провала в файле теста — строка утверждения о флаге, текста таймаута
        pytest нет.

        Ловит мутацию: утверждение о флаге стоит после заметок «не
        ответил» (провал по заметке «отказ») или флага нет — провал не на
        его строке.
        """
        nodes = e2e_nodes(normal_run())
        self.assertTrue(nodes, "сквозного узла нет")
        tree = head_tree()
        flags = flag_names(serve_of(tree))
        self.assertTrue(flags, "флага нет")
        run = mutant_run("push_no_c")
        for node in nodes:
            meth = node.split("::")[-1]
            ranges = []
            for func in method_and_helpers(tree, CLASS, meth):
                for call in ast.walk(func):
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) \
                            and call.func.attr.startswith("assert") \
                            and any(f".{fl}" in ast.unparse(call) for fl in flags):
                        ranges.append((call.lineno, call.end_lineno))
            failure = run.failed().get(case_key(node))
            self.assertIsNotNone(failure, f"{node} зелёный под мутацией\n{run.tail()}")
            self.assertNotIn("Timeout", failure[1], failure[1][-3000:])
            lines = failure_lines(failure[1])
            self.assertTrue(any(a <= ln <= b for ln in lines for a, b in ranges),
                            f"провал на строках {lines}, утверждение о флаге — "
                            f"{ranges}\n{failure[1][-3000:]}")

    def test_ac15_gh_timeout_number_reddens_end_to_end(self):
        """`gh` с пределом 60 вместо `config.GH_TIMEOUT_SEC` краснит сквозной узел — подставной `gh` спит меньше 60 с и доживает до конца сна.

        Сценарий: во временной копии `ci.gh` берёт предел числом 60;
        сквозной узел (предел 2 с, `gh` спит 2 × 2 + 15 с) — красный.

        Ловит мутацию: подставной `gh` спит прежние 60 с — `gh` с пределом
        60 снят по таймауту, заметка «не ответил», события конца сна нет, и
        сквозной узел зелёный; либо утверждения об отсутствии события конца
        сна нет.
        """
        nodes = e2e_nodes(normal_run())
        self.assertTrue(nodes, "сквозного узла нет")
        run = mutant_run("gh_timeout_number")
        red = [n for n in nodes if case_key(n) in run.failed()]
        self.assertTrue(red, f"сквозной узел зелёный под мутацией\n{run.tail()}")

    def test_ac16_counts_asserted_and_serve_unchanged_for_count(self):
        """`SilentHostingTest` утверждает `self.silence.hits == 1`, держит прежний `assertGreaterEqual` дословно; `serve` вне правила молчания не изменён.

        Сценарий: среди утверждений методов `SilentHostingTest` головы —
        `assertEqual` с `self.silence.hits` и `1`, дословное
        `assertGreaterEqual(self.silence.hits, 1, …)` базы и `assertEqual` с
        `1` и числом записей `gh pr close` журнала (`pr_closes`/`gh_calls`).
        `GitHttpHosting.serve` головы вне блока правила молчания совпадает
        с базой (`ast.dump`), счёт `silence.hits` в блоке — прежний.

        Ловит мутацию: счёт пуша перенесён в журнал `pre-receive` (который
        молчащий пуш не видит) правкой `serve` либо вторым инкрементом
        `hits`; прежнее `assertGreaterEqual` заменено равенством.
        """
        tree = head_tree()
        texts = class_assertions(tree, CLASS)
        hits_eq = [t for t in texts if t.startswith("self.assertEqual(")
                   and "self.silence.hits" in t and re.search(r"\b1\b", t)]
        self.assertTrue(hits_eq, f"нет assertEqual(self.silence.hits, 1): {texts}")
        _c, base_m = find_method(base_tree(), METHOD, CLASS)
        ge = [t for t in assertion_texts(base_m) if t.startswith("self.assertGreaterEqual(")]
        self.assertEqual(missing(ge, texts), [], "прежнее assertGreaterEqual не дословно")
        closes = [t for t in texts if t.startswith("self.assertEqual(")
                  and ("pr_closes" in t or "gh_calls" in t) and re.search(r"\b1\b", t)]
        self.assertTrue(closes, f"нет равенства одного gh pr close: {texts}")

        base_serve, head_serve = serve_of(base_tree()), serve_of(tree)
        b_block, h_block = silence_block(base_serve), silence_block(head_serve)
        self.assertIsNotNone(h_block, "блока правила молчания в serve нет")
        self.assertEqual(ast.dump(b_block.test), ast.dump(h_block.test),
                         "условие правила молчания изменено")

        def outside(func, block):
            return [ast.dump(s) for s in func.body if s is not block]
        self.assertEqual(outside(base_serve, b_block), outside(head_serve, h_block),
                         "serve изменён вне правила молчания")

        def hits_updates(block):
            return sorted(ast.dump(n) for n in ast.walk(block)
                          if isinstance(n, (ast.Assign, ast.AugAssign))
                          and any(isinstance(t, ast.Attribute) and t.attr == "hits"
                                  for t in (n.targets if isinstance(n, ast.Assign)
                                            else [n.target])))
        self.assertEqual(hits_updates(b_block), hits_updates(h_block), "счёт hits изменён")

    def test_ac16_second_push_reddens_silent_hosting(self):
        """Второй пуш удаления ветки (`silence.hits == 2`) краснит `SilentHostingTest`.

        Сценарий: во временной копии уборка зовёт `_delete_origin_branch`
        дважды; прогон `SilentHostingTest` — красный.

        Ловит мутацию: тест держит только `hits ≥ 1` — мутант зелёный.
        """
        run = mutant_run("push_twice")
        self.assertTrue(run.failed(CLASS), f"мутант зелёный\n{run.tail()}")

    def test_ac16_second_pr_close_reddens_silent_hosting(self):
        """Второй запуск `gh pr close` краснит `SilentHostingTest`.

        Сценарий: во временной копии уборка зовёт `_close_project_pr`
        дважды; прогон `SilentHostingTest` — красный.

        Ловит мутацию: тест не считает запуски `gh pr close` по журналу
        подставных программ — мутант зелёный.
        """
        run = mutant_run("gh_twice")
        self.assertTrue(run.failed(CLASS), f"мутант зелёный\n{run.tail()}")

    def test_ac17_no_wallclock_comparison_and_docstring_describes_mechanism(self):
        """В файле нет утверждений над настенным временем; описание `test_ac6_…` говорит об аргументах предела, флаге и счётчиках и перечисляет три мутации.

        Сценарий: в каждой функции файла головы имена, присвоенные от
        `time.monotonic()`/`time.time()`/`time.perf_counter()` (и выражений
        над ними), — «время»; ни одно `self.assert…` и ни один `assert` их
        не касается. Первая строка описания метода и абзац «Ловит мутацию»
        не говорят о допуске времени («допуск», «не дольше», «укладывается»,
        «настенн»), называют флаг, счёт вызовов и аргументы предела; абзац
        «Ловит мутацию» называет пары `-c`/`lowSpeed`, `GH_TIMEOUT_SEC` и
        «отказ».

        Ловит мутацию: сравнение `elapsed` переписано в `self.assertTrue(
        elapsed < limit)` или в `assert`; описание оставлено прежним («не
        дольше 2 × GH_TIMEOUT_SEC + 10 с»).
        """
        tree = head_tree()
        clock = {"monotonic", "time", "perf_counter", "monotonic_ns", "time_ns",
                 "perf_counter_ns"}

        def is_clock(n):
            return (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr in clock and isinstance(n.func.value, ast.Name)
                    and n.func.value.id == "time")

        bad = []
        for func in [n for n in ast.walk(tree)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            tainted: set = set()
            changed = True
            while changed:
                changed = False
                for n in ast.walk(func):
                    if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign)) \
                            and n.value is not None and any(
                                is_clock(x) or (isinstance(x, ast.Name) and x.id in tainted)
                                for x in ast.walk(n.value)):
                        targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                        for t in targets:
                            for x in ast.walk(t):
                                if isinstance(x, ast.Name) and x.id not in tainted:
                                    tainted.add(x.id)
                                    changed = True
            for n in ast.walk(func):
                is_assert = isinstance(n, ast.Assert) or (
                    isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr.startswith("assert"))
                if is_assert and any(is_clock(x) or (isinstance(x, ast.Name)
                                                     and x.id in tainted)
                                     for x in ast.walk(n)):
                    bad.append(f"{func.name}:{n.lineno}: {ast.unparse(n)[:120]}")
        self.assertEqual(bad, [], "утверждения над настенным временем")

        _c, meth = find_method(tree, METHOD, CLASS)
        doc = ast.get_docstring(meth) or ""
        first = doc.splitlines()[0] if doc else ""
        paragraph = ""
        for block in re.split(r"\n\s*\n", doc):
            if block.strip().startswith("Ловит мутацию"):
                paragraph = block
        self.assertTrue(paragraph, f"нет абзаца «Ловит мутацию»: {doc}")
        text = (first + "\n" + paragraph).lower()
        for word in ("допуск", "не дольше", "укладывается", "настенн"):
            self.assertNotIn(word, text, f"описание о допуске времени: {first}\n{paragraph}")
        self.assertIn("флаг", text, "описание не называет флаг истечения молчания")
        self.assertTrue(any(w in text for w in ("счёт", "счет", "ровно один",
                                                "ровно по одному", "hits")),
                        "описание не называет счётчики вызовов")
        self.assertTrue(any(w in text for w in ("аргумент", "timeout=", "lowspeedtime",
                                                "-c ")),
                        "описание не называет аргументы предела")
        low = paragraph.lower()
        self.assertTrue("-c" in low or "lowspeed" in low, "мутация «пуш без -c» не названа")
        self.assertIn("gh_timeout_sec", low, "мутация «предел числом» не названа")
        self.assertIn("отказ", low, "мутация «срабатывание как отказ» не названа")

    def test_ac17_three_docstring_mutations_redden_silent_hosting(self):
        """Каждая из трёх мутаций абзаца «Ловит мутацию» краснит `SilentHostingTest`.

        Сценарий: во временной копии по очереди — пуш без пар `-c`; предел
        пуша числом 60 вместо `config.GH_TIMEOUT_SEC`; срабатывание предела
        как «отказ» (`_left_reason` не пишет «не ответил»). Каждый прогон
        `SilentHostingTest` — с красным узлом и без таймаута pytest.

        Ловит мутацию: тесты класса держат только состояние `killed` и
        `hits ≥ 1` — мутант «предел числом» зелёный.
        """
        for name in ("push_no_c", "push_limit_number", "silent_as_refusal"):
            with self.subTest(mutation=name):
                run = mutant_run(name)
                failed = run.failed(CLASS)
                self.assertTrue(failed, f"{name}: мутант зелёный\n{run.tail()}")
                self.assertFalse([k for k, v in failed.items() if "Timeout" in v[1]],
                                 f"{name}: таймаут pytest\n{run.tail()}")


if __name__ == "__main__":
    unittest.main()
