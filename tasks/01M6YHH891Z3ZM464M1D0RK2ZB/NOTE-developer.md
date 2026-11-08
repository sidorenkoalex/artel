# Записка developer — 01M6YHH891Z3ZM464M1D0RK2ZB

## Выяснено
- Код: `config.SUITE_RUN_POLL_SEC = 1.0`. `suite_run._POLL_SEC` удалена, опрос `_wait`/`wait_request` и `mutation_run --wait` читает config.
- Тестовый файл suite_run: копия config задаёт 0.1; `pids.discard(os.getpid())`; пределы 8/3; ac16 гейт сверяет outcome; ac24 сверяет отчёт без «не уложился» и `PYTEST_SUMMARY` в `<лог запуска без .log>-base.log`. Помощники `process_snapshot`/`path_needles`/`assert_no_process` лежат в SuiteRunSandbox; ac21 прощает пробу и корень только процессам `holder` и его потомкам по ppid.
- Итоги прогонов: планка — 8 passed; долгоживущий — 3 passed; файл suite_run — 26 passed за 170 с серийно; mutation_run_flags — 40 passed.
- Мутация «фон до отказа `--failed`» роняет ac20 (проверено, код возвращён).

## Не сработало
- `pytest -n` в шаге роли: все воркеры «node down». Гонял серийно.
- Запись в /tmp из Bash роли отклонена: временную мутацию делал через Edit.

## Где остановился
- PLAN.md ready, guard ок. AC-10 (mutation-run base/head) не гонял: это делает приёмка.

## Чего не хватило
- Знания, что xdist в шаге роли не работает (предел процессов?).
