# Записка spec_auditor — 01M545EB0A9F191WTDSPCH36GA

## Выяснено
- brief.skills_text (orchestrator/brief.py:519-550) читает скилы роли с ГОЛОВЫ main (`gitcmd.show(config.MAIN_BRANCH, …)`), не с диска; SPEC/ТЗ для проектных скилов называют диск `config.ROOT/skills/<имя>.md` — источник текста проектного скила в SPEC не назван.
- Единственный вызов skills_text — runner.py:476; argv шага — runner.py:1550 `provider.command(model_id, docs_dir=…)`; role_env (runner.py:964) не получает conn/target.
- ALLOWED_TOOLS — только claude.py:45/165; тест-хвост argv артели — tests/test_providers.py:55-61; test_review_package.py:1302 — на DEFAULT_TARGET (артель), не краснеет.
- Строка миссий: role_prompt.py:238, :314, knowledge_cards.py:953 — подтверждено.
- Вердикт: concerns (AC-4 без точного равенства списка; нет AC на отдельный вызов проверки имени; источник текста скила; fail-open дефолт проекта).

## Не сработало
- Bash с `cd`/переменными/пайпами просит подтверждения — пользоваться Read/Grep и полными путями.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Где читается текст скилов (main vs диск) — искал в brief.py.
