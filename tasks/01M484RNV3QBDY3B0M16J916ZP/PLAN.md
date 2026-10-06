---
task: 01M484RNV3QBDY3B0M16J916ZP
type: plan
author_role: developer
status: escalate
schema_version: 5
---

# PLAN: Этап 3 ADR-0021, часть 3 из 3: прочие развилки, сторож и сквозной тест внешнего потока

## Подход

Код требования 1 внесён (коммит пульта 0d010214 после таймаута прошлого
шага, сверен на этом шаге). Строки таблицы SPEC «удалить» сняты без новой
механики: фильтр «только артель» заменён фильтром «тот же проект»
(`zone_lock`, `catalog`), а в остальных местах фильтр просто убран
(стоп-кран, `_dirty_refuses`, паспорт, «sha зафиксирован», `show`,
`docs --fetch-all`, `diff_bytes`, гейт отработки ревью, свежесть ветки).
Оставленные строки (16, 18, 19, 21, 24, 25, 28, 29) узнают артель одной
функцией `repo_context.is_artel`. Признак принимает контекст, имя
проекта, строку задачи и путь клона, потому что эти развилки держат
разные формы субъекта. Своё разрешение remote/базы в `fsm.py` (строка 17)
заменено на `repo_context.resolve`.

Сторож (требование 3) и сквозной тест (требования 4–5) — долгоживущие
файлы test_author `tests/test_01m484rnv3qbdy3b0m16j916zp_*.py`. Новых
своих тестов на эти свойства не пишу (требование 7 их засчитывает), свой
тест — только на формы субъекта `is_artel`
(`tests/test_repo_context.py::IsArtelSubjectsTest`). Карта (требование 6)
описана первыми строками докстрингов `repo_context`,
`advance_gates/__init__`.

Две защитные правки — следствие паспорта у артели (строка 14). Паспорт
пишется на КАЖДОМ переходе FSM артели, поэтому плотницкая запись в ссылку
документов теперь достижима из песочниц, где git подменён или его нет:
- `gitcmd.carpentry`: при `OSError` (git не запускается) возвращает
  ненулевой `CompletedProcess`, как и `gitcmd.git()`. Переход FSM (в
  частности, kill switch) не падает из-за записи «только для глаз».
- `artifact_branch.write_commit`: пустой или не-байтовый ответ
  `hash-object` значит «запись не удалась», а не исключение.

## Шаги

1. Требование 1: строки 1–15, 17, 20, 22, 23, 26, 27 — удалить развилку;
   строки 16, 18, 19, 21, 24, 25, 28, 29 — признак `repo_context.is_artel`
   (требование 2). Сделано.
2. Требования 3–5: долгоживущие файлы test_author зелёные на ветке
   (42 passed, 15 subtests). Планка `plank-run`: 2 passed.
3. Требование 6: докстринги модулей, `python3 scripts/codebase_map.py`.
   Сделано.
4. Требование 7: смена ожиданий существующих тестов. Обвязки двух классов
   поправлены без смены утверждений (см. «Влияние на систему»). Остальное
   ждёт мандата — раздел «Эскалация».
5. Требование 8: разбивка ниже.

### Разбивка упоминаний `config.DEFAULT_TARGET` в `orchestrator/` (требование 8)

Ветка задачи, `grep -rn DEFAULT_TARGET orchestrator/`: 67 строк
(на `main` 4d6f5b77 — 96).

| Категория | Строк | Где |
|---|---|---|
| комментарии и докстринги | 12 | alerts.py:20, catalog.py:471, fixation.py:87, runner.py:1096, checkpoint.py:202, repo_context.py:155, :162, review.py:221, ci.py:81, schema.py:21, artifact_source.py:8, advance_gates/__init__.py:32 |
| определение | 1 | config.py:56 |
| значение по умолчанию (`x or config.DEFAULT_TARGET`, возврат умолчания) | 25 | catalog.py:229, :511, :663; store.py:231, :537, :538; runner.py:366; pull.py:567, :663; github_adapter.py:128, :227, :300; artifact_branch.py:80, :580; zone_lock.py:287, :316; cleanup.py:85, :389; ci_rerun.py:272; fsm.py:247; workspace.py:57; doctor/branch_freshness.py:43; doctor/orphans.py:80, :83; doctor/artifact_branches.py:138 |
| намеренная константа | 26 | alerts.py:238 (проект алерта волны); store.py:229; artifact_cleanup.py:53, :97; artifact_branch.py:91; ci.py:85, :740, :764; canary.py:1252; budget.py:421; review.py:231, :496; notes.py:233, :635 (клон артели для `note`/`doc-commit`); coldstart.py:34; workspace.py:158; schema.py:110, :123, :192 (умолчание колонки); docs_fetch.py:108, :109 (порядок проектов); doctor/misc_checks.py:69; doctor/orphans.py:53, :96; doctor/artifact_branches.py:201; advance_gates/acceptance.py:37 |
| развилки поведения — проверки пункта 8 | 0 | — (сторож `tests/test_01m484rnv3qbdy3b0m16j916zp_gate_target_guard.py`) |
| развилки поведения — прочие | 3 | repo_context.py:171, :173, :176 — тело единственного признака `is_artel`; восемь оставленных развилок таблицы зовут его, прямого сравнения на их месте нет |

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 2 |
| 4 | 2 |
| 5 | 2 |
| 6 | 3 |
| 7 | 2, 4 |
| 8 | 5 |

