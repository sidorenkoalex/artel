---
task: 01M58PG72PG64GS790XM2EWS61
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: G1а-2: компоненты проекта — проверки doctor (версии инструментов, карта путей CI, каталоги) и ключ кэша итога

## Фаза A — план
- Таблица покрытия полна: требования 1-13 привязаны к шагам 1-4.
- Шаги проверяемые и по размеру как MR: ключ кэша, строка предела, `component_checks`, тесты.
- Подход согласуется с ANSWER-1/ANSWER-2: помощник `with_tools` один на `decide` и `_task_own_profile`; ключ базы прежний; `repo_context.py`/`suite_run.py` не тронуты. «Влияние на систему» соответствует diff: 4 кодовых файла зоны и новый `tests/test_component_checks.py`.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `doctor/cli.py::full_suite_timeout_check`: при `multi` — `skip` с `MULTI_COMPONENT_PENDING`, при `TargetsError` — `fail` с причиной; AC-1/AC-2 долгоживущего файла зелёные |
| 2 | OK | `component_checks` вызывается следом за `project_entry_checks`; имена `project-{tools,paths,workdir}-<проект>-<компонент>[-<инструмент>]` |
| 3 | OK | `which(path=…)` + `subprocess.run` с `env PATH`, таймаут 10 с; сравнение по числовым частям; stdout→stderr; ненулевой код — skip с кодом |
| 4 | OK | объединение `paths` и `depends_on` вида `paths`/`files`, warn с обеими строками |
| 5 | OK | `_top_level`/`regex_alternatives`; `^(a\|b)c` → skip «хвост» |
| 6 | OK | `find_variable`: YAML с кавычками/блоком, `[export ]KEY=`, комментарии пропускаются |
| 7 | OK | `check_workdir`; без `workdir` строки нет |
| 8 | OK | у записи без `components:` — `[]` (AC-15 doctor зелёный) |
| 9 | OK | `Profile.tools` (вне хэша), `with_tools` в `decide` и `_task_own_profile` |
| 10 | OK по коду, сторожа нет | `_lock_sums`: отслеживаемый файл берётся из блоба дерева, игнорируемый — из `root`; `full_suite` передаёт `root`. Проверку держит только разовая планка — см. R1-F1 |
| 11 | OK по коду, сторожа нет | `tools and not base` — ключ базы прежний; см. R1-F1 |
| 12 | OK | при пустых `tools` `data` не меняется; AC-15 планки сверяет с кодом базы — зелёный |
| 13 | OK | тесты без сети, учебные `/bin/sh`-инструменты, форма sled |

## Замечания
- major — `tests/test_component_checks.py` (в целом); свойства кода в `orchestrator/acceptance.py:2161-2182` (`_own_suite_result_key`) и `orchestrator/project_profile.py:229-239` (`with_tools`) — долгоживущие свойства ключа кэша итога (требования 9-11) закрыты только планкой `acceptance_tests/test_tools_key.py` и `test_base_and_unchanged_key.py` с пометкой `Группа: разовый`. Планку после мержа не гоняет никто. Без сторожа в `tests/` остаются:
  (а) смена объявленных `tools` меняет ключ рабочего дерева;
  (б) смена игнорируемого git файла блокировки при том же дереве меняет ключ;
  (в) `base=True` не зависит ни от `tools`, ни от файлов блокировки;
  (г) `decide` даёт профиль с `tools` единственного компонента.
  Проверено временной мутацией: убрал строку `data["tools"] = {...}` (acceptance.py:2182) — `tests/test_component_checks.py`, долгоживущий файл задачи и `tests/test_01m58fnwbv25ff26e7az9q9912_components.py` остались зелёными (28 passed). Сценарий: будущая правка ключа выбросит элемент `tools`, и гейт приёмки переиспользует зелёный итог после смены версии Node или игнорируемого `package-lock.json` без единого красного теста. Предложение: добавить в `tests/test_component_checks.py` тесты (а)-(в) на публичном `acceptance.suite_result_key(tree, profile, root=…, base=…)`, по образцу `TrackedLockKeyTest` (игнорируемый файл — через `.gitignore`), и (г) через `project_profile.with_tools`/`decide` на учебной записи; у каждого — заявка «Ловит мутацию».
