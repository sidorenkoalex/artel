---
task: 01M484RNV3QBDY3B0M16J916ZP
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Этап 3 ADR-0021, часть 3 из 3: прочие развилки, сторож и сквозной тест внешнего потока

## Подход

Код требования 1 внесён (коммит пульта 0d010214 после таймаута шага,
сверен на следующем шаге). Строки таблицы SPEC «удалить» сняты без новой
механики. В `zone_lock` и `catalog` фильтр «только артель» заменён
фильтром «тот же проект». В остальных местах фильтр просто убран:
стоп-кран, `_dirty_refuses`, паспорт, «sha зафиксирован», `show`,
`docs --fetch-all`, `diff_bytes`, гейт отработки ревью, свежесть ветки.
Оставленные строки (16, 18, 19, 21, 24, 25, 28, 29) узнают артель одной
функцией `repo_context.is_artel`. Признак принимает контекст, имя
проекта, строку задачи и путь клона: эти развилки держат разные формы
субъекта. Своё разрешение remote и базы в `fsm.py` (строка 17) заменено
на `repo_context.resolve`.

Сторож (требование 3) и сквозной тест (требования 4–5) — это
долгоживущие файлы test_author `tests/test_01m484rnv3qbdy3b0m16j916zp_*.py`.
Своих тестов на эти свойства нет: требование 7 их засчитывает. Свой тест
написан только на формы субъекта `is_artel`
(`tests/test_repo_context.py::IsArtelSubjectsTest`). Карту (требование 6)
описывают первые строки докстрингов `repo_context` и
`advance_gates/__init__`.

Две защитные правки — следствие паспорта у артели (строка 14). Паспорт
пишется на КАЖДОМ переходе FSM артели, поэтому плотницкая запись в ссылку
документов теперь достижима из песочниц, где git подменён или его нет:
- `gitcmd.carpentry`: при `OSError` (git не запускается) возвращает
  ненулевой `CompletedProcess`, как и `gitcmd.git()`. Переход FSM (в
  частности, kill switch) не падает из-за записи «только для глаз».
- `artifact_branch.write_commit`: пустой или не-байтовый ответ
  `hash-object` значит «запись не удалась», а не исключение.

На этом шаге закрыта причина возврата — эскалация, на которую ответил
ANSWER-1. Ожидания 15 методов сменены по мандату ослабления с соблюдением
условий 1–4 ответа (перечень — в «Влиянии на систему»).

## Шаги

1. Требование 1: строки 1–15, 17, 20, 22, 23, 26, 27 — развилка
   удалена; строки 16, 18, 19, 21, 24, 25, 28, 29 — признак
   `repo_context.is_artel` (требование 2).
2. Требования 3–5: долгоживущие файлы test_author зелёные на ветке.
   Планка `plank-run` зелёная.
3. Требование 6: докстринги модулей, затем `python3 scripts/codebase_map.py`
   (карта пересобрана и на этом шаге).
4. Требование 7: смена ожиданий 15 существующих методов по мандату
   ANSWER-1. Обвязки двух классов поправлены без смены утверждений.
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

### Методы, сменившие ожидание по мандату ANSWER-1 (условие 4)

Имена не менялись, ни один метод не удалён, число утверждений ни в одном
не уменьшилось. Проверки «является предком» не применялись: там, где
ожидание касается цепочки коммитов, сверяется точный список родителей.

- `tests/test_alerts_wave_breaker.py::CheckWaveBreakerFailureTest::test_foreign_target_is_not_counted`.
  Было: `assertFalse(opened)`, алертов волны `[]`. Стало:
  `assertTrue(opened)`, алертов волны ровно 1. «Ловит мутацию» описывает
  возврат счёта волны только по артели.
- `tests/test_runner_wave_breaker.py::WaveBreakerAlertsOpenTest::test_foreign_target_alert_is_not_returned`.
  Было: `wave_breaker_alerts_open(...) == []`. Стало: длина результата 1.
  «Ловит мутацию» описывает возврат отбора по проекту артели.
- `tests/test_catalog_wave_breaker_status.py::WaveBreakerSuffixTest::test_empty_for_foreign_target_even_if_alert_open`.
  Было: суффикс `""`. Стало: суффикс
  `"  [СТОП-КРАН ВОЛНЫ: run/auto не начинают новый шаг]"` (точное
  равенство). «Ловит мутацию» описывает пометку только у артели.
- `tests/test_split_assessment_merge_gate.py::SnapshotSplitAssessmentTest::test_external_target_skips_diff_but_still_reads_split_assessment`.
  Было: `assertIsNone(row["diff_bytes"])`. Стало: `diff_bytes` равен
  длине диффа в байтах (`len(diff_text.encode("utf-8"))`). Утверждение о
  `split_assessment` не тронуто.
- `tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package`.
  Было: точный перечень git-вызовов кончается
  `rev-parse --verify --quiet refs/heads/<ветка>`. Стало: после него ещё
  `["-C", clone, "rev-parse", "--verify", "--quiet", "refs/artifacts/<id>"]`
  (поле `артефакты=`). Перечень остаётся точным: любое чтение diff
  по-прежнему его ломает.
- `tests/test_step_refixation.py::OwnStepCommitRefixesWithoutIncidentTest::test_refixation_is_journaled_with_both_shas`,
  `::ForeignCommitKeepsIncidentTest::test_fixed_sha_is_not_touched`,
  `::ForeignCommitKeepsIncidentTest::test_integrity_incident_still_raised`,
  `::UnclosedRunWindowNotCountedTest::test_commit_inside_unfinished_run_still_escalates`.
  Было: `entry_sha` — возврат `enter_tests_writing()`, то есть голова
  ссылки ДО `approve`. Стало: `entry_sha = self.head()` сразу после
  `enter_tests_writing()`, то есть голова ПОСЛЕ `approve` с коммитом
  паспорта. Утверждения методов не тронуты. Общий помощник
  `enter_tests_writing` не менялся: соседние методы вне мандата не задеты.
