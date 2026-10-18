---
task: 01M55V7WB94C9BZXTXTTH83YWV
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: CI ветки внешнего проекта: запросы gh к репозиторию проекта

## Фаза A: план
- Таблица покрытия полна: требования 1–8 и ANSWER-2 привязаны к шагам; шаги
  размера MR. Подход (адресация внутри `ci.py`, вызывающие передают клон
  параметром `repo`, признак артели — только `repo_context.is_artel`)
  совпадает с К-2/К-4 и не вводит параллельного признака.
- «Влияние на систему» соответствует diff: `ci.py`, `ci_rerun.py`,
  `fsm_merge_gate.py`, фикстуры по ANSWER-2, новый `tests/test_ci_project_gh_address.py`;
  `acceptance.py`/`github_adapter.py` не тронуты. Откат — revert.
- Пробел плана: строки покрытия требований 5 и 7 (и передачи клона из
  вызывающих — AC-7) ссылаются только на планку, которая помечена
  `Группа: разовый`; сторожа в `tests/` план не предусматривает — см. R1-F1.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `ci.gh`: `gh api` → `GH_REPO` без `--repo`, `gh run/pr` → `--repo`; разбор https/scp регулярками `_HTTPS_URL_RE`/`_SCP_URL_RE`; иной вид — отказ без запуска с адресом и «вид адреса не разобран»; `GH_REPO` и без `token_slot` (окружение собирается по любому из `GH_REPO`/`GH_TOKEN`). Внешний проект — `_project_area_name` + `repo_context.resolve`, артель — `is_artel`. |
| 2 | OK | `_project_kwargs` даёт `{}` у артели и `config.ROOT` (ROOT вне `projects_root()`), `extra` пуст без переменных — argv/env/cwd прежние; AC-1 долгоживущего файла зелёный, подмены прежней формы не правлены. |
| 3 | OK | Сигнатуры `check_runs`, `failed_check_names`, `find_run_id`, `check_run_workflow_run`, `trigger_rerun` с `repo: Path \| None = None`; внутренние `_commit_workflow_runs`, `_no_checks_by_branch`, `_main_line_runs` получают клон; вызывающие `ci_rerun.py:222-234,275-291,310`, `fsm_merge_gate.py:295-296` передают. |
| 4 | OK | `_inherited_from_main`: у проекта — `refs/remotes/origin/<base>` клона, проверки — у проекта, фраза «от <base> <sha>»; у артели — прежний `head_sha("main")`. |
| 5 | OK по коду / нет сторожа в `tests/` | `ci_rerun.py:283` `fsm._origin_main_sha(target, **project)`; у артели `{}`. См. R1-F1. |
| 6 | OK | долгоживущий `tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py::ArtelGhUnchangedTest`. |
| 7 | OK по коду / нет сторожа в `tests/` | `fsm_merge_gate.py:301-318`: при `not ci.rerun_started` — «повтор не запущен: <note>…», ни «флейк», ни «подтверждённый красный»; возврат и `sys.exit` прежние. См. R1-F1. |
| 8 | OK | подставной `gh`, `subprocess.run` перехвачен, адреса localhost. |

## Замечания

