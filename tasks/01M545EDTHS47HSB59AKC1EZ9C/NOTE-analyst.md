# Записка analyst

## Выяснено
- ТЗ ссылается на SPEC родителя 01M53B45XW3J56RJHGD70TD8A2: `git show refs/artifacts/01M53B45XW3J56RJHGD70TD8A2:tasks/01M53B45XW3J56RJHGD70TD8A2/SPEC.md`.
- Шаг 2 (возврат с spec_gate 17.10): внесены О-1…О-5, Ф-1, Т-1…Т-5. Добавлены AC-12 (только remote-подкоманды; -C каталога проекта без токена), AC-13 (URL push = url записи), AC-14 (check_base_branch), AC-15 (verifying_status/trigger_rerun с repo=), AC-16 (запись без token_slot — прежняя авторизация, warn «нет токена проекта», sandbox-подмена keychain.token). AC-1 расширен исключением .artel/projects/artel/ и config.ROOT; AC-3 — без `git config --get-all`, GIT_CONFIG_GLOBAL не подменяется; AC-10 — два случая распознавания роли (ARTEL_ROLE и HOME дома роли, runner.py:1116-1133).
- trigger_rerun (ci.py:1221) сейчас вовсе не передаёт repo= в gh — AC-15 сформулирован «в вызовах ci.gh с repo=», буквально по решению Оператора.
- _push_closing_sha — artifact_branches.py:126-146 (push на :137, вызов из главной копии :174).

## Не сработало
- Bash с `$`-подстановками в команде шагу запрещён («Contains expansion»).

## Где остановился
- SPEC переписан, status: ready, guard ок. 16 AC, budget 45 оставлен (рамка ТЗ).

## Чего не хватило
- Ничего существенного; номера строк runner.py в причине возврата (1067-1068) не совпали с main — функция на 1116.
