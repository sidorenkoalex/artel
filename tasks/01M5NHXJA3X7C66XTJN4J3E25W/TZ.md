---
task: 01M5NHXJA3X7C66XTJN4J3E25W
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: ADR-0027, часть Б: правила стиля pytest в скилах, инвариант общих фикстур, устойчивое подключение фикстур

# ADR-0027, часть Б: правила стиля pytest в скилах, инвариант общих фикстур, устойчивое подключение фикстур в conftest.py

## Факты

ADR-0027 «Новые тесты артели в стиле pytest» принят Оператором 23.10.2026 (`docs/adr/0027-pytest-style-tests.md`, пп. 1, 6, 7). Части А1 (01M5N9V4S984GRRXSMBK5JX7V1, общие фикстуры `tests/fixtures.py`, условное подключение в `conftest.py`) и А2 (01M5N9WK9SGB7KDYJP736DP6CV, правила guard) — смержены. Эта часть — приложения к защищённым путям; с её мержа стиль pytest обязателен для новых файлов (ADR-0027 п. 1, решение Оператора 23.10 по вопросу 1). Сверено с origin/main e2f34d71 (после А1); приложения проверены сессией `git apply --check` и прогоном нового инварианта на дереве с наложенными приложениями (10 passed).

- `skills/test-authoring.md` требует unittest (раздел «Каждый AC-n — тест либо пометка», `subTest` в «Стоимость и устойчивость долгоживущих тестов», раздел Vitest «Разделы выше о unittest»).
- `skills/review-checklist.md` — перечень того, чего гейт не видит, без фикстур pytest.
- `conftest.py`: `importlib.util.find_spec("tests.fixtures")` бросает `ModuleNotFoundError`, если нет самого пакета `tests` (независимая проверка А1 24.10) — зеркало с `conftest.py` без `tests/` упадёт при загрузке.
- Подмена закрытого имени `acceptance._x` после CR-8 этап 1 (01M5N8ASJ63ZKF3M9ETC7A3P5V) не действует на вызовы через публичное имя (строка бэклога 24.10).

## Требования

1. Приложения 1–4 ниже исполняются без изменений.
2. Тесты (новый файл в `tests/`, в стиле pytest; у каждой функции — «Ловит мутацию:»): (а) `conftest._fixtures_plugins()` при отсутствии пакета `tests` (временный каталог с копией `conftest.py` и пакетом `orchestrator` по симлинку, без `tests/`, `PYTHONPATH` только на этот каталог) — сбор pytest проходит, код 0 (подпроцесс); (б) при наличии `tests/fixtures.py` — фикстура `tmp_root` видна тесту-функции под `tasks/<id>/acceptance_tests/` без импорта (подпроцесс); (в) инвариант `SharedFixturesWrapSandboxClassesInvariantTest` краснеет на временной копии `tests/fixtures.py` с фикстурой, подменяющей `config` сама (запуск метода инварианта с подменённым `PATH`). Тесты пишут задачи этой волны в стиле pytest — первые по новым правилам.
3. Существующие тесты не правятся и остаются зелёными.

Зоны: tests/

Ограничение зон по смыслу: в `tests/` — только новые файлы; правки защищённых путей — только Приложениями 1–4.

Только чтение/Приложением: conftest.py, skills/test-authoring.md, skills/review-checklist.md, tests/test_invariants.py (защищённые — Приложения 1–4). Только чтение: tests/fixtures.py, tests/sandbox.py, scripts/guard.py, docs/adr/0027-pytest-style-tests.md, orchestrator/acceptance.py.

Не входит: перевод существующих тестов (волны консолидации); ускорение `_pytest_aliases` в guard (строка бэклога 24.10); правки guard.

Бюджет: $25.

## Приложения PLAN

### Приложение 1 (устойчивое подключение общих фикстур): conftest.py

Защищённый путь; решение Оператора 23.10.2026 (ADR-0027 п. 2), уточнение по независимой проверке А1.

```diff
diff --git a/conftest.py b/conftest.py
index 2aecfdc..24a2325 100644
--- a/conftest.py
+++ b/conftest.py
@@ -30,8 +30,17 @@ from orchestrator.config import ARTEL_ROLE_ENV
 # если модуль есть в дереве прогона: зеркала репозитория в тестах берут
 # этот файл без `tests/fixtures.py`. Тест, запросивший фикстуру при
 # отсутствии модуля, падает с «fixture not found» — громко.
-pytest_plugins = (["tests.fixtures"]
-                  if importlib.util.find_spec("tests.fixtures") else [])
+def _fixtures_plugins() -> list:
+    """`["tests.fixtures"]`, если модуль находится; `find_spec` бросает
+    `ModuleNotFoundError`, когда нет самого пакета `tests` — тогда `[]`."""
+    try:
+        found = importlib.util.find_spec("tests.fixtures")
+    except ModuleNotFoundError:
+        return []
+    return ["tests.fixtures"] if found else []
+
+
+pytest_plugins = _fixtures_plugins()
 
 # Флаги pytest, за которыми следует отдельное значение — не позиционный
 # аргумент-путь (тот же список, что нёс `bash_guard._PYTEST_VALUE_FLAGS`).
```

