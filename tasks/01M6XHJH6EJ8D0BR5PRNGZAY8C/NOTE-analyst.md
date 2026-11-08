# Записка analyst

## Выяснено
- Возврат со spec_gate (7 решений) закрыт правкой SPEC.md: треб. 2 — `heavy_sandbox_names(sources)` + `size_findings(source, label, heavy)`, псевдонимы импорта, usefixtures, формы импорта subprocess/multiprocessing, имя в теле функции; треб. 3 — guard строит перечень по дереву проверки, `lint_base` на amend.py:293/:317.
- AC-2/AC-4 — полный перебор литералами parametrize (решение 3); AC-6 — каждый путь вызова (tests_writing, amend-tests с ветки/из планки, preflight).
- Новый раздел SPEC «Решения Оператора на гейте SPEC»: решение → требование/AC, что сверено по коду.
- Сверено: sandbox.py:1861/2018/2027/2040/2057/2076, report_outcome_sandbox.py:335, outcome_gate_sandbox.py:251; amend.py:293/317 без lint_base, :725 с ним; test_lint.py импортирует только ast.
- AC по-прежнему 9, budget 55; guard — ок, status: ready.

## Не сработало
- Длинный heredoc в Bash — «Parser aborted»; правки сделаны через Edit.

## Где остановился
- Готово.

## Чего не хватило
- Ничего существенного.
