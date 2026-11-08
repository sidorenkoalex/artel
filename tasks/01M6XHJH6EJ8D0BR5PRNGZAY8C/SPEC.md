---
task: 01M6XHJH6EJ8D0BR5PRNGZAY8C
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/test_lint.py, scripts/guard.py, orchestrator/project_profile.py, orchestrator/targets.py, orchestrator/advance_gates/tests_writing.py, orchestrator/amend.py, orchestrator/preflight.py, docs/codebase-map.md, tests/
merge_after: 01M6XGM3R08KRQED1GGQRST24S
budget_usd: 55
---

# SPEC: Метка размера у новых долгоживущих файлов и её статическая проверка на выходе из tests_writing (ADR-0032, этап 4)

## Контекст
ADR-0032 п. 2 (принят 08.11.2026, `e4de84a0`) вводит три размера теста:
малый (чистые функции, временный каталог, подмены; без настоящего git, БД
пульта и процессов), средний (песочница с настоящим git и БД пульта,
команда пульта в процессе теста), большой (дочерние процессы `artel.py` и
pytest, живые процессы, сигналы). Новые долгоживущие файлы объявляют
размер меткой `pytest.mark.size(...)` на уровне модуля; guard проверяет,
что метка есть и что ресурсы файла ей не противоречат. Существующие файлы
меток не получают; проверка статическая — сигнал, не гарантия.

Статика долгоживущих файлов сегодня — `guard.long_lived_errors_from_files`
(`scripts/guard.py:4425`): линт детерминизма (`lint_errors_from_files`,
`scripts/guard.py:4507`, правила — `orchestrator/test_lint.py::findings`,
`:190`) и стиль pytest; `lint_base` — {метка файла guard: залоченный
текст}, на выходе из `tests_writing` его нет, у `amend-tests` — есть.
Разбор `pytestmark` уже есть в guard (`_is_pytestmark_assign` `:1400`,
`_pytestmark_marks` `:1450`, псевдонимы — `_pytest_aliases` `:1977`).
Вызывающие: `orchestrator/advance_gates/tests_writing.py:518`, `:643`;
`orchestrator/amend.py:293`, `:317`, `:725`; `orchestrator/preflight.py:198`,
`:213`. Около 125 существующих тестовых файлов строят в песочнице образцы
долгоживущих файлов без метки и проходят через эту функцию — поэтому
правило включается полем профиля проекта, которого у вымышленных проектов
песочниц нет. `--strict-markers` не включён: незарегистрированная метка
даёт только `PytestUnknownMarkWarning`.

## Требования

1. **Поле профиля `size_marks`.** Необязательное подполе `test_profile`
   (входит в `targets.PROFILE_OPTIONAL`, `orchestrator/targets.py:93`) со
   значением `required`; нет поля — правило выключено. Иное значение —
   отказ разбора профиля, называющий `test_profile.size_marks`, найденное
   значение и ожидаемое `required`. `project_profile.Profile`
   (`orchestrator/project_profile.py:66`) несёт поле.
