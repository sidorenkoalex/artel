---
operator: Alexander Sidorenko
model: unknown
artel_sha: 1abccfda6dc80f338131d89e93c9e5129bbf15c9
---

# RETRO: 01M6N7CYKDAMAKENX60CBK7VQX — Ручной мерж для GitHub, часть 2: открытие пары github + target-human, проверки записи и строки doctor

Итог: done, sha 67abf32f42ebbbb397988608831d6ef6b486d038
Адрес артефактов: refs/artifacts/01M6N7CYKDAMAKENX60CBK7VQX
Суть: Ручной мерж для GitHub, часть 2: открытие пары github + target-human, проверки записи и строки doctor — Часть 1 (задача 01M6M1799YCY5HXMHHD71SHJET, смержена 05.11) дала `_GitHub` функции MR, но пара `github` + `target-human` по-прежнему закрыта (`orchestrator/targets.py:31-33`, `SUPPORTED_PAIRS = {("github", "operator"), ("gitlab", "target-human")}`).

Стоимость итого: $35.70
  analyst: $7.07, токенов 7101778 (input=140, output=56053, cache_write=582579, cache_read=6463006), провайдер claude, модель claude-opus-5-5
  spec_auditor: $11.55, токенов 19488793 (input=290, output=109297, cache_write=703774, cache_read=18675432), провайдер claude, модель claude-opus-5-5
  test_author: $10.46, токенов 21987891 (input=194, output=124767, cache_write=460503, cache_read=21402427), провайдер claude, модель claude-opus-5-5
  developer: $5.23, токенов 10862563 (input=138, output=36496, cache_write=299448, cache_read=10526481), провайдер claude, модель claude-opus-5-5
  reviewer: $1.38, токенов 1582293 (input=28, output=11059, cache_write=108657, cache_read=1462549), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: 2 (последняя): test_author: критерий неисполним тестом — AC-9: критерий требует, чтобы `kill` задачи `github` + `target-human` ДО отправки удалял заранее заведённую ветку задачи из `origin` и писал «ветка origin <ветка>: удалена». Это недостижимо в зонах задачи: уборка удаляет ветку отправкой `push --delete` через `gitcmd.in_repo` с `-c http.lowSpeedLimit…` (`orchestrator/cleanup.py:253-276`), а белый список отправок любой записи с `merge_gate` не `operator` отказывает и глобальной опции `-c` перед push, и `--delete` чего-либо, кроме `refs/artifacts/<id>` (`orchestrator/gitcmd.py:836-841`, `:866-876`); `orchestrator/gitcmd.py` по SPEC («Не входит») — только для чтения. Прогон на стенде подтверждает: GitLab с `target-human` сегодня пишет «ветка origin <ветка>: оставлено — отказ: отправка отказана (проект …): глобальная опция git -c перед push», ветка в `origin` остаётся. Вопрос Оператору (блокирует AC-9, прочие критерии не блокирует): (A) открыть `orchestrator/gitcmd.py` для правки белого списка — разрешить `push --delete refs/heads/<ветка>` ветки задачи проекта, уходящей в `killed`, без `-c` (зона и инвариант белого списка — решение Оператора); (B) переписать AC-9 «до отправки»: ветка в `origin` остаётся, запись «уборка» несёт прежний исход удаления «ветка origin <ветка>: …» (отказ белого списка) и «PR не тронут: MR вливают люди проекта», `gh pr close` не вызван; (C) до отправки уборка проекта людей ветку origin не трогает вовсе, запись — только «PR не тронут: MR вливают люди проекта». Дефолт при молчании — (B): совпадает с прежним поведением GitLab (AC-10 «записи прежние») и не трогает белый список. Части AC-9 «после отправки» и `github` + `operator` от ответа не зависят; их тесты готовы (записка шага, приложение).

Приёмочные тесты: 5 тест(ов), 0 manual, 0 skip
