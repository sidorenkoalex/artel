---
task: 01M5M6YQR587QNPCTG3T93TZ9J
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/config.py, tests/
budget_usd: 25
---

# SPEC: Справочник ядра в брифе — только developer и test_author, предел 16 КиБ

## Контекст
Ревизия кода 22.10 (находка CR-2026-10-22-11) показала, что промпт
test_author вырос с 39 до 95 КиБ. Из этого прироста справочник ядра в
брифе занимает в среднем 25,8 КиБ (у developer — 25,7 КиБ). 23.10
Оператор принял вариант А: справочник ядра получают только developer и
test_author, предел снижается с 32 768 до 16 384 байт. По ролям код уже
раздаёт справочник так: `brief._core_reference_part` зовут только
`brief.developer_brief` и `brief.test_author_answer_component`. Значит,
задача меняет предел `orchestrator/config.py:1007` и закрепляет состав
по ролям тестом на уровне промпта роли. `targets.yaml` Оператор уже
поправил (`core_reference.min_uses: 13`, коммит c35e9a86): справочник
артели — 14 725 байт, это ниже нового предела.

## Требования
1. `config.CORE_REFERENCE_MAX_BYTES = 16_384`. Комментарий над
   константой называет решение Оператора 23.10 (находка
   CR-2026-10-22-11) и прежнее значение 32 768. Формулы предела и
   предупреждения (`size > limit`, `size * 10 > limit * 9`), тексты
   алертов и строки пропуска не меняются.
2. Состав по ролям не меняется: справочник ядра получают только
   developer и test_author, каждый в своём брифе.
3. Свойства критериев ниже держат тесты в `tests/`. Тесты
   детерминированные и без сети: песочница и подмена
   `reference_cache.get_reference` по образцу `ReferenceBriefSandbox`
   из `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`.
   Тесты ловят мутации: предел оставлен 32 768 или задан литералом мимо
   `config`; справочник добавлен в бриф ещё одной роли; формула 90 %
   изменена.

## Критерии приёмки
AC-1. Предел по умолчанию, без подмены `config.CORE_REFERENCE_MAX_BYTES`.
Справочник ровно 16 384 байта UTF-8 включается и в бриф developer
(`brief.developer_brief`), и в добавку test_author
(`brief.test_author_answer_component`). Справочник 16 385 байт не
включается: вместо него стоит строка «не включён» и поднимается алерт
`brief.core_reference_oversized`. Справочник 20 000 байт (между новым и
прежним пределом) не включается; на коде до правки он включается.

AC-2. Предупреждение 90 % при пределе по умолчанию. Справочник 15 000
байт (больше 90 % от 16 384) включается и поднимает предупреждение
`brief.core_reference_near_limit`. Справочник 14 000 байт включается без
этого предупреждения.

AC-3. Состав промпта по ролям. Для каждой из пяти ролей (analyst,
spec_auditor, test_author, developer, reviewer) собирается
`role_prompt.mission_brief_package` при справочнике 10 000 байт с
уникальной меткой. В брифе developer и test_author метка встречается
ровно один раз. В миссии, брифе и пакете analyst, spec_auditor и
reviewer её нет.

AC-4. Размер куска справочника. В собранном брифе developer и
test_author кусок справочника (от метки компонента
`brief.CORE_REFERENCE_LABEL` до конца компонента) не больше
`config.CORE_REFERENCE_MAX_BYTES` байт UTF-8 плюс обрамление компонента.

AC-5. Сводка `reference` (`projects.reference_summary`) при размере
справочника 20 000 байт печатает «предел 16384 байт» и «больше предела —
в бриф не попадёт».

## Оценка объёма и деление
Прогноз диффа: 12 КиБ

Сработал сигнал числа затрагиваемых модулей и файлов. Его дают пути
только для чтения, перечисленные в «Не входит». На запись задача
трогает две зоны: одну константу с комментарием в
`orchestrator/config.py` и новый тестовый файл в `tests/`.

Обоснование монолита: делить нечего. Правка предела — одна строка с
комментарием. Тесты AC-1, AC-2 и AC-5 проверяют именно новое значение,
поэтому без правки предела они красные, а правка без них ничем не
закреплена. Каждая часть по отдельности оставила бы систему либо с
красным `tests/`, либо с незакреплённым пределом.

## Не входит
- Правка `orchestrator/config.py` сверх `CORE_REFERENCE_MAX_BYTES` и
  комментария над ним.
- Правка `targets.yaml`: это защищённый путь, Оператор её уже сделал.
- Правка кода, который только читается: `orchestrator/brief.py`,
  `orchestrator/projects.py`, `orchestrator/reference_cache.py`,
  `orchestrator/role_prompt.py`, `orchestrator/review.py`,
  `orchestrator/runner.py`, `orchestrator/context_package.py`,
  `orchestrator/store.py`, `orchestrator/advance_gates/capacity.py`,
  `orchestrator/targets.py`, `orchestrator/fsm_merge_gate.py`,
  `orchestrator/alerts.py`, `scripts/core_reference.py`, файл кэша
  `.artel/projects/artel/knowledge/derived/core-reference.md`,
  `docs/backlog.md`.
- Отбор справочника по обращениям ролей (метрика `explore-stats`).
- Сокращение скилов `skills/test-authoring.md` и
  `skills/spec-authoring.md`.
- Отдельная настройка предела справочника для внешних проектов.
- Правка существующих тестов: они не меняются. Что они остаются
  зелёными, проверяет полный набор `tests/` — её держит пульт.

## Материалы
- `docs/audits/code-revision-2026-10-22.md` (копия ревизии), находка
  CR-2026-10-22-11.
- `orchestrator/config.py:1004`–`1007` — предел и комментарий.
- `brief._core_reference_part` — применение предела в брифе;
  `orchestrator/projects.py:96`/`112` — `reference_summary`.
- `tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py`
  (`ReferenceBriefSandbox`, `LimitTest`,
  `OtherRolesTest::test_ac3_reviewer_analyst_and_spec_auditor_get_no_reference`),
  `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py` — существующие
  тесты берут предел из `config` и подменяют его, литерала 32768 в
  утверждениях нет.
