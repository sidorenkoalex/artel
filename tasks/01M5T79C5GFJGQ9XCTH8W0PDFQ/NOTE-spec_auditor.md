# Записка spec_auditor — 01M5T79C5GFJGQ9XCTH8W0PDFQ

## Выяснено
- Третий аудит, SPEC sha 8fef2363…: SPEC-AUDIT.md сдан, status ready, verdict pass, guard ок.
- Оба решения Оператора на гейте SPEC (№1 — шесть пунктов, №2 — три пункта) в SPEC внесены.
- Подмен `mock.patch.object(acceptance, "subprocess", …)` в tests/ ровно 10, перечень SPEC полон. `PytestSpy` (`test_report_outcome_module.py:76-87`) не-pytest argv передаёт настоящим run/Popen.
- Подмены `acceptance.subprocess.run` (около 15 мест) подменяют глобальный модуль, а место 1 идёт через Popen, так что видимость после переноса прежняя.
- `explicit_repo.py:63`: первый параметр новой публичной функции gitcmd должен называться repo/path/root/cwd/repo_path.

## Не сработало
- Не годятся `ls` в шелле и `cd … &&` с относительными путями. Нужны абсолютные пути.

## Где остановился
- Аудит закончен.

## Чего не хватило
- Ничего существенного.
