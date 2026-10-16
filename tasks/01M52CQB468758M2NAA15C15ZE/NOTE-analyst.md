# NOTE analyst — 01M52CQB468758M2NAA15C15ZE

## Выяснено
- Возврат с spec_gate 16.10: десять замечаний Оператора внесены в SPEC (итерация 2), guard: ок.
- Зоны родителя 17: добавлены fsm_advance.py, advance_gates/tests_writing.py, advance_gates/test_integrity.py (в D0-3, только передача профиля).
- workdir/env только при runner: pytest-own (targets.check отказывает при pult-pytest и по умолчанию) — требование 1, AC-13.
- acceptance_suite (acceptance.py:1807-1848) — в D0-2, берёт профиль задачи сама; fsm.py:1294 и fsm_autogate.py:326 зовут её.
- Перевод целей полного набора — в месте запуска (D0-2); suite_run.py передаёт targets=("tests",) (:525,:565), его логика не меняется.
- AC 15 штук: AC-1 оба пути команды (None и [python3,-m,pytest]); AC-2/3/4/6 по восьми местам; AC-7 сверка с профилем; AC-8..12 plank-run, amend-tests, pull, two-sided, сухой сбор tests_writing.
- Раздел «## Матрица неослабления» (заголовки mandate.MATRIX_HEADERS) — строка про снятие -p timeout у pytest-own.
- Порог бюджета деления — config.py:587 = 60, сигнал по бюджету не срабатывает; бэклог — :186.
- Рамки частей: $25 / $45 / $40 (сумма выше рамки ТЗ $50 — сказано в SPEC).

## Не сработало
- ls в Bash недоступен; читать Read/sed/grep.

## Где остановился
- SPEC.md сдан, status: ready, guard: ок.

## Чего не хватило
- Формат «матрицы неослабления» искал в mandate.py/operator-gates.md:53 — в шаблоне SPEC раздела нет.
