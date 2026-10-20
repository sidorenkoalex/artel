# Записка spec_auditor

## Выяснено
- Все ссылки SPEC файл:строка совпадают с кодом (fsm_advance.py:732/804/806, test_integrity.py:77/1040/1074/1722, acceptance.py:688/793/2309/2315/2401/3425, two_sided.py:336/411, gitcmd.py:533, project_profile.py:184/440, advance_gates/acceptance.py:213).
- `parse_junit` (reporters/outcome.py:133-164) никогда не ставит `retries` — «прошёл с повтором» выразим только записью pult-vitest; сквозной сценарий на junit-xml отчётах повтор не выразит.
- `diff_base` -> None (gitcmd.py:545-547) обязывает к fail-closed; SPEC не называет исход сбоя git/выписки.
- Текстовый гейт пропускает канарейку (test_integrity.py:1754); SPEC о канарейке молчит.
- Длительный тест tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py:1876-1881 ведёт in_dev -> verifying на профиле components+report — новый гейт его затронет.
- `_answer_mandate` элементы: путь, путь::Класс, путь::Класс::метод; id исходов с параметрами `[..]` и `#n`.

## Не сработало
- `ls`/`for` в оболочке шага недоступны — читал через python3.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns, guard ок. Главные пункты: Е1 (fail-closed при сбое git/выписки не назван), В1 (раннер «по номеру прогона» не различает выписки), В5 (красный перепрогона — по записи теста или по прогону), Д1 (долгоживущие сценарии components+report через новый гейт).

## Чего не хватило
- Нет.
