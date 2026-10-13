# Записка spec_auditor — 01M4TVBT9ZCRQDY669QV3S95MA

## Выяснено
- Факты SPEC о коде подтверждены (reference_cache.py:38/43/94/144/192, targets.py:67/166, store.py:1136, artel.py:1857, projects.py:40/63, config.py:983/992); brief.py формулы — :775 и :780 (SPEC/ТЗ пишут ~781-783 — там текст сообщения).
- Главная находка: форма входа `get_reference_for_target(conn, target, *, reason, sha)` без task_id, а журнал BUILT/FAILED пишется `store.journal(conn, task_id, …)` (reference_cache.py:160,178), тесты ищут его по задаче (`tests/test_01m4s24963r9h18an2xdp6r15b_cache.py:245-247`); путь `unverified` (reference_cache.py:129-135) требует task_id для головы ветки.
- FAILED_ACTION при поводе reference с task_id=None уйдёт на DEFAULT_TARGET (store.py:1163-1164 + task_target :701-707) — SPEC закрепляет target только у BUILT_ACTION (AC-14).
- Размер в сводке: бриф меряет байты UTF-8 всего текста кэша (brief.py:773); SPEC базу размера не фиксирует.
- `reference` без БД: store.db() (store.py:331) заводит БД молча; SPEC молчит (для target-init — оговорено).
- artel в targets.yaml несёт core_reference (targets.yaml:53) — существующие тесты target-init на DEFAULT_TARGET начнут собирать справочник.
- yamlmini.scalar отдаёт int/bool (yamlmini.py:42-63) — проверка min_uses реализуема.

## Где остановился
SPEC-AUDIT.md заполнен, verdict concerns, guard прогнан.

## Чего не хватило
Быстрого способа увидеть, кто зовёт store.journal по task_id в тестах справочника — искал grep'ом по task_steps.
