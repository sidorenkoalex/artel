# Записка spec_auditor

## Выяснено
- Визит 4 (spec_sha 42c154f4…): решения гейта №3 перенесены — запрет литералов/`targets.FORGES` в любом узле ast `ci.py` и мутации AC-21, `(None, причина)` «краснота без упавшего задания» (таблица п.8, AC-16), два конвейера в AC-32.
- Строки ci.py/targets.py/gitcmd.py/github_adapter.py/test_invariants.py из SPEC сходятся с HEAD 5705cfdf8; в ci.py сейчас нет литералов "github"/"gitlab".
- Наблюдение без отклонения: ci получает `repo`, а не имя проекта; имя для forge — через `ci._project_context` (:135-157).

## Не сработало
- Команды bash с `$VAR` отклоняет песочница (simple_expansion) — писать пути целиком.

## Где остановился
- SPEC-AUDIT.md: status ready, verdict pass; guard ок.

## Чего не хватило
- Ничего существенного.