## Влияние на систему

- Прогоны: долгоживущие файлы задачи — 42 passed; планка — 2 passed.
  Полный набор `suite-run` №4: 4516 прошло, 19 упало. Повтор упавших
  (№5) — те же 19.
- Проверка причин. Временный возврат паспорта артели к прежнему
  `send_pending` (проба, сразу отменена) — 12 из 19 зеленеют. Это
  следствие строки 14 (AC-5): переход FSM артели теперь добавляет коммит
  паспорта в `refs/artifacts/<id>`, голова ссылки и фиксация сдвигаются
  на него. Ещё 5 — прямые следствия строк 7, 9, 11, 23, 27. Одно —
  следствие строки 15 (лишний `rev-parse` ссылки документов для поля
  `артефакты=`).
- Обвязки поправлены без смены утверждений:
  - `tests/test_doctor.py::BranchFreshnessCheckTest` — `setUp` подменяет
    `gitcmd.in_repo` (`fetch` успешен), лямбды `commits_behind` принимают
    `base=`. Строка 27: артель тоже идёт через `fetch` и
    `origin/<base>`. Без этой подмены `test_stale_active_task_warns`
    красный, а соседние методы проходили бы впустую (задача
    пропускалась до `commits_behind`).
  - `tests/test_fsm_map_conflict_autoresolve.py::MapConflictAutoResolveTest`
    — `setUp` глушит `artifact_branch.append_passport_line` тем же
    приёмом, что уже стоящая там заглушка черновика MR. Глобальный мок
    `subprocess.run` регенератора карты ловил плотницкий
    `git hash-object` паспорта.
- `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`
  красный и при отдельном прогоне. `orchestrator/liveness.py` ни от чего
  не импортирует и в диффе задачи не тронут, падение от задачи не
  зависит (похоже на ограничение окружения шага на сигналы группе
  процессов). Отмечаю, не чиню.
- Инварианты, гейты и лимиты не ослаблены. Стоп-кран волны теперь
  блокирует больше задач, замок зон действует у любого проекта, паспорт
  ведётся и у артели. Защищённые пути не тронуты, приложений к PLAN нет.
- Откат — revert merge-коммита задачи.

## Риски

- Паспорт у артели — коммит в `refs/artifacts/<id>` на каждом переходе.
  На каждом переходе добавляется push ссылки в `origin`; отказ push
  досылается тем же `send_pending`-механизмом следующего перехода.
- Стоп-кран волны теперь останавливает шаги внешних проектов. До
  подключения реального внешнего проекта эффекта нет.

## Предложения системе

- `tests/` патчат глобальный `subprocess.run` (`fsm.subprocess` — это
  модуль stdlib) под одну точку: любая новая git-запись по пути перехода
  ловится чужим моком (`MapConflictAutoResolveTest` — второй случай после
  `gh` черновика MR). Стоит отдать регенератору карты свою точку подмены.
- Точные перечни git-вызовов шага (`tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package`)
  краснеют от любого нового чтения по пути шага, не относящегося к
  предмету теста (здесь — поле `артефакты=`).

## Эскалация

**Вопросы** (по блокирующести):

