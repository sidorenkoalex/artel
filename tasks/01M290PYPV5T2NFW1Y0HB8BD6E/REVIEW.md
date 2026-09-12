---
task: 01M290PYPV5T2NFW1Y0HB8BD6E
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: `auto` после эскалации по конфликту подтяжки начинает с шага роли, не с предварительного advance

## Фаза A: проверка плана

1. Покрытие требований — полное: SPEC несёт 4 требования / 7 AC, PLAN
   таблицей «Покрытие требований» назначает каждому шаг (1→шаги 1-2,
   2→шаг 2, 3→шаги 2-3, 4→шаги 1-3), ни одно требование не осталось без
   шага.
2. Шаги — проверяемые единицы, не микрооперации: три файла правки
   (`pull.py` константа+журналирование, `auto.py` два новых узла и
   встроенная проверка, `brief.py` фильтр) плюс покрытие приёмочными —
   размер типового MR, соответствует бюджету $45 и обоснованию монолита
   в SPEC («части не мержимы по отдельности осмысленно»).
3. Подход не конфликтует с конвенциями: продолжает уже существующий
   приём инъекции параметров `fsm.py -> pull.py` (без обратного
   импорта), дублирование текстовой константы между `auto.py`/`brief.py`
   — тот же приём, что уже применён для `REFUSAL_ACTION_PREFIX`
   (`store.py`/`auto.py`), причина явно объяснена топологией импортов
   (`auto.py -> fsm.py -> review.py -> brief.py`), риск дублирования
   зафиксирован в разделе «Риски» PLAN.md.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (маркер эскалации in_dev по конфликту подтяжки + анкер в `_role_step_since_state_entry`) | OK | `pull.py:240-245` журналирует `PULL_CONFLICT_ROLE_STEP_MARKER` только при `state == "in_dev"`, только на ветке после `merge --abort` (не инцидент очистки worktree, не авторазрешаемая карта); `auto.py:325-334` читает маркер как исключение из `_ESCALATED_RETURN_DETAILS`. AC-1/AC-2 — зелёные приёмочные тесты. |
| 2 (стоп-кран AC-4) | OK | `_pull_conflict_marker_streak` (auto.py:634-652) + встроенная проверка в `_pre_advance_step` (auto.py:684-705): срабатывает на 2-й подряд эскалации того же основания, оставляет `escalated`, именованная причина. AC-4 воспроизведён приёмочным тестом на 6 раундов — сходится. |
| 3 (единый перечень «роль ещё не закончила» + фильтр брифа) | OK | `ROLE_NOT_FINISHED_REFUSAL_ACTIONS` (auto.py) и `_ROLE_NOT_FINISHED_REFUSAL_ACTIONS` (brief.py) — идентичные литералы, сверено побайтово; `advance_refusal_history` (brief.py:686-688) вычитает их до построения блока. AC-5/AC-6 — зелёные. |
| 4 (существующие тесты не ослаблены) | OK | diff не касается `tests/` вовсе (только `orchestrator/{auto,pull,brief}.py` + `docs/codebase-map.md`); прогон 97+26 тестов затронутых модулей зелёный (см. «Проверено исполнением»). |

## Замечания

<нет — 0 blocker/major/minor>

## Реестр замечаний

<пусто: замечаний в этой итерации не заведено>

## Вердикт

approved

## Проверено исполнением

- `python3 scripts/codebase_map.py --check` — тихий успех, карта соответствует коду ветки (built_at_sha корректно продвинут до `5d033863b…`, импорт `pull` в `auto.py` и обратная ссылка `pull.py -> auto.py` отражены).
- `python3 -m pytest tasks/01M290PYPV5T2NFW1Y0HB8BD6E/acceptance_tests/test_ac1_ac2_ac4_pull_conflict_gate.py tasks/01M290PYPV5T2NFW1Y0HB8BD6E/acceptance_tests/test_ac3_ac5_ac6_brief_refusal_class.py -v` — 7 тестов (AC-1, AC-2, AC-3, AC-4, AC-5, AC-6×2), все зелёные.
- `python3 -m pytest tests/test_auto_cycle.py tests/test_pull.py tests/test_brief.py tests/test_fsm_merge_conflict_note.py tests/test_auto_escalated_return_rework_gate.py tests/test_fsm_advance_gate_framework.py tests/test_fsm_advance_gate_smoke.py tests/test_fsm_autogate.py tests/test_fsm_branch_correct_status_reads.py tests/test_fsm_draft_mr_reentry.py tests/test_fsm_map_conflict_autoresolve.py tests/test_fsm_map_regen.py tests/test_fsm_merge_gate_done_snapshot.py tests/test_fsm_merge_gate_scratch_worktree_cleanup.py tests/test_fsm_retro.py tests/test_fsm_review_rework_gate.py tests/test_fsm_review_rework_sha_gate.py tests/test_advance_refusal_history.py tests/test_advance_guard.py tests/test_cmd_approve_dispatch.py` — 200 тестов, все зелёные (числа совпадают с заявленными в PLAN «Влияние на систему»: 50+9+22+16+... = 97 из первых пяти файлов, проверено `--collect-only`).
- `python3 -m pytest tests/test_answer*.py` — 26 тестов, все зелёные (упомянуты в PLAN как непосредственно затронутый соседний модуль).
- `git diff 699fa124...HEAD -- orchestrator/fsm.py orchestrator/store.py orchestrator/watch.py` — пусто: подтверждено, что заявленные в «Не входит»/PLAN «fsm.py не потребовал правки» файлы действительно не тронуты.
- `git diff 699fa124...HEAD -- docs/backlog.md` — пусто: разрешение конфликта подтяжки (ANSWER-1) выполнено как предписано — версия main взята целиком, ничего из ветки не сохранено.
- Ручное прочтение полных тел `pull.py::_handle_merge_failure`/`evaluate`, `auto.py::_role_step_since_state_entry`/`_pull_conflict_marker_streak`/`_pre_advance_step`/`_rework_gate_blocks`, `brief.py::advance_refusal_history` — логика константного маркера, анкера гейта и стоп-крана прослежена построчно на нескольких сценариях (одиночная эскалация, повторная эскалация того же основания, эскалация другого основания — например, budget — между двумя эскалациями конфликта подтяжки); во всех случаях поведение соответствует SPEC/PLAN и не даёт ложного срабатывания стоп-крана раньше, чем роль получит гарантированный шанс.

## Предложения системе

- Раздел «--- ОТКАЗ ADVANCE (история) ---» пакета этого самого шага
  ревью нёс живой пример П2 копилки 11.09 (`переход отклонён: дерево не
  на ветке задачи` — тот самый класс, который правит требование 3):
  орchestrator, ведущий эту задачу, ещё работает на коде ДО мержа этого
  фикса, поэтому дефект воспроизвёлся на моём же брифе. Не дефект diff'а
  (код правильно фильтрует этот класс — доказано AC-5), но стоит иметь в
  виду при подготовке итогов задачи: сразу после мержа стоит проверить,
  что аналогичные live-отказы исчезли из брифов реальных задач.