- major — `tests/test_component_checks.py:25-32` (`test_unclosed_class_is_unparseable`) — заявка «по концу строки проверяется только глубина `()`» тестом не ловится. На входе `^(a|[b)` скобка `)` поглощается незакрытым классом, глубина в конце равна 1, и отказ даёт уже `depth`. Проверено временной мутацией: `if depth or in_class or escaped:` → `if depth:` (project_checks.py, `_top_level`) — тест зелёный (5 passed), при этом `regex_alternatives("a|[b")` вернул `{'a', '[b'}` вместо отказа. Проверка `in_class` в конце строки без сторожа. Предложение: вход с нулевой глубиной и незакрытым классом (например, `a|[b` или `^(a)|[b`) и заявка, соответствующая сломанному месту.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | tests/test_component_checks.py; orchestrator/acceptance.py:2161-2182, orchestrator/project_profile.py:229-239 | свойства ключа (tools и игнорируемый файл блокировки меняют ключ рабочего дерева, ключ базы от них не зависит, `decide` несёт `tools`) держит только разовая планка | после мержа удаление элемента `tools` из ключа не краснит ни один тест (проверено мутацией) — устаревший итог переиспользуется | добавить сторожа (а)-(г) в `tests/test_component_checks.py` на публичном `suite_result_key`/`with_tools`; fixed (developer, итерация 2): в `tests/test_component_checks.py` добавлены `ToolsKeyTest` — (а) `test_declared_tools_change_work_tree_key`, (б) `test_ignored_lock_change_changes_work_tree_key` (файл в `.gitignore`), (в) `test_base_key_ignores_tools_and_locks` — на публичном `suite_result_key`, и `DecideToolsTest` (г) на учебном `targets.yaml`; каждый краснеет на своей временной мутации, мутация «убрать `data["tools"]`» краснит (а) и (б) |
| R1-F2 | fixed | tests/test_component_checks.py:25-32 | заявка «проверяется только глубина `()`» не ловится: вход теста (ведущая группа с незакрытым классом внутри, см. «Замечания») отказывает и по глубине | проверка `in_class` в конце строки без сторожа; мутация `if depth:` зелёная, строка из альтернативы `a` и незакрытого класса `[b` на верхнем уровне разбирается | вход с нулевой глубиной и незакрытым классом, заявка по нему; fixed (developer, итерация 2): добавлен `test_unclosed_class_at_zero_depth_is_unparseable` — два входа с нулевой глубиной и незакрытым классом `[b` верхнего уровня (после альтернативы `a` и после группы `^(a)`); краснеет на мутации без `in_class` в конце строки |

## Вердикт
changes_requested — закрыть R1-F1 (сторожа ключа кэша в `tests/`) и R1-F2 (вход теста под заявленную мутацию). Код решения по SPEC корректен; замечания касаются только сторожей.

## Проверено исполнением
- `python3 …/artel.py plank-run 01M58PG72PG64GS790XM2EWS61` — 4 passed, код выхода pytest 0.
- `python3 -m pytest -q tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py tests/test_component_checks.py tests/test_01m58fnwbv25ff26e7az9q9912_components.py` — 28 passed, 168 subtests passed.
- Временная мутация `_top_level`: `if depth or in_class or escaped:` → `if depth:` — `tests/test_component_checks.py` 5 passed (не покраснел); `regex_alternatives('a|[b')` = `{'[b','a'}`. Код возвращён, `git status` чистый.
- Временная мутация `_own_suite_result_key`: строка `data["tools"] = …` удалена — три файла выше 28 passed (не покраснели). Код возвращён, `git status` чистый.
- CI коммита c59239ca — зелёный (из пакета).

## Предложения системе
- Класс «свойство кода помечено в планке `разовый`, потому что вход закрытый (`_task_own_profile`, `_profile_command`)»: часть свойства (ключ от `tools`/файлов блокировки, независимость ключа базы) проверяема через публичный `suite_result_key`, но в `tests/` её никто не перенёс. В skills/test-authoring.md стоит добавить правило: разовая пометка из-за закрытого входа обязывает автора назвать публичный срез свойства для `tests/`.
