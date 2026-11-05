# Записка analyst

## Выяснено
- Итерация 7 (пятый возврат, решения №5.1–№5.5) внесена в SPEC; AC по-прежнему три.
- №5.1: подменённый docker пишет свой os.getpgrp(); тест сверяет его с os.getpgrp() теста; os.getpgid — только зависшему; finally — только pid зависших (у зависшего down — и дочерний).
- №5.2: по пределу os.killpg группы; предел down — COMPOSE_TEARDOWN_TIMEOUT_SEC части 1 (120 с, в main пока нет — константа части 1), прочие — DOCKER_CALL_TIMEOUT_SEC 10 с. AC-2: зависший down с дочерним процессом.
- №5.3: строки в all_checks, cmd_doctor(fix=True) с подменой прочих починок (test_doctor_closed_ref_fix.py:177-183, сверено).
- №5.4: docker не найден — warn (стенды) / fail (запись); PATH строки записи — правило части 1 + machine.path; зависание network ls/context inspect в AC-2.
- №5.5: живость без хоста (lease.py:408 сравнивает хост — сверено); process_alive не меняется, lease.py в «Не входит».

## Не сработало
- —

## Где остановился
- SPEC.md status: ready, guard ок.

## Чего не хватило
- —