2. **Правила размера** — публичные функции `orchestrator/test_lint.py`
   (решение Оператора 1):
   - `heavy_sandbox_names(sources) -> frozenset`: по исходникам
     `tests/sandbox.py` и `tests/*_sandbox.py` (словарь путь → текст)
     отдаёт имена корней `RealGitSandbox`, `InitializedTmpRootTest`,
     `SchemaTmpRootTest`, `SchemaSeededTmpRootTest`,
     `TaskIdSchemaConnTmpRootTest` и всех их подклассов в этих файлах — в
     том числе через примеси и цепочки (на main это, например,
     `TaskSeededTmpRootTest`, `BudgetSeededTmpRootTest`,
     `SchemaConnTmpRootTest` `tests/sandbox.py:1861`, `ConnRealGitSandbox`
     `:2018`, `SyncedOriginConnSandbox` `:2027`, `OriginRealGitSandbox`
     `:2040`, `AutoOriginSandbox` `:2057`, `GitignoreCommittedRealGitSandbox`
     `:2076`, `ReportSandbox` `tests/report_outcome_sandbox.py:335`,
     `OutcomeGateSandbox` `tests/outcome_gate_sandbox.py:251`); классы, не
     наследующие корень (например, `TmpRootTest`), в перечень не входят;
   - `size_findings(source, label, heavy)` — список пар (номер строки,
     нарушение), `heavy` — перечень `heavy_sandbox_names`:
   - нет метки размера на уровне модуля (`pytestmark =
     pytest.mark.size("<имя>")`, в том числе в списке `pytestmark = [...]`,
     с псевдонимом модуля pytest) — нарушение «нет метки размера», строка 1;
   - имя вне `small`, `medium`, `large` или не строковый литерал —
     нарушение с найденным значением;
   - `small`: класс файла наследует имя из `heavy` — по имени базы, в том
     числе через локальный подкласс файла и цепочку локальных подклассов
     (решение 2), и при импорте с псевдонимом (`from tests.sandbox import
     RealGitSandbox as R`, `import tests.sandbox as sb` и
     `sb.RealGitSandbox`); тест или фикстура файла принимает параметр
     `real_git`, `origin_real_git` или `initialized_tmp_root`, либо берёт
     такую фикстуру через `pytest.mark.usefixtures(...)` на уровне модуля
     или теста (решение 6); файл импортирует `subprocess` или
     `multiprocessing` в любой из форм `import x`, `import x as y`,
     `from x import y`, или вызывает `os.system`, `os.popen`, `os.fork`,
     `os.spawn*` — нарушение с именем найденного;
   - `medium`: вызов `subprocess.run`, `subprocess.Popen`,
     `subprocess.call`, `subprocess.check_call`, `subprocess.check_output`,
     в любом узле выражений аргументов которого (`ast.walk`) есть
     строковый литерал, оканчивающийся на `artel.py`, или литерал
     `"pytest"`, либо имя уровня модуля или имя в теле той же функции
     (решение 6), присвоенное выражению с таким литералом, — нарушение «дочерний artel.py или pytest в среднем файле»;
   - `large` — без нарушений по ресурсам.
3. **Где применяется.** Новый именованный параметр `size_marks: bool =
   False` у `guard.long_lived_errors_from_files`; вызывающие
   (`tests_writing.py:518`, `:643`; `amend.py:293`, `:317`, `:725`;
   `preflight.py:198`, `:213`) передают `True`, когда профиль проекта
   задачи несёт `size_marks: required`. guard строит перечень
   `heavy_sandbox_names` по дереву проверки один раз на вызов и передаёт
   его в `size_findings`. Правила применяются к `.py` долгоживущей группы.
   Залоченный файл: если `lint_base[label]` есть и не несёт метки размера
   на уровне модуля (залочен до правила), правила размера к файлу не
   применяются; если несёт — применяются в полном объёме. На путях
   `amend-tests`, где `lint_base` сейчас не передаётся (`amend.py:293`,
   `:317`), вызывающий передаёт залоченные тексты так же, как на пути
   `amend.py:725`, — исключение залоченных файлов действует на всех путях
   (решение 5). Текст отказа — «<файл>:<строка>: размер — <нарушение>
   (ADR-0032 п. 2)».
4. **Приложения 1–3** (раздел «Материалы» ниже) — в PLAN.md без
   изменений текста: регистрация метки в `pyproject.toml`, включение
   `size_marks: required` у записи артели в `targets.yaml`, правило
   объявления размера в `skills/test-authoring.md`.

## Критерии приёмки

Все случаи «отдельными случаями» ниже — литералы `parametrize`; выпадение
любого элемента перечня — красный случай (решение Оператора 3).

AC-1. Given исходник без метки, When `size_findings`, Then нарушение «нет метки размера» в строке 1 (Поверхность решения: orchestrator.test_lint.size_findings(source, label, heavy) -> list[tuple[int, str]]; Размер проверки: малый).

