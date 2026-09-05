---
task: 01M1R66X5SMD3ZEDCVAJ0DR7K2
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 4
---

# REVIEW: guard на артефактных ветках — черновики не красят CI, сданные артефакты проверяются строго

## Фаза A — проверка плана

1. **Покрытие.** Таблица «Покрытие требований» PLAN.md полна: все 6 требований
   SPEC отображены на шаги 1–4 (требования 1–5 → шаг 1, требование 6 →
   шаг 4 диф-приложением). Пробелов нет.
2. **Размер шагов.** 4 шага — `scripts/guard.py` (одна атомарная правка одной
   функции + CLI), новый тестовый файл, регенерация карты, диф-приложение
   для Оператора. Не микрооперации и не «сделать всё» — размер MR
   разумный, монолит обоснован PLAN.md явно (недостижимый код при разбиении
   логики/CLI, несовместимый CI при разбиении guard.py/ci.yml).
3. **Конвенции.** Подход не конфликтует с существующей архитектурой:
   `.github/workflows/ci.yml` — защищённый путь, правится диффом-приложением
   Оператору (`skills/conventions-core.md`), не напрямую; `*.py`-правка
   сопровождена регенерацией `docs/codebase-map.md` тем же шагом
   (`skills/conventions-core.md`). Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (без флага — поведение не меняется ни на бит) | OK | `check_content(label, text, artifact_branch_mode=False)` вызывает `_content_errors` напрямую; `check()` и `orchestrator/fsm.py:338` (`guard_refuses`) зовут `check`/`check_content` без нового параметра — не изменены ни строкой. AC-1: `test_ac1_default_call_unaffected.py` (2/2), `test_ac9_required_scenarios.py::DraftSpecStillBlocksAdvanceTest` — зелёные. |
| 2 (draft spec/plan/review/test_report — только базовые условия frontmatter) | OK | `is_draft_lenient`/`basic_frontmatter_errors` реализуют предикат и базовую проверку буквально по требованию (`task`/`type`/`schema_version` на месте, `schema_version` не выше `SUPPORTED_SCHEMA_VERSION`). AC-2: `test_ac2_draft_downgraded_to_warning.py` (2/2) зелёные, для всех четырёх типов (юнит-тест `test_plan_review_test_report_draft_are_lenient` подтверждает не только `spec`). |
| 3 (`tz`/`questions`/`answer` не меняются ни при каком статусе) | OK | `is_draft_lenient` возвращает `False` для типов вне `DRAFT_LENIENT_TYPES` независимо от `status`. AC-4: `test_ac4_tz_questions_answer_unaffected.py` (3/3) зелёные, включая `QUESTIONS.md` со `status: draft`. |
| 4 (CLI-флаг `--all --artifact-branch`, семантика exit-кода) | OK | `ARTIFACT_BRANCH_FLAG` вынимается из `sys.argv` до сравнения `args == ["--all"]` — работает в любом порядке аргументов. AC-5/AC-6: `test_ac5_cli_flag_enables_mode.py` (2/2), `test_ac6_exit_code_by_status.py` (2/2) зелёные. |
| 5 (первая строка — сводка «сдано N / черновиков M / нарушений K») | OK | Сводка печатается первой строкой до списков предупреждений/ошибок; `N`/`M` считаются по `status` независимо от типа (не сужено до четырёх типов). AC-7: `test_ac7_summary_line_format.py` (2/2) зелёные, включая проверку порядка строк. |
| 6 (`ci.yml`: диф-приложение для Оператора, `git apply --check`) | OK | `.github/workflows/ci.yml` в кодовой ветке НЕ тронут (`git diff --stat` пуст) — верно для защищённого пути. Диф приложен в PLAN.md «Диф для Оператора»; извлечён и прогнан этим ревью: `git apply --check` на текущем дереве задачи проходит без конфликтов. `pull_request`-триггер учтён отдельно (не подпадает под `artifact/*`). AC-8 помечен `manual` в `test_scope_markers.py` с обоснованием «защищённый путь, диф проверяется Оператором на гейте PLAN» — легитимная причина (тот же класс, что уже применён в 01M1QHQ277PQQA894X97RVEX9Y). |

## Замечания

