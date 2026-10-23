# Записка test_author

## Выяснено
- AC-1..AC-6 — долгоживущий файл `tests/test_01m5mhvm25kh83wgz5k256wn9q_observation_freshness.py`; AC-7 — разовый `acceptance_tests/test_ac7_untouched_files.py` (через `_pult.changed_paths()`).
- `_launch_observation`/`_observation_fresh` закрытые — в долгоживущем файле их брать нельзя; AC-4 гоняется через CLI `run <id> --observation <ID>` (Popen подменён), AC-5 — через поле `fresh` у `observe show <id> --json` (оно и есть `_observation_fresh`).
- Образец CLI-песочницы: `tests/test_01m4fz6qyppkyqzfex14qh8xt6_launch.py`.
- На текущем коде красны AC-1..AC-5 по правильным причинам (нет функций; три копии разбора; ValueError на ""; счётчик now = 0). AC-6 на текущем коде зелен (ветка pid is None уже на watch.datetime) — держит поведение.
- Стаб (observation_age/observation_link_fresh в watch, вызовы в artel) — всё зелёное, включая соседние тесты наблюдения; стаб откатан.

## Не сработало
- (пусто)

## Где остановился
- Готово: plank-run зелёный (AC-7), preflight — все проверки пройдены.

## Чего не хватило
- Ничего существенного.