AC-2. Given исходник `small` — отдельными случаями: класс наследует каждый из `RealGitSandbox`, `InitializedTmpRootTest`, `SchemaTmpRootTest`, `SchemaSeededTmpRootTest`, `TaskIdSchemaConnTmpRootTest`, `TaskSeededTmpRootTest`, `BudgetSeededTmpRootTest`, `OriginRealGitSandbox`, `SchemaConnTmpRootTest`, `ConnRealGitSandbox`, `SyncedOriginConnSandbox`, `AutoOriginSandbox`, `GitignoreCommittedRealGitSandbox`, `ReportSandbox`, `OutcomeGateSandbox` (перечень `heavy` — те же имена литералом); класс наследует локальный подкласс файла, а тот — песочницу из перечня; класс наследует локальный класс, который наследует другой локальный класс, а тот — песочницу (два уровня); песочница импортирована как `from tests.sandbox import RealGitSandbox as R` и через `import tests.sandbox as sb` с базой `sb.RealGitSandbox`; функция с параметром каждой из `real_git`, `origin_real_git`, `initialized_tmp_root`; `pytest.mark.usefixtures("<фикстура>")` для каждой из них на уровне модуля и на уровне теста; `import subprocess`, `import subprocess as sp`, `from subprocess import run`, `import multiprocessing`, `import multiprocessing as mp`, `from multiprocessing import Process`; вызовы `os.system`, `os.popen`, `os.fork`, `os.spawnl`, `os.spawnv`, — Then нарушение называет найденное; тот же исходник с `medium` — без нарушений по ресурсам. Отдельно: Given исходники-образцы строками в памяти (корень, подкласс через примесь, подкласс второго уровня, посторонний класс), When `heavy_sandbox_names`, Then перечень несёт корень и оба подкласса и не несёт постороннего класса (Поверхность решения: orchestrator.test_lint.size_findings(source, label, heavy) -> list[tuple[int, str]]; orchestrator.test_lint.heavy_sandbox_names(sources) -> frozenset; Размер проверки: малый).

AC-3. Given `small` с фикстурами `tmp_root`, `tmp_dir` и `from tests.sandbox import FakeProc`, Then нарушений нет (Поверхность решения: orchestrator.test_lint.size_findings(source, label, heavy) -> list[tuple[int, str]]; Размер проверки: малый).

AC-4. Given `medium` — отдельными случаями: каждая из `subprocess.run`, `subprocess.Popen`, `subprocess.call`, `subprocess.check_call`, `subprocess.check_output` с литералом `"orchestrator/artel.py"` и с литералом `"pytest"` в аргументах (например, `[sys.executable, "orchestrator/artel.py", "status"]`, `[sys.executable, "-m", "pytest", path]`); `subprocess.run([sys.executable, str(ROOT / "orchestrator" / "artel.py")])`; константа модуля `ARTEL = str(ROOT / "artel.py")` и `subprocess.run([sys.executable, ARTEL])`; имя, присвоенное в теле той же функции выражению с литералом `artel.py` и с литералом `"pytest"` и переданное вызову, — Then нарушение; тот же исходник `large` — без нарушений (Поверхность решения: orchestrator.test_lint.size_findings(source, label, heavy) -> list[tuple[int, str]]; Размер проверки: малый).

AC-5. Given `pytestmark = [pytest.mark.size("small"), pytest.mark.slow]` и `import pytest as pt` с `pt.mark.size("small")`, Then метка распознана; `size("huge")` и `size(NAME)` — нарушение с найденным значением (Поверхность решения: orchestrator.test_lint.size_findings(source, label, heavy) -> list[tuple[int, str]]; Размер проверки: малый).

AC-6. Given профиль вымышленного проекта с `size_marks: required` и новый долгоживущий файл без метки — отдельными случаями каждого пути вызова: выход из `tests_writing`, `amend-tests` с ветки, `amend-tests` из планки, `preflight`, — Then отказ называет файл и «нет метки размера»; профиль без поля, тот же файл — отказа нет. Отдельно: путь `amend-tests` из планки, залоченный текст без метки — отказа нет (Размер проверки: средний — каждый путь в песочнице вымышленного проекта).

AC-7. Given `guard.long_lived_errors_from_files(files, task_id, network_addresses=True, lint_base={label: text}, size_marks=True)`, где залоченный текст без метки и новый текст без метки, Then нарушений размера нет; где залоченный текст несёт `size("small")`, а новый — добавляет параметр `real_git` или снимает метку, Then отказ (Поверхность решения: scripts.guard.long_lived_errors_from_files(files, task_id, ..., lint_base, size_marks) -> list; Размер проверки: малый).

AC-8. Given `size_marks: other`, When разбор профиля, Then отказ называет `test_profile.size_marks`, значение `other` и ожидаемое `required`, текста «неизвестное подполе» нет (Размер проверки: малый).

AC-9. Мутации «правило размера применяется без `size_marks`», «подкласс песочницы из требования 2 не распознан», «`pytestmark` списком не распознан», «залоченный файл с меткой пропускается» — красные.

