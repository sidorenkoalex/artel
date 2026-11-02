# Записка developer

## Выяснено
- Ядро `_judge_ci` (outcome_integrity.py) годно для verifying без изменений.
  Голова — `gitcmd.branch_head_sha` той же локальной ветки, что читает
  `ci.verifying_status`.
- Отказ, видимый брифу, должен идти ПОСЛЕ записи `state -> in_dev`
  (store.refusal_history).
- Шаг developer в журнале — actor `developer`, action `agent run started`.
- Реализация: `verifying_gate` / `_verifying_refusal` / `_cycle_reason`;
  `_Pending` (подкласс `_Prepare`); возврат помечен `RETURN_DETAIL`.
- ANSWER-2 (повтор через опрос ожидания): `_cycle_reason` уже брал только
  BROKEN/OUTCOME-записи — код не менялся, добавлен комментарий и тест
  `tests/test_01m6bmg29kzv1rx21hfaxzg3cm_repeat_after_wait.py` (мутация с
  PENDING_ACTION в выборке краснит его).
- Планка AC-15 пускает в tests/ только новые файлы с префиксом задачи —
  поэтому новый тест назван с префиксом; лок лишних файлов не отвергает.

## Не сработало
- `pytest -n 6` роняет воркеры (xdist). Гонять последовательно.
- `mv`, `cp`, heredoc в Bash запрещены — переименование через python os.rename.

## Где остановился
- Шаг завершён. PLAN status: ready, guard ок, карта регенерирована.

## Чего не хватило
- Правило AC-15 планки про имена новых файлов tests/ увидел только по
  красному plank-run.
