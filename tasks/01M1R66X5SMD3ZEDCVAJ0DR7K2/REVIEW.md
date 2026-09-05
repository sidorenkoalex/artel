---
task: 01M1R66X5SMD3ZEDCVAJ0DR7K2
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 4
---

# REVIEW: guard на артефактных ветках — черновики не красят CI, сданные артефакты проверяются строго

## Фаза A — проверка плана

PLAN.md не менялся со времени итерации 1 (диф этой итерации — только
`tests/test_guard_artifact_branch_mode.py` докстринги, `docs/codebase-map.md`
и подтяжка main). Оценка итерации 1 остаётся в силе: таблица покрытия
требований 1–6 полна, шаги — проверяемые единицы разумного размера (монолит
обоснован в PLAN.md явно), подход не конфликтует с конвенциями (защищённый
путь `.github/workflows/ci.yml` правится диффом-приложением, не напрямую;
`*.py`-правка сопровождена регенерацией `docs/codebase-map.md`). Замечаний к
плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (без флага — поведение не меняется ни на бит) | OK | Код не менялся с итерации 1 — `check_content(..., artifact_branch_mode=False)` зовёт `_content_errors` напрямую. `test_ac1_default_call_unaffected.py` (2/2) зелёный. |
| 2 (draft spec/plan/review/test_report — только базовые условия frontmatter) | OK | `is_draft_lenient`/`basic_frontmatter_errors` без изменений в этой итерации. `test_ac2_draft_downgraded_to_warning.py` (2/2) зелёный. |
| 3 (`tz`/`questions`/`answer` не меняются ни при каком статусе) | OK | `test_ac4_tz_questions_answer_unaffected.py` (3/3) зелёный. |
| 4 (CLI-флаг, семантика exit-кода) | OK | `test_ac5_cli_flag_enables_mode.py` (2/2), `test_ac6_exit_code_by_status.py` (2/2) зелёные. |
| 5 (сводка «сдано N / черновиков M / нарушений K» первой строкой) | OK | `test_ac7_summary_line_format.py` (2/2) зелёный. |
| 6 (`ci.yml`: диф-приложение для Оператора, `git apply --check`) | OK | `.github/workflows/ci.yml` в кодовой ветке НЕ тронут (`git diff --stat main...HEAD -- .github/` пуст). Диф из PLAN.md «Диф для Оператора» перепроверен этим заходом: извлечён и `git apply --check` на текущем дереве задачи проходит без ошибок. AC-8 помечен `manual` в `test_scope_markers.py` с тем же обоснованием, что и итерация 1 (защищённый путь, легитимный прецедент 01M1QHQ277PQQA894X97RVEX9Y) — принято. |

## Замечания

Новых замечаний нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | `tests/test_guard_artifact_branch_mode.py` | 13/16 тестовых методов были без заявки `Ловит мутацию: …` в докстринге | нельзя было подтвердить, что тест ловит правдоподобную поломку CI-гейта guard.py | Проверено этой итерацией: все 16 методов файла теперь несут докстринг с конкретной заявленной мутацией (диф коммита `ee09fab6`). Прочитан код каждого метода против его заявки — заявки конкретны (называют функцию/поле/сравнение, которое могло бы сломаться: `DRAFT_LENIENT_TYPES`, `BASIC_META_FIELDS`, сравнение `== "draft"`, дефолт `artifact_branch_mode`, порядок вызова `schema_errors` внутри `basic_frontmatter_errors` и т.д.) и правдоподобны — каждая соответствует реальной ветке кода в `scripts/guard.py:963-1023`, ни одна не пересказывает имя метода. Полный прогон `python3 -m unittest tests.test_guard_artifact_branch_mode -v` — 16/16 зелёные. Закрыто. |

## Вердикт

`approved`. Единственное замечание итерации 1 (R1-F1, докстринги тестов)
исправлено и подтверждено — код `scripts/guard.py` реализует все 6
требований SPEC корректно (без изменений с итерации 1, где логика уже была
полностью проверена), `.github/workflows/ci.yml` обработан верно как
защищённый путь (диф применяется чисто, файл не тронут в кодовой ветке), ни
один существующий тест/гейт/инвариант не ослаблен. Реестр замечаний закрыт
целиком (0 записей со статусом, отличным от `accepted`).

## Проверено исполнением

- `python3 -m unittest tests.test_guard_artifact_branch_mode tests.test_guard_schema tests.test_guard_split_signals tests.test_guard_zones tests.test_id_format_guard tests.test_invariants tests.test_review_registry_gate -v` — 159 тестов, `OK` (затронутые модули + инварианты, включая `GuardKeepsTheIntegritySectionTest`).
- `python3 -m unittest discover -s tasks/01M1R66X5SMD3ZEDCVAJ0DR7K2/acceptance_tests -p 'test_ac*.py' -v` — 19 тестов, `OK` (AC-1..AC-7, AC-9; AC-8 закрыт легитимной manual-пометкой, см. выше).
- Прочитан diff `d092ab75..ef6bfe96` (реальный диапазон изменений итерации — инкрементальный diff пакета от sha `ef6bfe96` до HEAD был пуст, т.к. HEAD ветки САМ есть `ef6bfe96`; настоящий коммит с прошлым вердиктом (`changes_requested`) обнаружен через `git log -- tasks/.../REVIEW.md` и `git merge-base main <ветка>` — совпадает с классом инцидента T087 из `review-checklist.md`, «Инкрементальный diff… пустой не значит без изменений»). Диф ограничен `docs/codebase-map.md`, `tests/test_guard_artifact_branch_mode.py` плюс подтяжка main (не относящиеся к задаче файлы других задач в `docs/codebase-map.md`-листингах импортов — следствие подтяжки, ожидаемо).
- `git diff --stat 0fe22b6a(merge-base с main) ef6bfe96 -- scripts/ tests/ docs/codebase-map.md orchestrator/` — только `scripts/guard.py`, `tests/test_guard_artifact_branch_mode.py`, `docs/codebase-map.md` затронуты за всё время задачи; `orchestrator/` не тронут.
- `git diff --stat main task/... -- .github/` — пусто, защищённый путь не тронут кодовой веткой.
- `python3 scripts/codebase_map.py` перегенерирован и сравнён с закоммиченной версией (`git diff -- docs/codebase-map.md` после регенерации) — расхождение только в строке `built_at_sha` (не дефект, `review-checklist.md`); рабочее дерево восстановлено `git checkout -- docs/codebase-map.md` после сверки.
- Извлечён диф `.github/workflows/ci.yml` из PLAN.md «Диф для Оператора» скриптом (парсинг блока ` ```diff `) и прогнан `git apply --check /tmp/ci_diff.patch` на текущем дереве задачи — применяется без ошибок.
- Прочитан код `scripts/guard.py:963-1023` (`DRAFT_LENIENT_TYPES`, `BASIC_META_FIELDS`, `is_draft_lenient`, `basic_frontmatter_errors`, `check_content`) построчно против каждой из 16 заявок `Ловит мутацию:` в `tests/test_guard_artifact_branch_mode.py` — все заявки соответствуют реальным веткам кода, ни одна не пересказывает имя теста.

## Предложения системе
