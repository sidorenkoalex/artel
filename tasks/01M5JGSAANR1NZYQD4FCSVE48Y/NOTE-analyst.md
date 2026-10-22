# Записка analyst

## Выяснено
- Круг 3 (возврат spec_gate 22.10, круг 2, 7 решений): SPEC переписан, 28 AC, status ready, guard ок.
  - п.1: в таблицу мест добавлены advance_gates/review.py:209 (заявка мутации, строка tests_writing.py/zones.py заменена), advance_gates/acceptance.py:73 (long_lived_manifest + вызывающие fsm_autogate:107, pull:648, amend:525, acceptance:117/:632, review:332), :111, :561, zones.py:287, test_integrity.py:1299 (_external_helpers — отказ, без отката), :1756, fsm_advance.py:318, :519, fsm_merge_gate.py:1393, acceptance.py:3360 (full_suite_limit → TargetsError у multi при не-компонентной команде). Покрытие — AC-9/AC-22.
  - п.2: fsm_merge_gate.py:1093 — наибольший component_limit по _selected_components; AC-27. Замечание: у multi command там — кортеж профилей, ветка :1085 срабатывает раньше; :1093 фактически достижима только при не-кортеже.
  - п.3: :858/:912 помечены «недостижимо», исключены из обещания AC-22; :912 = checks_local (:926).
  - п.4: AC-13/AC-14 — отрицательные случаи (frontend без report / канарейка).
  - п.5: запись пропуска — `SKIP_ACTION` «проверка тестов не выполняется: гейт неослабления по исходам», деталь «голова <sha>» + строки компонентов; review_lines — NOT_RUN_LINE + строки «гейт исходов: компонент …». Привязка к голове — мой вывод для проверяемости.
  - п.6: требование 4 — граница по компоненту-владельцу X; X вне границы — не проверяется (AC-28).
  - п.7: матрица +4 строки (автогейт, _external_helpers, мандат, :1093).

## Не сработало
- Bash: `$?`, `${}` и циклы в команде требуют подтверждения — только простые grep/Read.

## Где остановился
- SPEC.md сдан (ready), guard ок.

## Чего не хватило
- Полный перечень мест: `grep -rn "project_profile\.decide(\|profile_of(\|full_suite_limit(\|for_task(" orchestrator/`.
