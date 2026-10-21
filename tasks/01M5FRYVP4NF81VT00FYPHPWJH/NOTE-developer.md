# Записка developer — 01M5FRYVP4NF81VT00FYPHPWJH

## Выяснено
- Реализовано все 11 требований: acceptance.py (`_bans_rerun_plugins`, `NO_RERUN_PLUGINS_ARGS` в `_report_argv` сразу за `command`, поле ключа), targets.py (`_check_rerun_ban`, вызов в `_check_components`), fsm.py (импорт константы в функции), refusal_classes/outcome_integrity (тексты), liveness.GATE_OWNER_MARKER, маркер в `_gate` и `two_sided.run`, doctor/orphans.py (ветка выписок до маркера канарейки, prune только при удалённой выписке), mandate.py (`_FILE_PATH_TOKEN_RE`).
- Планка 10/10, долгоживущие 6/6. Карта регенерирована.
- Свой тест: tests/test_targets_rerun_ban_wrapper.py (граница обёртки, `--reruns-only`, `-p` в конце) — обе мутации ловит.

## Не сработало
- `pytest -n 8` по списку файлов — воркеры падают (сторож conftest); гонял последовательно, долго (>10 мин на 34 файла).

## Где остановился
- Прогон тестов затронутых модулей; потом PLAN.md status: ready и guard.

## Чего не хватило
- Ничего существенного.
