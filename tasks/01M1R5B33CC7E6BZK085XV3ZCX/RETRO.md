---
operator: Alexander Sidorenko
model: unknown
artel_sha: 2c0e3675f9368c355eaab21d1516ed137573f778
---

# RETRO: 01M1R5B33CC7E6BZK085XV3ZCX — B2 ТЗ-1: репозиторный контекст target для git/gh-слоя

Итог: killed — причина: причина не найдена в журнале
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: B2 ТЗ-1: репозиторный контекст target для git/gh-слоя

Стоимость итого: $141.21
  analyst: $4.51, 8296054 токенов
  test_author: $22.36, 57380467 токенов
  developer: $8.12, 17336742 токенов
  reviewer: $5.08, 9689553 токенов

Ревью: 1 итераций; приёмка: 0 отказ(ов)

Эскалации: 2 (последняя): эскалация от разработчика: **Вопросы** (по блокирующести; дефолт — если Оператор промолчит):

1. `tasks/.../acceptance_tests/test_ac4_pull_main_or_escalate.py` —
   оба теста (`ExternalTargetPullMainTest.
   test_ac4_external_target_branch_gets_merged_in_the_target_clone` и
   `SelfTargetPullMainUnchangedTest.
   test_ac4_self_target_still_merges_in_the_pult_worktree`) красны:
   фикстура заводит задачу (`insert_external_task`/`store.insert_task`)
   БЕЗ единого коммита в артефактную ветку — `tasks/<id>/SPEC.md` там
   не существует. `pull._materialize_and_run_plank` (существующая,
   НЕ этой задачей введённая логика — `orchestrator/pull.py`, ветка
   «acceptance_tests/ нет → читай SPEC.md») в этом случае отказывает
   `Refused` вместо `Pulled`, и обе SelfTarget/ExternalTarget проверки
   получают `outcome == "refused"` вместо ожидаемого `"pulled"`.
   Варианты: (a) Оператор поправляет планку (добавляет
   `artifact_branch.commit_files(TASK, {f"tasks/{TASK}/SPEC.md": ...},
   ...)` в `setUp` обоих тестовых классов) — тогда я доведу шаг
   штатно; (b) Оператор подтверждает, что этот дефект планки —
   отдельная эскалация test_author, а эта задача сдаётся с этими двумя
   тестами красными, остальными 15 из 17 AC — зелёными. Дефолт при
   молчании — (b), с пометкой в REVIEW.md/RETRO, что планка требует
   правки отдельным ходом.
2. `tasks/.../acceptance_tests/test_ac15_ac16_ac17_end_to_end.py::
   EndToEndExternalTargetFlowTest.
   test_ac15_full_flow_merges_into_the_target_origin_only` — ожидает
   состояние `"review"` сразу после ОДНОГО `fsm.cmd_advance(TASK)` из
   `in_dev`; фактический (правильный, уже смерженный, задокументированный
   `docs/adr/0015-ci-before-review.md` «Решение» п.1) порядок —
   `in_dev -> verifying -> review`. Тест написан против состояния FSM,
   устаревшего к моменту старта этого шага (SPEC сама называет условие
   «код стартует после мержа ... группы процессов» — похоже, эта же
   категория гонки задела и порядок состояний, не только зоны
   fsm_advance.py/doctor.py). Изменение порядка состояний НЕ входит в
   объём этой SPEC (и правка бы ослабила ADR-0015 — принцип
   целостности запрещает это разработчику). Варианты: (a) Оператор
   поправляет планку (добавляет промежуточный `store.set_state(...,
   "verifying", ...)`/второй `cmd_advance()` перед первым `assertEqual`
   — ровно тем же приёмом, что уже применён к `verifying -> acceptance`
   ниже в этом же тесте); (b) сдать задачу с этим одним сценарием
   красным (два других класса того же файла, `CapacityGateThroughAdvanceTest`
   и `SandboxIsolationTest`, — зелёные, доказывают AC-16/AC-17
   независимо). Дефолт при молчании — (b).

**Контекст**: код реализован полностью по всем 17 AC. Прогон
`tasks/01M1R5B33CC7E6BZK085XV3ZCX/acceptance_tests/` целиком:
14 из 17 тестовых методов зелёные (AC-1, AC-2, AC-3, AC-5, AC-6, AC-7,
AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-16, AC-17 — все свои
тестовые классы полностью зелёные); AC-4 (2 из 3 методов) и один
сценарий AC-15 (1 из 3 методов) красны по причинам выше, ПОДТВЕРЖДЕНО:
для AC-4 self-сценарий (`SelfTargetPullMainUnchangedTest`) падает ТОЙ
ЖЕ ошибкой, что и внешний — доказывает, что причина не в
self/external-разводке этой задачи, а в фикстуре. Юнит-тесты
затронутых модулей (`tests/test_gitcmd_*`, `tests/test_ci_status*`,
`tests/test_github_adapter.py`, `tests/test_capacity_gate.py`,
`tests/test_review_package.py`, `tests/test_branch_freshness_gate.py`,
`tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_acceptance*`,
`tests/test_doctor.py`, `tests/test_merge_gate_ci_wait.py`,
`tests/test_fsm_merge_gate_done_snapshot.py`, `tests/test_fsm_map_regen.py`,
`tests/test_fsm_retro.py`, `tests/test_fsm_advance_gate_smoke.py`,
`tests/test_fsm_advance_gate_framework.py`, `tests/test_zones_gate.py`,
`tests/test_zones_approve.py`, `tests/test_advance_guard.py`,
`tests/test_pull.py`, `tests/test_multitarget*`,
`tests/test_split_assessment_merge_gate.py`,
`tests/test_fsm_review_rework_*`, `tests/test_artifact_branch_push.py`,
`tests/test_budget_live_lease_and_escalation.py`,
`tests/test_doctor_artifact_branch_*`, `tests/test_fsm_draft_mr_reentry.py`,
`tests/test_git_fixation.py`, `tests/test_auto_cycle.py`,
`tests/test_repo_context.py`) — все зелёные.

**Блокирует**: доведение требования 6/AC-15 (сквозной прогон как
единственная проверка полноты флоу, см. SPEC «Оценка объёма и деление»
п.3) до состояния «все локальные acceptance_tests/ зелёные» без
правки локальной планки — которая мне недоступна (T023: «их правка —
эскалация, не правка»). Код к передаче готов и закоммичен; ждёт
решения Оператора по планке (или подтверждения дефолта — сдать с
двумя красными сценариями).

Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
