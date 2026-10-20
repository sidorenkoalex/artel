# Записка spec_auditor — 01M5DDTVZEA40ZB9BHEH4YDEE7

## Выяснено
- Сверка свежести на мерже идёт не через `fsm_merge_gate._origin_main_sha` (:150), а через `fsm._origin_main_sha` (fsm.py:170) внутри `pull.evaluate` (pull.py:766); исход `Fresh()` (pull.py:112) sha не несёт, `_sync_main_or_wait` возвращает строку "fresh" (fsm_merge_gate.py:746). Fresh() возвращается и при несостоявшемся фетче (pull.py:770) и при doc-only отставании (pull.py:785).
- Помощник `merge` теста (tests/test_component_report_gates.py:428) подменяет `_sync_main_or_wait` строкой "fresh" — сменить форму возврата нельзя без правки утверждений/подмен.
- `refusal_class` по умолчанию даёт OPERATOR_FIXES (refusal_classes.py:149-152) — AC-2 по классу без проверки членства в словаре мутацию не ловит.
- `_check_failure_kind` — tests_writing.py:752 (SPEC пишет 750). Прочие адреса подтверждены.
- `_report_suite_result_key` (acceptance.py:3170) может вернуть None; режим base=True/False для ключа головы в SPEC не задан.
- Правило п.7 уже исполняется кодом (outcome_integrity.py:280-281, 294-295).
- Тело мержа на каждом заходе после ожидания CI снова проходит sync→гейт: доказательство по записи первого захода — штатный путь.

## Где остановился
SPEC-AUDIT.md написан, вердикт concerns.

## Чего не хватило
Где берётся sha main сверки свежести (pull.evaluate, а не fsm_merge_gate) — искал дольше всего.
