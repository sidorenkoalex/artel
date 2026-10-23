---
task: 01M5MVSP9YW0DYA4YQ1KSG0AHF
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Тесты планки и долгоживущие тесты проверяются на ожидание по часам и чтение живых файлов до лока

## Подход
Разбор линта детерминизма переезжает дословно из классовых методов
`tests/test_invariants.py::DeterministicTestsLintTest` в модуль пульта
`orchestrator/test_lint.py` (только `ast`, без импорта `orchestrator`):
`classmethod`/`staticmethod` стали функциями модуля, `cls._X` — `X`,
константы `CLOCK_CALLS`, `LIVE_FILES`, `LIVE_FILE_CONFIG_ATTRS` — на уровне
модуля; публичны `findings` и `top_level_functions`, прочее — закрытые
помощники с прежними именами без класса. `SyntaxError` пробрасывается.

guard (`scripts/guard.py`) получает узел `lint_errors_from_files(files, *,
lint_base=None)`: на каждый (метка, текст) — `test_lint.findings`,
`SyntaxError` — пропуск файла; строки «<метка>::<метод>: строка N: …».
С базой метод гасится, только если в базе под тем же «Класс::метод»
одинаковый `ast.dump` узла (`ast.dump` без атрибутов — сдвиг строк не
меняет узел). `long_lived_errors_from_files` получает именованный
`lint_base=None` и зовёт узел в цикле сразу после пропуска не-`.py` без
метки, до `plank_file_group` — для каждого `.py` и только при
`network_addresses` (признак артели). Так выход `tests_writing` (оба гейта:
групп планки и долгоживущих файлов), `preflight` и долгоживущие файлы
`amend-tests` получают проверку без правки их кода; классы отказа прежние.

`orchestrator/amend.py`:
- файлы планки артели — `_plank_lint_errors` (метки приведены к форме
  `acceptance_tests/…` функцией `_plank_label`), считаются отдельно от
  `_group_line_errors` и складываются с его ошибками (ранний выход проверки
  групп их не отменяет) на трёх местах: `_amend_plank_only`,
  `_amend_with_long_lived`, `_cmd_amend_tests_from_branch`. База — снимок на
  `tests_locked_sha` (`_branch_tests_snapshot`) с теми же метками
  (`_plank_lint_base`);
- долгоживущие файлы, путь рабочей копии — база = голова кодовой ветки до
  правки (`_code_head_long_lived`), параметр `lint_base` у
  `_long_lived_errors`;
- `--from-branch` — `_locked_long_lived_texts`: файл с суммой головы, равной
  перечню, — база сам себе (не проверяется); иначе — текст ревизии из
  `git log <голова> -- <файл>`, где sha256 blob равен сумме перечня
  (`_text_with_digest`); ревизии нет — базы нет, проверяются все методы.
  Передаётся через `_check_code_head_long_lived(lint_base=…)`.
- пути «по правилу» (`_by_rule`) не тронуты: у артели правило планки всегда
  по умолчанию (`project_profile.plank_rule`), а у чужого проекта линта нет.

Защищённый `tests/test_invariants.py` правится только Приложением 1 (текст
Оператора из SPEC, без изменений); в рабочей копии файл не меняется.

## Шаги
1. `orchestrator/test_lint.py` — перенос разбора; однократное сравнение
   эквивалентности на дереве `tests/`.
2. `scripts/guard.py` — `lint_errors_from_files`, `lint_base`, вызов в
   `long_lived_errors_from_files`.
3. `orchestrator/amend.py` — база и линт планки/долгоживущих на путях
   рабочей копии и `--from-branch`.
4. Приложение 1 к `tests/test_invariants.py`; `git apply --check`, прогон
   `DeterministicTestsLintTest` с приложением; карта кодовой базы.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 4 |
| 3 | 2 |
| 4 | 2, 3 |
| 5 | 2 |
| 6 | 2, 3 |
| 7 | долгоживущие файлы test_author (`tests/test_01m5mvsp9yw0dya4yq1ksg0ahf_*.py`) |
| 8 | 1 |
| 9 | 1–4 |

## Влияние на систему
- Гейты выхода `tests_writing`, `preflight` и `amend-tests` артели стали
  строже: новые отказы — только на нарушение правила, которое уже держит
  инвариант дерева `tests/`; классы отказов прежние
  (`refusal_classes.py:116–117`). Чужие проекты не затронуты
  (`network_addresses` ложно).
- Ничего не ослаблено: правило перенесено побайтно (сравнение ниже), перечень
  `_EXCEPTIONS` и тесты-образцы не тронуты, а `test_rule_corpus_is_frozen`
  в защищённом файле закрепляет точные находки.
- Задачи, залоченные до правки: в `amend-tests` неизменённые методы
  гасятся базой лока, поэтому старые нарушения отказа не дают.
- Цикл импорта исключён: `test_lint` импортирует только `ast`.
- Откат — revert merge-коммита задачи (приложение откатывается тем же
  revert'ом).

### Однократное сравнение эквивалентности (требование 8, AC-2)
Ветка до применения приложения, прежний разбор —
`tests.test_invariants.DeterministicTestsLintTest.findings`, новый —
`orchestrator.test_lint.findings`, на каждом `tests/**/*.py` с меткой
`tests/<путь>`:

```
файлов: 658 ключей прежний: 62 ключей новый: 62
побайтно равны: True True
```
(второе значение — `repr(old).encode() == repr(new).encode()`, третье — `old == new`).

### Проверка приложения
`git apply --check` текста Приложения 1 на чистом дереве ветки — проходит.
С приложением (применено временно и откачено `git checkout`):
`python3 -m pytest tests/test_invariants.py -k DeterministicTestsLintTest` —
`6 passed, 16 subtests passed`.

## Риски
- `--from-branch` перебирает `git log` файла и считает sha256 каждой
  ревизии — линейно по числу ревизий файла; долгоживущие файлы правятся
  редко.
- Помощники планки (`_*.py`, `markers.py`) линтом не проверяются — принятый
  Оператором пробел (SPEC, «Не входит»).

## Предложения системе
- `python3 -m pytest … -n 4` в рабочей копии роли падает «node down» —
  скил coding-standards про прогон затронутых модулей не говорит, что xdist
  тут недоступен; тесты затронутых модулей (19 файлов) шли 5 минут.

## Приложение 1 (вынос разбора линта детерминизма): tests/test_invariants.py

Текст Оператора из SPEC задачи, без изменений (решение Оператора
23.10.2026, вариант А).

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
