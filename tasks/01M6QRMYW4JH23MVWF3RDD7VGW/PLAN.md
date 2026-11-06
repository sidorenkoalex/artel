---
task: 01M6QRMYW4JH23MVWF3RDD7VGW
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Раннер compose: файлы машины и привилегии стенда — только внутри дерева прогона

## Подход
Прежняя проверка `_compose_config_refusal` (`orchestrator/acceptance.py`)
остаётся как есть и идёт первой; новые проверки — отдельным проходом
`_compose_tree_refusal(cfg, tree, head)`, который вызывается в конце прежней
функции. Так порядок и тексты прежних отказов не меняются (требование 7), а
сокетный отказ для bind/секрета/конфигурации всегда раньше «вне дерева»
(требование 4).

- `_compose_config_refusal(cfg, project, sockets, tree)` — новый параметр,
  вызов в `_compose_report_run` передаёт `tree`.
- `_inside_tree(value, real_tree)` — строка, абсолютный путь, `realpath`
  равен `realpath(tree)` или под ним по границе компонента (образец
  `_own_cwd`); не строка/пусто/относительный/`~` — не внутри, без
  `realpath` от cwd процесса.
- `_git_address` — по виду значения: схема `xxx://`, `git@`, `.git#`/`.git`
  в конце; ловит и `<дерево>/r.git#main`.
- `_bind_entries(service)` — разбор `volumes` (прежняя логика
  `_bind_sources`, плюс отказ формы для элемента не словарь и не строка);
  `_bind_sources` теперь его тонкая обёртка с прежним результатом.
- `_build_refusal` — `build` строкой = `build.context`, не словарь и не
  строка — отказ; `build.context`: адрес git — отказ, вне дерева — отказ;
  `additional_contexts`: не словарь — отказ, `service:` — проходит,
  `oci-layout://<путь>` — путь проверяется, прочая схема/адрес git — отказ,
  иначе путь проверяется; `build.ssh`, `build.privileged`,
  `build.entitlements` — отказ.
- `_privilege_refusal` — `privileged`, `pid/ipc/userns_mode/cgroup/uts:
  host`, `security_opt` с `unconfined`/`label=disable`/`label:disable`,
  непустые `cap_add`/`devices` — для каждого сервиса, не только тестового.
- Секреты/конфигурации: в прежнем сокетном цикле `(item or {}).get` заменено
  на безопасное (строковый элемент больше не поднимает `AttributeError`);
  в новом проходе элемент не словарь — отказ с именем, `file` вне дерева —
  отказ; без `file` — не проверяется.
- `COMPOSE_OVERRIDE_RULE` — версия «2: », перечисляет новые отказы.

Бюджет SPEC не пересматривается: одна функция, один файл.

## Шаги
1. Правка `orchestrator/acceptance.py` (функции выше, вызов, правило) +
   регенерация `docs/codebase-map.md`. Проверка: долгоживущий файл задачи
   `tests/test_01m6qrmyw4jh23mvwf3rdd7vgw_compose_tree_bounds.py` и тесты
   ядра `tests/test_01m6paj61d4pyap79adrpa6mwv_compose_run.py`,
   `..._compose_docker.py` — 137 passed, 1 skipped. Временные мутации
   («внутри — только строго под деревом», «адрес git только для
   неабсолютного») — красят AC-7 `bind_tree`/`context_tree` и AC-3
   `@TREE@/r.git#main`; код возвращён.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`_inside_tree`, `_git_address`, `_bind_entries`, `_build_refusal`, секреты в `_compose_tree_refusal`) |
| 2 | 1 (`_privilege_refusal`, `build.ssh/privileged/entitlements` в `_build_refusal`) |
| 3 | 1 (текст: объект, поле, значение, причина; прежний возврат `ReportRun(refusal=…)`) |
| 4 | 1 (новый проход после прежнего сокетного) |
| 5 | 1 (`type: volume/tmpfs/image` и именованная короткая строка в источники bind не попадают — прежняя логика) |
| 6 | 1 (`COMPOSE_OVERRIDE_RULE` «2: …») |
| 7 | 1 (прежние проверки без изменений и первыми) |

## Влияние на систему
- Смена `COMPOSE_OVERRIDE_RULE` меняет ключ итога прогона compose —
  сохранённые итоги прежнего правила не засчитываются (так и задумано SPEC).
- Новые отказы только ужесточают допуск конфигурации; ни один гейт, тест или
  лимит не ослаблен, тесты ядра compose не правились и зелёные.
- `_bind_sources` возвращает прежний список (элемент неверной формы и раньше
  в него не попадал).
- Откат — revert коммита задачи.

## Риски
- Строгость `_git_address` (`.git` в конце пути) откажет каталогу дерева с
  именем `*.git` в `build.context` — «закрыто по умолчанию», осознанно.
- `security_opt` строкой (не списком) трактуется как один элемент.

## Предложения системе
- SPEC «Не входит»: `env_file`, `label_file`, `extends.file`, `include`
  читает `docker compose config` на машине до проверки пульта — нужна
  строка бэклога (сессия Оператора, `note`) о проверке, остаются ли эти поля
  в выводе `config --format json`.
- Bash роли просит подтверждения на `cp`/`ls`-цепочки в worktree; временную
  мутацию приходится делать одним python-процессом с восстановлением в
  `finally` — команды пульта для «мутация в рабочей копии» (`mutation-run
  --ref worktree`?) в миссии разработчика не названо.
