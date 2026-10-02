---
task: 01M3Y75C9TY76083CG1PK00EM4
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Проверка CI, зависшая в состоянии «идёт» при известном исходе, не останавливает задачу

## Подход
- **Одно правило завершённости** — `ci.check_finished(run) -> (finished, line)`:
  `status == "completed"` либо заданы оба поля `conclusion` и `completed_at`
  (тогда `line` — строка журнала «<имя>: GitHub отдаёт status=… при
  conclusion=…, completed_at=… — считаю завершённой»). Оба читателя
  (`verifying_status`, `branch_status`) зовут его через общий
  `ci._unfinished_checks(runs)` — литерала `"completed"` в их телах нет
  (AC-3). Строки о прочтении вопреки `status` дописываются к `note` после
  итога, каждая своей строкой (`_with_reread`): первая строка остаётся
  итогом, на ней стоят `verifying_is_red`/`status_kind`/`red_status_sha`.
- **Состояние «проверка зависла»** — новый исход `ci.VERIFYING_STUCK =
  "stuck"`, только в `verifying_status`: незавершённая проверка со статусом
  `in_progress`/`queued`, без `conclusion`, возраст (`started_at`, без него
  `created_at`) больше `config.CI_STUCK_CHECK_MINUTES = 45`. Зависшая важнее
  идущих рядом. `note`: «CI коммита <sha>: проверка зависла (порог 45 мин)
  — <имя> (check-run id <id>, status=…) висит <N> мин без исхода; …».
  Нет «не зелёный:» — `verifying_is_red` ложно, `auto` не останавливается
  как на красном; `fsm_advance.verifying` не трогается — любой не-зелёный
  исход ждёт, потолок `VERIFYING_CEILING_SEC` прежний. Неразобранная отметка
  времени — не «зависла» (идёт). На гейте мержа (`branch_status`) этого
  состояния нет (SPEC «Не входит»).
- **`ci-rerun` в состоянии «зависла»**: `_cmd_ci_rerun` при
  `VERIFYING_STUCK` идёт в `_stuck_rerun`: id check-run'ов берутся из `note`
  (`ci.stuck_check_ids`, тот же приём, что `red_status_sha`), прогон
  workflow каждого — `ci.check_run_workflow_run(id)` (`gh api
  …/actions/jobs/<id>` → `run_id`: check-run задания Actions — это job), и
  `ci.trigger_rerun(branch, run_id=…)` — тот же узел перезапуска и ожидания
  `gh run watch`. С заданным `run_id` поиск по sha пропускается и прогон
  перезапускается без `--failed` (в зависшем прогоне упавших заданий нет).
  Сверки красного пути (sha красной записи журнала, флейк против main)
  вынесены в `_red_rerun` без изменений и для «зависла» не применяются:
  статус прочитан только что по текущей голове, упавших заданий нет.
  Отказы по основанию, состоянию и lease не тронуты. Прогон не найден —
  именованный отказ `CI_RERUN_REFUSED_ACTION`, без перезапуска «наугад».

## Шаги
1. `orchestrator/config.py`: `CI_STUCK_CHECK_MINUTES = 45`.
2. `orchestrator/ci.py`: `check_finished`, `_unfinished_checks`,
   `_with_reread`, `_check_age_minutes`, `_stuck_checks`, `stuck_check_ids`,
   `VERIFYING_STUCK`; правка `verifying_status`/`branch_status`;
   `check_run_workflow_run`; `trigger_rerun(branch, run_id="")`.
3. `orchestrator/ci_rerun.py`: развилка stuck/red, `_stuck_rerun`,
   `_red_rerun` (перенос прежних требований 4–7 дословно).
4. `tests/test_ci_stuck_check_run.py` — 10 тестов на границы, не покрытые
   долгоживущим файлом; `python3 scripts/codebase_map.py`.

Проверки (каждая в переднем плане, `-p no:cacheprovider -p timeout -o timeout=120`):
- планка задачи: `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py` +
  `tasks/01M3Y75C9TY76083CG1PK00EM4/acceptance_tests/` — зелёные;
- затронутые модули: `test_ci_stuck_check_run`, `test_ci_rerun_command`,
  `test_ci_status`, `test_ci_status_kind_gate`, `test_merge_gate_ci_wait`,
  `test_verifying_ceiling`, `test_auto_cycle`, `test_watch`,
  `test_codebase_map`, `test_guard_mutation_claim` — 257 passed;
  `test_long_lived_transitions`, `test_01m3rwa2786hcac8pt3xsbkqt4_autogate`,
  `test_fsm_autogate`, `test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker`,
  `test_github_adapter`, `test_acceptance` — 81 passed.
- сторожа проверены временными мутациями `ci.py` (правило без
  `completed_at`, «зависла» без сверки статуса, `--failed` у заданного
  прогона, строки перед итогом, неразобранный возраст, `id` вместо
  `run_id`, отключённое «зависла») — на каждой `tests/test_ci_stuck_check_run.py`
  красный, код возвращён.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (одно правило, строка журнала) | 2 |
| 2 (константа, «зависла», запись с именем/id/возрастом) | 1, 2 |
| 3 (`ci-rerun` перезапускает прогон зависшей проверки) | 2, 3 |
| 4 (тесты в новом файле с «Ловит мутацию») | 4 |

## Влияние на систему
- `note` статуса CI может стать многострочным (только при прочтении вопреки
  `status`); все разборы `note` (`verifying_is_red`, `status_kind`,
  `red_status_sha`, `watch`) ищут подстроки итога, который остаётся первой
  строкой, — их поведение не меняется.
- Гейт мержа: проверка с `conclusion`+`completed_at` теперь читается
  завершённой и там (требование 1) — `failure` даёт красный `note` и
  штатный ре-ран гейта, `success` — зелёный. Проверка без исхода
  по-прежнему не зелёная (инвариант 19 не ослаблен).
- `trigger_rerun` без `run_id` — байт-в-байт прежний путь (`--failed`, поиск
  по sha), гейт мержа его так и зовёт. Красный путь `ci-rerun` перенесён в
  `_red_rerun` без изменения проверок и текстов отказов
  (`tests/test_ci_rerun_command.py` зелёный без правок).
- Существующие тесты не менялись. Откат — revert коммита задачи.

## Риски
- Предположение «id check-run'а задания Actions = id job» — так в GitHub API
  (job id и check-run id совпадают); если нет — `ci-rerun` откажет
  именованно «прогон workflow зависшей проверки … не найден», без
  перезапуска не того прогона.
- `gh run rerun <id>` по ещё идущему прогону GitHub может отклонить — тогда
  `trigger_rerun` вернёт «ре-ран прогона … не запущен», и `ci-rerun`
  закончится именованным отказом (AC-9 прежней SPEC), Оператор увидит текст
  `gh`. Инцидент 02.10 (прогон уже `completed`) этим не задет.

## Предложения системе
- Временная мутация, сохраняющая длину строки (`if stuck:` → `if False:`),
  и возврат исходника в ту же секунду оставили устаревший
  `orchestrator/__pycache__/ci.*.pyc`: Python сверяет pyc по mtime+размеру,
  и следующие прогоны шли по мутанту. skills/coding-standards.md («Сторожа
  проверяй временной мутацией») стоит дополнить: после возврата кода
  удалить `__pycache__` модуля (или гонять мутации с
  `PYTHONDONTWRITEBYTECODE=1`).
