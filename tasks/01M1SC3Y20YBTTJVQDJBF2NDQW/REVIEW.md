---
task: 01M1SC3Y20YBTTJVQDJBF2NDQW
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 4
---

# REVIEW: идемпотентность `workspace.ensure` не зависит от символических ссылок в пути

SPEC.md/PLAN.md отсутствовали в присланном пакете (ни в кодовой ветке,
ни в рабочем дереве) — прочитаны адресно из головы артефактной ветки
`artifact/01m1sc3y20ybttjvqdjbf2ndqw` (коммит `cfe47033`, шаг
developer), где они и материализованы штатно; на диске рабочего
дерева в момент ревью они тоже уже были на месте.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`workspace.ensure`/`on_task_branch`/`remove` сравнивают пути после `Path.resolve()` с обеих сторон) | OK | Единственная точка сравнения — `workspace._registered` (orchestrator/workspace.py:38-45): `wt_path.resolve()` против `Path(p).resolve()` для каждой строки `registered_paths()`. `ensure`/`on_task_branch`/`remove` уже вызывают только её (orchestrator/workspace.py:47-96, не изменены) — правка одной функции закрывает все три места, как заявлено в PLAN. |
| 2 (повторный `ensure` для worktree, зарегистрированного под символической ссылкой, не падает и не зовёт `git worktree add` повторно) | OK | Проверено чтением реализации и прогоном `test_ac1_second_ensure_call_does_not_invoke_worktree_add`/`test_ac5_repeated_call_survives_symlinked_registration_without_extra_worktree` — оба зелёные. |
| 3 (`canary._drive_task` не крутит холостые проходы на `agent run SKIPPED` с одной из двух причин ТЗ, убивает немедленно с текстом причины из журнала) | OK | `orchestrator/canary.py:577-591` (`_last_role_skip_reason`) читает ПОСЛЕДНЮЮ запись журнала, сверяет `action == "agent run SKIPPED"` и подстроку причины из `_SKIP_SHORTCIRCUIT_REASONS`; `_drive_task` (orchestrator/canary.py:648-654) проверяет это на каждом проходе сразу после `auto.cmd_auto` и до всех гейтовых веток — убивает через `_kill_inconclusive(conn, task_id, f"canary: {skip_detail}")`, причина уходит и в журнал (`action`), и в алерт (`detail` алерта = та же строка). Третья реальная причина `agent run SKIPPED` в `runner.py` («промпт не записан/не прочитан», «claude CLI не найден») сознательно не матчится — это соответствует «Не входит» SPEC, эмпирически проверено (`runner.py:620,631,642,679,699` — ровно 5 мест, только 2 совпадают с `_SKIP_SHORTCIRCUIT_REASONS`). |
| 4 (отчёт прогона печатает причину исхода `killed`: «штатно»/«не сошлась: <причина>») | OK | `_kill_outcome_note` (orchestrator/canary.py:594-608) отличает `_kill_at_merge_gate`/`_kill_at_verifying` (штатно) от `_kill_inconclusive` (по литералу-маркеру `detail`, реальная причина берётся из `action`); `_task_metrics`/`_run_one_task` (orchestrator/canary.py:723-724, 828) добавляют `kill_note` в скобках рядом с `исход=`. |

## Замечания

Нет.

## Реестр замечаний

(пусто — новых замечаний в этой итерации не заведено, прошлых итераций у задачи не было)

## Вердикт

approved

Diff точечный, строго в границах зон SPEC (`orchestrator/workspace.py`,
`orchestrator/canary.py`; `docs/codebase-map.md` — обязательная
регенерация карты тем же коммитом при правке `*.py`, содержимое кроме
`built_at_sha` не отличается от свежей перегенерации, что и требуется
конвенцией). Публичные сигнатуры не менялись, новые функции —
приватные помощники. Ни один существующий тест/гейт/лимит не ослаблен
(`CANARY_MAX_STALL_ITERS`/`CANARY_MAX_ESCALATION_CYCLES` не тронуты;
`DriveTaskStallCapTest` — генуинная стагнация без записи SKIPPED —
по-прежнему упирается в полный стоп-кран, отдельно защищено новым
приёмочным тестом AC-7). Область изменения обратима — точечный revert
трёх мест, как описано в PLAN «Влияние на систему»/«Риски», отдельный
путь отката не требуется.

