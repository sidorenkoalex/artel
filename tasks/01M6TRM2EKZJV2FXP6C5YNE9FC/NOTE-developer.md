# Записка developer

## Выяснено
- Реализация: `_await_running_main_ci` в `orchestrator/fsm_merge_gate.py`
  (зовётся из `_refuse_if_main_red` при MAIN_RUNNING, после ветки
  --fixes-main); `_await_main_ci` читает цвет один раз.
- Долгоживущий файл задачи 9/9 зелёный; `..._main_ci.py` 20/20 после
  переписи двух методов по мандату; test_main_ci_line, one_push_per_command,
  merge_reference, full_suite_reuse зелёные.
- В переписанном `test_ac4_green_after_running...` состояние `gh`
  переключается вложенным `patch_sleep(fsm_merge_gate, …)` — у
  `MainCiSandbox.fake_sleep` нет хука.

## Не сработало
- Составная Bash-команда (cp + heredoc) требует подтверждения — мутации
  делать через Edit.

## Где остановился
- Шаг закончен: код, тесты, карта, PLAN ready, guard по PLAN — ок.
  test_report_outcome_module и mr_delivery — 78 passed.

## Чего не хватило
- Ничего существенного.
