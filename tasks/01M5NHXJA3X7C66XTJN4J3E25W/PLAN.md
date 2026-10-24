---
task: 01M5NHXJA3X7C66XTJN4J3E25W
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: ADR-0027, часть Б — правила стиля pytest в скилах, инвариант общих фикстур, устойчивое подключение фикстур в conftest.py

## Подход
Задача целиком — правки защищённых путей, поэтому весь код идёт
приложениями этого PLAN (требование 1): Приложения 1–3 — дословно блоки
```diff раздела «Приложения PLAN» `TZ.md`, Приложения 4–5 — дословно блоки
раздела «Приложения Оператора (гейт SPEC 24.10.2026)» SPEC.md (Приложение 4
ТЗ заменено решением Оператора и в PLAN не переносится). Блоки перенесены
программно (извлечение текста между ```diff и ``` из TZ.md/SPEC.md), без
ручного набора — так исключён дрейф текста (AC-1).

Тесты требований 2–5 (а, б, в и пять мутаций AC-4) уже написаны ролью
test_author в долгоживущем файле
`tests/test_01m5nhxja3x7c66xtjn4j3e25w_shared_fixtures.py` (стиль pytest,
«Ловит мутацию:» у каждой функции) и залочены перечнем сумм; разработчик
его не правит и своих файлов в `tests/` не добавляет — свойств, не
покрытых им, у требований SPEC нет. Ветка не меняет ни одного файла кода
(AC-6): `*.py` в orchestrator/, scripts/, tests/ не правятся, карта кодовой
базы не регенерируется.

## Шаги
1. PLAN.md с Приложениями 1–5 в порядке номеров; проверка
   `git apply --check` каждого приложения по очереди на чистом дереве
   ветки (база после подтяжки main 8417c85b).
2. Прогон долгоживущего файла задачи на дереве «ветка + приложения»
   (временное наложение `git apply`, прогон, откат `git apply -R`) и
   планки командой `plank-run`.
3. `scripts/guard.py` на артефактах задачи, `status: ready`.

Проверено в шаге (24.10.2026, база 8417c85b): `git apply --check` каждого
из Приложений 1–5 по очереди на чистом дереве — код 0 у всех; на дереве
«ветка + Приложения 1–5» `python3 -m pytest
tests/test_01m5nhxja3x7c66xtjn4j3e25w_shared_fixtures.py
tests/test_invariants.py::SharedFixturesWrapSandboxClassesInvariantTest` —
12 passed, 98 subtests passed; дерево после `git apply -R` чистое.
`plank-run`: AC-5, AC-6 зелёные; AC-1 в шаге красный только потому, что
читает PLAN.md из ссылки документов, куда его переносит автокоммит пульта
по итогам шага.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 (долгоживущий файл test_author) |
| 3 | 2 |
| 4 | 2 |
| 5 | 2 |
| 6 | 1, 3 |

## Влияние на систему
- `conftest.py` (Приложение 1): `pytest_plugins` вычисляется функцией
  `_fixtures_plugins`, которая дополнительно ловит `ModuleNotFoundError`
  при отсутствии пакета `tests`; при наличии `tests/fixtures.py` поведение
  прежнее (`["tests.fixtures"]`), фикстуры видны как раньше.
- `tests/test_invariants.py` (Приложение 4): добавлен новый класс
  инварианта 42, существующие инварианты не меняются — гейты и проверки
  только усиливаются. `docs/invariants.md` (Приложение 5) — одна строка
  реестра.
- `skills/test-authoring.md`, `skills/review-checklist.md`
  (Приложения 2–3): с мержа новые тестовые файлы — только в стиле pytest;
  существующие файлы unittest дописываются в своём стиле.
- Откат — revert merge-коммита задачи (приложения ложатся в него).

## Риски
- Приложения 1–3 нарезаны на e2f34d71; если main успеет поменять те же
  места `skills/*.md` или `conftest.py` до мержа, приложение перестанет
  применяться — гейт применимости на выходе `in_dev` и на мерже это
  покажет.

## Предложения системе

## Приложение 1 (устойчивое подключение общих фикстур): conftest.py

Защищённый путь; решение Оператора 23.10.2026 (ADR-0027 п. 2), текст —
Приложение 1 `TZ.md` без изменений.

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

## Приложение 2 (правила стиля pytest для роли test_author): skills/test-authoring.md

Защищённый путь; ADR-0027 пп. 1–4, 7; текст — Приложение 2 `TZ.md` без
изменений.

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

## Приложение 3 (что ревьювер сверяет глазами): skills/review-checklist.md

Защищённый путь; ADR-0027 п. 7; текст — Приложение 3 `TZ.md` без изменений.

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

## Приложение 4 (инвариант 42: общие фикстуры — переходники над песочницами): tests/test_invariants.py

Защищённый путь; ADR-0027 п. 6; текст — Приложение 4 раздела «Приложения
Оператора (гейт SPEC 24.10.2026)» SPEC.md без изменений (заменяет
Приложение 4 ТЗ).

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index 3d106dd..2d105f6 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -3165,3 +3165,83 @@ class ReportedOutcomeNotGreenInvariantTest(unittest.TestCase):
                                  vitest["profile"])
             self.assertEqual(run.green, expected, flow.note(
                 f"повторов {retries}: {run}\n{out}"))
+
+
+class SharedFixturesWrapSandboxClassesInvariantTest(unittest.TestCase):
+    """Инвариант 42 (docs/invariants.md; ADR-0027, часть Б): общие фикстуры
+    `tests/fixtures.py` — переходники над классами песочниц
+    `tests/sandbox.py`, своей подготовки и подмен в модуле нет:
+    (1) верхний уровень модуля — только строка документации, импорты и
+    определения функций; (2) у фикстуры единственный декоратор
+    `pytest.fixture`, тело — ровно импорт класса из `tests.sandbox` и
+    `yield from _sandbox(<класс>)`, класс — наследник `TmpDirTest` или
+    `TmpRootTest`; (3) ни одна функция модуля (в том числе `_sandbox` и
+    помощники уборки) не обращается к `config`, `mock`, `patch`,
+    `monkeypatch`, `setattr`, `environ`. Так изоляция фикстуры совпадает
+    с изоляцией класса и держится инвариантом 37.
+
+    Ловит мутацию: фикстура или `_sandbox` подменяет `config` сама,
+    фикстура задана присваиванием или дополнительным декоратором, фикстура
+    отдаёт не песочницу."""
+
+    PATH = REPO_ROOT / "tests" / "fixtures.py"
+    FORBIDDEN = {"config", "mock", "patch", "monkeypatch", "setattr", "environ"}
+
+    def _tree(self):
+        return ast.parse(self.PATH.read_text(encoding="utf-8"))
+
+    def test_module_top_level_is_imports_and_functions(self):
+        for index, node in enumerate(self._tree().body):
+            docstring = (index == 0 and isinstance(node, ast.Expr)
+                         and isinstance(node.value, ast.Constant)
+                         and isinstance(node.value.value, str))
+            with self.subTest(line=node.lineno):
+                self.assertTrue(
+                    docstring or isinstance(
+                        node, (ast.Import, ast.ImportFrom, ast.FunctionDef)),
+                    f"строка {node.lineno}: {ast.unparse(node)[:80]}")
+
+    def test_no_function_touches_config_or_patching(self):
+        for node in ast.walk(self._tree()):
+            if isinstance(node, ast.Name):
+                names = {node.id}
+            elif isinstance(node, ast.Attribute):
+                names = {node.attr}
+            elif isinstance(node, ast.alias):
+                names = set(node.name.split(".")) | {node.asname}
+            else:
+                continue
+            line = getattr(node, "lineno", 0)
+            with self.subTest(line=line):
+                self.assertFalse(names & self.FORBIDDEN,
+                                 f"строка {line}: {sorted(names & self.FORBIDDEN)}")
+
+    def test_every_shared_fixture_wraps_a_sandbox_class(self):
+        from tests import sandbox
+        fixtures = []
+        for node in self._tree().body:
+            if not isinstance(node, ast.FunctionDef) or not node.decorator_list:
+                continue
+            fixtures.append(node)
+            with self.subTest(fixture=node.name):
+                self.assertEqual(
+                    [ast.unparse(d) for d in node.decorator_list],
+                    ["pytest.fixture"], node.name)
+                body = [st for st in node.body
+                        if not (isinstance(st, ast.Expr)
+                                and isinstance(st.value, ast.Constant)
+                                and isinstance(st.value.value, str))]
+                self.assertEqual(len(body), 2,
+                                 f"{node.name}: тело — не переходник")
+                imp, ret = body
+                self.assertIsInstance(imp, ast.ImportFrom, node.name)
+                self.assertEqual(imp.module, "tests.sandbox", node.name)
+                self.assertEqual(len(imp.names), 1, node.name)
+                name = imp.names[0].name
+                self.assertEqual(ast.unparse(ret),
+                                 f"yield from _sandbox({name})", node.name)
+                cls = getattr(sandbox, name)
+                self.assertTrue(
+                    issubclass(cls, (sandbox.TmpDirTest, sandbox.TmpRootTest)),
+                    f"{node.name}: {cls.__name__} — не песочница")
+        self.assertTrue(fixtures, "в tests/fixtures.py нет фикстур")
```

## Приложение 5 (регистрация инварианта 42): docs/invariants.md

Защищённый путь; правило `docs/invariants.md` «Как добавить инвариант»,
п. 4; текст — Приложение 5 раздела «Приложения Оператора (гейт SPEC
24.10.2026)» SPEC.md без изменений.

```diff
diff --git a/docs/invariants.md b/docs/invariants.md
index a1ce905..b2a1085 100644
--- a/docs/invariants.md
+++ b/docs/invariants.md
@@ -69,6 +69,7 @@ docs/adr/0002-integrity-principle.md, CLAUDE.md.
 | 39 | Порядок состояний FSM — `in_dev → verifying → review → acceptance → merge_gate`: CI подтянутой головы кодовой ветки проверяется ДО ревьювера, не после. Девять рубежей перехода `in_dev → review` (подтяжка main, прогон приёмочной планки, гейт зон, гейт заявки мутации — новые и изменённые тесты `tests/` без строки «Ловит мутацию:» в докстринге, 01M29A0F88P9GKSXFW90F99H2N, гейт неослабления тестов — удаление, переименование и ослабление тестов `tests/` без мандата Оператора, 01M3FQ2V77QNK95Z599DM124QN, гейт ёмкости, лок планки, гейт «замечания ревью не отработаны», сверка головы на origin) стоят на `in_dev → verifying` целиком, без повтора на `verifying → review`; в `review` из `verifying` ведёт только зелёный CI головы. Возврат `changes_requested` — в `in_dev`, повторный вход в `review` — снова через `verifying` | `refs/artifacts/01M1TQ0TRCZPRZX22C4084NCPB:tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac01_ac09_state_order.py`; `refs/artifacts/01M1TQ0TRCZPRZX22C4084NCPB:tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac02_ac08_gates_moved_to_verifying.py` (приёмочные тесты задачи по адресу ссылки после мержа не исполняются, ADR-0018 п.2); `test_auto_cycle.py::FSM_STATES` | ADR-0015 (docs/adr/0015-ci-before-review.md); refs/artifacts/01M1TQ0TRCZPRZX22C4084NCPB:tasks/01M1TQ0TRCZPRZX22C4084NCPB/SPEC.md, требования 1-3 |
 | 40 | Git главной копии пульта не меняется в ходе задачи: от `new` до `done` (автокоммит шага, подтяжка `main`, мерж) ветки `refs/heads/*`, ссылки `refs/artifacts/*`, HEAD и `git worktree list` главной копии остаются прежними — ветка задачи, её рабочая копия, ссылка документов, временная рабочая копия мержа, коммит мержа и push живут в клоне проекта `.artel/projects/<имя>/repo`; git главной копии меняют только `pin-update`/`pin --to` и ремонт хуков самого пульта (`doctor --fix`) | `test_invariants.MainCopyGitUnchangedDuringTaskTest` | ADR-0021 пп. 1, 2, 12; refs/artifacts/01M42PENCS26D0656X8FR7DFA7:tasks/01M42PENCS26D0656X8FR7DFA7/SPEC.md, требования 2, 9 |
 | 41 | Неизвестный или неразобранный местный итог тестов не зелёный; повторы внутри прогона компонентов с отчётом пульта запрещены: у компонента с отчётом (`project_profile.reported` — компонент записи `components:` с `report` либо `test_profile` с `runner: pytest-own` и `report`) итог читается только из отчёта, а не из кода возврата и текста раннера; отчёта нет, он не разобран или пуст при ненулевом коде возврата — исход «неизвестно» (значение `acceptance.FULL_SUITE_NOT_STARTED`, деталь «итог неизвестен: …»), не зелёный ни в одном месте прогона (прогон планки, сухой сбор, повтор красных, `plank-run`, полный набор, `suite-run`, двусторонний прогон), и `approve --accept-red` его не принимает; тест, прошедший с числом повторов больше 0, красит прогон с причиной «повтор» | `test_invariants.ReportedOutcomeNotGreenInvariantTest`; `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py` | refs/artifacts/01M590GJAF0EDV4NBC4C99MFVH:tasks/01M590GJAF0EDV4NBC4C99MFVH/SPEC.md, требования 3, 6, 19; ADR-0026 п. 4 |
+| 42 | Общие фикстуры-песочницы в стиле pytest не несут своей изоляции: каждая фикстура `tests/fixtures.py` — переходник над классом `tests/sandbox.py` (единственный декоратор `pytest.fixture`, тело — импорт класса из `tests.sandbox` и `yield from _sandbox(<класс>)`, класс — наследник `TmpDirTest`/`TmpRootTest`), верхний уровень модуля — только импорты и функции, ни одна функция модуля не обращается к `config` и средствам подмены — изоляция фикстуры равна изоляции класса (инвариант 37) | `test_invariants.SharedFixturesWrapSandboxClassesInvariantTest` | ADR-0027 пп. 2, 6; refs/artifacts/01M5NHXJA3X7C66XTJN4J3E25W:tasks/01M5NHXJA3X7C66XTJN4J3E25W/SPEC.md |
 
 ## На ревью — тестом не выражаются
 
```
