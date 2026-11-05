# Записка developer

## Выяснено
- Итерация 1: правка — одна вставка в `orchestrator/canary.py::_pass_escalated_with_synthetic_answer` (вызов `fsm._mark_questions_answered` при условии approve, до `update_task`/`set_state`), докстринг дополнен.
- Итерация 2 (R1-F1): добавлен сторож `tests/test_canary_synthetic_answer_batch_mark.py` на `LightTransitionSandbox` с подменённым `canary.answer.cmd_answer`. Шесть мутаций (удалён, по истинности, после set_state, только escalated_from, только baseline, безусловный) — каждая краснит файл. Код канарейки возвращён `git checkout`, не менялся.
- Планка 7 passed; новый файл + test_canary_synthetic_answer + answered_batch — 28 passed. Карта регенерирована. R1-F1 в реестре REVIEW размечен `fixed`.

## Не сработало
- `cat` heredoc в Bash роли недоступен — артефакты писать Write. `$VAR` в команде Bash требует подтверждения — пути писать полностью.
- `scripts/guard.py` на тестовом файле требует frontmatter — guard только для артефактов.

## Где остановился
- PLAN.md status: ready, шаг завершён.

## Чего не хватило
- —
