# Записка spec_auditor (визит 4, SPEC c4aadfd0)

## Выяснено
- Отклонения визита 3 (1–8) закрыты решением на гейте и внесены в SPEC; ссылки SPEC на код сверены, перечень 43 фикстур совпал с grep.
- Новое: `_run_full_suite_to_log` ставит PYTHONUNBUFFERED=1 (acceptance.py:1368-1372) — вне закрытого перечня AC-11, строки матрицы нет.
- Лог suite-run — в config.LOGS/suite-run/<id>/ рядом с lock.json (suite_run.py:131-134, suite_lock.py:40-49); «каталог отчётов (журнал) на запись» = монтирование журналов пульта; лог пишет хост через stdout (acceptance.py:1371-1373).
- runner pult-pytest при required: интерпретатор venv пульта (acceptance.py:58-61) в контейнере не существует — сочетание не определено.
- run_repeat: пустой список = зелёно (acceptance.py:676-677, advance_gates/acceptance.py:169-176) — канала именованного отказа нет, вызывающий вне зон.
- Отметка установки в рабочей копии попадёт в `git add -A` чекпоинта (checkpoint.py:1722).
- Ключ base-итога suite_run.py:511,533 (вне зон) не охвачен требованием 9.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready, 7 отклонений; guard ок.
- Ещё: SPEC не задаёт pult-pytest при required (venv пульта в контейнере нет); _kill_group на :1332,:1337,:1385,:1388, а не :1334,:1388.

## Чего не хватило
- Где лежит лог полного набора suite-run (suite_lock.directory) — искал дольше всего.