- major — `orchestrator/fsm_merge_gate.py:295-318`, `orchestrator/ci_rerun.py:222-234`, `:275-291`, `:310` — долгоживущие свойства требований 5, 7 и передачи клона проекта из вызывающих (AC-7, AC-10, AC-11) сторожит только планка `acceptance_tests/test_callers.py`, помеченная `Группа: разовый`; после мержа её не гоняет ни CI, ни автогейт (ADR-0018 п.3). Проверено временной мутацией: убрал ветку `not ci.rerun_started(...)` в `_ci_confirm_red_or_flake` (запись снова «подтверждённый красный»/«флейк» при незапущенном повторе), убрал `**project` у `fsm._origin_main_sha`, `ci.trigger_rerun(branch)` и `ci.check_run_workflow_run(check_id)` в `ci_rerun.py` — `tests/test_merge_gate_ci_wait.py tests/test_ci_rerun_command.py tests/test_ci_stuck_check_run.py tests/test_ci_status_kind_gate.py tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py tests/test_ci_project_gh_address.py` — 61 passed, ни одного красного; код возвращён `git checkout`. Сценарий: любой будущий рефакторинг вызывающих молча вернёт `ci-rerun`/ре-ран гейта мержа sled в репозиторий артели (ровно инцидент задачи) или ложную запись `flake-rate`. Закрытые имена (`_ci_confirm_red_or_flake`, `fsm._origin_main_sha`) тестам разработчика в `tests/` доступны — ограничение, объяснившее разовую группу планки, на них не распространяется. Предложение: добавить в `tests/` (свой файл разработчика, не повтор долгоживущего) тесты с заявками «Ловит мутацию: …»: (а) `_ci_confirm_red_or_flake` при `trigger_rerun`, вернувшей «ре-ран CI не запущен: …», и красном/зелёном `branch_status` — запись `flake-rate` содержит «повтор не запущен» и причину, без «подтверждённый красный»/«флейк»; при запущенном — прежняя; (б) `ci_rerun` задачи внешнего проекта передаёт `repo=<клон>` в `check_run_workflow_run`, `failed_check_names` (оба вызова), `trigger_rerun` (оба места) и `fsm._origin_main_sha`, у артели — без `repo`; (в) `_ci_confirm_red_or_flake` задачи внешнего проекта зовёт `trigger_rerun(branch, repo=<клон>)`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/fsm_merge_gate.py:295-318; orchestrator/ci_rerun.py:222-234, 275-291, 310 | требования 5, 7 и передача клона из вызывающих (AC-7/10/11) без сторожа в `tests/` — только разовая планка; временная мутация всех четырёх мест не покраснила ни одного теста `tests/` | регресс вызывающих после мержа вернёт `ci-rerun`/ре-ран гейта мержа в репозиторий артели или ложную запись `flake-rate`, никто не заметит | добавить тесты `tests/` на запись `flake-rate` при незапущенном повторе (красный и зелёный исход) и на `repo=<клон>` у всех вызовов `ci`/`_origin_main_sha` из `ci_rerun.py` и `fsm_merge_gate.py` (и прежнюю форму у артели) |

## Вердикт
changes_requested — закрыть R1-F1 (сторожа в `tests/` для требований 5, 7 и
передачи клона из `ci_rerun.py`/`fsm_merge_gate.py`). Код по существу SPEC
реализован верно, дефектов поведения не найдено.

## Проверено исполнением
- `python3 …/artel.py plank-run 01M55V7WB94C9BZXTXTTH83YWV` — 4 passed, код 0.
- `python3 -m pytest -q -p no:xdist tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py tests/test_ci_project_gh_address.py tests/test_ci_status.py tests/test_main_ci_line.py tests/test_merge_gate_ci_wait.py tests/test_ci_rerun_command.py tests/test_ci_stuck_check_run.py tests/test_main_ci_fetched_repo.py tests/test_01m4pmqsypr2kd6n1jcvg9zabv_branch_verdict.py tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py` — 164 passed, 104 subtests (прогон с `-n 8` упал на старте воркеров — «node down», среда; повторён последовательно).
- Временная мутация (см. R1-F1): `fsm_merge_gate.py` `if not ci.rerun_started(...)` → `if False`, снят `**project` у трёх вызовов `ci_rerun.py`; 6 файлов `tests/` — 61 passed; код восстановлен `git checkout`, `git status` чистый.
- `python3 scripts/codebase_map.py` — расхождение только в `built_at_sha` (карта свежа), файл возвращён.
- Сверка диффа `tests/`: `sandbox.py`, `…project_area.py`, `…artel_docs_ref.py` — только данные фикстур (адрес проекта, `route_url_to_bare`) по ANSWER-2; утверждений не удалено/не изменено.

## Предложения системе
- Планка, вынужденно разовая из-за закрытых имён (`test_callers.py` этой задачи), оставляет долгоживущие свойства без сторожа, если план не назначает тест `tests/` разработчику; стоит в test-authoring/шаблоне PLAN требовать строку «сторож в tests/» для каждого AC разовой планки, проверяющего свойство кода.
