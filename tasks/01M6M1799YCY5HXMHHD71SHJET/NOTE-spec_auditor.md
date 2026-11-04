# Записка spec_auditor

## Выяснено
- Визит 2 (spec_sha 481831b0…): факты SPEC о коде подтверждены по HEAD 89698bf92 (forge.py:69-84/127-212, ci.py:69-98, github_adapter.py:107-115/342/372-381/402-458, fsm_merge_gate.py:1587-1590/1672-1714/1840-1908, mr_sync.py:38/53/306-359, repo_context.py:91/97, тест GH_CALLS :370-383, метод :1189-1202).
- Существующие тесты не ломаются: ExistingLinkTest (test_mr_delivery_units.py:79-122) патчит targets.target без `forge` → «хостинг не определён» → прежнее поведение (требование 8 это покрывает); подделки реестра (mr_delivery.py:328-386, test_invariants.py:627-637) без ASSIGNEE_BY_NAME; hosting_registry.py:32 — у _GitHub по-прежнему нет job_test_report.
- Решения 1-9 гейта учтены.
- Новые отклонения: разбор адреса PR «<адрес проекта>/pull/<n>» ломается на url с `.git`/`/`/scp (ci.py:101-107 эти виды допускает); AC-14 не ловит «разрешённая форма + хвост» (`pr ready 7 --undo`) и недесятичный номер; artel-цель в github_call (remote "origin").

## Не сработало
- `command -v gh` в песочнице роли требует подтверждения — поведение gh опытом не проверено.

## Где остановился
SPEC-AUDIT.md: verdict concerns, status ready.

## Чего не хватило
Живого `gh` для сверки вывода `pr create` (вид адреса при url с .git/scp).
