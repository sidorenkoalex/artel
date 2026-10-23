---
task: 01M5MVSP9YW0DYA4YQ1KSG0AHF
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Тесты планки и долгоживущие тесты проверяются на ожидание по часам и чтение живых файлов до лока

# Тесты планки и долгоживущие тесты проверяются на ожидание по часам и чтение живых файлов до лока

## Факты

Строка бэклога «Проверка детерминизма тестов планки на выходе tests_writing, до лока» (приоритет 1). Решение Оператора 23.10.2026: вариант А — разбор линта выносится в модуль пульта `orchestrator/test_lint.py`, `tests/test_invariants.py` зовёт его (правка защищённого файла — приложением PLAN ниже); правило действует и на файлы `acceptance_tests/`. Сверено с `origin/main` d95b7d59.

- Канарейка 20261022T213109Z на 6e19ccb8 красная: test_author в канареечной задаче залочил долгоживущий файл `tests/test_01m5jrd1471qk23aw4y5t5vz6r_log_filters.py` (был только в ветке канарейки, в `origin/main` его нет), метод `LogSinceRelativeTest::run_relative` (строка 229) — цикл повтора по `int(time.time())`. Инвариант `tests/test_invariants.py::DeterministicTestsLintTest` ловит такое только в CI ветки, когда тесты уже залочены; разработчик не вправе править ни тест, ни линт — эскалация.
- Линт — `DeterministicTestsLintTest` (`tests/test_invariants.py:1999–2565`): константы `_CLOCK_CALLS`, `_LIVE_FILES`, `_LIVE_FILE_CONFIG_ATTRS`, `_SANDBOX_HELPERS`; перечень `_EXCEPTIONS` (61 запись «файл::метод»; на `origin/main` дерево `tests/` даёт ровно эти 61 нарушение); разбор — классовые методы на `ast` (`_wall_clock_waits` — правило часов, `_live_reads` с помощниками — правило живых файлов, `_top_level_functions`, `findings(source, rel)`, `tree_findings(tests_dir)`); тесты AC-1…AC-5 и образцы через `findings`. Проверяется только дерево `tests/**/*.py` без `tests/sandbox.py`; каталоги `acceptance_tests/` не проверяются. Внешних зависимостей у разбора нет (`ast`, `Path`, `textwrap`); `tests/test_invariants.py` уже импортирует `orchestrator` и `scripts.guard`.
- Выход `tests_writing` (`orchestrator/fsm_advance.py`, около строк 570–643): трассируемость AC, затем гейты `_tests_writing_test_groups_gate` и `_tests_writing_long_lived_gate` (`orchestrator/advance_gates/tests_writing.py`), им передаётся `network_addresses = repo_context.is_artel(target)` (`fsm_advance.py:598`); затем переход в `in_dev` и лок. Отказы этих двух гейтов уже имеют класс «чинит роль» (`orchestrator/advance_gates/refusal_classes.py`): `auto` повторяет шаг test_author с отказом в брифе.
- Образец переноса правила в пульт — сетевые адреса: `guard.network_address_hits` (`scripts/guard.py:4081`) зовут инвариант, оба гейта через `guard.long_lived_errors_from_files` (`scripts/guard.py:3982`), `preflight` и `amend`. Файлы планки перебирает `guard.acceptance_test_files` (`scripts/guard.py:4112`).
- `skills/test-authoring.md` (раздел «Стоимость и устойчивость долгоживущих тестов», строки 200–202; раздел об окружении теста, строка 382) правило содержит в общем виде.

## Требования

