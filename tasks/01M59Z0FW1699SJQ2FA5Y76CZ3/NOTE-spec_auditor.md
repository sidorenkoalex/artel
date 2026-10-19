## Выяснено
- Адреса SPEC (acceptance.py:688/709/719/752-754/1172-1282/1283/1460/1907/1923/1951/2307-2313, plank_run.py:61-77/186-195, guard.py:2620, project_profile.py:104-108, targets.py:493-510) — сходятся с кодом c2dc427f.
- Факт SPEC «pult-vitest выкладки не получает» неверен для компонента с workdir: единственный компонент с workdir обязан иметь runner: pytest-own (targets.py:73, 421-428), `_own()` (acceptance.py:121) смотрит только на runner, и `_layout_mode` даёт «layout» — выкладка под long_lived_dir/.artel-plank сегодня есть (фикстура tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:557-585).
- Отсюда коллизия требования 5: pult-vitest с runner: pytest-own без plank_layout — и «отказ» (не-pytest), и «прежняя выкладка» (pytest-own).
- `--ignore` в `_report_argv` добавляется только при own (runner: pytest-own); путь — через `_own_target` (от workdir). SPEC пишет «--ignore=<plank_layout до <id>>» без уточнения базы пути.
- Существующие тесты с компонентами по отчёту без plank_layout (report_outcome.py:927-934 test_ac11, :1480 test_ac16) останутся зелёными, но run/collect/run_plank в них станут отказом — покрытие свойства «неизвестно не зелено в точечных местах» деградирует молча; матрицы в SPEC нет.
- `drop_from_code_copy` для остатка plank_layout не покрыт ни одним AC.
- codebase-map в COMMON_ZONES (config.py:809) — регенерация карты зону не нарушает.

## Не сработало
- grep с `cd … &&` и пайпами через head/awk требует подтверждения — используй абсолютные пути/git grep без пайпов.

## Где остановился
- SPEC-AUDIT.md написан, verdict concerns.

## Чего не хватило
- Долго искал, у какого профиля работает выкладка сегодня: ключ — `_own()` по runner, а не по report (acceptance.py:121) и правило targets.py:421-428.
