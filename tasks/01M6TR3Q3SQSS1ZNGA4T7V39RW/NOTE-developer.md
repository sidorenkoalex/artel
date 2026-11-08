# Записка developer — 01M6TR3Q3SQSS1ZNGA4T7V39RW

## Выяснено
- Долгоживущий файл tests/test_01m6tr3q3sqss1znga4t7v39rw_role_requests.py задаёт форму: очередь
  suite-run/<id>/requests/<n>.json, итог <n>.result.json (поля свободные — тест читает flat_text),
  фразы-константы в его шапке (NOT_IN_FLIGHT, STEP_OVER, INTERRUPTED, LOCK_BUSY, QUEUED, STILL_RUNNING
  «прогон не прерван, повтори», REQUEST_ACTION).
- Исполнитель зовёт docker из процесса пульта (ppid=драйвер), дочерний прогон — в той же сессии.
- Дочерний прогон планки — cmd_plank_run(..., ref_if_no_draft=True): нет каталога черновика →
  зафиксированная планка ссылки.
- tests/test_01m462…_suite_run.py и tests/test_01m46c…_suite_run_appendix.py в шаге роли виснут:
  отвязанный фон копии пульта стоит на `git show refs/artifacts/…` через role_bin/role_git.py из PATH
  роли (видно `/bin/ps`; `ps` без пути роли недоступен). Путь background задача не меняет. Тесты
  оставляют осиротевшие фоны в $TMPDIR — я снял шесть (`os.killpg`, cwd проверен через lsof).

## Не сработало
- Запуск тех двух файлов в шаге роли (таймаут 120 с и 580 с) — см. выше, вердикт за CI.

## Где остановился
- Всё сделано: долгоживущий 32/32, планка 6/6, тесты модулей 75 + 175 passed, карта регенерирована
  после подтяжки main, guard ок, PLAN status: ready.

- Возврат из verifying (08.11): `_compose_call` → публичное `compose_call` в acceptance.py,
  вызовы в runner.py/acceptance.py переведены; карта регенерирована.

## Чего не хватило
- Штатного способа узнать, что тест копии пульта несовместим с окружением роли (role_git в PATH).