### Приложение 2 (правила стиля pytest для роли test_author): skills/test-authoring.md

Защищённый путь; ADR-0027 пп. 1–4, 7; решение Оператора 23.10.2026 (вопрос 1 — стиль обязателен для новых файлов).

```diff
diff --git a/skills/test-authoring.md b/skills/test-authoring.md
index 2c859f6..5757841 100644
--- a/skills/test-authoring.md
+++ b/skills/test-authoring.md
@@ -25,8 +25,9 @@ refs/artifacts/T023) — код будут чинить под тест, не н
 Для каждого `AC-n` из SPEC — ровно один из трёх исходов, иначе выход
 невалиден и переход дальше откажет с именем критерия:
 
-- **Тест.** unittest в `tasks/<id>/acceptance_tests/test_*.py`, метод
-  `test_ac<n>_<что_проверяет>` (например `test_ac2_missing_mark_blocks_advance`).
+- **Тест.** Функция pytest в `tasks/<id>/acceptance_tests/test_*.py`
+  (стиль — раздел «Стиль pytest»), имя `test_ac<n>_<что_проверяет>`
+  (например `test_ac2_missing_mark_blocks_advance`).
   Имя метода — единственная связь критерия с тестом: отдельного
   документа-сводки нет, трассируемость и сводка на гейте читают его
   прямо из кода.
@@ -194,8 +195,39 @@ test_ac4_invariants_diff_attachment.py`.
 «команда — FSM — база — git»; тогда докстринг теста называет, какую связку
 он держит.
 
-Короткий конечный перечень вариантов перебирай целиком в одном тесте через
-`subTest`, не отдельным методом на вариант.
+Короткий конечный перечень вариантов перебирай целиком одной функцией
+через `@pytest.mark.parametrize` со списком литералов, не отдельной
+функцией на вариант (`subTest` — только в существующих файлах unittest).
+
+## Стиль pytest (ADR-0027)
+Новый тестовый файл — и файл планки, и долгоживущий файл в `tests/` —
+пишется в стиле pytest: функции модуля `def test_…`, простой `assert`,
+`pytest.raises(..., match=…)`, варианты — `parametrize` литералами.
+Существующий файл дописывается в своём стиле; смешение стилей в одном
+файле — отказ guard.
+
+- Песочницы — общие фикстуры `tests/fixtures.py` (подключены корневым
+  `conftest.py`, импорт не нужен): `tmp_dir`, `tmp_root`,
+  `initialized_tmp_root`, `real_git`, `origin_real_git`,
+  `light_transition` — экземпляр соответствующего класса
+  `tests/sandbox.py` после `setUp()`; атрибуты и методы — как у `self`
+  наследника класса.
+- Собственная фикстура объявляется в самом тестовом файле;
+  `conftest.py` в каталоге планки запрещён.
+- Фикстура только готовит окружение: утверждений и ожидаемых значений
+  в ней нет — ожидаемое пишется в теле теста или в литералах
+  `parametrize`. Правку литерала фикстуры залоченного теста гейт
+  неослабления снимает только мандатом Оператора.
+- Запрещены (отказ guard): утверждение в фикстуре или в её помощнике;
+  `pytest.xfail(`/`pytest.importorskip(` в теле теста; `pytest.skip(`
+  в фикстуре и на уровне модуля вне `pytestmark`;
+  `@pytest.fixture(params=…)`; `indirect=`; `pytest_generate_tests`;
+  `request.getfixturevalue(`; `@pytest.fixture(name=…)`. Пропуск —
+  только видимой меткой `@pytest.mark.skipif(..., reason=…)`.
+- Подмена атрибута модуля пульта, у которого есть публичный близнец
+  (например `acceptance.reported` и `acceptance._reported`, CR-8),
+  делается по публичному имени: вызывающие модули берут публичное
+  имя, и подмена закрытого его не затронет.
 
 Тест не ждёт по реальному времени: `sleep` и опрос с таймаутом ради
 наступления события не применяются. Время и паузы подменяются. Предел
@@ -442,7 +474,7 @@ escalate/skip после ответа Оператора, проверь, что
 05.09.
 
 ## Компонент с меткой `AC-<n>: ` (Vitest)
