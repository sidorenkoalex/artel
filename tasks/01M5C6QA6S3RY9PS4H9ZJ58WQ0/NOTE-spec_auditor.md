# Записка spec_auditor — 01M5C6QA6S3RY9PS4H9ZJ58WQ0

## Выяснено
- Все адреса SPEC сверены с кодом и сошлись (canary.py:279/2607/2807/2848, artel.py:1563/1586/1772, notes.py:266/1262/1312, pool_seal.py:316, merge_queue.py:111, fsm_merge_gate.py:1379/1509, liveness.py:27/56, config.py:428/515, sandbox.py:90).
- Пути записи в main: только notes._commit_and_push (notes.py:1193), pool_seal._commit_through_clone (pool_seal.py:307), fsm_merge_gate._push_merged_main (:1270). Других нет.
- Тело окна мержа зовётся только из цикла (fsm_merge_gate.py:1577); цикл — только из fsm._approve_merge_gate (fsm.py:1410).
- Время старта процесса уже умеет doctor/stale_cycles.process_start_time (ps lstart, точность секунда, None при сбое).
- Тесты файла результата проверяют только наличие файла/status (test_canary_detach_result.py:24-25, test_01m4axpy…_canary_detach.py:118) — смена отбора их не ломает.
- cmd_canary на сигнале бросает SystemExit (canary.py:2871) — run_stamp не возвращается; файл результата на этом пути остаётся без run_stamp.

## Не сработало
- Составные bash-команды с cd/подстановкой режутся песочницей — читать через Read/grep по абсолютному пути.

## Где остановился
- Вердикт concerns, SPEC-AUDIT.md записан.

## Чего не хватило
- Источник «времени старта процесса» в SPEC не назван — искал, есть ли готовый помощник (нашёлся в doctor/stale_cycles.py:42).
