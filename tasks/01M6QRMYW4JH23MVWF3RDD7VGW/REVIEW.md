---
task: 01M6QRMYW4JH23MVWF3RDD7VGW
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Раннер compose: файлы машины и привилегии стенда — только внутри дерева прогона

## Фаза A — план
Таблица покрытия PLAN полна (требования 1–7 → шаг 1). Один шаг размера MR
оправдан: одна функция одного файла (так и в SPEC, «обоснование монолита»).
Подход — новый проход `_compose_tree_refusal` после прежнего — прямо даёт
требования 4 и 7, с архитектурой не конфликтует. «Влияние на систему»
совпадает с diff: `orchestrator/acceptance.py` + регенерированная карта;
откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_inside_tree` (`acceptance.py:1144`): не строка / не `isabs` → не внутри без `realpath` от cwd; `realpath` дерева берётся один раз (`:1225`); равенство и граница `+ os.sep`. bind (обе формы через `_bind_entries`), `file` секретов/конфигураций (только при наличии ключа `file`), `build` строкой/не словарь, `build.context` + `_git_address` по виду значения (ловит `<дерево>/r.git#main`), `additional_contexts` (`service:` проходит, `oci-layout://` — путь, прочая схема — отказ, не словарь — отказ), элемент `volumes` и элемент `secrets`/`configs` неверной формы — отказ с именем. |
| 2 | OK | `_privilege_refusal` по каждому сервису (не только тестовому); `build.ssh/privileged/entitlements` в `_build_refusal`; `no-new-privileges:true` проходит. |
| 3 | OK | Тексты называют сервис/секрет/конфигурацию, поле, значение (для строковых), причину; возврат прежним путём `ReportRun(refusal=…)` (`:1415`). |
| 4 | OK | Сокетные проверки bind и `file` — в прежнем цикле, тексты прежние; новый проход после. Строковый элемент секрета в сокетном цикле больше не поднимает `AttributeError` (`item if isinstance(item, dict) else {}`). |
| 5 | OK | Разбор `volumes` прежний: `type != bind` и короткая строка без `/ . ~` в источники не попадают; `driver_opts` не тронут. |
| 6 | OK | Версия «2: », правило называет новые отказы. |
| 7 | OK | Прежние проверки и их порядок не изменены (сверено телом функции `:1090-1132` против base); `_bind_sources` возвращает прежний список. |

## Замечания
Блокирующих и major нет. Вкусовое, без записи в реестр: между
`_git_address` и `_build_refusal` четыре пустые строки
(`orchestrator/acceptance.py:1163-1166`) — лишние две можно убрать при
следующей правке файла.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6qrmyw4jh23mvwf3rdd7vgw_compose_tree_bounds.py tests/test_01m6paj61d4pyap79adrpa6mwv_compose_run.py tests/test_01m6paj61d4pyap79adrpa6mwv_compose_docker.py` — 137 passed, 1 skipped (93 с); тесты ядра compose не покраснели.
- `artel.py plank-run 01M6QRMYW4JH23MVWF3RDD7VGW` — «планки нет: в refs/artifacts/… нет test_*.py»; у задачи только долгоживущий файл в `tests/`, он прогнан выше.
- Временные мутации (одним python-процессом, восстановление в `finally`, `git status` чист после) на долгоживущем файле задачи:
  - `real == real_tree` → `False` («только строго под деревом») — `-k ac7`: 2 failed (`bind_tree`, `context_tree`);
  - проверка `_git_address` для `build.context` снята — `-k ac3_build`: 1 failed (`@TREE@/r.git#main`);
  - `_UNSAFE_SECURITY_OPT` сужено до `seccomp:unconfined` — `-k ac6`: 3 failed (apparmor, label=, label:).
  Заявки «Ловит мутацию» AC-3, AC-6, AC-7 подтверждены.
- `python3 scripts/codebase_map.py` — расхождение с закоммиченной картой только в `built_at_sha`; изменение откачено `git checkout`.
- Дифф `tests/` вне файла задачи пуст — существующие тесты не тронуты.

## Предложения системе
- Песочница Bash роли отклоняет heredoc с `{"` («expansion obfuscation»): скрипт временной мутации пришлось класть файлом в каталог документов и убирать `task-rm` — тот же натир, что в PLAN разработчика; команда пульта для временной мутации рабочей копии сняла бы оба.