Безопасность тестов (из ТЗ): исходники — строками в памяти; вымышленный проект и рабочие копии — во временной песочнице (`tests.sandbox`); без сети; настоящая запись проектов пульта и его локальный слой не читаются;
настоящие файлы `tests/` не меняются.

## Решения Оператора на гейте SPEC
- Решение 1 (перечень из дерева проверки, `heavy_sandbox_names`,
  псевдонимы импорта) — требования 2, 3; AC-2. Сверено: классы
  `tests/sandbox.py:1861`, `:2018`, `:2027`, `:2057`, `:2076`,
  `tests/report_outcome_sandbox.py:335`, `tests/outcome_gate_sandbox.py:251`
  на месте и наследуют корни.
- Решение 2 (два уровня локальных подклассов) — требование 2; AC-2.
  `OriginRealGitSandbox` (`tests/sandbox.py:2040`) — класс модуля
  песочниц: в AC-2 он стоит в перечне баз, «локальный подкласс» —
  отдельный случай.
- Решение 3 (полный перебор литералами `parametrize`) — AC-2, AC-4.
- Решение 4 (каждый путь вызова) — AC-6.
- Решение 5 (`lint_base` на путях `amend.py:293`, `:317`) — требование 3;
  AC-6. Сверено: оба вызова сейчас без `lint_base`, `amend.py:725` — с ним.
- Решение 6 (`usefixtures`, формы импорта `subprocess`, имя в теле
  функции) — требование 2; AC-2, AC-4.
- Решение 7 (перенос разбора `pytestmark` в `test_lint.py`; приложение 3
  поверх `7aef13ab`) — записка разработчику в «Материалах»; AC-1, AC-5.
  Сверено: `orchestrator/test_lint.py:10` импортирует только `ast`,
  `scripts/guard.py` импортирует `test_lint`.
- Все проверки — против временного дублёра: исходники строками в памяти,
  вымышленный проект во временной песочнице.

## Оценка объёма и деление
Сработавший сигнал: число файлов зоны ≥ 5 (7 модулей кода плюс
`docs/codebase-map.md` и `tests/`). Прочие сигналы: критериев 9 (< 10),
`budget_usd` 55 (< порога), слов-маркеров нет.

**Обоснование монолита** (материал для решения Оператора): поле профиля
(требование 1), функция правил (требование 2) и подключение у вызывающих
(требование 3) — одна смена механики. Часть «правила без подключения»
мержима, но не даёт свойства ADR-0032 п. 2 и не проверяема критерием
AC-6; часть «подключение без поля профиля» невозможна — `True` у
вызывающих выводится из поля. Семь модулей зоны — в основном точечные
правки вызовов (`tests_writing.py`, `amend.py`, `preflight.py` — передать
флаг из профиля), ядро — `test_lint.py` и `guard.py`. Приложение 2
(`targets.yaml`) включает правило у артели и осмысленно только вместе с
кодом, который поле читает. Деление дало бы 2–3 задачи по ~$25 с общей
ценой выше монолита.

## Не входит
- Метки в существующих файлах и реестр размеров по замеру (этап 1 ADR-0032).
- Сверка времени теста с ориентиром размера.
- Правила о фикстурах общего состояния (этап 5).
- Изменение линта детерминизма и правил стиля pytest.
- Правка локального слоя записей проектов (`.artel/targets.yaml`).
- Правка существующих тестов: если краснеет тест, сверяющий точный
  перечень подполей профиля или текст отказов
  `long_lived_errors_from_files`, — эскалация с именем теста, без правки.
  Полный зелёный набор `tests/` её держит пульт.
- Правка защищённых путей `pyproject.toml`, `targets.yaml`,
  `skills/test-authoring.md` в ветке — только приложениями PLAN
  (требование 4).
- Только чтение: `docs/adr/0032-test-cost-and-growth.md`,
  `docs/adr/0027-pytest-style-tests.md`, `tests/sandbox.py`,
  `tests/fixtures.py`, `orchestrator/repo_context.py`, `orchestrator/artel.py`.

## Материалы
- ТЗ: `tasks/01M6XHJH6EJ8D0BR5PRNGZAY8C/TZ.md`; ADR-0032 п. 2.
- Порядок: после 01M6XGM3R08KRQED1GGQRST24S — Приложение 3 снято поверх
  приложений той задачи к `skills/test-authoring.md`, они должны быть в main.