- `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py::ApproveAfterIncidentTest::test_ac9_approve_exit_from_incident`.
  Было: `head == moved`. Стало: список родителей головы ровно `[moved]`.
  Утверждение `fixed == head` остаётся.
- `tests/test_artifact_ref_sync.py::SendAfterCommitTest::test_refusal_is_journaled_commit_kept_and_retried_on_transition`.
  Было: после `set_state` `origin_head() == head`. Стало:
  `origin_head() == local_head()` и `parents(local_head()) == [head]`.
- `tests/test_artifact_ref_sync.py::KillDocsRefTest::test_synced_ref_kills_with_a_closing_commit_in_origin`.
  Было: `parents(head) == [head0]`. Стало: точная цепочка. У коммита
  закрытия ровно один родитель — коммит паспорта. Его родители ровно
  `[head0]`, а `diff --name-only head0 паспорт` ровно
  `[tasks/<id>/PASSPORT.md]`. Утверждения о RETRO.md и
  `origin_head == head` не тронуты.
- `tests/test_division_parent_cleanup.py::DivisionParentCleanupTest::test_division_keeps_the_artifact_branch_of_the_parent`.
  Было: голова артефактной ветки родителя после `approve` равна
  `head_before`. Стало: ссылка есть, родители новой головы ровно
  `[head_before]`, а `diff --name-only head_before голова` ровно
  `[tasks/<PARENT>/PASSPORT.md]`: SPEC.md не тронут, RETRO.md нет.
  Утверждение о «## Деление» в SPEC.md не тронуто. Мутация из докстринга
  проверена временной правкой: после `cleanup_killed_task` в
  `fsm._cleanup_divided_parent` дописан `snapshot.commit_closing(...,
  "killed")`. Тест покраснел (родитель головы — не `head_before`), код
  возвращён.
- `tests/test_git_fixation.py::RunnerEscalationHintsIncludeShaTest::test_agent_failure_escalation_hint_includes_full_fixed_sha`.
  Было: sha в подсказке — возврат `enter_in_dev()`. Стало:
  `sha = self.head()` после перехода в `escalated`, как в соседнем
  `test_integrity_incident_hint_includes_full_fixed_sha`.
- `tests/test_git_fixation.py::AutogateMergeGateHintIncludesShaTest::test_autogate_transition_hint_includes_full_fixed_sha`.
  Было: `fixed_sha` прочитан до автогейта. Стало: прочитан из БД после
  перехода в `merge_gate`.

### Прочее

- Прогоны этого шага: `suite-run` №6 (полный набор) — прошло 4534,
  упало 1, пропущено 2. Упал только `test_liveness` (см. ниже); база не
  досчитана. Планка `plank-run` — 2 passed.
- Обвязки поправлены без смены утверждений (прошлый шаг):
  - `tests/test_doctor.py::BranchFreshnessCheckTest`: `setUp` подменяет
    `gitcmd.in_repo` (`fetch` успешен), лямбды `commits_behind` принимают
    `base=`. Причина — строка 27: артель тоже идёт через `fetch` и
    `origin/<base>`.
  - `tests/test_fsm_map_conflict_autoresolve.py::MapConflictAutoResolveTest`:
    `setUp` глушит `artifact_branch.append_passport_line` тем же приёмом,
    что и заглушку черновика MR.
- `orchestrator/fsm.py`: на этом шаге только перенос строки докстринга
  `_snapshot_split_assessment`, поведение не менялось.
- `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`
  по ANSWER-1 (вопрос 2, вариант а) — падение окружения роли, задача его
  не трогает.
- Инварианты, гейты и лимиты не ослаблены. Стоп-кран волны теперь
  блокирует больше задач, замок зон действует у любого проекта, паспорт
  ведётся и у артели. Защищённые пути не тронуты, приложений к PLAN нет.
- Откат — revert merge-коммита задачи.

## Риски

- Паспорт у артели — коммит в `refs/artifacts/<id>` на каждом переходе.
  К каждому переходу добавляется push ссылки в `origin`. Отказ push
  досылается механизмом `send_pending` на следующем переходе.
- Стоп-кран волны теперь останавливает шаги внешних проектов. Пока
  реальный внешний проект не подключён, эффекта нет.

## Предложения системе

- `tests/` патчат глобальный `subprocess.run` (`fsm.subprocess` — это
  модуль stdlib) под одну точку. Поэтому любая новая git-запись на пути
  перехода попадает в чужой мок (`MapConflictAutoResolveTest` — второй
  случай после `gh` черновика MR). Стоит дать регенератору карты свою
  точку подмены.
- Точные перечни git-вызовов шага (`tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package`)
  краснеют от любого нового чтения на пути шага, даже не относящегося к
  предмету теста (здесь — поле `артефакты=`).
- В ответе на эскалацию Оператор отметил: раздел SPEC «Меняемое
  поведение» засчитывается только на approve гейта SPEC. Требование 7 этой
  SPEC («после мандата смену проводит раздел "Меняемое поведение"») этим
  неисполнимо по букве. Для задач, где мандаты выдаются по эскалации,
  analyst-шаблону стоит сразу ссылаться на мандат ослабления.
