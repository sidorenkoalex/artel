# Записка spec_auditor

## Выяснено
- SPEC-AUDIT.md сдан: verdict concerns, status ready, guard ок.
- Ключевые расхождения SPEC с кодом amend.py: `acceptance_test_files(tdir, rule)` — каталог на диске, в `--from-branch` только снимок (amend.py:1109); Python-путь проверяет ВСЕ долгоживущие файлы (amend.py:851/878/1163), а не только изменённые; отказы долгоживущих — через `_refuse` «долгоживущие файлы tests/» (amend.py:881/1166), не `_refuse_group_lines`/`_refuse_traceability`.
- fsm.py:1207 — запись DECLARED пишется до точки, где встанет новая сверка; у DECLARED нет отзыва.
- Мандата (ANSWER) на правку трёх методов пока нет.
- guard не импортирует project_profile — разбор идентификатора в guard будет копией parse_test_id.

## Не сработало
- Bash с `cd …;`, переменными, `ls`, `..` в путях требует подтверждения — звать grep/python3 по относительным путям, читать Read.

## Где остановился
- Аудит завершён.

## Чего не хватило
- Где у SPEC живёт матрица неослабления (шаблон и скил её не называют) — пришлось читать mandate.matrix_refusals и answer.py.
