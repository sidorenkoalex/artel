---
task: 01M5G6PDQA7AYDYDPA7DD5JD4S
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-3: ответ Оператора

## Ответы

Ответ Оператора на эскалацию test_author (AC-7, AC-8): вариант A.

На Darwin test_ac9_timeout_kills_group_not_green (и test_ac3 timeout_integrations) ждёт прежним select.select на исходном дескрипторе; ожидание через selectors/poll и перенос на дескриптор ≥ 1100 — вне Darwin (sys.platform != "darwin"). AC-7 и AC-8 уточняются «вне Darwin»: свойство держит CI на Linux (оба задания, python и python-min). На Darwin функция ожидания не меняет прежнего поведения; тест функции ожидания на Darwin проверяет, что выбран прежний путь (select.select), а вне Darwin — poll/selectors на дескрипторе ≥ 1100 с закрытым исходным. Пропуск теста на Darwin (вариант B) и смена канала FIFO (вариант C) — нет. Корень сбоя на CI — утечка дескрипторов БД (store.py) — чинится в этой же задаче независимо от платформы.
