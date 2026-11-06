---
operator: Alexander Sidorenko
model: unknown
artel_sha: c0528d57fe7c464c648bfe289ab656c0b920422a
---

# RETRO: 01M6RB78H213K6EGXSE83PB5GX — kill: удаление ветки задачи в origin проекта под белым списком отправки

Итог: killed — причина: kill switch: решение Оператора 06.11: посылка ТЗ неверна — белый список отправки намеренно запрещает --delete ветки задачи у проекта с мержем людьми (ADR-0029; tests/test_01m6n7cykdamakenx60cbk7vqx_people_flow.py:904); отказ «-c перед push» был у ветки, которой в origin не было, — удалять было нечего
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: kill: удаление ветки задачи в origin проекта под белым списком отправки — --- task: 01M6RB78H213K6EGXSE83PB5GX type: tz author_role: operator status: draft schema_version: 2 --- # ТЗ: kill: удаление ветки задачи в origin проекта под белым списком отправки # kill: удаление ветки задачи в origin проекта под белым списком отправки ## Факты 1. `kill` задачи внешнего проекта удаляет ветку задачи в origin (`cleanup_project_remote`, `orchestrator/cleanup.py:284`; `_delete_origin_branch`, `:265-281`) вызовом `_bounded` (`:258-262`), который добавляет перед `push` глобальные опции `-c http.lowSpeedLimit=1 -c http.lowSpeedTime=<config.GH_TIMEOUT_SEC>` — предел времени отправки. 2.

Стоимость итого: $2.49
  analyst: $1.06, токенов 1155368 (input=26, output=8104, cache_write=85737, cache_read=1061501), провайдер claude, модель claude-opus-5-5
  spec_auditor: $1.43, токенов 1866907 (input=40, output=15185, cache_write=96587, cache_read=1755095), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: 1 (последняя): эскалация от аудитора SPEC

Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
