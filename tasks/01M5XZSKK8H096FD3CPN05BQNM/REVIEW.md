---
task: 01M5XZSKK8H096FD3CPN05BQNM
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: GitLab В1.2: гейт неослабления по исходам из отчётов задания CI

## Фаза A — план
- Таблица покрытия PLAN полна (требования 1–9 → шаги 1–4); шаг 4 честно
  описывает итерацию ревью 1 (R1-F1/F2/F3).
- Подход не изменился: одна точка ветвления в `_gate` (`merge` и
  `full_suite == ci`), ядро `_judge_ci`; толкование ANSWER-1 п.1 теперь
  отражено в «Подходе» (`outcome.forge_key_ids`, BROKEN по id базы).
- «Влияние на систему» соответствует инкрементальному диффу: тронуты
  `outcome_integrity.py` (`_ci_cases`, `_judge_ci`), `reporters/outcome.py`
  (вынос `forge_key_ids` из `parse_forge_report`, поведение прежнее), новый
  `tests/test_outcome_ci_head_key_module.py`, сужение метода
  `tests/test_report_outcome_module.py` (метод новый на ветке —
  `git grep` по `main` его не находит). Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | без изменений с итерации 1; AC-1/AC-9 зелёные |
| 2 | OK | без изменений; ANSWER-1 п.2 реализован в `_ci_report` |
| 3 | OK | без изменений |
| 4 | OK | без изменений |
| 5 | OK | R1-F1 закрыт: `_judge_ci` (`outcome_integrity.py:1174-1183`) — ключ зелёного теста базы, неразобранный в голове, даёт BROKEN по id базы; GONE того же id из `compare` вытесняется `taken` (:1190-1191) |
| 6 | OK | без изменений |
| 7 | OK | без изменений |
| 8 | OK | сопоставление головы с базой по ключу отчёта (ANSWER-1 п.1); `parse_forge_report` после выноса `forge_key_ids` даёт те же записи (тот же порядок `sorted(outcomes)`) |
| 9 | OK | ветка только для `merge and ci`; существующие тесты не тронуты |

## Замечания

Новых замечаний blocker/major/minor нет. Наблюдение без записи в реестр:
`_ci_cases` зовёт `forge_key_ids` дважды (напрямую и внутри
`parse_forge_report`) — лишний проход по отчёту, на результат не влияет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/advance_gates/outcome_integrity.py:1174-1183 | модуль записи головы не найден в дереве головы → GONE вместо BROKEN (ANSWER-1 п.1) | вид находки расходился с решением Оператора | accepted: карта `base_ids` ключ → id, `lost` даёт BROKEN по id базы; тест `tests/test_outcome_ci_head_key_module.py::test_module_missing_in_head_tree_is_broken_not_gone` проверен временной мутацией (`lost` пуст) — красный со строками «исчез: …», код восстановлен |
| R1-F2 | accepted | tests/test_report_outcome_module.py::test_forge_report_key_without_separator_and_record_shape | повтор свойств долгоживущего файла | дублирующий сторож | accepted: оставлены ключ без `::` и форма записи; метод новый на ветке (в `main` его нет), сужение не ослабляет существующий тест |
| R1-F3 | accepted | orchestrator/advance_gates/outcome_integrity.py, хвост `_judge_ci` | дублирование хвоста `_judge` | два места правки | accepted (rejected разработчика выдерживает критику): хвосты различаются (`flaky_lines`, `prior_line`, `replaced_lines`, счётчики), общий помощник потребовал бы правки локального пути `_judge`, который требование 9 держит прежним; замечание было minor-вкусом |

## Вердикт
approved — R1-F1 исправлен по существу и закрыт сторожем в `tests/`,
R1-F2/R1-F3 закрыты; реестр целиком `accepted`.

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_outcome_ci_head_key_module.py tests/test_01m5xzskk8h096fd3cpn05bqnm_ci_outcome_gate.py tests/test_report_outcome_module.py::test_forge_report_key_without_separator_and_record_shape`
  — 48 passed (36.0 с).
- Временная мутация `outcome_integrity.py:1175` (`if key in base_ids and False` —
  неразобранный ключ головы отброшен) → `tests/test_outcome_ci_head_key_module.py`
  красный: отказ со строками «исчез: <id> — база: passed; ветка: нет записи» ×3;
  файл восстановлен `git checkout --`, `git status` чист.
- `python3 -m pytest -q -p no:cacheprovider tests/test_report_outcome_module.py tests/test_merge_outcome_module.py tests/test_outcome_components_module.py`
  — 78 passed (135.8 с).
- `git grep test_forge_report_key_without_separator main -- tests/` — пусто:
  сужаемый метод в базе отсутствует, существующие утверждения не ослаблены.

## Предложения системе
- Пакет ревью итерации 2 не отмечает, какие методы `tests/` новые на ветке, а
  какие есть в base: сужение метода, добавленного прошлой итерацией, пришлось
  проверять `git grep` по `main` вручную.
