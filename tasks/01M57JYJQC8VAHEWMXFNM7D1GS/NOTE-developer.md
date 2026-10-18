# Записка developer — 01M57JYJQC8VAHEWMXFNM7D1GS

## Выяснено
- amend.py обе ветви зовут acceptance.collect/run с cwd=wt и command=own (amend.py:550-554, :724-728) —
  выкладка внутри run/collect покрывает amend без правки amend.py.
- Реализация: acceptance._plank_layout (exclude в info/exclude до copytree, уборка в finally),
  run/collect/run_plank(task_id=...) гонят из выкладки; run_full_suite +--ignore=<lld>/.artel-plank;
  drop_from_code_copy убирает остаток по профилю задачи. plank_run.py передаёт task_id.
- Тесты задачи (19) зелёные; затронутые модули 87+119 passed; две правки теста 01m56g23 по мандату, мутация проверена.
- Свой тест: tests/test_acceptance_plank_layout_refusal.py (отказ без info/exclude), мутация проверена.

## Не сработало
- pytest -n/xdist в шаге: все узлы «node down». Гонять последовательно.

## Где остановился
- PLAN.md status: ready, guard ок; suite-run №1 зелёный (5842 прошло, 0 упало). Шаг сдан.

## Чего не хватило
- Ничего существенного.
