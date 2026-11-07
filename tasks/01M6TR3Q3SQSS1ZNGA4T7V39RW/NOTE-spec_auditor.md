# Записка spec_auditor — 01M6TR3Q3SQSS1ZNGA4T7V39RW (аудит, spec_sha 3bf9a772)

## Выяснено
- sha SPEC на диске = 3bf9a772eb218cc75e9b017e73875bdede55c243. Дифф к прошлой проверенной bd7b21ff — `git diff ca95d86e5 b4b8c269f -- tasks/<id>/SPEC.md` (ссылка refs/artifacts/<id>).
- Решения гейта №5.1–5.2 внесены: AC-14 (down -v от ребёнка по ppid раньше docker ps исполнителя), AC-26 и треб. 1/7/AC-20/матрица — `pytest-own` с командой-заглушкой, AC-3/AC-15 — добор pid по calls-файлу, AC-4 — вторая пара «прогон не прерван».
- Код: `_compose_call` — прямой Popen, start_new_session (acceptance.py:898-901) → ppid вызова docker = pid ребёнка; при BaseException группа вызова снимается и исключение пробрасывается (:919-922) → finally `_compose_teardown` (:1464-1467) kill + down -v. `pytest-own` — команда профиля как есть (acceptance.py:138) → заглушка ловится.
- suite-run берёт замок без ожидания (suite_run.py:298) — фон красной фазы AC-3/15 не висит до вызова заглушек.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns (мелкое: `plank-run --wait` без запроса не задан; строки матрицы для run_agent_once нет; ссылка AC-17), status ready.

## Чего не хватило
- Ничего существенного; дифф версий по артефактной ссылке и прошлый SPEC-AUDIT (git show e2e5dc17d:…) сэкономили время.
