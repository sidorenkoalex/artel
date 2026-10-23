---
task: 01M5NHXJA3X7C66XTJN4J3E25W
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/
budget_usd: 25
---

# SPEC: ADR-0027, часть Б — правила стиля pytest в скилах, инвариант общих фикстур, устойчивое подключение фикстур в conftest.py

## Контекст
ADR-0027 «Новые тесты артели в стиле pytest» (`docs/adr/0027-pytest-style-tests.md`,
пп. 1, 6, 7) принят Оператором 23.10.2026; части А1 (01M5N9V4S984GRRXSMBK5JX7V1,
общие фикстуры `tests/fixtures.py` и условное подключение в `conftest.py`) и
А2 (01M5N9WK9SGB7KDYJP736DP6CV, правила guard) смержены. Остались правки
защищённых путей: `skills/test-authoring.md` всё ещё требует unittest,
`skills/review-checklist.md` не называет фикстуры pytest в перечне того,
чего гейт не видит, а `conftest.py` (строки 33–34 на e2f34d71) зовёт
`importlib.util.find_spec("tests.fixtures")`, который бросает
`ModuleNotFoundError` без пакета `tests` — зеркало с `conftest.py` без
`tests/` падает при загрузке. Инварианта, что общая фикстура — только
переходник над классом песочницы, нет. С мержа этой части стиль pytest
обязателен для новых файлов (ADR-0027 п. 1).

Решения Оператора на гейте SPEC 24.10.2026 (круги 1 и 2, по SPEC-AUDIT.md):
Приложение 4 ТЗ заменено усиленным текстом (круг 2 — проверка всех сегментов
имени импортируемого модуля и псевдонима), добавлено Приложение 5 —
регистрация инварианта 42 в `docs/invariants.md`; оба текста — в разделе
«Приложения Оператора (гейт SPEC 24.10.2026)» ниже. Приложения 1–3 —
тексты из `TZ.md` задачи. CI ветки задачи накладывает приложения PLAN
перед тестами (`scripts/plan_appendix_ci.py`, jobs `python`/`python-min`),
поэтому новые тесты, опирающиеся на `conftest._fixtures_plugins` и на новый
инвариант, идут на дереве «ветка + приложения».

## Требования

1. В PLAN.md приложениями переносятся без изменений: Приложения 1–3 из
   `TZ.md` (Приложение 1 — `conftest.py`, Приложение 2 —
   `skills/test-authoring.md`, Приложение 3 — `skills/review-checklist.md`),
   Приложение 4 — `tests/test_invariants.py` в тексте, заменившем
   Приложение 4 ТЗ решением Оператора 24.10.2026, и Приложение 5 —
   `docs/invariants.md` (регистрация инварианта 42); тексты Приложений 4 и 5 —
   раздел «Приложения Оператора (гейт SPEC 24.10.2026)» этого SPEC.
2. Тесты задачи — новый файл в `tests/`, в стиле pytest (функции модуля,
   простой `assert`); у каждой тестовой функции — строка «Ловит мутацию:».
3. Тест (а): во временном каталоге с копией `conftest.py` и пакетом
   `orchestrator` по симлинку, без `tests/`, с `PYTHONPATH` только на этот
   каталог, сбор pytest в подпроцессе явно названного тест-файла этого
   временного каталога, с загруженным `conftest.py` (без `--noconftest`), без
   `ARTEL_ROLE` в окружении подпроцесса, завершается кодом 0
   (`conftest._fixtures_plugins()` при отсутствии пакета `tests`).
4. Тест (б): при наличии `tests/fixtures.py` фикстура `tmp_root` видна
   тесту-функции под `tasks/<id>/acceptance_tests/` без импорта (подпроцесс).
5. Тест (в): инвариант `SharedFixturesWrapSandboxClassesInvariantTest`
   краснеет на временной копии `tests/fixtures.py` с фикстурой, подменяющей
   `config` сама (запуск методов инварианта с подменённым атрибутом `PATH`),
   и на каждой из пяти мутаций временной копии, перечисленных в AC-4.
6. Существующие тесты не правятся и остаются зелёными; в `tests/` —
   только новые файлы; защищённые пути ветка не меняет — они правятся
   только Приложениями 1–5.

## Критерии приёмки

AC-1. На текущей базе ветки задачи (после подтяжки main) с наложенными приложениями PLAN.md содержимое `conftest.py`, `skills/test-authoring.md`, `skills/review-checklist.md`, `tests/test_invariants.py` и `docs/invariants.md` совпадает с результатом наложения на ту же базу текстов Приложений 1–3 из `TZ.md` и Приложений 4–5 из раздела «Приложения Оператора (гейт SPEC 24.10.2026)» этого SPEC — приложения в PLAN.md перенесены без изменений.

AC-2. Во временном каталоге с копией `conftest.py` (после Приложения 1) и пакетом `orchestrator` по симлинку, без каталога `tests/`, с `PYTHONPATH`, указывающим только на этот каталог, сбор явно названного тест-файла временного каталога, с загруженным `conftest.py` (без `--noconftest`), без `ARTEL_ROLE` в окружении подпроцесса — код 0.

