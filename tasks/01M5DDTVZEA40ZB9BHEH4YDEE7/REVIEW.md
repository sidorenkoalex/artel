---
task: 01M5DDTVZEA40ZB9BHEH4YDEE7
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: G3а-2а — гейт исходов на гейте мержа, пакет ревьювера, двусторонний прогон по имени ошибки

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–8 сопоставлены шагам 1–6; требование 7 честно отнесено к уже действующему правилу `in_pass_to_pass` (G3а-1а), отдельного кода не требует.
- Шаги — размера модуля (по одному на файл зоны), не микрооперации.
- Подход в рамках архитектуры: ядро `_judge` параметризовано базой (`base_of`) вместо дублирования гейта; мерж-шаг по образцу `test_integrity.merge_gate_escalates`; `_check_failure_kind` только импортируется (отложенный импорт), не переносится. «Влияние на систему» совпадает с diff: 5 модулей зоны + 2 файла `tests/`, `pull.py`/`fsm.py` и модули «только для чтения» не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_judge` (outcome_integrity.py): строка `голова; база; ключ; мандат` сразу после строки чисел; ключ — `acceptance._report_suite_result_key(<голова>^{tree}, profile, False, root=<выписка головы>)` в `_component_key`, `None` → `_Prepare` до прогонов и до поиска доказательства (на `in_dev` записи нет — AC-1 тест). `fingerprint` — sha256 отсортированных уникальных элементов через `\n`, иначе «нет»; элементы берутся `_covering_pair`, публичные `covering`/`_covering` сохранили сигнатуры и исходы. |
| 2 | OK | `fsm_merge_gate.py`: `_outcome_integrity_merge_gate` строго между `sync_outcome != "fresh"` и `_acceptance_locks_refuse`; база — `_merge_base_of(lambda: _origin_main_sha(ctx))` = `git merge-base <голова> <sha main>`; `None`/пусто от фетча → `_Prepare`. На `in_dev` — `_diff_base` (прежний `gitcmd.diff_base`). Цель — `store.task_target`, канарейка — `store.get_task`. Документное отставание не проверяется отдельно (AC-7 doc-only тест). |
| 3 | OK | `_proven`: сверка (голова, база, ключ) и отпечатка, пересчитанного ТЕКУЩИМ мандатом над id покрытых находок записи (`_covered_ids` → `_covering_pair`); отозванный элемент → `None` → не доказательство. Запись «гейт исходов: доказан для головы <sha7> и базы <sha7>». Старые записи без строки — `proof_fields` → `None`. |
| 4 | OK | `merge_gate_escalates`: находка → журнал «merge отклонён: гейт неослабления по исходам» + `escalated`; сбой подготовки (любой `_Prepare`/исключение `_gate`) → журнал «… — подготовка» и `sys.exit` с «повтори artel.py approve <id>», состояние не тронуто, до CI/push не доходит. Ключ в `REFUSAL_CLASSES` → «чинит Оператор». `_full_suite_or_refuse` не тронут. |
| 5 | OK | `review._outcome_gate_lines`: в границе раздел есть всегда, строки `review_lines` по записи с текущей головой либо «гейт исходов для головы <sha7> не исполнялся»; канарейка отсекается прежним началом функции; вне границы `outcome_lines is None` → прежнее условие и прежний текст (`outcome_note` пустой). `branch_head_sha` возвращает `""`, не `None` — срез `[:7]` не падает (проверено чтением gitcmd.py:594). |
| 6 | OK | `two_sided._run_side_report`: `strict = in_outcome_bounds(profile)`; `failed`/`error` и `passed` с повтором → `_check_failure_kind`; пусто — `assertion`, иначе `kind` → `_verdict` «упал не на проверке: <вид>». Вне границы — прежняя ветка `elif` без изменений. |
| 7 | OK | Прежнее правило перепрогона базы (`in_pass_to_pass`), AC-13 тест зелёный. |
| 8 | OK | `tests/test_component_report_gates.py` — +2 строки подмены `_outcome_integrity_merge_gate` в помощнике `merge`, утверждений не меняет (`git diff` — 0 изменённых `self.assert…`). Прочие тесты не правлены. |

## Замечания
Блокирующих и major замечаний нет.

Наблюдения без требования правки (в реестр не заносятся):
- `outcome_integrity.py` `_gate`: подсказка `GateRefusal` («повтори artel.py advance») на мерже не используется — `merge_gate_escalates` печатает свою, с `approve`; вывод верный.
- Разбор id покрытых находок (`_finding_id`) зависит от формата `Finding.line`; формат `compare`/`_redness` сверен по коду (outcome_integrity.py:135–165, 333–348) — маркеры « — база: »/« — ветка: » соответствуют. Риск неверного разбора приводит лишь к лишнему прогону (PLAN «Риски»), ложного прохода нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `artel.py plank-run 01M5DDTVZEA40ZB9BHEH4YDEE7` — 3 passed, код выхода 0.
- `python3 -m pytest -q -p no:xdist tests/test_outcome_integrity.py tests/test_component_report_gates.py tests/test_full_suite_reuse.py tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py` — 45 passed, 49 subtests passed (138 с).
- `python3 -m pytest -q -p no:xdist tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py tests/test_01m56tnz3e72xy9xstavs99cn2_two_sided_variants.py tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_refusal_classes.py tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py tests/test_refusal_classes.py tests/test_mandate_test_id.py tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py tests/test_project_profile_gates.py` — 141 passed, 138 subtests passed (соседние гейты, двусторонний прогон, классы отказов, FAIL_TO_PASS G3а-1а).
- Временная мутация: `fingerprint` — `sorted(set(...))` → `list(...)`; `tests/test_outcome_integrity.py -k fingerprint` — 1 failed (тест ловит заявленную мутацию); код возвращён, `git status` чист.
- `git diff c8974c8b -- tests/test_component_report_gates.py | grep "^[-+] *self.assert"` — 0 строк (утверждения не менялись).
- `docs/codebase-map.md` содержит новые публичные `fingerprint`, `merge_gate_escalates`, `proof_fields` (карта регенерирована в ветке).
- Полный набор `tests/` не гонялся (решение Оператора 05.09); CI коммита 90a04eac зелёный (16 проверок).

## Предложения системе
- Долгоживущий `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py` идёт ~133 с (порог 60 с): сквозные `approve` с двумя полными наборами на подслучай. Для test_author: стоит ли делить файл по классам AC, чтобы порог времени файла не превышался одним модулем.
- `pytest -n` (xdist) в рабочей копии падает «node down: Not properly terminated» — тесты затронутых модулей пришлось гнать с `-p no:xdist`; стоит указать в скиле ревьювера.
