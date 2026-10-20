# NOTE-reviewer (итерация 1)

## Выяснено
- Код прочитан по диффу пакета: outcome_integrity (строка доказательства, _proven, merge_gate_escalates, review_lines), fsm_merge_gate (шаг после «fresh»), review.py, two_sided.py, refusal_classes.
- branch_head_sha возвращает "" (не None) — review_lines не падает на срезе.
- _origin_main_sha фетчит в клон ctx (объект main есть для merge-base).
- Планка 3 passed; тесты затронутых модулей + долгоживущий файл задачи — зелёные; мутация fingerprint ловится.
- Вердикт: approved, реестр пуст.

## Не сработало
- `pytest -n 4` в рабочей копии — node down; гонять с `-p no:xdist`.

## Где остановился
- REVIEW.md записан (approved).

## Чего не хватило
- Формат строк Finding.runs для разбора id — искал в compare/_redness (outcome_integrity.py:135–165, 333–348).
