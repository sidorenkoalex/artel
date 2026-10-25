# Записка spec_auditor — 01M5TBCY7WTN121S136XP2C6SR (аудит 5, редакция 5, sha e32944db)

## Выяснено
- Решение гейта №4 внесено: требование 10 без алерта 100 %; требование 4 называет KNOWN/PARTIAL/ESTIMATED; AC-29.
- spend.py: PARTIAL/ESTIMATED журналируют ДО charge (:824→:825, :834→:835), KNOWN — после (:182→:208, :319→:325).
- watch.py: два цикла — cmd_watch (:734, _emit_steps :442) и _watch_observation (:381, _observation_events :273).

## Не сработало
- `cd ... && git` и `ls` в Bash отклоняются; работают одиночные `git grep`, `git hash-object`.

## Где остановился
- SPEC-AUDIT.md: status ready, verdict concerns (цикл watch не назван; гонка журнала/начисления — наблюдение).

## Чего не хватило
- Кода Э1 (board.py, epics.py, new --epic/--after).
