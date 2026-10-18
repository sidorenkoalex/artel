# Записка developer — 01M57JYJQC8VAHEWMXFNM7D1GS

## Выяснено
- amend.py обе ветви зовут acceptance.collect/run с cwd=wt и command=own — выкладка внутри run/collect покрывает amend.
- Реализация: acceptance._plank_layout (exclude в info/exclude до copytree, уборка в finally); run_full_suite +--ignore;
  drop_from_code_copy убирает остаток; plank_run.py передаёт task_id.
- ANSWER-2 отработан (шаг 2): _exclude_layout — open("a+") + fcntl.flock(LOCK_EX), проверка и запись под замком;
  сбой → «отказ выкладки планки: … не записан (причина)». Тесты: test_acceptance_plank_layout_refusal.py (+2 метода:
  каталог вместо info/exclude, EIO на flock), новый test_acceptance_plank_exclude_lock.py. Мутации проверены.
- Риск importlib для _pult — записан в PLAN «Предложения системе».

## Не сработало
- pytest -n/xdist в шаге: все узлы «node down». Bash шага не пускает cp/heredoc-цепочки — мутации через Edit.

## Где остановился
- suite-run №2 зелёный (5846/0/2); guard ок; PLAN status: ready. Шаг сдан.

## Чего не хватило
- Ничего существенного.