1. Новый модуль `orchestrator/test_lint.py`, только стандартная библиотека (без импорта модулей `orchestrator` — guard импортирует его, а модули `orchestrator` импортируют guard): функции `findings(source: str, rel: str) -> dict` («файл::метод» → список нарушений) и `top_level_functions(tree)` с поведением, побайтно равным нынешним классовым методам `DeterministicTestsLintTest.findings` и `_top_level_functions` (оба правила — ожидание по часам и чтение живых файлов; тексты нарушений «строка N: …» прежние); константы правил (`CLOCK_CALLS`, `LIVE_FILES`, `LIVE_FILE_CONFIG_ATTRS`) живут в модуле; `findings` пробрасывает `SyntaxError`, как прежде (пропуск синтаксически сломанного файла — только в guard).
2. Приложение PLAN к `tests/test_invariants.py` (раздел «Приложения PLAN» ниже) исполняется без изменений: класс зовёт `test_lint`, его перечень `_EXCEPTIONS`, `_SANDBOX_HELPERS`, обход дерева и все прежние тесты-образцы не меняются; добавляется тест `test_rule_corpus_is_frozen`, которому `orchestrator/test_lint.py` обязан соответствовать.
3. Ядро `scripts/guard.py`: линт вызывается внутри `long_lived_errors_from_files` в цикле по файлам сразу после пропуска не-`.py` без метки и до `plank_file_group` и фильтра по группе — для каждого файла с окончанием `.py` и только при признаке проекта артели (`network_addresses=True`); так проверку получают и долгоживущие файлы, и файлы планки обычных групп, а через ту же функцию — `preflight` и `amend-tests`. Файл с синтаксической ошибкой линтом пропускается (`SyntaxError` гейт не роняет — его называет сухой сбор). Строка ошибки: «<файл>::<метод>: строка N: <нарушение>»; для файлов `acceptance_tests/` имя — путь, как его даёт `guard.acceptance_test_files`.
4. Пути `amend-tests` передают в `long_lived_errors_from_files` новый именованный параметр `lint_base: dict[str, str] | None` (метка файла → текст залоченного состояния: для планки — артефактная ветка на `tests_locked_sha`, для долгоживущих — голова кодовой ветки до правки, как в `_code_head_long_lived`). Нарушение метода не считается, если у метода с тем же «Класс::метод» в базе одинаковый `ast.dump` узла (задачи, залоченные до этой правки, не получают отказа за старые методы). По умолчанию `None` — проверяются все методы. Перечень `_EXCEPTIONS` гейтом не читается.
5. Гейт срабатывает до лока: нарушение — отказ выхода `tests_writing` тем же классом «чинит роль» (`refusal_classes.py:116–117`), состояние остаётся `tests_writing`, `tests_locked_sha` не выставлен.
6. Для чужого проекта (`is_artel` ложно) проверки нет.
7. Тесты (новый файл в `tests/`, у каждого — строка «Ловит мутацию:»):
   (а) долгоживущий файл ветки с циклом `while time.time() < deadline` в методе — отказ «долгоживущие файлы tests/» с «файл::метод: строка N», состояние `tests_writing`, лока нет;
   (б) обычный файл `acceptance_tests/` с `time.sleep(1)` и файл с путём `Path(__file__).parent.parent / "targets.yaml"` — отказ «группы приёмочных тестов» с адресом (Ловит мутацию: линт перенесён после фильтра по группе);
   (в) чистые файлы и файл с синтаксической ошибкой — линт отказа не даёт;
   (г) `amend-tests`: долгоживущий файл задачи залочен с методом `time.sleep(1)` (лок до правки); правка другого метода — отказа нет; добавленный правкой метод с `time.sleep(1)` — отказ;
   (д) проект не артель — те же нарушения не дают отказа (зелёный и до, и после; страхует от подключения линта без признака артели).
   На текущем коде (а), (б) красные (проверки нет); (в), (г), (д) зелёные (линта нет вовсе; вторая часть (г) краснеет, если правку `amend` не сделать).
8. Эквивалентность переноса на дереве `tests/` — однократная проверка разработчика: результат `test_lint.findings` на всём дереве ветки равен прежнему разбору (число ключей и побайтное равенство) — вывод сравнения приложить к PLAN. Постоянную защиту правила держит закреплённый набор образцов с точными текстами — тест `test_rule_corpus_is_frozen` в приложении PLAN.
9. Существующие тесты, кроме приложения PLAN к `tests/test_invariants.py`, не правятся и остаются зелёными.

Зоны: orchestrator/test_lint.py, scripts/guard.py, orchestrator/amend.py, docs/codebase-map.md, tests/

Ограничение зон по смыслу: в `scripts/guard.py` — только подключение линта к ошибкам долгоживущих файлов и файлов планки; прочие проверки guard не меняются; в `orchestrator/amend.py` — только требование 4 (передача `lint_base`); в `scripts/guard.py` — также параметр `lint_base`.

Только чтение: docs/ (имя каталога — элемент правила живых файлов, сам каталог не меняется), orchestrator/fsm_advance.py, orchestrator/advance_gates/tests_writing.py, orchestrator/advance_gates/refusal_classes.py, orchestrator/repo_context.py, orchestrator/preflight.py.

