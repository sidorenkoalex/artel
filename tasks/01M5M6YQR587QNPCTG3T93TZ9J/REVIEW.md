---
task: 01M5M6YQR587QNPCTG3T93TZ9J
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Справочник ядра в брифе — только developer и test_author, предел 16 КиБ

## Фаза A — план
- Таблица покрытия полна: требования 1–3 → шаг 1 и долгоживущий файл test_author.
- Шаг один, размер MR — одна константа, что соответствует SPEC («обоснование монолита»).
- Подход не конфликтует с архитектурой: `brief.py:1143` и `projects.py:112` читают
  `config.CORE_REFERENCE_MAX_BYTES`, литерала предела в `orchestrator/`/`scripts/` вне
  `config.py` нет (`grep -rn "32768\|32_768\|CORE_REFERENCE_MAX_BYTES" orchestrator scripts`).
- «Влияние на систему» = diff: тронут только `orchestrator/config.py` (+ карта, долгоживущий
  тест test_author). Откат — revert строки, описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `config.py:1007-1010`: `16_384`, комментарий называет решение Оператора 23.10, CR-2026-10-22-11 и прежнее 32 768. Формулы/тексты в `brief.py`/`projects.py` не тронуты (diff их не содержит). |
| 2 | OK | Код состава не менялся; держит AC-3 долгоживущего файла (зелёный). |
| 3 | OK | Долгоживущий `tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py`: песочница `LightTransitionSandbox`, подмена `reference_cache.get_reference`, без сети; мутация «предел 32 768» проверена исполнением — красный. |
| AC-1…AC-5 | OK | Все пять методов зелёные на ветке. |

## Замечания
Нет замечаний уровня blocker/major/minor.

Наблюдение (не замечание): утверждение `len(chunk) <= limit + len(framing)` в AC-4 почти
тождественно при `chunk = reference + framing`; содержательную работу в методе делают
проверка «всё прочее — обрамление» и счёт метки. Тест залочен, правка — только `amend-tests`;
на вердикт не влияет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5m6yqr587qnpctg3t93tz9j_core_reference_limit.py tests/test_01m4s24ebvb72b8wyj3jy96y0e_brief_reference.py tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py` — 32 passed, 109 subtests passed.
- Временная мутация «предел оставлен 32 768» (подмена `config.CORE_REFERENCE_MAX_BYTES = 32768` в процессе, `unittest` по модулю долгоживущего файла; код на диске не менялся) — FAILED (failures=7): AC-1, AC-2 (15000 у обеих ролей), AC-5 (все 4 подслучая). Заявка «Ловит мутацию» AC-1/AC-2/AC-5 подтверждена.
- `artel.py plank-run 01M5M6YQR587QNPCTG3T93TZ9J` — отказ «планки нет» (в refs/artifacts нет `test_*.py`): у задачи только долгоживущий файл в `tests/`, разовой планки нет.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md | grep -v built_at_sha` — расхождений по содержимому нет, карта свежа; рабочая копия возвращена `git checkout`.
- CI коммита ac00356a зелёный (из пакета).

## Предложения системе
- Приём «временная мутация» правкой файла (`sed -i` по `orchestrator/`) в шаге ревьювера упирается в запрос подтверждения; для констант модуля работает подмена атрибута в процессе (`python3 -c "...; config.X = ...; unittest..."`) — стоит назвать этот приём в `skills/review-checklist.md`.