AC-3. При наличии `tests/fixtures.py` тест-функция, лежащая под `tasks/<id>/acceptance_tests/` и запросившая фикстуру `tmp_root` параметром без импорта, проходит в подпроцессе pytest.

AC-4. Методы `SharedFixturesWrapSandboxClassesInvariantTest`, запущенные с `PATH`, подменённым на временную копию `tests/fixtures.py`, завершаются провалом (хотя бы одного метода) на каждой из мутаций копии: (0) добавлена фикстура, подменяющая `config` сама; (1) помощник `_sandbox` импортирует `config`; (2) у фикстуры дополнительный декоратор сверх `pytest.fixture`; (3) фикстура задана присваиванием (`<имя> = pytest.fixture(<функция>)`); (4) фикстура-переходник импортирует из `tests.sandbox` и отдаёт через `_sandbox` класс, не являющийся наследником `TmpDirTest`/`TmpRootTest`; (5) помощник `_sandbox` импортирует `config` с псевдонимом (`import orchestrator.config as cfg`). На немутированной копии `tests/fixtures.py` все методы зелёные.

AC-5. Тесты задачи — новый файл в `tests/` в стиле pytest: тестовые функции уровня модуля без классов `unittest.TestCase`, у каждой тестовой функции в докстринге строка «Ловит мутацию:».

AC-6. Ветка не меняет ни одного существующего файла в `tests/` и ни одного защищённого пути (`conftest.py`, `skills/test-authoring.md`, `skills/review-checklist.md`, `tests/test_invariants.py`, `docs/invariants.md` и прочие): в `tests/` добавляются только новые файлы, правки защищённых путей идут только приложениями PLAN.md.

## Оценка объёма и деление

Сработавший сигнал: зона задевает инвариантный механизм
(`tests/test_invariants.py` — Приложение 4 добавляет инвариант 42,
Приложение 5 регистрирует его в `docs/invariants.md`).

Прогноз диффа: 14 КиБ (пять приложений ~8 КиБ текстом плюс один новый
тестовый файл ~5–6 КиБ).

Обоснование монолита (материал для решения Оператора): задача уже — часть Б
нарезки ADR-0027 (А1, А2 смержены); правка механизма инварианта — одно
добавление класса Приложением 4 и строки реестра Приложением 5, существующие
инварианты не меняются. Тесты (а) и (в) опираются на
`conftest._fixtures_plugins` (Приложение 1) и на
`SharedFixturesWrapSandboxClassesInvariantTest` (Приложение 4), а
приложения к скилам (2, 3) вводят обязательность стиля, которому тесты
задачи и следуют: отделённые от приложений, тесты не имеют предмета, а
приложения без тестов остаются без проверки требований ТЗ. Объём (6
критериев, одна зона `tests/`, $25) ниже порогов деления.

## Не входит

- Перевод существующих тестов в стиль pytest (волны консолидации).
- Ускорение `_pytest_aliases` в guard (строка бэклога 24.10) и любые правки guard (`scripts/guard.py` — только чтение).
- Правки `tests/fixtures.py`, `tests/sandbox.py`, `docs/adr/0027-pytest-style-tests.md`, `orchestrator/acceptance.py` — только чтение.
- Зелёный полный набор `tests/` (существующие тесты остаются зелёными) — её держит пульт.

## Материалы

- `TZ.md` задачи, раздел «Приложения PLAN» — тексты Приложений 1–3 (Приложение 4 ТЗ заменено, см. ниже).
- Только чтение/Приложением (защищённые пути, правка — только Приложениями
  1–5): `conftest.py`, `skills/test-authoring.md`,
  `skills/review-checklist.md`, `tests/test_invariants.py`, `docs/invariants.md`.
- `docs/adr/0027-pytest-style-tests.md`, пп. 1, 2, 6, 7.
- SPEC части А1: `refs/artifacts/01M5N9V4S984GRRXSMBK5JX7V1`.
- `scripts/plan_appendix_ci.py` — наложение приложений PLAN в CI ветки задачи.
- `SPEC-AUDIT.md` задачи (круги 1 и 2, вердикт concerns) — основание решений Оператора 24.10.2026.

## Приложения Оператора (гейт SPEC 24.10.2026)

Тексты решения Оператора на гейте SPEC: Приложение 5 — круг 1, Приложение 4 —
круг 2 (24.10.2026, по SPEC-AUDIT.md: для импортов проверяются все сегменты
имени модуля и псевдоним). Приложение 4 проверено сессией на дереве main с
приложениями 1, 4, 5: зелёный; мутации «импорт `config` с псевдонимом в
`_sandbox`» и «`from orchestrator import config` в `_sandbox`» — красные.

### Приложение 4 (заменяет Приложение 4 ТЗ): tests/test_invariants.py

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

### Приложение 5 (регистрация инварианта 42): docs/invariants.md

Защищённый путь; правило `docs/invariants.md` «Как добавить инвариант», п. 4.

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