Не входит: изменение перечня `_EXCEPTIONS` и тестов-образцов; правка `skills/test-authoring.md` (правило там есть; уточнение примером — отдельной правкой Оператора); новый класс отказа.

## Приложения PLAN

### Приложение 1 (вынос разбора линта детерминизма): tests/test_invariants.py

Защищённый путь; решение Оператора 23.10.2026 (вариант А). Кроме переноса разбора, приложение добавляет тест `test_rule_corpus_is_frozen` — закреплённый набор образцов с точными находками (снят прогоном нынешней реализации 23.10): ослабление правила в незащищённом модуле краснит защищённый файл.

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -39,6 +39,7 @@
                           ci, cleanup, config, fsm, fsm_advance, gitcmd,
                           runner, stack, store)
 from orchestrator.advance_gates import test_integrity  # noqa: E402
+from orchestrator import test_lint  # noqa: E402
 from scripts import guard  # noqa: E402
 from tests.sandbox import (FakeProc, SpyRun, TmpRootTest, _stub_check_stack,  # noqa: E402
                            capture, capture_new_task_id,
@@ -2019,11 +2020,6 @@
     файла (защищённый путь, на виду у Оператора).
     """
 
-    _CLOCK_CALLS = ("monotonic", "time", "monotonic_ns", "time_ns")
-    _LIVE_FILES = ("targets.yaml", "roles.yaml", "model_sets.yaml")
-    # Имена `config`, равные имени живого файла (относительный путь от
-    # корня, а не путь песочницы).
-    _LIVE_FILE_CONFIG_ATTRS = ("MODEL_SETS_REL",)
     _SANDBOX_HELPERS = "tests/sandbox.py"
 
     # «файл::метод» -> обоснование (SPEC 01M4G8MNEPECNX1TCEDW4T4RPX,
@@ -2210,202 +2206,19 @@
     }
 
     # --- разбор -----------------------------------------------------------
-
-    @classmethod
-    def _is_time_module(cls, node) -> bool:
-        return ((isinstance(node, ast.Name) and node.id == "time")
-                or (isinstance(node, ast.Attribute) and node.attr == "time"))
-
-    @classmethod
-    def _is_clock_call(cls, node, from_time: set) -> bool:
-        if not isinstance(node, ast.Call):
-            return False
-        func = node.func
-        if isinstance(func, ast.Attribute):
-            return (func.attr in cls._CLOCK_CALLS
-                    and cls._is_time_module(func.value))
-        return isinstance(func, ast.Name) and func.id in from_time & set(
-            cls._CLOCK_CALLS)
-
-    @classmethod
-    def _is_sleep_call(cls, node, from_time: set) -> bool:
-        if not isinstance(node, ast.Call):
-            return False
-        func = node.func
-        if isinstance(func, ast.Attribute):
-            return func.attr == "sleep" and cls._is_time_module(func.value)
-        return isinstance(func, ast.Name) and func.id == "sleep" and (
-            "sleep" in from_time)
-
-    @staticmethod
-    def _zero_pause(call: ast.Call) -> bool:
-        args = list(call.args) + [k.value for k in call.keywords]
-        return (len(args) == 1 and isinstance(args[0], ast.Constant)
-                and not isinstance(args[0].value, bool)
-                and args[0].value == 0)
-
-    @staticmethod
-    def _walk_own(node):
-        """Узлы `node` без тел вложенных функций и классов — у вложенной
-        функции свой обход (её нарушение адресуется той же функцией
-        верхнего уровня)."""
-        stack = [node]
-        while stack:
-            current = stack.pop()
-            yield current
-            for child in ast.iter_child_nodes(current):
-                if current is not node and isinstance(
-                        current, (ast.FunctionDef, ast.AsyncFunctionDef,
-                                  ast.Lambda, ast.ClassDef)):
-                    continue
-                stack.append(child)
-
-    @staticmethod
-    def _from_time_names(tree) -> set:
-        return {alias.asname or alias.name for node in ast.walk(tree)
-                if isinstance(node, ast.ImportFrom) and node.module == "time"
-                for alias in node.names}
-
-    @classmethod
-    def _wall_clock_waits(cls, func, from_time: set) -> list:
-        """Строки ожидания по часам внутри функции `func` (вместе с
-        вложенными функциями)."""
-        found = []
-        for node in ast.walk(func):
-            if cls._is_sleep_call(node, from_time) and not cls._zero_pause(node):
-                found.append(f"строка {node.lineno}: time.sleep с ненулевой "
-                             f"паузой")
-            elif isinstance(node, (ast.While, ast.For, ast.AsyncFor)):
-                # Условие цикла и условия `if` в его теле: срок проверяется
-                # там; сравнение меток времени в утверждении — не ожидание.
-                checks = [node.test] if isinstance(node, ast.While) else []
-                checks += [sub.test for stmt in node.body
-                           for sub in cls._walk_own(stmt)
-                           if isinstance(sub, ast.If)]
-                if any(cls._is_clock_call(sub, from_time)
-                       for check in checks for sub in ast.walk(check)):
-                    found.append(f"строка {node.lineno}: цикл до срока по "
-                                 f"time.monotonic()/time.time()")
-        return found
-
-    @classmethod
-    def _mentions_file(cls, node) -> bool:
-        return any(isinstance(sub, ast.Name) and sub.id == "__file__"
-                   or isinstance(sub, ast.Attribute) and sub.attr == "__file__"
-                   for sub in ast.walk(node))
-
-    @classmethod
-    def _is_live_name(cls, node) -> bool:
-        if isinstance(node, ast.Constant) and isinstance(node.value, str):
-            value = node.value.strip("/")
-            return (value in cls._LIVE_FILES or value == "docs"
-                    or value.startswith("docs/"))
-        return (isinstance(node, ast.Attribute)
-                and node.attr in cls._LIVE_FILE_CONFIG_ATTRS)
-
-    @classmethod
-    def _rooted(cls, node, roots: set) -> bool:
-        """Выражение — путь от настоящего корня: несёт `__file__` или имя,
-        связанное с таким путём."""
-        return cls._mentions_file(node) or any(
-            isinstance(sub, ast.Name) and sub.id in roots
-            for sub in ast.walk(node))
-
-    @classmethod
-    def _path_parts(cls, node) -> list | None:
-        """Части выражения-пути: операнды цепочки `/`, получатель и
-        аргументы `joinpath`/`os.path.join`; `None` — не путь."""
-        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
-            return [*(cls._path_parts(node.left) or [node.left]),
-                    *(cls._path_parts(node.right) or [node.right])]
-        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
-            if node.func.attr == "joinpath":
-                return [node.func.value, *node.args]
-            if node.func.attr == "join" and ast.unparse(node.func.value) in (
-                    "os.path", "path"):
-                return list(node.args)
-        return None
-
-    @classmethod
-    def _live_path(cls, node, roots: set) -> bool:
-        parts = cls._path_parts(node)
-        return bool(parts) and any(cls._rooted(p, roots) for p in parts) and any(
-            cls._is_live_name(p) for p in parts)
-
-    @classmethod
-    def _bound_names(cls, statements, test) -> set:
-        """Имена, связанные присваиванием в `statements` со значением,
-        удовлетворяющим `test` (до неподвижной точки: имя от имени)."""
-        names: set = set()
-        assigns = [node for stmt in statements for node in ast.walk(stmt)
-                   if isinstance(node, (ast.Assign, ast.AnnAssign))
-                   and node.value is not None]
-        changed = True
-        while changed:
-            changed = False
-            for node in assigns:
-                targets = node.targets if isinstance(node, ast.Assign) else [
-                    node.target]
-                new = {t.id for t in targets if isinstance(t, ast.Name)} - names
-                if new and test(node.value, names):
-                    names |= new
-                    changed = True
-        return names
+    # Правила разбора (часы и живые файлы) — модуль пульта
+    # `orchestrator/test_lint.py`: тот же разбор зовёт гейт выхода
+    # `tests_writing` до лока планки (решение Оператора 23.10.2026).
+    # Перечень `_EXCEPTIONS` и обход дерева `tests/` остаются здесь.
 
     @classmethod
-    def _live_reads(cls, func, module_roots: set, module_live: set) -> list:
-        local_roots = cls._bound_names(
-            func.body, lambda value, names: cls._rooted(
-                value, module_roots | names))
-        roots = module_roots | local_roots
-        found = []
-        for node in ast.walk(func):
-            if cls._live_path(node, roots):
-                found.append(f"строка {node.lineno}: путь к живому файлу "
-                             f"репозитория {ast.unparse(node)}")
-            elif (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
-                  and node.id in module_live):
-                found.append(f"строка {node.lineno}: имя модуля {node.id} — "
-                             f"путь к живому файлу репозитория")
-        return found
-
-    @classmethod
     def _top_level_functions(cls, tree):
-        """(«Класс::метод» или «функция», узел) — функции верхнего уровня
-        модуля и методы его классов."""
-        for node in tree.body:
-            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
-                yield node.name, node
-            elif isinstance(node, ast.ClassDef):
-                for item in node.body:
-                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
-                        yield f"{node.name}::{item.name}", item
+        return test_lint.top_level_functions(tree)
 
     @classmethod
     def findings(cls, source: str, rel: str) -> dict:
-        """{«файл::метод»: [нарушения]} исходника `source` файла `rel`.
+        return test_lint.findings(source, rel)
 
-        Код модуля вне функций (кроме определений имён) не исполняет
-        ожиданий — его присваивания лишь связывают имена корня."""
-        tree = ast.parse(source)
-        from_time = cls._from_time_names(tree)
-        module_stmts = [node for node in tree.body
-                        if isinstance(node, (ast.Assign, ast.AnnAssign))]
-        module_roots = cls._bound_names(
-            module_stmts, lambda value, names: cls._rooted(value, names))
-        module_live = cls._bound_names(
-            module_stmts, lambda value, names: (
-                cls._live_path(value, module_roots)
-                or any(isinstance(sub, ast.Name) and sub.id in names
-                       for sub in ast.walk(value))))
-        result = {}
-        for qualname, func in cls._top_level_functions(tree):
-            hits = (cls._wall_clock_waits(func, from_time)
-                    + cls._live_reads(func, module_roots, module_live))
-            if hits:
-                result[f"{rel}::{qualname}"] = hits
-        return result
-
     @classmethod
     def tree_findings(cls, tests_dir: Path) -> dict:
         found = {}
@@ -2458,7 +2271,79 @@
             if qualname not in names:
                 problems.append(f"{key}: метода нет в файле")
         self.assertEqual([], problems, "\n".join(problems))
+
+    # Закреплённый набор правил (решение Оператора 23.10.2026): разбор живёт
+    # в незащищённом `orchestrator/test_lint.py`; точные находки образцов
+    # держат правило здесь, на виду у Оператора.
+    _RULE_CORPUS = {
+        'sleep_attr': (
+            'import time\n\nclass T:\n    def test_a(self):\n        time.sleep(1)\n',
+            {'tests/test_probe.py::T::test_a': ['строка 5: time.sleep с ненулевой паузой']}),
+        'sleep_from': (
+            'from time import sleep\n\ndef helper():\n    sleep(0.5)\n',
+            {'tests/test_probe.py::helper': ['строка 4: time.sleep с ненулевой паузой']}),
+        'sleep_zero_clean': (
+            'import time\n\nclass T:\n    def test_a(self):\n        time.sleep(0)\n',
+            {}),
+        'while_monotonic': (
+            'import time\n\nclass T:\n    def test_a(self):\n        deadline = time.monotonic() + 5\n        while time.monotonic() < deadline:\n            pass\n',
+            {'tests/test_probe.py::T::test_a': ['строка 6: цикл до срока по time.monotonic()/time.time()']}),
+        'for_if_time': (
+            'import time\n\nclass T:\n    def test_a(self):\n        for _ in range(10):\n            if time.time() > 3:\n                break\n',
+            {'tests/test_probe.py::T::test_a': ['строка 5: цикл до срока по time.monotonic()/time.time()']}),
+        'from_monotonic': (
+            'from time import monotonic\n\nclass T:\n    def test_a(self):\n        while monotonic() < 9:\n            pass\n',
+            {'tests/test_probe.py::T::test_a': ['строка 5: цикл до срока по time.monotonic()/time.time()']}),
+        'targets_file': (
+            'from pathlib import Path\n\nclass T:\n    def test_a(self):\n        Path(__file__).parent.parent / "targets.yaml"\n',
+            {'tests/test_probe.py::T::test_a': ["строка 5: путь к живому файлу репозитория Path(__file__).parent.parent / 'targets.yaml'"]}),
+        'roles_joinpath': (
+            'from pathlib import Path\n\nclass T:\n    def test_a(self):\n        Path(__file__).resolve().parent.joinpath("roles.yaml")\n',
+            {'tests/test_probe.py::T::test_a': ["строка 5: путь к живому файлу репозитория Path(__file__).resolve().parent.joinpath('roles.yaml')"]}),
+        'model_sets_osjoin': (
+            'import os\n\nclass T:\n    def test_a(self):\n        os.path.join(os.path.dirname(__file__), "model_sets.yaml")\n',
+            {'tests/test_probe.py::T::test_a': ["строка 5: путь к живому файлу репозитория os.path.join(os.path.dirname(__file__), 'model_sets.yaml')"]}),
+        'docs_dir': (
+            'from pathlib import Path\nROOT = Path(__file__).parent.parent\n\nclass T:\n    def test_a(self):\n        ROOT / "docs" / "backlog.md"\n',
+            {'tests/test_probe.py::T::test_a': ["строка 6: путь к живому файлу репозитория ROOT / 'docs' / 'backlog.md'", "строка 6: путь к живому файлу репозитория ROOT / 'docs'"]}),
+        'module_live_name': (
+            'from pathlib import Path\nTARGETS = Path(__file__).parent.parent / "targets.yaml"\n\nclass T:\n    def test_a(self):\n        TARGETS.read_text()\n',
+            {'tests/test_probe.py::T::test_a': ['строка 6: имя модуля TARGETS — путь к живому файлу репозитория']}),
+        'model_sets_rel': (
+            'from pathlib import Path\nfrom orchestrator import config\n\nclass T:\n    def test_a(self):\n        Path(__file__).parent.parent / config.MODEL_SETS_REL\n',
+            {'tests/test_probe.py::T::test_a': ['строка 6: путь к живому файлу репозитория Path(__file__).parent.parent / config.MODEL_SETS_REL']}),
+        'sandbox_root_clean': (
+            'from orchestrator import config\n\nclass T:\n    def test_a(self):\n        config.ROOT / "targets.yaml"\n',
+            {}),
+        'ns_clocks': (
+            'import time\n\nclass T:\n    def test_a(self):\n        while time.monotonic_ns() < 9:\n            pass\n\n    def test_b(self):\n        while time.time_ns() < 9:\n            pass\n',
+            {'tests/test_probe.py::T::test_a': ['строка 5: цикл до срока по time.monotonic()/time.time()'], 'tests/test_probe.py::T::test_b': ['строка 9: цикл до срока по time.monotonic()/time.time()']}),
+        'async_for': (
+            'import time\n\nclass T:\n    async def test_a(self):\n        async for _ in g():\n            if time.time() > 3:\n                break\n',
+            {'tests/test_probe.py::T::test_a': ['строка 5: цикл до срока по time.monotonic()/time.time()']}),
+        'sleep_false_kw': (
+            'import time\n\nclass T:\n    def test_a(self):\n        time.sleep(False)\n\n    def test_b(self):\n        time.sleep(secs=0)\n',
+            {'tests/test_probe.py::T::test_a': ['строка 5: time.sleep с ненулевой паузой']}),
+    }
 
+    def test_rule_corpus_is_frozen(self):
+        """Каждый образец набора даёт ровно закреплённые находки с точными
+        текстами «строка N: …»; чистые образцы — ни одной; исходник с
+        синтаксической ошибкой — `SyntaxError`, как прежде.
+
+        Ловит мутацию: из `orchestrator/test_lint.py` убрано имя живого
+        файла, вид цикла (`for`, `async for`, условие `if` в теле), часы
+        `*_ns`, форма пути (`joinpath`, `os.path.join`), `from time import …`,
+        имя модуля от `__file__` или `MODEL_SETS_REL`; пауза `sleep(0)` или
+        `sleep(secs=0)` стала нарушением, а `sleep(False)` — нет; либо
+        `findings` глотает `SyntaxError`.
+        """
+        for name, (source, expected) in self._RULE_CORPUS.items():
+            with self.subTest(образец=name):
+                self.assertEqual(expected, self.findings(source, "tests/test_probe.py"))
+        with self.assertRaises(SyntaxError):
+            self.findings("def (", "tests/test_probe.py")
+
     # --- образцы ------------------------------------------------------------
 
     def assert_caught(self, source: str) -> None:
```

Бюджет: $40.
