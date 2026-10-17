# Записка analyst

## Выяснено
- ТЗ ссылается на SPEC родителя 01M53B45XW3J56RJHGD70TD8A2: `git show refs/artifacts/01M53B45XW3J56RJHGD70TD8A2:tasks/01M53B45XW3J56RJHGD70TD8A2/SPEC.md`.
- Шаг 3 (второй возврат с spec_gate 17.10, повторный аудит): внесены З-1 (исключение из признака по -C: config.ROOT вне config.PROJECTS и .artel/projects/artel/; признак URL push независим от пути — треб.1, 8, AC-1, AC-11, AC-13), Ф-1 (AC-15 о verifying_status/trigger_rerun снят → «Не входит»), М-1 (треб.9: подмена keychain.token отдаёт test-token-<слот> для любого слота; фикстуры sandbox.py:1057-1065 не меняются), Ф-2 (треб.8: главная копия источником только у артели, artifact_branches.py:171-174; AC-11 — прямой вызов _push_closing_sha), AC-16 → тест на саму подмену (часть «без token_slot» осталась как AC-15), AC-8 5.3 формы on: строка/список/отображение, 5.6 — warn.
- Итого 16 AC, нумерация сквозная; budget 45 не менялся.

## Не сработало
- Bash с `$`-подстановками в команде шагу запрещён («Contains expansion»).

## Где остановился
- SPEC правлен, status: ready, guard ок.

## Чего не хватило
- Ничего существенного.
