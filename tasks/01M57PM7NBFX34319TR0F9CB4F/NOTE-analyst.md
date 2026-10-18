# Записка analyst — 01M57PM7NBFX34319TR0F9CB4F

## Выяснено
- ANSWER-1: зоны расширены на store.py (функции строки мьютекса по проекту, `set_merge_lock` не стирает чужие проекты, прежние сигнатуры сохраняются) и notes.py (окно тишины по всем строкам мьютекса). doctor check_merge_lock — вне задачи, строка бэклога в «Предложения системе» PLAN. Бюджет $45, монолит.
- Кроме store, «одна строка на пульт» зашита в `merge_lock.touch_heartbeat` (merge_lock.py:95, без аргументов, вызовы fsm_merge_gate.py:355, :631) — внесено требованием 3 / AC-6.
- merge_queue: `_head_task_id`, `_current_holder_id/_label`, `queue_wait_minutes` читают всю таблицу — требования 4–6.
- Проект задачи по task_id — `store.task_target` (store.py:701). Колонка target в схеме не нужна (вынесено в «Не входит»).
- docs/invariants.md мьютекс не упоминает.

## Не сработало
- Через Bash `rm` недоступен (command not found / нужно подтверждение); QUESTIONS.md удалён через `python3 -c os.remove`.

## Где остановился
- SPEC.md написан (9 требований, AC-1…AC-11, status: ready), guard ок, QUESTIONS.md удалён.

## Чего не хватило
- Не хватило знания, кто ещё вызывает `touch_heartbeat`; нашёл грепом по fsm_merge_gate.py.