- Заметки разработчику (из ТЗ и решения Оператора 7): поле — в
  `PROFILE_OPTIONAL`, иначе оно станет обязательным у всех профилей
  (`targets.py:1244`). Разбор `pytestmark` (`_is_pytestmark_assign`,
  `_pytestmark_marks`, `_pytest_aliases`) переносится в
  `orchestrator/test_lint.py`, `scripts/guard.py` берёт его оттуда —
  импорт `guard` из `test_lint` дал бы цикл. Приложение 3 снято поверх
  `7aef13ab`: если CI ветки покраснеет на неприменимом приложении,
  Оператор подтянет main в ветку командой `pull-main` в `verifying`. Задача, возвращённая в `tests_writing`
  после мержа правила, получит отказ на файлах без метки — роль ставит
  метку сама. Проба независимой проверки (выключатель набросан, 36 файлов,
  вызывающих эти гейты) — 569 тестов зелёные.

### Приложение 1 (регистрация метки размера): pyproject.toml

Защищённый путь; ADR-0032 п. 2.

```diff
diff --git a/pyproject.toml b/pyproject.toml
index 484d32b07..ebca46435 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -11,3 +11,8 @@
 testpaths = ["tests"]
 python_files = ["test_*.py"]
 timeout = 120
+# Метка размера теста (ADR-0032 п. 2): small — чистые функции и подмены,
+# medium — песочница с настоящим git и БД пульта, large — дочерние процессы,
+# живые процессы, сигналы. Объявляется на уровне модуля новых долгоживущих
+# файлов: `pytestmark = pytest.mark.size("small")`.
+markers = ["size(name): размер теста — small, medium или large (ADR-0032)"]
```

### Приложение 2 (включение правила у записи артели): targets.yaml

Защищённый путь; ADR-0032 п. 2.

```diff
diff --git a/targets.yaml b/targets.yaml
index 0dd5a433b..061ca7df9 100644
--- a/targets.yaml
+++ b/targets.yaml
@@ -51,6 +51,9 @@ targets:
       report: junit-xml
       install: []
       full_suite_timeout_sec: 1500
+      # Метка размера обязательна у новых долгоживущих файлов (ADR-0032 п. 2):
+      # guard на выходе из tests_writing; у проекта без поля правило выключено.
+      size_marks: required
     # Справочник ядра в брифе developer/test_author (SPEC
     # 01M4S24963R9H18AN2XDP6R15B, 01M4S24EBVB72B8WYJ3JY96Y0E): модули ядра и
     # константы, которые роль получает коротким ответом «как пользоваться»;
```

### Приложение 3 (как объявлять размер файла): skills/test-authoring.md

Защищённый путь; ADR-0032 п. 2; дифф снят поверх приложений задачи этапа 3 01M6XGM3R08KRQED1GGQRST24S.

```diff
diff --git a/skills/test-authoring.md b/skills/test-authoring.md
index 91d08479f..e5b44a707 100644
--- a/skills/test-authoring.md
+++ b/skills/test-authoring.md
@@ -208,6 +208,15 @@ test_ac4_invariants_diff_attachment.py`.
 `initialized_tmp_root`); средний не запускает
 `artel.py` и pytest дочерним процессом. Не укладываешься в заявленный
 размер — эскалация с именем критерия, не тест большего размера молча.
+Размер файла объявляй меткой на уровне модуля:
+`pytestmark = pytest.mark.size("small")` (`"medium"`, `"large"`) — по
+самому тяжёлому тесту файла; тесты разных размеров разводи по файлам. У
+проекта с `size_marks: required` (артель) долгоживущий файл без метки,
+малый файл с песочницей настоящего git или БД пульта или с процессами и
+средний файл с дочерним `artel.py` или pytest guard отклоняет на выходе из
+`tests_writing` с именем файла и строкой. Проверка статическая: команда
+пульта внутри малого теста может сама вызвать git — размер такого теста
+выдаст замер, а ревьювер вернёт его замечанием.
 - Критерий несёт строку «Поверхность решения» — правило проверяй малыми
   тестами на этой функции: полный перебор конечных вариантов литералами
   `parametrize`, случайные входы от `random` — здесь, где они дёшевы.
```
