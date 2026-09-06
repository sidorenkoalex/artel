---
task: 01M1TKP269W9JN3NBJCR5Q6C3B
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 4
---

# REVIEW: канарейка — диагностика незелёного прогона и бейзлайн только с зелёного исхода

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (AC-1, AC-2, AC-3) | OK | `_save_diagnostics` (orchestrator/canary.py:797-840) зовётся ИЗНУТРИ `with _ephemeral_clone()` до его выхода — журнал (`store.task_steps`), логи ролей клона (`config.LOGS.glob(f"{task_id}-*.log")`) и PLAN/REVIEW артефактной ветки клона (`gitcmd.show`) пишутся под `outer_root`, посчитанным ДО входа в блок; отсутствие PLAN/REVIEW не роняет команду. Подтверждено прогоном `test_ac1_ac2_ac3_diagnostics_on_inconclusive_outcome.py` (4/4 зелёных). |
| 2 (AC-5, AC-6) | OK | `_journal_excerpt_lines` (canary.py:781-793, лимит 18) + строка метрик + строка пути диагностики — не более 20 строк на задачу; путь печатается буквально. Подтверждено `test_ac5_ac6_output_path_and_journal_excerpt.py` (2/2 зелёных). |
| 3 (AC-7, AC-8) | OK | `_needs_diagnostics(normal_outcome, mismatch)` — единая точка решения, переиспользуемая и для диагностики, и (инвертированно) для бейзлайна/сравнения (canay.py:886-922) — симметрия по ANSWER-1.md соблюдена. Подтверждено `test_ac4_ac7_normal_outcome_baseline_and_diagnostics.py` (4/4) и `test_ac8_killed_runs_excluded_from_baseline_and_deviation.py` (2/2). |
| 4 (AC-9) | OK | `.gitignore` уже несёт `.artel/` целиком — правка не нужна, подтверждено `test_ac9_gitignore_excludes_canary_dir.py` (2/2 зелёных с рождения). `prune._canary_diag_candidates` (prune.py) применяет тот же `config.LOG_RETENTION_DAYS`, без фильтра «последние N задач» — обоснованно (`task_id` диагностики — id уничтоженного эфемерного клона, никогда не попадает в `store.all_tasks`). `docs/retention.md` дополнен разделом по образцу `.artel/logs/`; правка вне заявленных `zones` (SPEC зоны: `orchestrator/canary.py, orchestrator/prune.py, tests/, .gitignore`) легитимно расширена ANSWER-2.md + PLAN.md «## Расширение зон» — мандат Оператора на месте. Подтверждено `test_ac9_prune_retention_for_canary_dir.py` (3/3). |

## Замечания

- major — tests/test_canary.py:179-262 (классы `NeedsDiagnosticsTest`, `JournalExcerptLinesTest`, `DiagnosticsDirTest`, все 8 тестовых методов: 184, 187, 190, 193, 223, 237, 243, 259) и tests/test_prune.py:79-127 (класс `PruneCanaryDiagCandidatesTest`, методы 100, 103, 109, 114) — новые тесты не несут докстринг с заявкой `Ловит мутацию: …` (skills/test-authoring.md, review-checklist п. «Тесты»), у части методов нет докстринга вообще (просто голое тело). В ЭТОМ ЖЕ файле tests/test_canary.py уже есть прецедент прямо противоположной практики — `MacKeyTest`, `OpensslSecretPassingTest`, `PoolSerializationRoundtripTest`, `RestorePoolIfMissingNoOpTest` (не тронуты этим диффом) несут докстринг с явной заявкой мутации на КАЖДЫЙ метод. Без заявки я не могу свериться с тем, что тест ловит правдоподобную поломку, а не исполняет ритуал покрытия (например, `test_path_shape` в `DiagnosticsDirTest` — не очевидно, ловит ли он путаницу `outer_root`/`config.ROOT`, или просто фиксирует форму пути). Предложение: добавить каждому из 12 методов докстринг вида «<сценарий>. Ловит мутацию: <что сломали — тест покраснеет>», тем же стилем, что и у соседних классов файла.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | tests/test_canary.py:179-262, tests/test_prune.py:79-127 | 12 новых тестовых методов без докстринга «Ловит мутацию» (4 класса) | ревьювер не может свериться с заявленной чувствительностью теста, разрыв с практикой этого же файла | дописан докстринг каждому из 12 методов (`NeedsDiagnosticsTest`, `JournalExcerptLinesTest`, `DiagnosticsDirTest`, `PruneCanaryDiagCandidatesTest`) в формате «Ловит мутацию: …» по образцу `MacKeyTest` и др.; `python3 -m unittest tests.test_canary tests.test_prune` — 66/66 зелёных |

## Вердикт

changes_requested — единственное замечание R1-F1 (major, тесты). Логика требований 1-4 (AC-1..AC-9) реализована корректно и симметрично относительно ANSWER-1.md/ANSWER-2.md, вся приёмочная планка и юнит-тесты зелёные — после дописывания докстрингов ожидаю approve.

## Проверено исполнением

- `python3 -m unittest tests.test_canary tests.test_prune -v` — 66 тестов, все зелёные (включая 12 новых из этого диффа: `NeedsDiagnosticsTest`, `JournalExcerptLinesTest`, `DiagnosticsDirTest`, `PruneCanaryDiagCandidatesTest`).
- `python3 -m unittest discover -s tasks/01M1TKP269W9JN3NBJCR5Q6C3B/acceptance_tests -p "test_*.py" -v` — 18 тестов, все зелёные (AC-1..AC-9 целиком).
- `python3 scripts/codebase_map.py` — диф свёлся только к строке `built_at_sha` (некритично, см. review-checklist), откачено обратно `git checkout -- docs/codebase-map.md`, регенерации по существу не требуется.
- `git diff f4c29600...HEAD -- tests/test_canary.py tests/test_prune.py | grep '^-'` — пусто: дифф теста только добавляет, ни один существующий тест/ассерт не ослаблен и не удалён.
- Точечное чтение: orchestrator/canary.py (полный файл вокруг диффа — `_ephemeral_clone`, `_kill_outcome_note`, `_drive_task`, `_task_metrics`, `_save_diagnostics`, `_run_one_task`), orchestrator/prune.py, orchestrator/agent_log.py (формат имени лог-файла `{task_id}-{role}-{n}.log`, подтверждает корректность glob `f"{task_id}-*.log"`), orchestrator/artifact_branch.py (`branch_name` совпадает с тем, что читает `gitcmd.show` внутри клона), orchestrator/config.py (`LOG_RETENTION_DAYS = 90`, `COMMON_ZONES` включает `docs/codebase-map.md`), `.gitignore` (`.artel/` целиком, без правки покрывает `.artel/canary/`) — для проверки конкретных замечаний по коду (все сошлось, замечаний по коду нет).
- Прочитаны с артефактной ветки (`git show artifact/01m1tkp269w9jn3nbjcr5q6c3b:...`): SPEC.md, PLAN.md, все acceptance_tests/*.py (не показаны в пакете ревью) — для сверки покрытия требований и обоснования расширения зон.

## Предложения системе

(пусто)
