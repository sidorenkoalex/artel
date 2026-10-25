# Записка analyst — 01M5T79C5GFJGQ9XCTH8W0PDFQ

## Выяснено
- Шаг 2 (возврат со spec_gate 26.10): решения Оператора (1)–(6) по SPEC-AUDIT перенесены в SPEC, число AC прежнее (9), budget 40, status ready, guard ок.
  - (1) треб. 4/AC-9: места 1 и 4 не на пути SpyRun (глобальный subprocess.run); места 2,3,5,6,7 остаются на пути, видимом SpyRun и шпионам subprocess.run. Альтернатива «доказательство в PLAN» оставлена только для fake_git/LightTransitionSandbox (её допускает ТЗ-4).
  - (2) import subprocess в outcome_integrity.py сохраняется; сторож AC-2 импорт не запрещает (треб. 1, 5, AC-2).
  - (3) carpentry для места 1 убрана: только функция gitcmd на Popen, срок 15 с, `-C <root>` (треб. 2).
  - (4) OSError места 1 выходит исключением из suite_tree_hash (Контекст, треб. 3, AC-8).
  - (5) место 4: TimeoutExpired при запуске → SOURCE_FAILED «ls-tree: TimeoutExpired: …» (Контекст, треб. 3, AC-4, AC-8).
  - (6) AC-1: поведенческий тест на каждое место, обёртки acceptance._launch/_run_capture не используются (треб. 1, AC-1).
- Ранее: LightTransitionSandbox подменяет gitcmd.git/in_repo/show/ls_tree_files; SpyRun стоит на глобальном subprocess.run (sandbox.py:1682).

## Не сработало
- `ls` в shell недоступен (command not found) — читать файлы инструментом Read.

## Где остановился
- SPEC правлен и прошёл guard; шаг закончен.

## Чего не хватило
- Ничего нового: аудит дал адреса строк для всех решений.
