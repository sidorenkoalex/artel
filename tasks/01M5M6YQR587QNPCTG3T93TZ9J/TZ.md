---
task: 01M5M6YQR587QNPCTG3T93TZ9J
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Справочник ядра в брифе: только developer и test_author, предел 16 КиБ

# Справочник ядра в брифе: только developer и test_author, предел 16 КиБ

## Факты

Находка ревизии кода 22.10 CR-2026-10-22-11 (отчёт `docs/audits/code-revision-2026-10-22.md` копии ревизии): прирост промпта test_author 39 → 95 КиБ, из них справочник ядра в брифе — в среднем 25,8 КиБ в 72 из 75 промптов; developer — 25,7 КиБ. Решение Оператора 23.10 — вариант А: справочник ядра в брифе получают только developer и test_author, предел — 16 КиБ (было 32). Ссылки сверены с `origin/main` 97c3f5f9; `orchestrator/config.py`, `orchestrator/projects.py` и `orchestrator/brief.py` между HEAD главной копии (пин 89732e3e) и `origin/main` не менялись, `orchestrator/brief.py` сдвинут после строки 626 — на него ссылки по именам функций.

- Предел — `orchestrator/config.py:1007` (`CORE_REFERENCE_MAX_BYTES = 32_768`), байты UTF-8 текста кэша; комментарий над ним — `orchestrator/config.py:1004`–`1006`.
- Предел применяют два места: `brief._core_reference_part` (справочник крупнее предела заменяется строкой «справочник ядра: N байт > предел — не включён…» и алертом `brief.core_reference_oversized`; больше 90 % предела — предупреждение `brief.core_reference_near_limit`) и `orchestrator/projects.py:96` (`reference_summary`, сводка команды `reference`; предел читается в `orchestrator/projects.py:112`).
- `brief._core_reference_part` зовут только `brief.developer_brief` и `brief.test_author_answer_component`; бриф analyst (`brief.analyst_map_component`), бриф spec_auditor (`brief.spec_auditor_brief`) и ревью-пакет (`review.review_package`) справочника не несут. Это закреплено тестом `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py::OtherRolesTest::test_ac3_reviewer_analyst_and_spec_auditor_get_no_reference`. Значит, состав по ролям уже соответствует решению — задача закрепляет его тестом уровня промпта роли и меняет предел.
- Существующие тесты предела берут значение из `config.CORE_REFERENCE_MAX_BYTES` и подменяют его (`tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py::LimitTest`, `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`), литерала 32768 в них нет.
- Размер справочника артели сейчас: файл кэша `.artel/projects/artel/knowledge/derived/core-reference.md` — 28 333 байта (23.10). Генератор `scripts/core_reference.py` на дереве `origin/main` 71ce9904 с настройкой `core_reference` артели из `targets.yaml` даёт по порогу `min_uses`: 4 (текущее значение) — 28 320 байт; 5 — 24 473; 8 — 18 478; 10 — 16 637; 11 — 15 414; 13 — 14 725; 15 — 13 397. Предупреждение 90 % при пределе 16 384 — от 14 746 байт.
- Решение Оператора 23.10 (вариант А) исполнено: `targets.yaml` в `origin/main` — `core_reference.min_uses: 13` (коммит Оператора c35e9a86); генератор на дереве `origin/main` 97c3f5f9 даёт 14 725 байт — ниже нового предела 16 384 и ниже порога предупреждения 90 % (14 746). С прежним `min_uses: 4` (28 320 байт) справочник артели при новом пределе в бриф не попадал бы.

## Требуется

1. `config.CORE_REFERENCE_MAX_BYTES = 16_384`; комментарий над константой называет решение Оператора 23.10 (находка CR-2026-10-22-11) и прежнее значение 32 768. Формулы предела и предупреждения (`size > limit`, `size * 10 > limit * 9`), тексты алертов и строки пропуска не меняются.
2. Состав по ролям не меняется: справочник ядра — только в брифе developer и test_author.
3. Тесты, детерминированные, без сети (песочница и подмена `reference_cache.get_reference` — по образцу `ReferenceBriefSandbox` из `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`):
   - значение по умолчанию без подмены: справочник ровно 16 384 байта включается в бриф developer и в добавку test_author; 16 385 байт — нет (строка «не включён», алерт `brief.core_reference_oversized`); справочник 20 000 байт (между новым и прежним пределом) — не включён (на текущем коде — красный: включён);
   - справочник 15 000 байт (больше 90 % от 16 384) — включён и поднимает предупреждение `brief.core_reference_near_limit`; 14 000 байт — без предупреждения;
   - состав промпта ролей: для каждой из пяти ролей (analyst, spec_auditor, test_author, developer, reviewer) собрать `role_prompt.mission_brief_package` при справочнике 10 000 байт с уникальной меткой — метка есть ровно один раз в брифе developer и test_author и отсутствует в миссии, брифе и пакете analyst, spec_auditor, reviewer;
   - размер: в собранном брифе developer и test_author кусок справочника (от метки компонента `brief.CORE_REFERENCE_LABEL` до конца компонента) не больше `config.CORE_REFERENCE_MAX_BYTES` байт UTF-8 плюс обрамление компонента;
   - сводка `reference` (`projects.reference_summary`) при размере 20 000 байт печатает «предел 16384 байт» и «больше предела — в бриф не попадёт».
   Ловит мутацию: предел оставлен 32 768 или задан литералом мимо `config`; справочник добавлен в бриф ещё одной роли; формула 90 % изменена. Существующие тесты не правятся и остаются зелёными.

Зоны: orchestrator/config.py, tests/

Ограничение зон по смыслу: в `orchestrator/config.py` — только `CORE_REFERENCE_MAX_BYTES` и комментарий над ним.

Только чтение: .artel/projects/artel/knowledge/derived/core-reference.md, orchestrator/brief.py, orchestrator/context_package.py, orchestrator/store.py, orchestrator/advance_gates/capacity.py, orchestrator/targets.py (вызывающие подменяемых в тесте функций — не меняются), orchestrator/projects.py, orchestrator/reference_cache.py, orchestrator/role_prompt.py, orchestrator/review.py, orchestrator/runner.py, orchestrator/fsm_merge_gate.py, orchestrator/alerts.py, scripts/core_reference.py, targets.yaml, docs/backlog.md.


Не входит: правка `targets.yaml` (защищённый путь, уже сделана Оператором); отбор справочника по обращениям ролей (метрика `explore-stats`); сокращение скилов `skills/test-authoring.md` и `skills/spec-authoring.md`; предел справочника внешних проектов отдельной настройкой.

Бюджет: $25.
