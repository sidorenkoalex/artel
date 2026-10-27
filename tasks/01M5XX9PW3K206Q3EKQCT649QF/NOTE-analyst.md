# Записка analyst

## Выяснено
- Возврат аудита 1 из 2 (SPEC-AUDIT.md, 12 пунктов). Пункты 2, 3, 7, 9, 10, 11 и вид находки п. 4 — решения с последствиями, вынесены батчем в QUESTIONS.md (7 вопросов). SPEC.md по правилу батча не трогал.
- Пункты, которые правлю сам после ANSWER-2 (решение без Оператора):
  - п. 1: в `both` «неизвестно» старше красного — как `components_full_suite` (acceptance.py:3358-3359); пара «локальный красный + CI неизвестно» → «неизвестно».
  - п. 8: форма «неизвестно» в режиме `ci` — `FullSuiteRun(False, FULL_SUITE_NOT_STARTED, …)` с деталью, начинающейся `UNKNOWN_PREFIX` (acceptance.py:355, `is_unknown` :384); AC: `approve --accept-red` такой итог не принимает (fsm.py:1573-1584), в т.ч. в `both`.
  - п. 5: строки — `Profile` project_profile.py:66, `_component_value_error` targets.py:1207, вызов на мерже — обёртка `_outcome_integrity_merge_gate` fsm_merge_gate.py:1389, вызов :1517.
  - п. 6: AC-14 — совпадение с локальным JUnit только для отчёта без атрибута `file` и с найденным модулем (reporters/outcome.py:112, :123-124, :98-103).
  - п. 12: новый AC «нет отчёта головы (задания нет / `None`) → гейт не пропущен, отказ с причиной».
  - п. 9: добавить «## Матрица неослабления» (черновик таблицы — в SPEC-AUDIT.md:137-146).
  - AC-5: подмена с ≥2 попытками `ci_job` (проверка «наибольший id»).
- Ключ `_component_key` (outcome_integrity.py:813) требует выписки головы только ради файлов блокировки: `report_suite_result_key(tree, profile, base=True)` (acceptance.py:3069) обходится без выписки.
- Гейт мержа зовёт `acceptance.components_full_suite` (fsm_merge_gate.py:1085) — эта функция в зоне (acceptance.py), т.е. вариант B вопроса 1 реализуем без правки fsm_merge_gate.py; но её же зовёт `outcome_integrity._full_run` (:397).

## Не сработало
- `ls` в Bash недоступен (command not found) — читал через Read/sed.

## Где остановился
- QUESTIONS.md написан, guard прогнан; ждёт ANSWER-2. После ответа: правки SPEC по списку выше + ответы, удалить QUESTIONS.md, status ready.

## Чего не хватило
- Нет карточки, как `approve --accept-red` отличает «неизвестно» от красного (fsm.py:1573 + acceptance.is_unknown).
