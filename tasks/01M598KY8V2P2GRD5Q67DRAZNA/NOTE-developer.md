# Записка developer — 01M598KY8V2P2GRD5Q67DRAZNA

## Выяснено
- Реализация: `orchestrator/tz_check.py` (новый), `catalog._tz_content_check` +
  вызов в `cmd_new` после `ensure_clone`, журнал «проверка ТЗ» после
  `_new_task_row`; `artel._new_strict_tz_arg` + `_NEW_USAGE`.
- `cmd_new(strict_tz=True)` передаётся только при флаге — иначе ломается
  `tests/test_task_model_set_units.py::...test_set_flag_passes_name_and_keeps_tz`
  (assert_called_once_with без нового keyword).
- Долгоживущий файл задачи 19/19 зелёный (4 прогона со случайными зёрнами);
  соседние модули catalog/new/merge_after/canary_drive — 164 passed.
- В `_cmd_new` без `--target` при нескольких записях боевого targets.yaml —
  sys.exit «укажи проект»: юнит-тест argv обязан передавать `--target`.
- Замер волны G: QUESTIONS.md у задач волны G нет — сверял ANSWER-*/SPEC-AUDIT.

## Не сработало
- `pytest -n 4` в рабочем каталоге — воркеры падают (node down); гонял серийно.
- heredoc с f-строкой `{...}` в Bash отклоняется — сценарий писал файлом.

## Где остановился
- Повторный шаг: отказ advance по инварианту 35 (адреса не localhost в
  `tests/test_tz_check.py::test_url_with_port_is_not_a_ref`) — адреса заменены
  на `127.0.0.1`, тест зелёный, мутация левой границы его краснит;
  `guard.network_address_errors_from_files` по тестам задачи — пусто.
- Шаг завершён: PLAN.md status: ready, guard ок, карта регенерирована.
- plank-run: AC-11 зелёный; AC-15 красен только потому, что PLAN.md ещё не в
  ссылке документов (появится автокоммитом пульта); регулярка теста по
  локальному PLAN.md проходит.

## Чего не хватило
- Где взять вопросы аналитика для AC-15 (QUESTIONS.md нет) — искал дольше всего.
