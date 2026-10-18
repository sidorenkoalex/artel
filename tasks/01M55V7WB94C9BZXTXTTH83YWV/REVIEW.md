---
task: 01M55V7WB94C9BZXTXTTH83YWV
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: CI ветки внешнего проекта: запросы gh к репозиторию проекта

## Фаза A: план
- Таблица покрытия полна: требования 1–8 и ANSWER-2 привязаны к шагам; шаг 5
  (итерация R1-F1) назначает сторожей в `tests/` требованиям 3 (передача клона
  из вызывающих, AC-7), 5 (AC-10) и 7 (AC-11) — пробел итерации 1 закрыт.
- Подход не менялся (адресация внутри `ci.py`, признак артели — только
  `repo_context.is_artel`), конфликтов с архитектурой нет.
- «Влияние на систему» соответствует инкрементальному diff: код не менялся,
  добавлен один файл `tests/test_ci_callers_project_repo.py`. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | без изменений с итерации 1: `gh api` → `GH_REPO`, `gh run/pr` → `--repo`, разбор https/scp, отказ иного вида; сторож — долгоживущий файл задачи (AC-2, AC-8, AC-12) и `tests/test_ci_project_gh_address.py`. |
| 2 | OK | у артели прежняя форма; AC-1 долгоживущего файла зелёный; новые тесты проверяют и отсутствие `repo` у артели во всех вызовах вызывающих. |
| 3 | OK | передача клона из `ci_rerun.py:225,233,276,291,310` и `fsm_merge_gate.py:296` теперь под сторожем `CiRerunRepoTest`/`MergeGateRerunRepoTest`. |
| 4 | OK | `_inherited_from_main` по `origin/<base>` у проекта; сторож — AC-9 долгоживущего файла. |
| 5 | OK | `ci_rerun.py:283-284` `fsm._origin_main_sha(…, **project)`; сторож — `CiRerunRepoTest.test_red_path_passes_project_clone_everywhere`. |
| 6 | OK | долгоживущий `ArtelGhUnchangedTest`. |
| 7 | OK | `fsm_merge_gate.py:302-306` «повтор не запущен: <note>» при любом исходе; сторож — `FlakeRateNotStartedTest` (обе формы отказа × красный/зелёный; запущенный повтор — прежние записи). |
| 8 | OK | без сети; новые тесты — заглушки `ci`/`fsm`/`workspace`, настоящий `is_artel` через `ci._repo_kwargs`. |

## Замечания

Нет. Новый файл — тест разработчика на вызывающих (`ci_rerun`, `fsm_merge_gate`),
долгоживущий файл задачи их не покрывает — повтора нет (ADR-0020 п.4). Каждый
метод несёт «Ловит мутацию: …» с наблюдаемым расхождением (запись журнала,
`repo=` вызова); заявки подтверждены временной мутацией (см. ниже).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/fsm_merge_gate.py:295-318; orchestrator/ci_rerun.py:222-234, 275-291, 310 | требования 5, 7 и передача клона из вызывающих (AC-7/10/11) без сторожа в `tests/` | регресс вызывающих после мержа никто бы не заметил | закрыто: `tests/test_ci_callers_project_repo.py`; каждая из девяти временных мутаций (ветка `rerun_started`, `trigger_rerun` гейта мержа, `check_run_workflow_run`, `trigger_rerun(run_id=…)`, `failed_check_names` ×2, `_origin_main_sha`, `trigger_rerun` красного пути, `repo=` артели) красит файл |

## Вердикт
approved — R1-F1 закрыт, новых замечаний нет.

## Проверено исполнением
- `python3 -m pytest -q -p no:xdist tests/test_ci_callers_project_repo.py` — 5 passed, 12 subtests.
- Временная мутация (по одной, код восстанавливался после каждой, `git status` чистый), прогон `tests/test_ci_callers_project_repo.py`:
  `fsm_merge_gate.py` `if not ci.rerun_started(...)` → `if False` — 4 failed;
  `trigger_rerun(branch, **ci._repo_kwargs(repo))` → `trigger_rerun(branch)` — 1 failed;
  в `ci_rerun.py` снят `**project` у `check_run_workflow_run` — 1 failed, у `trigger_rerun(…, run_id=…)` — 1 failed,
  у `failed_check_names(head)` — 1 failed, у `failed_check_names(main_sha)` — 1 failed,
  у `fsm._origin_main_sha` — 1 failed, у `return ci.trigger_rerun(branch)` — 1 failed;
  `_project_kwargs` → `{'repo': task_repo}` всегда (артели тоже) — 2 failed.
- `python3 …/artel.py plank-run 01M55V7WB94C9BZXTXTTH83YWV` — 4 passed, код 0.
- `python3 -m pytest -q -p no:xdist` по `tests/test_ci_callers_project_repo.py tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py tests/test_ci_project_gh_address.py tests/test_merge_gate_ci_wait.py tests/test_ci_rerun_command.py tests/test_ci_stuck_check_run.py tests/test_ci_status.py` — 141 passed, 92 subtests.
- `python3 scripts/codebase_map.py` — расхождение только в `built_at_sha` (карта свежа), файл возвращён.
- CI коммита 09c53354 — зелёный (16 проверок, из пакета).

## Предложения системе
- Шаблон мутаций «снять `**kwargs` у вызова» удобно гонять одним python-heredoc с заменой строки и `finally`-возвратом — запись во `/tmp` в шаге требует подтверждения, так что скрипт держать только в stdin.
