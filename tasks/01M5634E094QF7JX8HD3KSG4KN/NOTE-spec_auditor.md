# Записка spec_auditor

## Выяснено
- Факты SPEC о brief.py/role_prompt.py по строкам подтверждаются (карта :382-416, алерт размера :778-803, developer :871-942, spec_auditor :961-1002, analyst :1261-1300, test_author :1303-1324; миссия developer role_prompt.py:95-97).
- Вердикт concerns, SPEC-AUDIT.md status ready, guard ок. Главное: не задан ref базы проекта и исход сбоя чтения конвенций (нет клона/ветки/git) — vs существующие шаги внешнего проекта в tests/test_multitarget_invariants.py:375-397 и tests/test_01m545eb…_project_role_step.py:199-224.
- Миссии analyst (:42-43) и spec_auditor (:240-242) у внешнего проекта будут говорить про карту в брифе; SPEC про spec_auditor молчит.
- AC-6/AC-7 только на developer; пометка об отсутствии AGENTS.md не проверяется.

## Не сработало
- bash с `cd`+`;`/переменной в составной команде отказан; `cd X && grep` работает.

## Где остановился
- Аудит сдан.

## Чего не хватило
- Как читать базовую ветку внешнего проекта — прецедент нашёлся в reference_cache.branch_commit (:293-309, локальная refs/heads без fetch).
