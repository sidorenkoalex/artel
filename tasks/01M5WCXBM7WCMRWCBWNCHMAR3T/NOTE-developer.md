# Записка developer

## Выяснено
- Новые модули: orchestrator/forge.py (типы результатов, реестр
  IMPLEMENTATIONS, _GitHub над ci.check_runs), orchestrator/gitlab_adapter.py
  (transport/request, постраничное чтение со сверкой X-Total, правила итога).
  ci.py: `_pipeline_project(repo)` → `forge.ci_by_pipeline`; ветки в
  verifying_status/branch_status/failed_check_names/main_line_status/
  find_run_id/check_run_workflow_run/trigger_rerun.
- Цикл импорта ci↔forge↔gitlab_adapter: в gitlab_adapter нужен
  `from __future__ import annotations` (аннотации `forge.Job` иначе падают).
- 211 долгоживущих тестов задачи зелёные.

- В ci.py аннотация `forge.PipelineStatus` — строкой: при импорте forge
  первым ci видит forge частично.
- Свой tests/test_forge_gitlab_request.py (чужой :id, scp-адрес,
  ci_by_pipeline), мутации проверены. Связанные наборы ci/invariants/А0 —
  311 passed, 1275 subtests.

## Не сработало
- `pytest -n 4` в шаге — воркеры падают «node down»; гонять без -n.

## Где остановился
- Шаг завершён: PLAN.md status: ready, guard ок, карта регенерирована.
  plank-run: планка только markers.py — «планки нет», это норма задачи.

## Чего не хватило
- —
