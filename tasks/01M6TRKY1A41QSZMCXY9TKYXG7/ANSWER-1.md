---
task: 01M6TRKY1A41QSZMCXY9TKYXG7
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Основание: решение Оператора 07.11.2026 — ТЗ задачи с мандатом на перевод случаев несвежей ветки одобрено словами «Да, вноси и заводи»; задачу ведёт сессия Оператора с правами волны G.

## Мандат

Ослабление тестов разрешено: tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py, tests/test_01m5xzskk8gzteca2kwafhe029_ci_full_suite.py

Пояснение: в этих файлах разрешено только перевести случаи несвежей ветки при `merge_gate: operator` (подслучай `stale` в `test_ac4_bad_ci_or_stale_branch_runs_local_suite`; случаи несвежей головы в `test_ac9_*` и `test_ac10_fresh_suite_rereads_ci_without_local_run`) на новое ожидание требования 1 SPEC либо на запись `target-human`; прочие утверждения, имена тестов и случаи не меняются.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит | Остаётся ли свойство после изменения | Чем покрыто после | Решение |
|---|---|---|---|---|
| tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py — подслучай `stale` переводится на новое ожидание | приёмка при несвежей ветке не принимает итог CI | для `merge_gate: operator` — нет, свойство переходит к `merge_gate` (подтяжка и CI новой головы под замком мержа, ADR-0031 п. 3); для `target-human` — да | `fsm_merge_gate._sync_main_or_wait`, инвариант 12; AC-2 и AC-11 задачи | ок при условии: AC-2 стоит на базе, отличной от main, и случай target-human сохраняет свежесть по origin/<base> |
| tests/test_01m5xzskk8gzteca2kwafhe029_ci_full_suite.py — случаи несвежей головы переводятся на новое ожидание или на запись target-human | итог CI не принят при голове, отставшей от origin/<base> | для `target-human` — да, тем же случаем на записи target-human; для `operator` — переходит к `merge_gate` | AC-2 задачи (случай target-human с базой не main) | ок при условии: сверка «свежесть по origin/<base>, не по origin/main» остаётся случаем на записи target-human |

Независимая проверка: подтверждаю — независимый проверяющий 07.11 сверил стенд `merge_gate: operator` теста (`tests/test_01m5xzskk8gzteca2kwafhe029_ci_full_suite.py:125`, `:424`) и потерю мутации «сверка с origin/main» без перевода на target-human.
