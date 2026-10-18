# Записка spec_auditor — 01M58FNWBV25FF26E7AZ9Q9912 (аудит SPEC a4898611, третий визит)

## Выяснено
- Ссылки SPEC на код верны (мелочь: `targets.load` — targets.py:100). Решения гейта №1 отражены все.
- `profile_of` — единственный читатель `test_profile` (grep по orchestrator/, scripts/).
- `plank_run.py:220` достижим в `tests_writing`: `decide` смотрится только в `_long_lived_arg` (:87, `.profile`), `runner.py:1323-1333` шаг не блокирует → трассировка `TargetsError` на записи с двумя компонентами.
- `suite_run._run`: `_profile_command` (:556) до `full_suite_limit` (:559) — безопасно.
- AC-2 не покрывает форму `depends_on.paths`, кавычки в `paths`; AC-9 — ширину перехвата `drop_from_code_copy`.

## Не сработало
- `cd …; sed` и `$W` в составных командах требуют подтверждения — бери абсолютные пути и Read.

## Где остановился
SPEC-AUDIT.md записан, verdict concerns (4 отклонения + мелочь), guard ок.

## Чего не хватило
Карты «какие команды роли доступны в каком состоянии» — достижимость `plank-run` выводил по runner.py и plank_run.py.
