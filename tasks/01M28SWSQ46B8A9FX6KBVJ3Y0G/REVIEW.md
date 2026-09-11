---
task: 01M28SWSQ46B8A9FX6KBVJ3Y0G
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: `amend-tests` гоняет трассируемость AC перед сдвигом лока планки

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`_cmd_amend_tests`: трассируемость после «изменения только в acceptance_tests/» и до коммита/сдвига лока) | OK | `orchestrator/amend.py:311-320` — `guard.acceptance_traceability_errors(tdir)` вызывается после проверки `outside` (amend.py:293-309) и до `acceptance.run` (amend.py:322); материализация `SPEC.md` (`_materialize_spec_if_missing`) выполняется ПОСЛЕ проверки «только в acceptance_tests/», как и требует PLAN, и убирается в `finally`. Подтверждено прогоном AC-1/AC-2/AC-5. |
| 2 (`_cmd_amend_tests_from_branch`: та же проверка по содержимому головы ветки) | OK | `orchestrator/amend.py:444-452` — `_branch_traceability_errors` читает SPEC.md и `acceptance_tests/` головы ветки git'ом (`gitcmd.show`/уже вычисленный `new_snapshot`), без обращения к диску worktree; тем же ядром `guard.scan_ac_content`/`guard.traceability_errors_from_content`, что и путь 1. Подтверждено прогоном AC-3/AC-8. |
| 3 (существующие проверки не ослаблены; порядок — сначала трассируемость, потом прогон) | OK | `acceptance.run`, `guard.scan_redness_markers`, сверка snapshot против артефактной ветки — ни один вызов не убран и не переставлен; трассируемость встала строго между «изменения только там» и прогоном в обоих путях. Порядок дополнительно проверен приёмочным AC-4 (мок `acceptance.run` не вызывается ни разу на сломанной трассируемости). |
| 4 (тесты покрывают а/б/в/г/д) | OK | (а)/(в) — AC-1/AC-5/AC-7; (б) — AC-6 (индентация — зависимость 01M28NX43E уже смержена в main, тест зелёный не по «риску» из PLAN, а по факту); (г) — AC-3/AC-8; (д) — `tests/test_amend.py` прогнан целиком, 34/34 зелёных, диффом подтверждено: ни один существующий ассерт не тронут (только добавления). См. минорное замечание ниже про докстринги трёх НОВЫХ unit-тестов. |

## Замечания

- minor — `tests/test_amend.py:218`, `tests/test_amend.py:224`, `tests/test_amend.py:408` — три новых тестовых метода (`test_valid_coverage_returns_no_errors`, `test_missing_criterion_test_names_it`, `test_creates_file_from_artifact_branch_and_returns_its_path`) без докстринга вовсе — нарушение skills/test-authoring.md («у каждого тестового метода — докстринг со сценарием и заявкой `Ловит мутацию: …`») и разрыв с собственной практикой этого же файла (все остальные ~30 методов диффа и файла такую заявку несут). Тесты сами по себе корректны и проверяют реальное поведение (позитивный путь покрытия и именование недостающего критерия) — не блокирует мерж, но стоит дописать докстринги со сценарием и мутацией, которую метод ловит, в следующей правке файла.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_amend.py:218, 224, 408 | 3 новых unit-теста без докстринга/заявки «Ловит мутацию» (skills/test-authoring.md) | нарушает конвенцию читаемости/трассируемости тестов, принятую в этом же файле; сами тесты работоспособны | минорно — ревьювер аппрувит без блокировки; допиши докстринги в следующей правке файла |

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tests/test_amend.py -q` — 34 passed (весь файл, включая новые `BranchTraceabilityErrorsTest`/`MaterializeSpecIfMissingTest`).
- `git checkout artifact/01m28swsq46b8a9fx6kbvj3y0g -- tasks/01M28SWSQ46B8A9FX6KBVJ3Y0G` (материализация SPEC.md/PLAN.md/acceptance_tests/ с артефактной ветки на диск worktree, т.к. на диске их не было) + `python3 -m unittest discover -s tasks/01M28SWSQ46B8A9FX6KBVJ3Y0G/acceptance_tests -v` — 9/9 приёмочных тестов (AC-1..AC-8, включая AC-6 «отступ маркера», чья зависимость 01M28NX43E уже в main) зелёные; после прогона правка снята из индекса (`git reset`), рабочее дерево возвращено к исходному untracked-состоянию `tasks/01M28SWSQ46B8A9FX6KBVJ3Y0G/`.
- `python3 scripts/codebase_map.py --check` — без вывода/расхождений (карта перегенерирована тем же коммитом, добавлен `orchestrator/yamlmini.py` в «Импортирует» `amend.py` и `orchestrator/amend.py` в «Импортируется» `yamlmini.py`; `built_at_sha`-строка не расхождение по правилу скила).
- Ручная сверка diff `tests/test_amend.py` (`git diff 3ad307a5f...HEAD -- tests/test_amend.py | grep '^-'`) — только заголовок файла, удалений строк нет: существующие ассерты не ослаблены (AC-9/требование 4д).
- Ручная сверка порядка проверок в `orchestrator/amend.py` (`_cmd_amend_tests`, `_cmd_amend_tests_from_branch`) построчным чтением — трассируемость встроена строго между существующими проверками, как того требует требование 3.
- CI коммита 6ee0c176 (из пакета ревью) — зелёный, 7 проверок.

## Предложения системе
