---
task: 01M6XHJH6EJ8D0BR5PRNGZAY8C
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Метка размера у новых долгоживущих файлов и её статическая проверка на выходе из tests_writing (ADR-0032, этап 4)

## Подход
- Правила — в `orchestrator/test_lint.py` (только стандартная библиотека,
  без цикла импорта с guard): `heavy_sandbox_names(sources)` собирает
  классы всех исходников модулей песочниц до обхода и замыкает подклассы
  корней `HEAVY_SANDBOX_ROOTS` до неподвижной точки (результат не зависит
  от порядка словаря; корень входит, только если определён в исходниках);
  `size_findings(source, label, heavy)` — метка модуля (одна, литерал из
  `small|medium|large`), затем ресурсы малого/среднего файла.
- Разбор `pytestmark` и псевдонимов pytest (`is_pytestmark_assign`,
  `pytestmark_marks`, `pytest_aliases`) перенесён в `test_lint.py`
  дословно (решение 7); guard держит прежние имена `_is_pytestmark_assign`,
  `_pytestmark_marks`, `_pytest_aliases` ссылками на них, поведение guard
  не меняется. Присваивание с аннотацией (`pytestmark: list = […]`)
  распознаётся только правилами размера — флагом `annotated=True`, чтобы
  не менять разбор пропусков и стиля pytest (вне зоны задачи).
- `guard.long_lived_errors_from_files(…, size_marks=False,
  sandbox_sources=None)`: перечень `heavy` строится один раз на вызов
  (`None` — `sandbox_sources_from_dir(config.ROOT)`); правила исполняются
  для Python-файлов группы «долгоживущий» без метки `AC-<n>: `; файл,
  чей залоченный текст `lint_base[label]` не несёт метки модуля,
  освобождён (`_size_rules_apply`). Текст — «<файл>:<строка>: размер —
  <нарушение> (ADR-0032 п. 2)».
- Поле профиля: `targets.PROFILE_FIELDS["size_marks"]` вида `size_marks`,
  в `PROFILE_OPTIONAL`; иное значение (в том числе не строка) — «подполе
  'test_profile.size_marks' — '<значение>', ожидается required».
  Компонент наследует поле через `COMPONENT_FIELDS = dict(PROFILE_FIELDS…)`.
  `project_profile.Profile.size_marks` (вне сравнения),
  `size_marks_required(profile)`, `sandbox_sources_at(rev, repo)` (git).
- Вызывающие читают модули песочниц из того же дерева, что проверяемые
  файлы: `tests_writing._tests_writing_long_lived_gate` — голова кодовой
  ветки через git (сбой git — отказ класса «чинит Оператор»);
  `preflight` — диск рабочей копии кода; `amend` рабочая копия — диск
  рабочей копии, `--from-branch` — дерево головы кодовой ветки
  (`amend._sandbox_sources`). На пути `amend.py:317`
  (`_labelled_long_lived_errors`) теперь передаётся `lint_base` тем же
  механизмом, что `amend.py:725`: рабочая копия — тексты головы кодовой
  ветки до правки, `--from-branch` — `_locked_long_lived_texts`.
  Пути по файлам планки получают флаг и дерево рабочей копии для
  единообразия; правила там не исполняются (группа файлов иная).

## Шаги
1. `orchestrator/test_lint.py` — перенос разбора `pytestmark`, правила
   размера; `scripts/guard.py` — ссылки на перенесённое, параметры
   `size_marks`/`sandbox_sources`, `sandbox_sources_from_dir`.
2. `orchestrator/targets.py`, `orchestrator/project_profile.py` — поле
   профиля, флаг, чтение модулей песочниц из git.
3. Вызывающие: `advance_gates/tests_writing.py`, `preflight.py`,
   `amend.py`; `docs/codebase-map.md` регенерирована.
4. Тест `tests/test_size_marks_sources.py` — свойства сверх долгоживущих
   файлов задачи: `sandbox_sources=None` читает `config.ROOT`, отбор путей
   модулей песочниц, нестроковое значение подполя. Мутации проверены:
   `None` → пустой перечень, шаблон пути `.*\.py`, проверка значения
   только у строк — тест красный; мутации AC-9 (флаг не читается,
   залоченный с меткой пропущен, пустой перечень, первая метка списка,
   нет замыкания подклассов) краснят
   `tests/test_01m6xhjh6ej8d0br5prngzay8c_size_rules.py`.
5. Приложения 1–3 (ниже) — без изменений текста SPEC; `git apply --check`
   каждого на чистом дереве ветки прошёл.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 1 |
| 3 | 1, 3 |
| 4 | 5 |

## Влияние на систему
- Правило выключено у всех профилей без подполя (`size_marks=False` по
  умолчанию у guard; `size_marks_required` — только `required`): ~125
  тестов, строящих образцы без метки, и вымышленные проекты песочниц не
  меняют поведения. Включается у артели приложением 2 после мержа.
- Линт детерминизма, стиль pytest, признаки долгоживущих файлов не
  тронуты: перенос разбора `pytestmark` — дословный, guard ссылается на
  те же функции; `annotated` по умолчанию выключен.
- Изменение `amend.py:317`: `lint_base` теперь передаётся и на пути
  правила планки не по умолчанию — у внешнего проекта линт там не
  исполняется (`network_addresses` только у артели), значит меняется
  только исключение залоченных файлов для правил размера.
- Гейты/лимиты не ослаблены: добавлена только новая проверка за флагом.
  Тесты затронутых модулей (amend, preflight, labelled gates, long-lived
  transitions, профиль, guard, docs dir layout и др.) — зелёные.
- Откат — revert merge-коммита; приложение 2 откатывается вместе с ним
  (без кода, читающего поле, запись с полем отвергалась бы разбором).

## Риски
- Долгоживущий файл, ошибочно положенный в планку, получит и правила
  размера (группа «долгоживущий») — он и так отклоняется
  `long_lived_plank_errors`.
- Статика — сигнал: обходы (`_sandbox(...)`, функции модуля песочниц,
  `-m orchestrator.artel`) не ловятся — принятый пробел SPEC.
- Приложение 3 снято поверх `7aef13ab` — в ветке задачи main уже
  подтянут (`e086fa1c`), проверка применимости прошла.

## Предложения системе
- `python3 -m pytest -n 8` в шаге роли валит все воркеры («node down: Not
  properly terminated») — без подсказки в скиле, почему; тесты затронутых
  модулей пришлось гнать последовательно пачками ≤ 10 минут.

## Приложение 1 (регистрация метки размера): pyproject.toml

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

## Приложение 2 (включение правила у записи артели): targets.yaml

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

## Приложение 3 (как объявлять размер файла): skills/test-authoring.md

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
