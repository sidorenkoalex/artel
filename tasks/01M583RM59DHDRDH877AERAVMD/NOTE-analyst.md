# Записка analyst — 01M583RM59DHDRDH877AERAVMD

## Выяснено
- ANSWER-1: вопрос 1 — B (окно suite_run.py:801-810 в «Не входит», зоны прежние; способ — отложенная доставка флагом, без pthread_sigmask); вопрос 2 — A (SIGINT в раннем окне: группа снята, каталоги удалены, KeyboardInterrupt наверх, строки прогона нет).
- Итерация 3 (возврат spec_gate, решения Д1/А1/В1/Е1): классы tests/test_canary_drive.py — CloneCodeDrivesTheTaskTest (:119; методы :145, :173), CloneProcessFailureTest (:219; :243, :259), InterruptedPultTest (:272; :274).
- Уборка CanaryLifecycleTest.stop_suites (lifecycle-тест :93) шлёт killpg SIGKILL, но ведение не дожидается — отсюда А1.
- `_interrupt_on_signal` canary.py:2737–2752; :2743 ставит SIG_IGN в обработчике.

## Не сработало
- `rm`/`cat` в шелле шага — читать через Read.

## Где остановился
- SPEC.md: Д1 — 3 строки матрицы (+AC-7 расширен этими методами); А1 — треб. 7 + AC-10; В1 — AC-8 переписан, строка в «Не входит»; Е1 — треб. 8, треб. 4 уточнено (участок сам не вводит SIG_IGN), абзац в «Способ», AC-11. 11 AC — сигнал ≥10 отмечен в «Оценке объёма». budget 35, guard ок, status: ready.

## Чего не хватило
- —
