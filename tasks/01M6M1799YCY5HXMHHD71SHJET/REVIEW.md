---
task: 01M6M1799YCY5HXMHHD71SHJET
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Ручной мерж для GitHub, часть 1 — функции MR хостинга GitHub через `gh`

## Фаза A — план

- Таблица покрытия PLAN полна: требования 1–10 привязаны к шагам 1–4; требование 9 закрыто тем, что прочие функции `_GitHub` не заведены и отказ собирает `_call` (сверено по diff: в `_GitHub` добавлены только `mr_status`/`open_mr`/`undraft_mr`/`assign_mr`).
- Шаги — по файлу на шаг, проверяемые; подход повторяет форму `gitlab_adapter` (результат через `mr_status`, закрытый список до отправки) — с архитектурой не конфликтует.
- «Влияние на систему» совпадает с diff: `forge.py`, `github_adapter.py`, `fsm_merge_gate.py`, удаление четырёх ключей `GH_CALLS`, карта; `targets.SUPPORTED_PAIRS`, `ci.py`, путь `operator` не тронуты. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `forge.py` `_GitHub.open_mr`: argv в порядке SPEC, `--draft`, затем `--assignee=<имя>` одним элементом; номер только из stdout при коде 0, `_GH_PR_URL_RE` с `$` и `[0-9]+` — хвост `/pull/7/files`, `/pull/7x` не разбирается; владелец/имя — `ci._owner_and_name(ctx.remote)` с `.lower()`; при коде ≠ 0 stderr не разбирается; частичный успех — `iid`+`url`+причина. |
| 2 | OK | `open_forge_mr` пишет `set_mr_link` при `iid is not None` до проверки причины; `MR_OPENED_ACTION` — только без причины. `_deliver_mr` — отдельная ветвь `reason and iid` с `MR_PARTIAL_DETAIL` (без «MR не открыт»), `("stopped",)`. Путь черновика (`ensure_forge_draft_mr`) не менялся: текст `черновой MR не открыт:` прежний, повтор видит ссылку (`mr_link(row)[0] is not None` → None). |
| 3 | OK | `MergeRequest.already_exists: bool = False`; ставится только при отказе `pr create` по двум текстам; `_deliver_mr` эскалирует по `already_exists` или 409; распознавание 409 GitLab прежнее. |
| 4 | OK | `pr view <n> --json GH_PR_FIELDS`; сопоставление полей по таблице; `(404)` — только код 1 + `Could not resolve to a PullRequest`; в прочих текстах `(404)` вычищается (`mr-sync` ищет код в причине) — разумная защита; не JSON / без целого `number` (bool исключён) — причина без `(404)`. |
| 5 | OK | `undraft_mr`: чтение → `pr ready` только для черновика → новое чтение; отказы — причина. |
| 6 | OK | `assign_mr`: `pr edit <n> --add-assignee=<имя>` одним аргументом, затем чтение. |
| 7 | OK | `github_call`: сверка argv целиком (`_github_form_allowed` — хвост, `[0-9]+` fullmatch, правило имён для `--assignee=`/`--add-assignee=`), затем артель и неразрешённый контекст — отказ без `ci.gh`; `repo=ctx.remote` всегда непуст; текст отказа — `GH_CALL_REFUSAL` + argv через пробел; причина без контекста — дословно по SPEC. `api`, `pr merge/close/comment` вне списка. `pipeline_status` не тронут. |
| 8 | OK | `mr_assignee(policy, target=None)`; признак — `forge.assignee_by_name` через `getattr(IMPLEMENTATIONS[value], "ASSIGNEE_BY_NAME", False) is True`, не литерал; целое для GitHub — строкой; неназначенное для GitHub — `ASSIGNEE_NOT_NAME` (без «не числовой id»), в том числе без поля; без проекта / GitLab / хостинг не определён — прежние тексты. Вызовы в `open_forge_mr` и `_ready_existing_mr` передают проект. |
| 9 | OK | Семь функций не заведены — `_call` отвечает «не реализовано для github»; `ensure_draft_mr`/`undraft_mr` адаптера и `SUPPORTED_PAIRS` не тронуты. |
| 10 | OK | В diff `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py` — только 5 удалённых строк четырёх ключей `GH_CALLS`; `GL_CALLS`/`GL_CALL_NAMES`, тела методов, прочие тесты не тронуты; `skip`/`xfail` нет. Покрыто ANSWER-1; ложное срабатывание гейта на `test_ac3_no_token_no_request`/`test_ac18_network_down_reason` — ANSWER-2, условие мандата («`GL_CALLS`, `GL_CALL_NAMES`, тела не меняются») выполнено. |

Тесты: долгоживущие свойства закрыты долгоживущими файлами задачи `tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_{units,gate}.py` (группа «долгоживущий», заявки «Ловит мутацию» с наблюдаемым расхождением); разработчик тестов в `tests/` не добавлял — повтора нет. Изменённые утверждения прежних тестов — только параметризация `GH_CALLS` по мандатам ANSWER-1/ANSWER-2; сужения данных под неизменным утверждением нет.

## Замечания

Блокеров и major нет. Наблюдения (не замечания, правки не требуют):
- `orchestrator/forge.py` `_GitHub.open_mr` берёт адрес PR из последней непустой строки stdout — соответствует поведению `gh pr create` (адрес последней строкой), живой формат сверит Оператор на пробе после части 2 (SPEC, «Не входит»).
- `orchestrator/forge.py` `open_mr` вызывает `repo_context.resolve(target).remote` без проверки на `None` — безопасно: при `None` `github_call` уже отказал бы кодом 1 и выполнение до этой строки не дошло бы.

## Реестр замечаний

Замечаний нет — реестр пуст.

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved

## Проверено исполнением

- `python3 …/artel.py plank-run 01M6M1799YCY5HXMHHD71SHJET` — `test_ac17_gh_calls_mandate.py`: 1 passed, код выхода pytest 0.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_units.py tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_gate.py tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py tests/test_mr_delivery_units.py` — 294 passed, 8 subtests passed (2:45).
- Временная мутация `fsm_merge_gate._deliver_mr`: `if result.already_exists or (` → `if False or (` — `test_ac5_already_exists_escalates_without_link[gh]` и `[422]` красные (2 failed); код возвращён `git checkout`, рабочая копия чистая.
- Временная мутация `github_adapter.open_forge_mr`: ссылка пишется только при результате без причины — `test_ac3_partial_success_on_merge_gate_keeps_link` и `test_ac4_partial_success_on_verifying_entry` красные (2 failed); код возвращён, рабочая копия чистая.
- Свежесть карты: `scripts/codebase_map.py` перегенерирован, сравнение без строк `built_at_sha:` — совпадает; файл восстановлен.
- `git diff da0462d…HEAD -- tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py` (в пакете) — только удаление четырёх ключей `GH_CALLS`.

## Предложения системе

- Сравнение карты без `built_at_sha` в шаге ревью упирается в запрет записи в `/tmp` и подстановку процессов в Bash — пригодилась бы команда пульта «карта свежа?» (read-only), чтобы ревьювер не перегенерировал отслеживаемый файл руками.
