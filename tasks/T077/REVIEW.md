---
task: T077
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: Guard называет точную причину отказа

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Каждое правило из списка (RULES-секции/статусы, `schema_version`, обязательные frontmatter-поля, поле `task`, AC-разметка, трассируемость AC↔тест, маркер красноты) прогнано по фактуре «мог бы агент починить по одному тексту» — все восемь категорий переписаны (`scripts/guard.py`, diff `schema_errors`/`check_content`/`spec_ac_errors`/`traceability_errors_from_content`/`redness_marker_errors_from_files`). |
| 2 | OK | Переписанные тексты называют форму целиком: same-line-после-двоеточия для маркера красноты, уровень H2 для секций, точный формат `AC-<номер>.` для разметки и т.д. — проверено вручную (см. «Проверено исполнением») и сверено с exact-match тестами в `tests/test_guard_schema.py`. |
| 3 | OK | Каждое переписанное сообщение содержит глагол действия («замени», «добавь», «впиши», «переименуй», «убери», …) — по образцу `review_evidence_errors`. |
| 4 | OK | `tests/test_guard_schema.py` пополнен exact-match тестами почти на каждую переписанную строку; ни один существующий тестовый метод не удалён (diff файла — чисто additive, `+256/-0`; подтверждено также приёмочным `test_ac5_existing_tests_not_deleted.py`, сравнивающим имена тестовых методов на merge-base). |
| 5 | OK | Для каждого переписанного сообщения есть тест с точным текстом (`SchemaErrorsMessageTest`, `MissingFrontmatterBlockMessageTest`, `MissingSectionMessageTest`, `SectionWrongLevelMessageTest`, `SpecAcMarkupMessagesTest`, `TraceabilityMessagesTest`, `RednessMarkerMessageTest` и др.). Для маркера красноты SPEC допускает единое сообщение на случаи «отсутствует»/«пусто» (AC-1 не требует различения текста, в отличие от `review_evidence_errors`) — оба случая явно протестированы отдельными тестами в `test_ac1_redness_marker_same_line.py`. |

AC-1..AC-6 — проверены напрямую (см. «Проверено исполнением»): AC-1 и AC-2 — целевые приёмочные тесты плюс ручной прогон `check_content`/`redness_marker_errors_from_files`; AC-3/AC-4 — приёмочные тесты сознательно сужены на две конкретные, проверяемые по коду категории (эскалируемая пометка `escalate` и формат `AC-n` в «оставшемся пункте») с явным обоснованием в докстринге, почему буквальный текст остальных категорий не тестируется угадыванием — остальное покрыто exact-match тестами `test_guard_schema.py`; AC-5 — приёмочный тест на diff тестовых методов к main, зелёный; AC-6 — полный набор `tests/` зелёный (987 тестов).

## Замечания

- minor — `tasks/T077/PLAN.md` (Шаги, шаг 1) — план заявляет синхронную правку `tests/test_acceptance_tests_flow.py`, `tests/test_analyst_role.py`, `tests/test_invariants.py`, `tests/test_yaml_parsing.py` «под новые тексты», но фактический diff эти четыре файла не касается. Проверено: `grep` по старым подстрокам изменённых сообщений в этих файлах не даёт совпадений с переписанными текстами (единственное совпадение — «недопустимый status» в `tests/test_acceptance_tests_flow.py:597` и `tasks/T064/acceptance_tests/test_ac4_existing_checks_not_weakened.py:147` — подстрока сохранена в новом тексте, тест зелёный), сами эти файлы проверяют только факт наличия ошибки (`len(errors) > 0`), а не точный текст. Правка действительно не требовалась — расхождение плана с фактом не привело к дефекту, но стоит поправить формулировку шага при следующей итерации плана.

## Вердикт
approved

## Проверено исполнением
- `python3 -m unittest discover -s tests` — 987 тестов, все зелёные (без учёта посторонних `ResourceWarning` про sqlite и служебного вывода `artel.py` в конце прогона — не относится к тестам).
- `python3 -m unittest discover -s tasks/T077/acceptance_tests -v` — 8 тестов (AC-1..AC-5; AC-6 — файл-заглушка со `skip`-пометкой, см. её обоснование), все зелёные.
- `python3 scripts/guard.py --all` — «GUARD: ок (252 файлов)»: новая логика различения уровня заголовка секции не даёт ложных срабатываний ни на одном существующем артефакте репозитория.
- `python3 -m unittest discover -s tasks/T072/acceptance_tests -v` — 5 тестов, все зелёные (T072 использован как образец «причина + действие», проверено, что T077 его не задел).
- `python3 -m unittest discover -s tasks/T064/acceptance_tests -v` — 8/9 зелёных, 1 падение (`test_ac3_review_transition_not_blocked_by_missing_marker`). То же падение воспроизведено на `main` (78d41ae) тем же прогоном в соседнем чистом воркчасти `/Users/al.sidorenko/projects/artel` — предсуществующий сбой, не связанный с T077 (проверено сравнением, не предположением).
- `python3 scripts/codebase_map.py` (регенерация) — расхождение с закоммиченным `docs/codebase-map.md` только в строке `built_at_sha` (29a57fc, коммит правки, вместо текущего HEAD 902dcf6, коммит «подтяжка main» без .py-изменений); содержимое карты (без строки `built_at_sha`) побайтово совпадает — по контракту `.github/workflows/ci.yml:75-81` («карта свежа: содержимое совпадает, отличается только built_at_sha») это не сбой свежести. Рабочее дерево после проверки возвращено в исходное состояние (`git checkout -- docs/codebase-map.md`), `git status --short` — пусто.
- Ручной прогон `guard.check_content` на артефакте с `### Критерии приёмки` (H3 вместо H2) — сообщение называет и текущий уровень (H3), и требуемый (H2), и действие («переименуй заголовок в '## Критерии приёмки'») — see AC-2.
- Точечное чтение `scripts/guard.py` (полный файл, функции `schema_errors`, `check_content`, `traceability_errors_from_content`) и `orchestrator/fsm.py` (grep по вызовам `guard.*errors`) — подтверждает заявление PLAN «Влияние на систему»: внешние потребители используют строки как есть, не парсят регэкспом.

## Предложения системе
(нет)
