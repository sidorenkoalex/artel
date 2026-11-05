# Записка spec_auditor

## Выяснено
- Факты SPEC о коде верны: spec_gate_decision.py:186-189 (isdigit/int), artel.py:2650-2675 (_cmd_reject), fsm.py:2078-2081 ловит только DecisionError, журнал хранит текст файла, не путь (fsm.py:2118, 2185).
- Опыт python3: '²' isdigit True, int → ValueError; '３','١' int → 3/1, отказ идёт веткой «не по порядку».
- Существующие тесты (tests/test_spec_gate_decision.py, tests/test_01m6kb0sjhda4d4gnem7pgz40p_decision_reject.py, test_lease_run_task_command.py) не ломаются; "decision=" в tests/ нет.
- Вердикт concerns: литерал «повторён» не задан (AC-6); два пробельных ключа — сейчас отказ «не сочетается…» (artel.py:2670), тр.4 vs AC-7 неясно; аргумент «--decisions…» не определён; порядок/сочетания вне AC-6.

## Не сработало
- grep с `--include=*.py` и `-e "--decision"` отклоняются оболочкой/правами; искать по `DECISION_FLAG\|"--decision"`.

## Где остановился
SPEC-AUDIT.md сдан (status: ready, verdict: concerns), guard ок.

## Чего не хватило
Ничего существенного.
