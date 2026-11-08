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
2. **Правила размера** — публичная функция
   `orchestrator.test_lint.size_findings(source, label)`, возвращающая
   список пар (номер строки, нарушение):
   - нет метки размера на уровне модуля (`pytestmark =
     pytest.mark.size("<имя>")`, в том числе в списке `pytestmark = [...]`,
     с псевдонимом модуля pytest) — нарушение «нет метки размера», строка 1;
   - имя вне `small`, `medium`, `large` или не строковый литерал —
     нарушение с найденным значением;
   - `small`: класс файла наследует песочницу с настоящим git
     (`RealGitSandbox` и её подклассы) или с БД пульта
     (`InitializedTmpRootTest`, `TaskSeededTmpRootTest`,
     `BudgetSeededTmpRootTest`, `SchemaTmpRootTest`,
     `SchemaSeededTmpRootTest`, `TaskIdSchemaConnTmpRootTest` и их
     подклассы) — по имени базы, в том числе через локальный подкласс; тест
     или фикстура файла принимает параметр `real_git`, `origin_real_git`
     или `initialized_tmp_root`; файл импортирует `subprocess`,
     `multiprocessing` или вызывает `os.system`, `os.popen`, `os.fork`,
     `os.spawn*` — нарушение с именем найденного;
   - `medium`: вызов `subprocess.run`, `subprocess.Popen`,
     `subprocess.call`, `subprocess.check_call`, `subprocess.check_output`,
     в любом узле выражений аргументов которого (`ast.walk`) есть
     строковый литерал, оканчивающийся на `artel.py`, или литерал
     `"pytest"`, либо имя уровня модуля, присвоенное выражению с таким
     литералом, — нарушение «дочерний artel.py или pytest в среднем файле»;
   - `large` — без нарушений по ресурсам.
3. **Где применяется.** Новый именованный параметр `size_marks: bool =
   False` у `guard.long_lived_errors_from_files`; вызывающие
   (`tests_writing.py:518`, `:643`; `amend.py:293`, `:317`, `:725`;
   `preflight.py:198`, `:213`) передают `True`, когда профиль проекта
   задачи несёт `size_marks: required`. Правила применяются к `.py`
   долгоживущей группы. Залоченный файл: если `lint_base[label]` есть и
   не несёт метки размера на уровне модуля (залочен до правила), правила
   размера к файлу не применяются; если несёт — применяются в полном
   объёме. Текст отказа — «<файл>:<строка>: размер — <нарушение>
   (ADR-0032 п. 2)».
4. **Приложения 1–3** (раздел «Материалы» ниже) — в PLAN.md без
   изменений текста: регистрация метки в `pyproject.toml`, включение
   `size_marks: required` у записи артели в `targets.yaml`, правило
   объявления размера в `skills/test-authoring.md`.

## Критерии приёмки

AC-1. Given исходник без метки, When `size_findings`, Then нарушение «нет метки размера» в строке 1 (Поверхность решения: orchestrator.test_lint.size_findings(source, label) -> list[tuple[int, str]]; Размер проверки: малый).

AC-2. Given исходник `small` — отдельными случаями: класс наследует `RealGitSandbox`; локальный подкласс `OriginRealGitSandbox`; класс наследует `TaskSeededTmpRootTest`; функция с параметром `real_git`; `import subprocess`, — Then нарушение называет найденное; тот же исходник с `medium` — без нарушений по ресурсам (Поверхность решения: та же; Размер проверки: малый).

AC-3. Given `small` с фикстурами `tmp_root`, `tmp_dir` и `from tests.sandbox import FakeProc`, Then нарушений нет (Поверхность решения: та же; Размер проверки: малый).

AC-4. Given `medium` — отдельными случаями: `subprocess.run([sys.executable, "orchestrator/artel.py", "status"])`; `subprocess.run([sys.executable, "-m", "pytest", path])`; `subprocess.run([sys.executable, str(ROOT / "orchestrator" / "artel.py")])`; константа модуля `ARTEL = str(ROOT / "artel.py")` и `subprocess.run([sys.executable, ARTEL])`, — Then нарушение; тот же исходник `large` — без нарушений (Поверхность решения: та же; Размер проверки: малый).

AC-5. Given `pytestmark = [pytest.mark.size("small"), pytest.mark.slow]` и `import pytest as pt` с `pt.mark.size("small")`, Then метка распознана; `size("huge")` и `size(NAME)` — нарушение с найденным значением (Поверхность решения: та же; Размер проверки: малый).

AC-6. Given профиль вымышленного проекта с `size_marks: required` и новый долгоживущий файл без метки, When выход из `tests_writing`, Then отказ называет файл и «нет метки размера»; профиль без поля, тот же файл — отказа нет (Размер проверки: средний — подключение в песочнице вымышленного проекта).

AC-7. Given `guard.long_lived_errors_from_files(files, task_id, network_addresses=True, lint_base={label: text}, size_marks=True)`, где залоченный текст без метки и новый текст без метки, Then нарушений размера нет; где залоченный текст несёт `size("small")`, а новый — добавляет параметр `real_git` или снимает метку, Then отказ (Поверхность решения: scripts.guard.long_lived_errors_from_files(files, task_id, ..., lint_base, size_marks) -> list; Размер проверки: малый).

AC-8. Given `size_marks: other`, When разбор профиля, Then отказ называет `test_profile.size_marks`, значение `other` и ожидаемое `required`, текста «неизвестное подполе» нет (Размер проверки: малый).

AC-9. Мутации «правило размера применяется без `size_marks`», «подкласс песочницы из требования 2 не распознан», «`pytestmark` списком не распознан», «залоченный файл с меткой пропускается» — красные.

Безопасность тестов (из ТЗ): исходники — строками в памяти; вымышленный проект и рабочие копии — во временной песочнице (`tests.sandbox`); без сети; настоящая запись проектов пульта и его локальный слой не читаются.

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
- Заметки разработчику (из ТЗ): поле — в `PROFILE_OPTIONAL`, иначе оно
  станет обязательным у всех профилей (`targets.py:1244`); переиспользовать
  разбор `pytestmark` из guard. Задача, возвращённая в `tests_writing`
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