-Разделы выше о unittest (метод `test_ac<n>_…`, `test_*.py`, `_*.py`,
+Разделы выше о тестах Python (функция `test_ac<n>_…`, `test_*.py`, `_*.py`,
 пометки `# AC-n: …`, `tests/`, `tests/sandbox.py`) относятся к
 Python-компоненту и к артели. Если компонент проекта задачи получает от
 правила планки метку `AC-<n>: ` (`project_profile.plank_rule`,
```

### Приложение 3 (что ревьювер сверяет глазами): skills/review-checklist.md

Защищённый путь; ADR-0027 п. 7.

```diff
diff --git a/skills/review-checklist.md b/skills/review-checklist.md
index 4231275..64157aa 100644
--- a/skills/review-checklist.md
+++ b/skills/review-checklist.md
@@ -100,8 +100,10 @@ MVP): проверяй PLAN.md первым блоком того же прог
      журнальная запись «ослабление тестов разрешено мандатом
      Оператора»), либо замечание major. Отдельно проверь то, чего гейт не видит:
      сужение данных под неизменным утверждением (`setUp`, списки в циклах
-     и `subTest`, файлы фикстур), перенос утверждения под условие,
-     вспомогательные функции глубже первого уровня.
+     и `subTest`, файлы фикстур, фикстуры pytest глубже первого уровня и
+     цепочка «помощник — фикстура `tests/fixtures.py` — тест в другом
+     файле»), перенос утверждения под условие, вспомогательные функции
+     глубже первого уровня.
 
 ## Задача класса «рефакторинг» (правила T015)
 Если ТЗ/SPEC называет задачу рефакторингом, к Фазе B добавь:
```

### Приложение 4 (инвариант: общие фикстуры — переходники над песочницами): tests/test_invariants.py

Защищённый путь; ADR-0027 п. 6.

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index 3d106dd..673d8ed 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -3165,3 +3165,55 @@ class ReportedOutcomeNotGreenInvariantTest(unittest.TestCase):
                                  vitest["profile"])
             self.assertEqual(run.green, expected, flow.note(
                 f"повторов {retries}: {run}\n{out}"))
+
+
+class SharedFixturesWrapSandboxClassesInvariantTest(unittest.TestCase):
+    """ADR-0027 (часть Б): каждая общая фикстура `tests/fixtures.py` —
+    переходник над классом песочницы `tests/sandbox.py`, своей подготовки
+    и подмен путей `config` в ней нет. Тело фикстуры — ровно импорт
+    класса из `tests.sandbox` и `yield from _sandbox(<класс>)`; класс —
+    наследник `TmpDirTest` или `TmpRootTest`. Так изоляция фикстуры
+    совпадает с изоляцией класса и держится инвариантом 37 (классы с
+    собственным `PATCHED_ATTRS`).
+
+    Ловит мутацию: фикстура подменяет `config` сама (частичный набор
+    путей) или отдаёт не песочницу — тело фикстуры не совпадает с
+    шаблоном переходника."""
+
+    PATH = REPO_ROOT / "tests" / "fixtures.py"
+
+    @staticmethod
+    def _is_fixture(node) -> bool:
+        for dec in node.decorator_list:
+            target = dec.func if isinstance(dec, ast.Call) else dec
+            if ast.unparse(target) in ("pytest.fixture", "fixture"):
+                return True
+        return False
+
+    def _wrapped_class(self, node) -> str:
+        body = [st for st in node.body
+                if not (isinstance(st, ast.Expr)
+                        and isinstance(st.value, ast.Constant)
+                        and isinstance(st.value.value, str))]
+        self.assertEqual(len(body), 2, f"{node.name}: тело — не переходник")
+        imp, ret = body
+        self.assertIsInstance(imp, ast.ImportFrom, node.name)
+        self.assertEqual(imp.module, "tests.sandbox", node.name)
+        self.assertEqual(len(imp.names), 1, node.name)
+        name = imp.names[0].name
+        self.assertEqual(ast.unparse(ret), f"yield from _sandbox({name})",
+                         node.name)
+        return name
+
+    def test_every_shared_fixture_wraps_a_sandbox_class(self):
+        from tests import sandbox
+        tree = ast.parse(self.PATH.read_text(encoding="utf-8"))
+        fixtures = [n for n in tree.body
+                    if isinstance(n, ast.FunctionDef) and self._is_fixture(n)]
+        self.assertTrue(fixtures, "в tests/fixtures.py нет фикстур")
+        for node in fixtures:
+            with self.subTest(fixture=node.name):
+                cls = getattr(sandbox, self._wrapped_class(node))
+                self.assertTrue(
+                    issubclass(cls, (sandbox.TmpDirTest, sandbox.TmpRootTest)),
+                    f"{node.name}: {cls.__name__} — не песочница")
```
