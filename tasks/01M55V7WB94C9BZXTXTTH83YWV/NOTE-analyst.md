# Записка analyst

## Выяснено
- Итерация 3 (возврат из spec_gate 18.10, шесть решений Оператора по аудиту) — все внесены в SPEC:
  (1) требование 2 — на все функции перечня и вызывающих из ci_rerun.py/fsm_merge_gate.py; перечень подмен дополнен находками аудита (test_ci_rerun_command.py:238/:242, test_ci_stuck_check_run.py:220, test_main_ci_fetched_repo.py:64) и test_01m4pmqsypr2kd6n1jcvg9zabv_branch_verdict.py:203 (head_sha("main")); AC-1 — «ни одна подмена не правится»;
  (2) внешний проект — по записи targets.yaml клона (требование 1); main_line_status(repo=config.ROOT) pin.py:86 / doctor/main_ci.py:33 — артель, в требовании 2 и AC-1;
  (3) сценарий main_line_status с клоном проекта — в AC-2;
  (4) ci_rerun.py:272 _origin_main_sha(repo=клон) — требование 5, AC-10;
  (5) _inherited_from_main: base проекта, origin/<base> клона — требование 4, AC-9; ТОЛЬКО для внешнего проекта: у артели head_sha("main") держит подмена долгоживущего теста 01m4pmq…:203, а AC-1 запрещает правку подмен — записано в «Не входит» (моё согласование двух решений, Оператор может поправить);
  (6) flake-rate «повтор не запущен» при rerun_started ложь (ci.py:1274) — требование 7, AC-11; тестов на прежний текст в этом случае нет (test_merge_gate_ci_wait.py:82 возвращает «запущен»).

## Не сработало
- Bash с `;`/xargs/$(…) просит подтверждения — команды по одной.

## Где остановился
- SPEC.md: status ready, 11 AC, budget_usd 35 (рамка ТЗ), монолит; guard ок.

## Чего не хватило
- Ничего.
