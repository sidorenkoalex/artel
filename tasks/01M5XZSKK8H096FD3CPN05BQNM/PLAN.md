---
task: 01M5XZSKK8H096FD3CPN05BQNM
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: GitLab В1.2: гейт неослабления по исходам из отчётов задания CI

## Подход
Эскалация снята по ANSWER-2 (ответ A): часть 1 (01M5XZSKK8GZTECA2KWAFHE029)
влита и подтянута в ветку (27e37361f) — `Profile.full_suite`/`ci_job`
(`orchestrator/project_profile.py:127-128`) и `targets.FULL_SUITE_CI` есть.

Режим `ci` включается в одной точке — `_gate`
(`orchestrator/advance_gates/outcome_integrity.py`) при `merge=True` и
`profile.full_suite == ci`: ветка `_gate_ci` → `_judge_ci`, без каталога
выписок. `merge=False` (выход из `in_dev`) идёт прежним `_judge` с
выписками — требования 1 и 9; сигнатуры `_outcome_integrity_gate_refuses` и
`merge_gate_escalates` не меняются. Многокомпонентная запись проходит тем
же `_gate` из `_components_gate`.

`_judge_ci`:
- годность отчёта стороны — `_ci_report`: последняя попытка `ci_job` по
  наибольшему `id` из `forge.pipeline_status(sha).jobs`, статус
  `forge.job_result` — `success` либо `failed` без `allow_failure`, отчёт
  `forge.job_test_report` разобран; номер попытки до и после чтения отчёта
  совпадает (тот же приём, что `ci.job_full_suite` части 1);
- голова — только ровно её sha, иначе `_Prepare` «нет отчёта головы: …»;
- база — `_ci_base_report`: точка ответвления (`_merge_base_of`), иначе
  родители из `git rev-list --parents -n1` с тем же `^{tree}`; найден у
  родителя — запись журнала «отчёт базы: задание <id> коммита <sha> (дерево
  совпадает с <точка>)»; не найден — `_Prepare` «нет отчёта базы: …»;
- перевод — `outcome.parse_forge_report` по файлам дерева коммита отчёта
  (`git ls-tree -r -z` под `workdir`, без выписки); любая неоднозначная
  запись базы — `_Prepare` «отчёт базы неоднозначен: <id|ключ>»;
- находки: тест `PASS_TO_PASS` базы, красный или «неизвестно» в голове, —
  BROKEN (снимается мандатом как BROKEN); запись головы сопоставляется с
  тестом базы и по ключу отчёта (ANSWER-1 п. 1): ключ зелёного теста базы,
  модуль которого в дереве головы не найден, — BROKEN по id базы, не GONE
  (`outcome.forge_key_ids`); прочее — прежний `compare`;
  замены — `_ci_replacement_findings` (REPLACED_MISSING / REPLACED_NOT_GREEN
  / новая находка «замена теста не проверяема в режиме ci» → отказ, не сбой);
  G3б-2 — прежние `_strict_findings`/`_code_exception_findings` по диффу git;
- `_proven` не зовётся; запись `PASSED_ACTION` — ключ
  `ci:<компонент>:<дерево головы>:<job головы>:<job базы>` (без пробелов,
  `PROOF_LINE` разбирает), без сумм файлов блокировки.

Перевод отчёта (требование 8) — `parse_forge_report` в
`orchestrator/reporters/outcome.py`: деление по первому `::`; `classname` с
`/` — путь; иначе самый длинный префикс точечного пути, чей `.py` есть в
дереве под `workdir`; класс — остаток с `::`; путь к корню — `_root_path`.
Статус вне перечня и два ключа одного идентификатора — запись с исходом
`UNKNOWN`; ключ без `::` или с ненайденным модулем — в списке неразобранных.

## Шаги
1. `reporters/outcome.py`: `FORGE_OUTCOMES`, `_forge_location`,
   `parse_forge_report` + юнит-тест
   `tests/test_report_outcome_module.py::test_forge_report_key_without_separator_and_record_shape`
   (проверен мутацией «ключ без `::` переводится» — красный).
2. `outcome_integrity.py`: `_ci_report`, `_ci_base_report`, `_ci_cases`,
   `_ci_replacement_findings`, `_judge_ci`, `_gate_ci`, ветка в `_gate`,
   вид `REPLACED_UNCHECKABLE` в `_RANK`/`_KINDS`.
3. Прогоны и карта: `tests/test_01m5xzskk8h096fd3cpn05bqnm_ci_outcome_gate.py`
   — 46 passed; тесты гейта исходов и соседей
   (`test_01m5fryvp4nf81vt00fyphpwjh_outcome_action_texts`,
   `test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior`,
   `test_merge_outcome_module`, `test_outcome_components_module`,
   `test_outcome_gate_module`, `test_refusal_classes`,
   `test_report_outcome_module`, `test_gate_owner_marker`,
   `test_mandate_test_id`) — 172 passed; `python3 scripts/codebase_map.py`.
4. Итерация ревью 1: R1-F1 — `forge_key_ids` в `reporters/outcome.py`,
   `_ci_cases` отдаёт карту ключ → id, `_judge_ci` даёт BROKEN по ключу
   базы для неразобранного ключа головы; тест
   `tests/test_outcome_ci_head_key_module.py::test_module_missing_in_head_tree_is_broken_not_gone`
   (мутация «ключ отброшен» — красный); R1-F2 — юнит-тест сужен до ключа
   без `::` и формы записи; R1-F3 — rejected (см. REVIEW). Прогоны:
   долгоживущий + `test_report_outcome_module` + новый — 89 passed; соседи
   гейта исходов — 131 passed, 42 subtests; карта регенерирована.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 2 |
| 3 | 2 |
| 4 | 2 |
| 5 | 2, 4 |
| 6 | 2 |
| 7 | 2 |
| 8 | 1, 2 |
| 9 | 2, 3 |

## Влияние на систему
Меняется только ветка гейта мержа для компонента `full_suite: ci`; `local`,
`both`, артель и выход из `in_dev` идут прежним `_judge` (существующие тесты
гейта исходов зелёные без правки). Fail-closed сохранён: любой сбой чтения
`forge`/git в режиме `ci` — `PREPARE_REFUSAL_ACTION` → `MERGE_PREPARE_ACTION`,
задача на `merge_gate`, не пропуск; «неизвестно» нигде не засчитывается
зелёным (инвариант 41), неоднозначная база не сужает `PASS_TO_PASS`.
Ослабления по матрице SPEC (нет перепрогона и третьей выписки на мерже в
`ci`) — решения ТЗ/ANSWER родителя, не этой правки. Новое действие журнала
`гейт исходов: отчёт базы` — информационное, не отказ. Откат — revert одного
merge-коммита.

## Риски
- `full_suite: both` на мерже судится локально (SPEC говорит только о `ci`);
  если Оператор захочет и для `both` отчёты CI — отдельная правка условия в
  `_gate`.

## Предложения системе
- `start_after` не удержал шаг разработчика при невлитой части 1 (записано
  сессией Оператора по ANSWER-2, п. 2).
