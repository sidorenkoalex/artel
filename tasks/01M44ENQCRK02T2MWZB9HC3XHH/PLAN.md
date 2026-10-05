---
task: 01M44ENQCRK02T2MWZB9HC3XHH
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: amend-tests отправляет кодовую ветку задачи в origin; verifying сам отправляет голову на исходе 422

## Подход
Единственный узел отправки — `github_adapter.ensure_head_in_origin`
(второго способа не заводим). Его подключаем в трёх местах:

- `orchestrator/amend.py`: общий помощник `_push_code_head(conn, t, task_id)`.
  Канареечная задача (`t["is_canary"]` — тот же признак, по которому
  `fsm_advance.py::in_dev` не зовёт `_origin_push_gate`) — no-op. Отказ узла
  уходит в существующий `_recovery_exit`: он уже пишет «amend-tests прерван»,
  выходит ненулевым кодом и называет путь `amend-tests <id> --from-branch
  --reason «…»`. В detail попадают причина узла и «почини доступ к origin».
  - `_amend_with_long_lived`: вызов сразу после записи (а) — коммита
    `long_changed` в кодовую ветку. Это раньше записи (б) (`_commit_plank`) и
    записи (в) (`tests_locked_sha`). При пустом `long_changed` вызова нет.
  - `_cmd_amend_tests_from_branch`: при непустом `long_diverged` — после
    проверок `_check_code_head_long_lived` и до коммита пересчитанного
    перечня в ссылку документов и сдвига лока. При пустом `long_diverged`
    вызова нет.
  - Режим без перечня (`_cmd_amend_tests` до `_amend_with_long_lived`) не
    меняется.
- `orchestrator/ci.py`: текст исхода 422 `verifying_status` без «git push -u
  origin»: описывает отправку головы пультом при опросе `verifying`, несёт
  «голова», «origin», «push», имя ветки. Исход остаётся `VERIFYING_NONE`:
  этого ждёт существующий `test_ci_status.py` и остальные потребители
  исхода. Признак 422 для обработчика — новая функция
  `ci.verifying_head_not_in_origin(note)` по подстроке текста. Это тот же
  приём, что `verifying_is_red`: повторного опроса GitHub нет.
- `orchestrator/fsm_advance.py::verifying`: после записи статуса CI, если
  признак 422 истинен и задача не канареечная, зовём
  `github_adapter.ensure_head_in_origin`. Узел сам пишет «push (голова не в
  origin)» или «push FAILED (голова не в origin)». Дальше идёт прежний путь
  ожидания: счётчик попыток, потолок от входа в состояние. Состояние на
  отказе не меняется, следующий опрос повторит попытку. На остальных
  исходах вызова нет.

Исключение канарейки в `verifying` SPEC прямо не требует. Оно повторяет
`_origin_push_gate`: SPEC ссылается на этот рубеж как на образец реакции,
и рубеж для канарейки origin не трогает.

## Шаги
1. `amend.py`: `_push_code_head` и два вызова (worktree-режим после (а),
   `--from-branch` при `long_diverged`).
2. `ci.py`: новый текст 422 и `verifying_head_not_in_origin`.
3. `fsm_advance.py::verifying`: отправка на исходе 422.
4. Юнит-тест предиката `ci.verifying_head_not_in_origin` в
   `tests/test_ci_status.py` (новый класс). Сценарии AC-1…AC-9 уже покрывает
   долгоживущий `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py`.
5. Регенерация `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1, 3 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 (режим без перечня не тронут) |
| 6 | 2, 3 |
| 7 | 3 (вызов только при признаке 422) |
| 8 | 2 |

## Влияние на систему
- Лок планки (`tests_locked_sha`): порядок записей (а)→(б)→(в) сохранён,
  отправка встаёт между (а) и (б). Отказ отправки не пишет ни (б), ни (в),
  а уходит в штатный путь восстановления `--from-branch`, который теперь
  тоже отправляет голову.
- `verifying`: переходы и потолок не меняются. Вне исхода 422 узел не
  вызывается, поэтому зелёный путь по-прежнему зовёт узел один раз за
  проход (`test_auto_cycle.py::test_origin_push_check_runs_once_not_twice_on_the_way_to_acceptance`).
- `ensure_head_in_origin` на успешной отправке может завести черновик MR
  (`_ensure_draft_mr_after_publish`). Это прежнее поведение узла, его
  повторяет и рубеж `in_dev -> verifying`.
- Существующие тесты и утверждения не меняются.
- Откат — revert одного merge-коммита.

## Риски
- Отправка из `verifying` на каждом опросе при недоступном origin пишет
  по записи «push FAILED» на опрос. Это поведение, которое требует SPEC
  (п.6); остановку `auto` на таком отказе SPEC выносит за рамки.

## Проверка
- `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py` + `tests/test_ci_status.py`:
  84 passed.
- `tests/test_amend.py`, `test_amend_long_lived.py`, `test_amend_remove.py`,
  `test_verifying_ceiling.py`, `test_github_adapter.py`, `test_auto_cycle.py`,
  `test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`: 146 passed.
- Мутации нового `VerifyingHeadNotInOriginTest`: при предикате, который
  всегда `True`, красен `test_other_none_outcomes_are_not_detected`; при
  предикате, который всегда `False`, красен `test_422_note_is_detected`.
  После проверки код возвращён.
- `plank-run`: разовой планки у задачи нет (только долгоживущий файл), pytest
  не запускался.
- Карта перегенерирована (`scripts/codebase_map.py`).

## Предложения системе
- `plank-run` на задаче, у которой планка только долгоживущая (`tests/test_<id>_*.py`), отвечает «планки нет». Долгоживущую группу локально приходится гонять прямым pytest. Стоит прогонять и её (`orchestrator/plank_run.py`).
