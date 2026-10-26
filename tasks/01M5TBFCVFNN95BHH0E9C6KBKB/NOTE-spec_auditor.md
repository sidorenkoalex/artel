# Записка spec_auditor — 01M5TBFCVFNN95BHH0E9C6KBKB

## Выяснено
- Э1 смержен в origin/main (f909b7dd9), в ветке задачи (761b646e9) epics.py нет — читать `git show origin/main:orchestrator/epics.py`.
- Э2а в in_dev, его SPEC — refs/artifacts/01M5TBCY7WTN121S136XP2C6SR.
- Команды эпика Э1 (new/edit/close) идут без lease → вне `deferred_sends` (область открывает только lease.py:375); add/remove — внутри lease задачи.
- Все места требования 15 уже терпят `epic-<id>` по построению (ключ по БД или по началу имени ветки), кроме retro_corpus (frontmatter с operator/model/artel_sha) и счётчиков docs --fetch-all.
- Рамка части деления: budget.apply_division_frame (budget.py:201) — источник operator; budget.py вне зон SPEC.

## Не сработало
- `ls`, перенаправление в /tmp, составные команды с переменными — отказ песочницы; работает `git show origin/main:<путь>` и grep по относительным путям.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns, 10 пунктов; guard ок.
- Главные: область deferred_sends для epic без lease (п.3), AC без миграции и проверки перечней (п.5), рамка как потолок Оператора + budget.py вне зон (п.6), слабые данные AC-12 (п.9).

## Чего не хватило
- Где открывается deferred_sends (только lease.run_locked) — искал grep'ом.
