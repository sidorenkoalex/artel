---
task: 01M1RFQ52S0VD22J628TXX96XS
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 4
---

# REVIEW: Облегчённая проекция карты кодовой базы для брифа роли

## Фаза A: проверка плана

1. Покрытие требований — таблица PLAN «Покрытие требований» полна:
   требование 1 → шаг 1, требования 2/3 → шаг 2, требование 4 явно
   отмечено «не требует кода». Все 17 AC PLAN относит к шагам 1–3.
2. Размер шага — один MR монолитом; SPEC «Обоснование монолита»
   аргументирует неделимость (функция без подключения — мёртвый код,
   подключение без функции не существует) и Оператор его принял
   05.09.2026. Согласен: границы зон (`scripts/codebase_map.py` /
   `orchestrator/brief.py`) действительно не дают самостоятельно
   мержимого промежуточного состояния.
3. Конфликтов с конвенциями/архитектурой не вижу: правила проекции
   действительно сведены в одно место (`_KEPT_FIELDS_BY_KIND` в
   `scripts/codebase_map.py`), `orchestrator/brief.py` не дублирует
   логику удаления блоков (проверено — см. «Проверено исполнением»).

Плана без замечаний.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`project_for_brief` — чистая функция, одно место правил) | OK | `scripts/codebase_map.py:186-201`; AC-1/AC-2/AC-3/AC-4/AC-5/AC-6/AC-7/AC-8 — приёмочные тесты зелёные (см. ниже). |
| 2 (`developer_brief`/`_handle_map_size_alert` — проекция после сверки свежести) | OK | `orchestrator/brief.py:613-616` — `project_for_brief` вызван на `map_text` уже ПОСЛЕ `_fresh_map_text_and_note`; алерт (`_handle_map_size_alert`) считает по `projected_map_text`, не по полному тексту. |
| 3 (опись/заголовок называют проекцию, полная карта — адресно) | OK | `MAP_PROJECTION_LABEL`/`MAP_PROJECTION_NOTE` (`orchestrator/brief.py:26-35`), применены и в `developer_brief` (:620-622), и в `analyst_map_component` (:682-684); размер/sha256 в описи и в журнале — от текста проекции (AC-13/AC-14, тесты зелёные). |
| 4 (скилы/миссии ролей не меняются) | OK | Diff не трогает `skills/*.md`/`orchestrator/role_prompt.py` (см. «Изменённые файлы»). |

## Замечания

- minor — `tasks/01M1RFQ52S0VD22J628TXX96XS/acceptance_tests/test_brief_map_projection.py:360-401, 438-461` — четыре теста (`test_ac12_analyst_component_label_names_the_projection`, `test_ac14_analyst_journal_entry_carries_the_projection_hash`, `test_ac15_stale_note_still_precedes_the_map_component_for_analyst`, `test_ac11_alert_still_fires_when_the_projection_itself_exceeds_the_ceiling`) не несут заявку «Ловит мутацию: …» в докстринге — их докстринги описывают только сценарий, но не называют мутацию, которую тест обязан ловить (в отличие от остальных 12 тестов того же файла и всех тестов `test_project_for_brief.py`, которые эту конвенцию соблюдают). Тесты по существу корректны (проверено запуском — все зелёные, каждый проверяет реальное поведение: заголовок компонента, sha256 журнала, порядок пометки/текста, срабатывание алерта), это находка про докстринг-дисциплину, не про корректность. Предложение: дописать «Ловит мутацию: …» этим четырём тестам по образцу соседних (например, `test_ac12_component_label_names_the_projection_and_points_to_the_full_map`, `test_ac14_journal_entry_for_the_map_carries_the_projection_hash`, `test_ac15_stale_note_still_precedes_the_map_component`, `test_ac11_no_alert_when_only_the_full_file_exceeds_the_ceiling` — их developer-эквиваленты уже несут заявку).

## Реестр замечаний

Пусто: единственная находка этой итерации — minor (см. «Замечания»),
без blocker/major записей на регистрацию/отслеживание через реестр
(«Вердикт»: 0 blocker/major → approved) — предыдущих итераций у этой
задачи не было (iteration: 1).

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved

Единственная находка — minor (недостающая заявка «Ловит мутацию» у 4
приёмочных тестов), не блокирует и не ломает предсказуемо ничего:
реализация полностью соответствует SPEC, все 17 AC проверены и зелены,
регрессия AC-17 подтверждена прогоном, зона правки не превышена, карта
кодовой базы актуальна по содержимому.

## Проверено исполнением

- `python3 -m unittest discover -s tasks/01M1RFQ52S0VD22J628TXX96XS/acceptance_tests -p 'test_*.py' -v` — 25 тестов (AC-1..AC-17), все `ok`.
- `python3 -m unittest tests.test_brief tests.test_codebase_map tests.test_fsm_map_regen tests.test_fsm_map_conflict_autoresolve -v` (AC-17, явно названные модули) — 44 теста, все `ok`.
- Прочитан текущий `orchestrator/brief.py` и `scripts/codebase_map.py` целиком (не только diff) — подтверждено: `orchestrator/brief.py` не определяет собственной логики удаления блоков карты (AC-6), только вызывает `codebase_map.project_for_brief`.
- Проверка свежести `docs/codebase-map.md` вручную: `python3 scripts/codebase_map.py` (регенерация в рабочем дереве) и сравнение с закоммиченной версией через `grep -v '^built_at_sha:'` + `diff` — содержимое идентично побайтово (различался только `built_at_sha`, что не дефект, см. review-checklist). Рабочее дерево восстановлено `git checkout -- docs/codebase-map.md` после проверки.
- `git log --oneline -- scripts/codebase_map.py orchestrator/brief.py docs/codebase-map.md`, `git show f972b3e2 -- docs/codebase-map.md`, `git show cc331869` — проверено, что финальная подтяжка main (f972b3e2) не оставила карту содержательно стухшей: конфликт слияния разрешился только по строке `built_at_sha`, остальной текст (включая изменения `orchestrator/zone_lock.py` со стороны main) объединился бесконфликтно и совпадает со свежей регенерацией.
- `git diff --stat main...task/01m1rfq52s0vd22j628txx96xs-oblegchyonnaya-proektsiya-kart` — подтверждено, что зона правки не превышена (ровно `scripts/codebase_map.py`, `orchestrator/brief.py`, плюс ожидаемая регенерация `docs/codebase-map.md`); `skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/` не тронуты.

## Предложения системе

(нет)
