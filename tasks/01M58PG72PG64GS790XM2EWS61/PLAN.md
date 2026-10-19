---
task: 01M58PG72PG64GS790XM2EWS61
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: G1а-2: компоненты проекта — проверки doctor и ключ кэша итога

## Подход
Две независимые части на общих учебных записях.

**doctor.** `full_suite_timeout_check` (`orchestrator/doctor/cli.py`)
перед `project_profile.full_suite_limit` смотрит `repo_context.profile_of`:
признак `multi` — строка `skip` с причиной `targets.MULTI_COMPONENT_PENDING`;
прочий `targets.TargetsError` перехватывается — строка `fail` с причиной,
цикл записей продолжается. Новый вход `project_checks.component_checks(name,
entry)` — рядом с `project_entry_checks` в цикле записей: только у записи с
`components:` (у `test_profile` строк нет), по компоненту — строка на
каждый инструмент `tools`, строка `paths_source`, строка `workdir`.
- `tools`: `PATH` — `env.PATH` компонента либо `PATH` процесса; наличие —
  `doctor.shutil.which(tool, path=PATH)`; запуск `doctor.subprocess.run(
  [<найденный путь>, "--version"], env={…, PATH}, timeout=10)` — тот же
  таймаут, что у `claude --version`/`codex --version` doctor. Версия —
  первая `\d+(\.\d+)*` stdout, иначе stderr; совпадение — по числу
  числовых частей требуемой (текст до первого пробела).
- `paths_source`: поиск переменной в файле клона (YAML `KEY:` с кавычками
  или блоком `>-`/`>`/`|-`/`|`, оболочка `[export ]KEY=`, комментарии
  пропускаются), разбор строки по правилу требования 5 (один `^`, одна
  ведущая группа, `|` верхнего уровня вне `()`/`[]`/после `\`), сравнение
  множеств с объединением `paths` компонента и `paths` его `depends_on`
  вида `paths`/`files`.
- `workdir`: `(клон / workdir).is_dir()`.

**Ключ кэша.** `Profile` получает поле `tools` (неизменяемое отображение,
вне хэша, по умолчанию пусто). Помощник `project_profile.with_tools(target,
profile)` берёт `tools` единственного компонента `components(target)`;
его зовут `decide` и `acceptance._task_own_profile`. `suite_result_key`
получает необязательный `root=` и передаёт его `_own_suite_result_key`;
`full_suite` зовёт ключ рабочего дерева с `root=root`. При `base=False` и
непустых `tools` в данные ключа добавляется элемент `tools`: объявленные
версии и суммы файлов блокировки `workdir` — отслеживаемый файл берётся
sha блоба из `git ls-tree <tree>`, игнорируемый — sha256 содержимого
рабочей копии. Без `root` при непустых `tools` ключа нет (`None` — прогон
без повторного итога, fail-closed). При пустых `tools` и при `base=True`
данные ключа прежние — байт в байт.

## Шаги
1. `Profile.tools`, помощник `with_tools`, вызовы в `decide` и
   `_task_own_profile`; элемент `tools` ключа рабочего дерева и `root` в
   цепочке `full_suite → suite_result_key → _own_suite_result_key`.
2. `full_suite_timeout_check` — `skip`/`fail` вместо исключения.
3. `component_checks` с проверками `tools`/`paths_source`/`workdir`,
   вызов в `all_checks`.
4. Юнит-тесты разбора строки и поиска переменной (`tests/test_doctor_component_parsing.py`),
   регенерация карты, прогон долгоживущего файла задачи, планки, тестов
   затронутых модулей.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 3 |
| 3 | 3 |
| 4 | 3, 4 |
| 5 | 3, 4 |
| 6 | 3, 4 |
| 7 | 3 |
| 8 | 3 |
| 9 | 1 |
| 10 | 1 |
| 11 | 1 |
| 12 | 1, 3 |
| 13 | 4 |

## Влияние на систему
- Ключ итога: при пустых `tools` (все сегодняшние записи — артель
  `pult-pytest`, sled `pytest-own`) данные ключа не меняются — сохранённые
  итоги не теряются (AC-15 планки сверяет с кодом базы). Ключ базы прежний
  при любых `tools` — гейт мержа и `suite-run` находят один и тот же итог.
- `Profile.tools` вне хэша и по умолчанию пуст: равенство `Profile`
  единственного компонента без `tools` и `test_profile` прежнее
  (`tests/test_01m58fnwbv25ff26e7az9q9912_components.py`).
- doctor: новые строки только у записей с `components:`; у записей с
  `test_profile` набор, исходы и тексты строк прежние. Перехват в
  `full_suite_timeout_check` не ослабляет проверку: отказ чтения профиля
  выходит строкой `fail` вместо падения команды.
- Гейты, лимиты, инварианты не трогаются. Откат — revert merge-коммита.

## Риски
- Учебные формы CI-файла шире разбираемых (якоря YAML, многострочные
  кавычки) дают `skip` с причиной, а не ложный `ok`.

## Проверка
- `tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py` — 12 passed,
  52 subtests; планка `plank-run` — 4 passed.
- `tests/test_component_checks.py` (свои сторожа: `|` в `[]`/после `\`,
  незакрытый класс, блок `|` и `"…"`, сумма отслеживаемого файла
  блокировки из блоба дерева, `tools` без `root` — ключа нет): 5 passed;
  временные мутации «класс `[` не распознаётся» и «отслеживаемый файл из
  рабочей копии» краснят три теста, код возвращён.
- Тесты затронутых модулей (18 файлов: doctor, full_suite_reuse,
  project_profile, suite_run, pytest-own, components G1а) — 252 passed.
- Карта `docs/codebase-map.md` регенерирована.
- `suite-run` №1 (полный набор): зелёный — прошло 5918, упало 0,
  пропущено 2.

## Предложения системе
- `orchestrator/doctor/__init__.py` (фасад) не входил в зоны, а новая
  функция проверки обязана идти через него по конвенции пакета — вызов
  сделан через `doctor.project_checks.component_checks`; аналитику стоит
  включать фасад в зоны задач, добавляющих проверку doctor.
