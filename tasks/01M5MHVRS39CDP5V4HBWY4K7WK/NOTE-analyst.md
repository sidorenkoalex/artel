## Выяснено
- ТЗ достаточно; SPEC.md написан (status: ready, budget_usd 25 по ТЗ, 9 AC), guard ок.
- `lease.run_locked` — orchestrator/lease.py:334, именованные on_refusal/same_host_ok/force.
- «ЗДЕСЬ» в докстрингах команд: workspace.py:264, ci_rerun.py:55, fsm.py:1681 (cmd_reject), runner.py:160; fsm.py:732, fsm.py:921, answer.py:309 — функции вне таблицы (в «Не входит»). У cmd_spec_audit, cmd_pull_main, cmd_zones_extend слова «ЗДЕСЬ» grep не нашёл — формулировку их докстрингов про порядок разработчику сверить по месту.
- Сработал сигнал объёма (файлов зоны ≥ 5) — в SPEC дано обоснование монолита для решения Оператора.

## Не сработало
- Ничего.

## Где остановился
- Шаг закончен: SPEC.md готов.

## Чего не хватило
- Ничего существенного.
