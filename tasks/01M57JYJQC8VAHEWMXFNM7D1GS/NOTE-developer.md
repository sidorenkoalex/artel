# Записка developer — 01M57JYJQC8VAHEWMXFNM7D1GS

## Выяснено
- amend.py обе ветви зовут acceptance.collect/run с cwd=wt и command=own — выкладка внутри run/collect покрывает amend.
- Реализация: acceptance._plank_layout (exclude в info/exclude до copytree, уборка в finally); run_full_suite +--ignore;
  drop_from_code_copy убирает остаток; plank_run.py передаёт task_id.
- ANSWER-2 отработан (шаг 2): _exclude_layout — open("a+") + fcntl.flock(LOCK_EX); сбой → отказ выкладки.
- ANSWER-3 (шаг 3): только уточнение мандата на правку assert_runs_file (:345-348) для гейта неослабления;
  код/тесты не менялись, в PLAN добавлен шаг 8. Тесты задачи + затронутые — 24 passed.

## Не сработало
- pytest -n/xdist в шаге: все узлы «node down». Bash шага не пускает ls/cp — обход через Read/Edit.

## Где остановился
- PLAN status: ready, guard прогнан. Шаг сдан.

## Чего не хватило
- Ничего существенного.
