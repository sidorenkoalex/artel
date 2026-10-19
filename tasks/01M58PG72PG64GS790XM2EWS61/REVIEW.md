---
task: 01M58PG72PG64GS790XM2EWS61
type: review
author_role: reviewer
status: changes_requested
iteration: 2
schema_version: 5
---

# REVIEW: G1а-2: компоненты проекта — проверки doctor (версии инструментов, карта путей CI, каталоги) и ключ кэша итога

## Фаза A — план
- Таблица покрытия полна (требования 1-13 → шаги 1-4); раздел «Проверка» дополнен итерацией 2 (сторожа R1-F1/R1-F2, временные мутации, `suite-run` №2 зелёный).
- «Влияние на систему» соответствует diff итерации: менялся только `tests/test_component_checks.py` (+127/−2), кодовые файлы не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1-8 | OK | код не менялся с итерации 1; долгоживущий файл задачи зелёный |
| 9 | OK по коду, сторож неполный | `decide` держит `DecideToolsTest`; вызов `with_tools` в `acceptance._task_own_profile` (acceptance.py:2464) без сторожа в `tests/` — см. R2-F1 |
| 10 | OK | `ToolsKeyTest`: (а) смена `tools`, (б) игнорируемый `package-lock.json` меняют ключ рабочего дерева — проверено мутациями |
| 11 | OK | `test_base_key_ignores_tools_and_locks` — мутация `if tools:` вместо `if tools and not base:` краснит его |
| 12 | OK | `test_tools_without_root_give_no_key_and_empty_tools_ignore_root`; AC-15 планки зелёный |
| 13 | OK | без сети, учебные git-репозитории и `targets.yaml` во временном каталоге |

## Замечания
- major — `orchestrator/acceptance.py:2464-2465` (`_task_own_profile` → `project_profile.with_tools`); тесты: `tests/test_component_checks.py` (нет сторожа) — то, что профиль автогейта приёмки несёт `tools` (требование 9, вход ключа рабочего дерева автогейта по требованию 10), держит только разовая планка (AC-12/AC-13). Проверено временной мутацией: `profile = project_profile.with_tools(target, Profile.from_values(...))` → `profile = Profile.from_values(...)` — 22 файла `tests/` (`test_component_checks.py`, долгоживущие файлы задачи и G1а, `test_acceptance*.py`, `test_full_suite_*.py`, `test_*pytest_own*.py`, `test_approve_acceptance_full_suite.py` и др.) — 240 passed, ни одного красного. Это тот же класс, что R1-F1, но в R1-F1 я назвал только вход `decide` — недосмотр прошлой итерации, к разработчику претензии за неполноту нет. Сценарий: будущая правка `_task_own_profile` уронит вызов помощника — у автогейта приёмки `Profile.tools` станут пустыми, ключ рабочего дерева перестанет видеть смену версии Node и игнорируемого файла блокировки, гейт переиспользует устаревший зелёный итог; ни один тест после мержа не покраснеет. Предложение: в `tests/test_component_checks.py` (по образцу `DecideToolsTest`, `config.TARGETS` на учебный файл) — тест, что `acceptance._task_own_profile` для записи с одним компонентом с `tools` даёт профиль с этими `tools` (и с пустыми у `test_profile`); если вход неудобен для `tests/` — сравнить ключ `suite_result_key(tree, _task_own_profile(...), root=…)` с ключом от профиля `decide`; заявка «Ловит мутацию: `_task_own_profile` не зовёт `with_tools` — `tools` пусты».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_component_checks.py; orchestrator/acceptance.py:2161-2182, orchestrator/project_profile.py:229-239 | свойства ключа (а)-(г) держала только разовая планка | — | accepted (reviewer, итерация 2): `ToolsKeyTest` и `DecideToolsTest` добавлены; временные мутации — удаление `data["tools"]` краснит (а) и (б), `"declared": {}` краснит (а), `if tools:` краснит (в), `decide` без `with_tools` краснит (г) |
| R1-F2 | accepted | tests/test_component_checks.py:36-45 | заявка про незакрытый класс не ловилась | — | accepted (reviewer, итерация 2): `test_unclosed_class_at_zero_depth_is_unparseable` (входы `a` и `[b` верхнего уровня, `^(a)` и `[b`) краснит мутация `if depth or escaped:` в `_top_level` (project_checks.py:549) |
| R2-F1 | open | orchestrator/acceptance.py:2464-2465; tests/test_component_checks.py | вызов `with_tools` в `_task_own_profile` (профиль автогейта приёмки) без сторожа в `tests/`, держит только разовая планка | мутация «убрать вызов помощника» — 22 файла `tests/` зелёные (240 passed); после мержа ключ автогейта может потерять `tools` без красного теста и переиспользовать устаревший итог | сторож в `tests/test_component_checks.py`: `_task_own_profile` записи с одним компонентом несёт его `tools`, у `test_profile` пусто; с заявкой «Ловит мутацию» |

## Вердикт
changes_requested — закрыть R2-F1 (сторож вызова `with_tools` в `_task_own_profile`). R1-F1 и R1-F2 приняты. Код решения по SPEC корректен; замечание касается только сторожа.

## Проверено исполнением
- `python3 -m pytest -q tests/test_component_checks.py tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py tests/test_01m58fnwbv25ff26e7az9q9912_components.py` — 33 passed, 167 subtests passed.
- `python3 …/artel.py plank-run 01M58PG72PG64GS790XM2EWS61` — 4 passed, код выхода pytest 0.
- Временные мутации (по одной, файл восстанавливался, `git status` в конце чистый) с прогоном `tests/test_component_checks.py`:
  - acceptance.py:2182 `data["tools"] = …` → `pass` — 2 failed (`test_declared_tools_change_work_tree_key`, `test_ignored_lock_change_changes_work_tree_key`);
  - project_checks.py:549 `if depth or in_class or escaped:` → `if depth or escaped:` — 1 failed (`test_unclosed_class_at_zero_depth_is_unparseable`);
  - acceptance.py:2164 `if tools and not base:` → `if tools:` — 1 failed (`test_base_key_ignores_tools_and_locks`);
  - `"declared": tools` → `"declared": {}` — 1 failed (`test_declared_tools_change_work_tree_key`);
  - project_profile.py:156 `decide` без `with_tools` — 1 failed (`test_decide_carries_single_component_tools`).
- Мутация R2-F1: acceptance.py:2464 `_task_own_profile` без `with_tools` — 22 файла `tests/` (перечень в замечании) — 240 passed, 400 subtests passed: не покраснел ни один.
- CI коммита aaf6a1d5 — зелёный (16 проверок, из пакета).

## Предложения системе
- review-checklist, «Полнота замечания»: когда свойство заходит в систему через несколько входов (здесь `decide` и `_task_own_profile` из требования 9), ревьюверу стоит перечислять сторожей на каждый вход SPEC сразу. Иначе, как в этой задаче, вторая итерация ловит то, что пропустила первая.
