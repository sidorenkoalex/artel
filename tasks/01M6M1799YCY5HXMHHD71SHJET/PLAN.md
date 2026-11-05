---
task: 01M6M1799YCY5HXMHHD71SHJET
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Ручной мерж для GitHub, часть 1 — функции MR хостинга GitHub через `gh`

## Подход
Реализация `forge._GitHub` повторяет форму `gitlab_adapter` (`open_mr`,
`undraft_mr`, `assign_mr` строят результат через `mr_status`), транспорт —
`gh pr …` через одну публичную точку `forge.github_call(target, *args)`.

- `forge.github_call` сверяет argv целиком с закрытым списком требования 7
  (`_github_form_allowed`: подкоманда, флаги, хвост, десятичность номера
  `[0-9]+`, значение исполнителя по правилу имён `github_name_ok`), затем
  отказывает артели (`repo_context.is_artel`) и проекту без контекста; только
  после этого — `ci.gh(*args, repo=ctx.remote)`. Отказ —
  `CompletedProcess(args, 1, "", причина)`, причина вне списка начинается с
  `GH_CALL_REFUSAL`.
- `open_mr`: argv `pr create --head … --base … --title … --body …
  [--draft] [--assignee=<имя>]`; номер — только из последней непустой строки
  stdout при коде 0 по `^https://<хост>/<владелец>/<имя>/pull/<число>$`;
  владелец/имя сверяются с `ci._owner_and_name(url записи)` без учёта
  регистра. Отказ `pr create` — причина без `iid`; признак
  `MergeRequest.already_exists` — по двум текстам требования 3. Чтение
  отказало после разобранного адреса — `iid`+`url`+причина (частичный успех).
- `mr_status`: `pr view <n> --json <набор>`, сопоставление полей требования 4;
  `(404)` в причине — только код 1 + `Could not resolve to a PullRequest`
  (из прочего текста `gh` подстрока `(404)` вычищается, чтобы `mr-sync` не
  принял его за «не найден»); не JSON / без целого `number` — причина без
  `(404)`.
- `undraft_mr`: чтение → `pr ready <n>` только для черновика → новое чтение;
  `assign_mr`: `pr edit <n> --add-assignee=<имя>` → новое чтение.
- Признак реализации `ASSIGNEE_BY_NAME = True` у `_GitHub`; `forge.assignee_by_name(target)`
  читает его `getattr` из реестра (по образцу `ci_by_pipeline`), не литералом.
  `github_adapter.mr_assignee(policy, target=None)`: при признаке — имя по
  правилу или целое строкой, неназначенное — текстом `ASSIGNEE_NOT_NAME`
  (без «не числовой id»); без проекта / без признака / хостинг не определён —
  прежняя ветка с прежними текстами.
- `open_forge_mr` пишет ссылку, если результат несёт `iid`, при любой причине;
  «MR открыт» — только без причины. `_deliver_mr`: отдельная ветвь
  «`iid` + причина» с текстом `MR_PARTIAL_DETAIL` (не «MR не открыт»), задача
  на гейте; эскалация «уже существует» — по `already_exists` или коду 409.
- Тест: из `GH_CALLS` удалены ровно четыре ключа по мандату ANSWER-1.

Бюджет SPEC ($40) не пересматривается.

## Шаги
1. `orchestrator/forge.py`: `MergeRequest.already_exists`, `github_call` и
   закрытый список, четыре функции `_GitHub`, `ASSIGNEE_BY_NAME`,
   `assignee_by_name`.
2. `orchestrator/github_adapter.py`: `mr_assignee(policy, target=None)`,
   `ASSIGNEE_NOT_NAME`, ссылка при `iid` с причиной в `open_forge_mr`.
3. `orchestrator/fsm_merge_gate.py`: ветвь частичного успеха и
   `already_exists` в `_deliver_mr`; проект в `mr_assignee` у
   `_ready_existing_mr`.
4. `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py`: удаление четырёх
   ключей `GH_CALLS`; регенерация `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2, 3 |
| 3 | 1, 3 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1 |
| 7 | 1 |
| 8 | 1, 2, 3 |
| 9 | 1 (прочие функции `_GitHub` не заведены — `_call` отвечает «не реализовано») |
| 10 | 4 |

Проверка: `tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_units.py` и
`…_github_mr_gate.py` — 96 passed; планка `plank-run` (AC-17) — 1 passed;
соседние `test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py`,
`test_mr_delivery_units.py`, `test_mr_sync_units.py`,
`test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_fields.py`,
`test_01m6ezxvfgxc6wbda9qjesazrw_hosting_registry.py`,
`test_01m5xz9z68v75vxf5z66c708t4_delivery_policy.py`,
`test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`,
`test_fail_closed_on_read_failure.py`, `test_invariants.py` — 349 passed;
`test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py` +
`test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py` — 82 passed, 1 упал на
`git fetch` песочницы под нагрузкой (`test_ac18_watch_notifies_once_on_outcome_change`),
повтор отдельно — зелёный.

ANSWER-2 (мандат на `test_ac3_no_token_no_request` и
`test_ac18_network_down_reason` — ложное срабатывание гейта неослабления на
правку `GH_CALLS`): условия мандата выполнены без новых правок — `git diff
main...HEAD` по `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py` —
только удаление четырёх ключей `GH_CALLS`; `GL_CALLS`, `GL_CALL_NAMES` и тела
обоих методов не тронуты. Повторный прогон этого файла и
`…_github_mr_units.py` — 262 passed.

## Влияние на систему
- GitLab: реализация не отдаёт `iid` с причиной, поэтому новая ветвь
  `open_forge_mr`/`_deliver_mr` для него не срабатывает; распознавание 409 и
  тексты прежние. Подделки `IMPLEMENTATIONS["gitlab"]` прежних тестов без
  `ASSIGNEE_BY_NAME` получают прежнее «только целое».
- Путь `gh` гейта `operator` (`ensure_draft_mr`, `undraft_mr` адаптера),
  `pipeline_status` через `ci.check_runs`, `targets.SUPPORTED_PAIRS` и семь
  прочих функций `forge` для github не тронуты: пара `github` +
  `target-human` по-прежнему закрыта, новые функции живым путём не зовутся до
  части 2.
- Безопасность: `gh` функций MR не уходит без `--repo` (артель и проект без
  контекста — отказ до запуска), `pr merge/close/comment` и `api` вне списка.
- Тест ослаблен только по мандату ANSWER-1 (четыре ключа), утверждения
  метода не менялись. Откат — revert коммита задачи.

## Риски
- Тексты `gh` («already exists», `Could not resolve to a PullRequest`), поток
  вывода адреса PR и вид `assignees`/`mergeCommit` сверены только по SPEC —
  живая проба на проекте GitHub после части 2 (Оператор).
- `--add-assignee` добавляет, а не заменяет исполнителя (требование 6,
  намеренно не выравнивается).

## Предложения системе
- Запуск `pytest -n 4` из шага роли роняет все воркеры xdist сообщением сторожа
  «полный прогон запрещён» (`conftest.py` видит воркер как полный прогон) —
  стоит упомянуть в скиле coding-standards, что тесты затронутых модулей
  гоняются без `-n`.
- Планка AC-17 читает `git show HEAD`: незакоммиченная правка теста по
  мандату в `plank-run` красна, пока роль сама не закоммитит — расходится с
  «коммитить самому не обязательно» (skills/coding-standards.md).
