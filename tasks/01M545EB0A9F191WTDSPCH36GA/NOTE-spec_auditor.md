# Записка spec_auditor — 01M545EB0A9F191WTDSPCH36GA (визит 3, spec_sha 7182268f)

## Выяснено
- Оба решения Оператора на гейте SPEC (№1 пп.1–6, №2 пп.1–2) внесены; факты SPEC о коде подтвердились.
- В-1: треб. 9/AC-8 «targets.yaml не читается» не ограничены внешним проектом; repo_context.py:82-89 + tests/test_repo_context.py:29 — артель разрешается без targets.yaml (SPEC 01M484RNV3QBDY3B0M16J916ZP). Буквально — артель не починит сломанный targets.yaml.
- В-2: AC-7 не называет точку вызова проверки project_skills (модуль/имя/форма исхода).
- В-3: runner.py:366 `t["target"] or DEFAULT_TARGET` — второй fail-open источник на пути шага, в SPEC не назван (tasks.target NOT NULL, schema.py:47).
- Запреты role-home settings.json:9-10 в относительной форме; подкоманды держит artel.py:1877-1906 — не ослабление.
- Вердикт concerns, status ready, guard ок.

## Не сработало
- `cd ... && cmd`, пайпы, `$D` в cd-команде просят подтверждения — только абсолютные пути, одна команда.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Где на пути шага берётся target брифа/предполёта: runner.py:366 в _refuse_before_start, не store.task_target.