1. Мандат на смену ожиданий существующих тестов (требование 7 SPEC). Все
   смены — прямые следствия решений «удалить» таблицы SPEC. Для каждой
   ниже: метод, было → стало, строка таблицы.

   Стоп-кран волны, замер диффа, точный перечень git-вызовов:
   - `tests/test_alerts_wave_breaker.py::CheckWaveBreakerFailureTest::test_foreign_target_is_not_counted`.
     Было: три задачи внешнего проекта с отказом «1b» не поднимают алерт
     (`assertFalse(opened)`, алертов `[]`). Стало: поднимают
     (`assertTrue(opened)`, один алерт волны). Строка 7, AC-3.
   - `tests/test_runner_wave_breaker.py::WaveBreakerAlertsOpenTest::test_foreign_target_alert_is_not_returned`.
     Было: алерт волны с `target=<другой>` не возвращается (`[]`).
     Стало: возвращается (отбор по источнику — один элемент). Строка 9.
   - `tests/test_catalog_wave_breaker_status.py::WaveBreakerSuffixTest::test_empty_for_foreign_target_even_if_alert_open`.
     Было: суффикс `""`. Стало:
     `"  [СТОП-КРАН ВОЛНЫ: run/auto не начинают новый шаг]"`. Строка 11.
   - `tests/test_split_assessment_merge_gate.py::SnapshotSplitAssessmentTest::test_external_target_skips_diff_but_still_reads_split_assessment`.
     Было: `assertIsNone(row["diff_bytes"])`. Стало: `diff_bytes` равен
     длине диффа в клоне проекта (в сценарии 14). Строка 23, AC-10.
   - `tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package`.
     Было: перечень git-вызовов шага кончается чтением кодовой ветки
     `rev-parse --verify --quiet refs/heads/<ветка>`. Стало: за ним ещё
     `["-C", clone, "rev-parse", "--verify", "--quiet", "refs/artifacts/<id>"]`
     (поле `артефакты=` записи «sha зафиксирован»). Чтения diff в шаге
     разработчика по-прежнему нет. Строка 15, AC-6.

   Паспорт у артели (строка 14, AC-5): голова ссылки и фиксация после
   перехода — коммит паспорта поверх прежней головы.
   - `tests/test_step_refixation.py::OwnStepCommitRefixesWithoutIncidentTest::test_refixation_is_journaled_with_both_shas`,
     `tests/test_step_refixation.py::ForeignCommitKeepsIncidentTest::test_fixed_sha_is_not_touched`,
     `tests/test_step_refixation.py::ForeignCommitKeepsIncidentTest::test_integrity_incident_still_raised`,
     `tests/test_step_refixation.py::UnclosedRunWindowNotCountedTest::test_commit_inside_unfinished_run_still_escalates`.
     Было: `entry_sha` — голова ссылки ДО `approve` в `tests_writing`
     (`enter_tests_writing`), с ним сверяются `fixed_sha` и тексты
     журнала и инцидента. Стало: `entry_sha` — голова ссылки ПОСЛЕ
     `approve` (= `tasks.fixed_sha` на входе в `tests_writing`). Остальные
     утверждения те же.
   - `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py::ApproveAfterIncidentTest::test_ac9_approve_exit_from_incident`.
     Было: `assertEqual(self.head(task_id), moved)` после
     `approve <id> <moved>`. Стало: родитель головы — `moved`. Утверждение
     `fixed == head` остаётся.
   - `tests/test_artifact_ref_sync.py::SendAfterCommitTest::test_refusal_is_journaled_commit_kept_and_retried_on_transition`.
     Было: после `set_state` `origin_head() == head`. Стало:
     `origin_head() == local_head()`, и `head` — родитель головы
     (досланная ссылка несёт коммит паспорта поверх `head`).
   - `tests/test_artifact_ref_sync.py::KillDocsRefTest::test_synced_ref_kills_with_a_closing_commit_in_origin`.
     Было: `parents(head) == [head0]`. Стало: `head0` — предок коммита
     закрытия (между ними коммит паспорта перехода в `killed`). Остальные
     утверждения (RETRO.md, `origin_head == head`) те же.
   - `tests/test_division_parent_cleanup.py::DivisionParentCleanupTest::test_division_keeps_the_artifact_branch_of_the_parent`.
     Было: голова артефактной ветки родителя после `approve` равна
     `head_before`. Стало: `head_before` — предок новой головы, ссылка не
     удалена. Утверждение о SPEC.md с разделом «## Деление» остаётся.
   - `tests/test_git_fixation.py::RunnerEscalationHintsIncludeShaTest::test_agent_failure_escalation_hint_includes_full_fixed_sha`.
     Было: в подсказке — sha из `enter_in_dev()` (до эскалации). Стало:
     sha головы ПОСЛЕ перехода в `escalated` (`self.head()`), как в
     соседнем `test_integrity_incident_hint_includes_full_fixed_sha`.
   - `tests/test_git_fixation.py::AutogateMergeGateHintIncludesShaTest::test_autogate_transition_hint_includes_full_fixed_sha`.
     Было: `fixed_sha` прочитан до автогейта. Стало: прочитан после
     перехода в `merge_gate`.

   Варианты: (а) мандат на весь список — смену проводит раздел SPEC
   «Меняемое поведение» (механика 01M45FJD46BX45VHC36S4VS9QN), правки
   тестов — следующим шагом developer; (б) мандат частичный — для
   исключённых методов сказать, какое поведение кода вернуть (например,
   паспорт у артели не вести — тогда строка 14 и AC-5 отпадают, и 10
   тестов паспорта не меняются).
   **Дефолт:** (а).

2. `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`
   красный на ветке и при отдельном прогоне, к диффу не относится.
   Варианты: (а) считать падением окружения шага, задача его не трогает;
   (б) завести отдельную строку бэклога. **Дефолт:** (а).

**Контекст.** Код требований 1–2 и 6 внесён, долгоживущие файлы и планка
зелёные. Обвязки двух классов поправлены без смены утверждений (см.
«Влияние на систему»). Полный набор красный только по перечню вопроса 1
и `test_liveness` (вопрос 2).

**Блокирует.** Зелёный полный набор `tests/` и, значит, выход из `in_dev`:
без мандата правка утверждений этих методов — нарушение неослабления.