- major — `tests/test_guard_artifact_branch_mode.py:29,49,60,63,73,78,112,138,143` (нет докстринга вовсе) и `:41,55,149,157` (докстринг есть, но без заявки) — 13 из 16 тестовых методов файла не несут заявку `Ловит мутацию: …` (skills/test-authoring.md, `review-checklist.md` п. «Тесты»: «докстринг обязан описывать сценарий и наблюдаемое свойство… пустой или пересказывающий тоже замечание»). Только 3 метода (`test_plan_review_test_report_draft_are_lenient:32`, `test_missing_schema_version_is_an_error:83`, `test_schema_version_present_but_zero_is_not_reported_as_missing:97`) называют конкретную мутацию — эти три проверены и мутация в каждом правдоподобна и реально ловится (перепроверено чтением кода `is_draft_lenient`/`basic_frontmatter_errors`). Для остальных 13 нельзя установить, какую правдоподобную поломку `guard.py` (файл, несущий CI-гейт задачи 01M1R66X5SMD3ZEDCVAJ0DR7K2) тест реально ловит, а какую пропустит — например `test_missing_task_is_an_error:78` и `test_clean_meta_has_no_errors:73` вообще без единой строки пояснения. Прецедент того же класса замечания и той же оценки серьёзности (major) — `tasks/01M1H186VEVG6NF40YKH1338MD/REVIEW.md`, R1-F3. Предложение: добавить `Ловит мутацию: …` к каждому из 13 методов, по образцу уже написанных трёх.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | `tests/test_guard_artifact_branch_mode.py:29,49,60,63,73,78,112,138,143,41,55,149,157` | 13/16 тестовых методов без заявки `Ловит мутацию: …` в докстринге | нельзя подтвердить, что тест ловит правдоподобную поломку CI-гейта guard.py, а не исполняет ритуал покрытия | добавить содержательный докстринг с заявленной мутацией к каждому из 13 перечисленных методов (по образцу трёх уже имеющихся в этом же файле) |

## Вердикт

`changes_requested`. Единственная найденная проблема — процедурная (докстринги
тестов), не функциональная: код `scripts/guard.py` реализует все 6 требований
SPEC корректно, `.github/workflows/ci.yml` обработан верно как защищённый путь
(диф применяется чисто), ни один существующий тест/гейт/инвариант не ослаблен.
После добавления заявленных мутаций к 13 методам `tests/
test_guard_artifact_branch_mode.py` задача готова к approve без повторной
проверки логики (она уже полностью подтверждена этим заходом).

## Проверено исполнением

- `python3 -m unittest tests.test_guard_artifact_branch_mode tests.test_guard_schema tests.test_guard_split_signals tests.test_guard_zones tests.test_id_format_guard tests.test_invariants tests.test_review_registry_gate -v` — 159 тестов, `OK` (затронутые модули + инварианты, включая `GuardKeepsTheIntegritySectionTest`).
- `python3 -m unittest discover -s tasks/01M1R66X5SMD3ZEDCVAJ0DR7K2/acceptance_tests -p 'test_ac*.py' -v` — 19 тестов, `OK` (AC-1..AC-7, AC-9 — все сценарии требования 6 закрывает manual-пометка AC-8, разобрана отдельно).
- Диф `.github/workflows/ci.yml` извлечён из PLAN.md «Диф для Оператора» и прогнан `git apply --check` на текущем дереве задачи (после подтяжки main, коммит `d092ab75`) — применяется без конфликтов; `git diff --stat -- .github/` на кодовой ветке пуст (файл не тронут задачей напрямую, верно для защищённого пути).
- `python3 scripts/codebase_map.py` перегенерирован во временном stash и сравнён с закоммиченной версией — расхождение только в строке `built_at_sha` (не дефект, см. `review-checklist.md`), остальное содержимое (новые публичные функции `basic_frontmatter_errors`/`is_draft_lenient`, новый файл `tests/test_guard_artifact_branch_mode.py` в списках «Импортируется») совпадает.
- `grep -rn "check_content\b"` по репозиторию — публичная сигнатура `check_content(label, text)` (2 позиционных аргумента) не сломана: все существующие вызыватели в других задачах (`tasks/T100`, `tasks/T072`, `tasks/T075`, `tasks/01M1NKTF173WV5CPDZ1C3WW69K`, `tests/test_guard_schema.py` и др.) продолжают работать без изменений.
- `git diff main...task/... -- tests/` вручную сверен на предмет удалённых/ослабленных ассертов в СУЩЕСТВУЮЩИХ файлах — правка добавляет только новый файл, ни одна существующая строка тестов не тронута.
- Воспроизведён самораскрытый в PLAN.md риск «Риски» (задвоение текста предупреждения при одновременном отсутствии `task`/`type`) — фактически задвоение (разными формулировками) наступает уже при отсутствии ОДНОГО `task` (не обязательно обоих полей сразу, как написано в PLAN), но вывод PLAN о том, что это не влияет на корректность exit-кода — подтверждён: `task` в любом случае остаётся в `errors`, только избыточен текст предупреждения. Не заведено отдельной записью реестра — чисто текстовая неточность самораскрытого риска, не код и не поведение.

## Предложения системе
