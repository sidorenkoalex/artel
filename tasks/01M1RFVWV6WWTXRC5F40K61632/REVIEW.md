---
task: 01M1RFVWV6WWTXRC5F40K61632
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 4
---

# REVIEW: Наблюдатель роста карты кодовой базы (часть а): история, самокалибрующийся порог, атрибуция

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`map_stats`, AC-1..AC-4) | OK | Без изменений с итерации 1 — чистая функция подтверждена юнитом `test_is_pure_no_disk_or_subprocess`; поля и сериализация верны. |
| 2 (запись журнала на мерже, AC-5..AC-7) | OK | Без изменений с итерации 1 — `_journal_map_size` на обеих успешных ветках `_regenerate_and_commit_map`, ни на одной ветке `_map_regen_incident`. |
| 3 (`check_map_growth`, AC-8..AC-16, константы AC-18) | OK | R1-F2 закрыт: условие изменено на `len(series) <= k` (`orchestrator/doctor.py:1671`), окно `series[:k]` больше не пересекается с оцениваемой записью ни при какой длине ряда — база сравнения перестала быть самоссылочной. Подтверждено новым юнитом `test_exact_calibration_length_is_still_silent` (`tests/test_doctor.py:2047`) и ручным прогоном сценария из итерации 1 (см. «Проверено исполнением») — алерт на k-й записи больше не заводится. |
| 4 (внешний target) | OK | Без изменений с итерации 1. |
| 5 (тесты, AC-17/AC-18) | OK | R1-F1 закрыт: все 14 ранее безымянных методов (`tests/test_codebase_map.py`, `tests/test_doctor.py`, `tests/test_fsm_map_regen.py`) получили докстринг с заявкой «Ловит мутацию: …», описывающей сценарий и наблюдаемое свойство, не пересказывающей имя метода — сверил каждый текстом диффа. R1-F3 закрыт: пустые строки PEP8 добавлены во всех трёх местах (`scripts/codebase_map.py:192-195`, `tests/test_codebase_map.py`, `tests/test_doctor.py`). Планка AC-17 зелёная (см. ниже), существующие ассерты не тронуты (сверено диффом `tests/`). |

## Замечания

(нет — оба замечания итерации 1 закрыты, новых не найдено)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_codebase_map.py; tests/test_doctor.py; tests/test_fsm_map_regen.py | 14 новых тестовых методов без докстринга и без заявки «Ловит мутацию: …» | нарушение конвенции `skills/test-authoring.md` | Проверено: все 14 методов несут докстринг с конкретным сценарием мутации и наблюдаемым свойством (не пересказ имени) — принято. |
| R1-F2 | accepted | orchestrator/doctor.py:1671 | на границе ровно `k` записей окно включает саму оцениваемую последнюю запись — самоссылочная база сравнения | возможен неожиданный алерт ровно в момент завершения калибровки | Проверено: `len(series) <= k` устраняет пересечение окна `series[:k]` с оцениваемой записью при любой длине ряда; новый юнит воспроизводит сценарий итерации 1 и подтверждает молчание — принято. |
| R1-F3 | accepted | scripts/codebase_map.py:192-193; tests/test_codebase_map.py:178-179; tests/test_doctor.py:2106-2107 | не хватает пустой строки (PEP8) между новым кодом и следующим определением | стиль | Проверено: пустые строки добавлены во всех трёх местах — принято. |

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tests/test_codebase_map.py tests/test_doctor.py tests/test_fsm_map_regen.py -q` — 153 passed, 3 subtests passed (в т.ч. вся планка AC-17 без правки существующих ассертов).
- `python3 -m pytest tasks/01M1RFVWV6WWTXRC5F40K61632/acceptance_tests/ -q` — 32 passed.
- `git diff main...task/01m1rfvwv6wwtxrc5f40k61632-nablyudatel-rosta-karty-kodovo -- tests/` — просмотрен целиком: удалённых/изменённых существующих ассертов и методов нет, только добавления (докстринги + новые тестовые методы/классы).
- `git diff main...task/01m1rfvwv6wwtxrc5f40k61632-nablyudatel-rosta-karty-kodovo` (трёхточечный, от merge-base с main) — вклад задачи ограничен зонами SPEC (`scripts/codebase_map.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/doctor.py`, `orchestrator/config.py`, `tests/`, `docs/codebase-map.md`); изменения `orchestrator/config.py` вне задачи (`PROGRAM_STOP_LOSS_USD`, `MAX_PARALLEL_TASKS`) — это коммиты Оператора на main, попавшие в ветку через «подтяжку main» (commits d2d2c60e, 09a183d7 уже на main), а не работа этой задачи; трёхточечный дифф подтверждает, что вклад задачи в `config.py` — ровно три новые константы (`MAP_GROWTH_CALIBRATION_MERGES`, `MAP_GROWTH_RATIO`, `MAP_JUMP_RATIO`).
- `python3 scripts/codebase_map.py` на HEAD ветки — диффнулась только строка `built_at_sha` (карта регенерирована задачей до подтяжки main, содержимое неизменно); изменение отменено (`python3 -c "import os; os.remove(...)"` + `git checkout -- docs/codebase-map.md`) перед сдачей ревью.
- Инкрементальный diff ревью-пакета (dfa62d0e..HEAD) состоял только из «подтяжки main» (ADR-0014, стоп-лосс, MAX_PARALLEL_TASKS) — сверен git log ветки и артефактной ветки (`git log --oneline` обеих), фактический фикс замечаний итерации 1 — коммит dfa62d0e, проверен отдельно построчно (`git show dfa62d0e`).

## Предложения системе
(пусто)
