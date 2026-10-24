# Записка ревьювера, итерация 1

## Выяснено
- Планка: 61 passed. Сверка `ast.dump` песочницы: 50/50 равны; `PytestSpy`, `pytest_output` и `FLAGS` тоже равны.
- Число утверждений по 26 тестам сходится, если учесть, что `self.assert_unknown` стал голым `assert_unknown`.
- Новый модуль, `tests/test_component_report_gates.py` и `ReportedOutcomeNotGreenInvariantTest`: 40 passed.
- `orchestrator/` и защищённые пути против базы 579a3819 не менялись.
- Вердикт — approved. Два косметических наблюдения (потерян `msg=` у `pytest.raises(OSError)` в ac16; ярлык `subTest` не доходит до `assert_unknown`) в реестр не вносил.

## Не сработало
- Составные bash-команды (`git apply; pytest; git apply -R`) и `cd` в `.artel/logs` требуют подтверждения. Heredoc с `{…'…}` и `$?` блокируется.
- `pytest -n 4 -p xdist` по этим файлам упал раньше сбора («node down: Not properly terminated»), тесты не запустились. Причину не разбирал; без `-n` всё зелёное.

## Где остановился
- REVIEW.md записан со статусом approved.

## Чего не хватило
- Исполнимого способа временной мутации для ревьювера: нужна одиночная команда пульта.