Единственное найденное при чтении наблюдение — не поднимаю до формального
замечания, так как оно не проявляется ни в одном сценарии сегодняшнего
кода и не требует правки для этого MR: `_MERGE_GATE_KILL_ACTION`/
`_VERIFYING_KILL_ACTION` (orchestrator/canary.py:94-95) — новые константы,
дублирующие ЛИТЕРАЛЬНО те же строки, что `_kill_at_merge_gate`/
`_kill_at_verifying` (orchestrator/canary.py:514-516, 527-529) пишут в
журнал напрямую, а не берут из констант. Сегодня строки побайтово совпадают
(проверено чтением) и все три теста AC-4 это подтверждают прогоном — но
будущая правка текста в одной из двух исходных функций без синхронной
правки константы молча превратит «штатно» в «не сошлась» в отчёте
прогона. Не блокирую этим MR — если поправите, замените инлайновые
строки в `_kill_at_merge_gate`/`_kill_at_verifying` на сами константы.

## Проверено исполнением

- `python3 -m pytest tasks/01M1SC3Y20YBTTJVQDJBF2NDQW/acceptance_tests/ -v` — 10 тестов (AC-1, AC-2, AC-3×2, AC-4×3, AC-5, AC-6, AC-7), все `PASSED`.
- `python3 -m pytest tests/test_workspace.py tests/test_canary.py -v` — 67 тестов (22 workspace + 45 canary), все `PASSED`, регрессия не сломана (совпадает с заявленным в PLAN «22/22 и 45/45»).
- Прочитаны `orchestrator/workspace.py` (`path`/`registered_paths`/`_registered`/`ensure`/`on_task_branch`/`remove`) и `orchestrator/canary.py` (константы, `_last_role_skip_reason`, `_kill_outcome_note`, `_kill_inconclusive`, `_drive_task`, `_task_metrics`, `_run_one_task`) целиком в контексте диффа — сверены с SPEC построчно.
- `grep -n '"agent run SKIPPED"' orchestrator/runner.py` — 5 мест; ручная сверка текста причин с `_SKIP_SHORTCIRCUIT_REASONS` подтвердила, что короткое замыкание берёт ровно 2 названные ТЗ причины («рабочий каталог роли не создан», «каталог окружения роли не создан») и не задевает остальные 3 («промпт не записан», «промпт не прочитан», «claude CLI не найден») — соответствует «Не входит» SPEC.
- `grep -n "registered_paths\|_registered" orchestrator/doctor.py` — подтверждено, что `doctor._orphan_worktrees`/`check_orphans` читают `registered_paths()` напрямую и не разделяют `_registered`, т.е. правка их не задевает (заявлено «Не входит» SPEC и в PLAN «Влияние на систему»).
- `python3 scripts/codebase_map.py` (пробный прогон, результат отменён `git checkout -- docs/codebase-map.md` после сверки, в рабочее дерево ничего не оставлено) — diff с версией из ветки задачи ограничен строкой `built_at_sha`, содержимое карты идентично.

## Предложения системе

Формальный статус минорного, но не блокирующего наблюдения (см.
«Замечания» выше) плохо ложится в текущий реестр: гейт `review ->
verifying` требует, чтобы КАЖДАЯ заведённая запись реестра была
`accepted`, а `fixed`/`rejected` закрывается в `accepted` только
следующей итерацией — то есть завести запись для находки, которую сам
же ревьювер считает не требующей правки в этом MR, и одновременно
вынести `approved` в этой же итерации, реестр не позволяет
непротиворечиво. Сейчас это решается тем, что такие находки просто не
заводятся как формальные «Замечания» (как здесь) — стоит явно описать
этот путь в `skills/review-checklist.md`, иначе на следующей похожей
находке кто-то либо будет вынужден без нужды разводить лишнюю
итерацию, либо занизит вердикт, чтобы реестр не блокировал переход.
