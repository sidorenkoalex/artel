# Записка analyst

## Выяснено
- Итерация 4 (возврат из spec_gate 18.10, третий аудит, К-1..К-4) — внесено в SPEC:
  К-1 — требование 7 и AC-11: незапущенный повтор + зелёный branch_status → flake-rate «повтор не запущен» с причиной, без «флейк» (fsm_merge_gate.py:297-302);
  К-2 — требование 3, подраздел «Форма передачи»: check_runs/failed_check_names/find_run_id/check_run_workflow_run/trigger_rerun получают repo: Path | None (путь клона), url/GH_REPO выводятся внутри ci.py; repo у ci.gh/check_runs_page/run_list остаётся URL (github_adapter gh pr без правки);
  К-3 — требование 1: https и scp git@хост:владелец/имя(.git); иной вид — именованный отказ без запуска gh (канал как отказ токена ci.py:66-69); AC-2 проверяет оба вида, новый AC-12 — отказ;
  К-4 — требование 1: сопоставление пути клона с записью через repo_context.clone_path/resolve, признак артели только repo_context.is_artel; repo_context.py read-only — сопоставление в зонах задачи.
- Прежние решения итерации 3 (требования 2, 4, 5; AC-1, AC-9, AC-10) сохранены.

## Не сработало
- Bash с `;`/xargs/$(…) просит подтверждения — команды по одной.

## Где остановился
- SPEC.md: status ready, 12 AC, budget_usd 35 (рамка ТЗ), монолит; guard ок.

## Чего не хватило
- Помощника «путь клона → запись targets.yaml» в коде нет (repo_context.clone_path только имя→путь) — разработчику писать его в ci.py.
