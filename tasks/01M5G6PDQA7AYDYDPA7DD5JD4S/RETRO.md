---
operator: Alexander Sidorenko
model: unknown
artel_sha: 9ef82fbaaeb40e1e50343f17ce5e30b87fb10d7b
---

# RETRO: 01M5G6PDQA7AYDYDPA7DD5JD4S — Неустойчивые тесты: зерно двустороннего наблюдения, select() и утечка дескрипторов БД, допуск времени kill

Итог: done, sha 33547d9af0cf6f0187f3d6ea5f206b279e55d696
Адрес артефактов: refs/artifacts/01M5G6PDQA7AYDYDPA7DD5JD4S
Суть: Неустойчивые тесты: зерно двустороннего наблюдения, select() и утечка дескрипторов БД, допуск времени kill — Три теста падают не при каждом прогоне, причины разные (разбор 22.10 в ТЗ). (1) `test_ac1_outcome_carries_relative_assertion_location` (`tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_two_sided_observation.py:549`) падает на зёрнах, где сдвиг `new` равен 7 и `new == bare_old` (доля 1/3999, зерно 189949286) — дефект теста, `two_sided.run` прав. (2) `VitestReporterTest::test_ac9_timeout_kills_group_not_green` (`tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1248`) падает `ValueError: filedescriptor out of range in select()`: соединения `store.db()` (`orchestrator/store.py:331`) в CPython 3.11+ входят в цикл ссылок (кэш выражений — `functools.lru_cache` вокруг соединения), их `__del__` (`orchestrator/store.py:281`) срабатывает только при сборке циклов, и в исполнителе xdist копится больше 1024 дескрипторов — дефект кода пульта; вместе с ним в двух тестах заменяется `select.select`. (3) `SilentHostingTest::test_ac6_silent_gh_and_origin_bounded_and_noted` (`tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py:570`) сравнивает настенное время `kill` с допуском 14 с, под нагрузкой — 14,2 с.

Стоимость итого: $37.35
  analyst: $7.24, токенов 5944087 (input=122, output=71670, cache_write=586448, cache_read=5285847), провайдер claude, модель claude-opus-5-5
  spec_auditor: $7.81, токенов 10029145 (input=180, output=98981, cache_write=493310, cache_read=9436674), провайдер claude, модель claude-opus-5-5
  test_author: $8.72, токенов 15324832 (input=200, output=153611, cache_write=335341, cache_read=14835680), провайдер claude, модель claude-opus-5-5
  developer: $2.69, токенов 35711031 (input=388, output=16950, cache_write=748683, cache_read=34945010), провайдер claude, модель claude-opus-5-5
  reviewer: $1.89, токенов 1666967 (input=42, output=20683, cache_write=146764, cache_read=1499478), провайдер claude, модель claude-opus-5-5

Ревью: 1 итераций; приёмка: 0 отказ(ов)

Эскалации: 3 (последняя): test_author: критерий неисполним тестом — AC-7: на macOS (машина пульта, где идут планка и полный набор пульта) select.poll и kqueue (selectors.DefaultSelector) не сообщают EOF именованного канала (FIFO) — проверено: после закрытия писателя poll/kqueue пусты, select.select видит готовность; test_ac9_timeout_kills_group_not_green ждёт именно EOF FIFO, и с ожиданием через poll/DefaultSelector он локально красен «потомок раннера пережил таймаут» при любой реализации. Как быть: (A) на Darwin test_ac9 ждёт прежним select.select на исходном дескрипторе, а poll/DefaultSelector и перенос на ≥ 1100 — вне Darwin (свойство держит CI Linux; AC-7/AC-8 уточняются «вне Darwin»); (B) test_ac9 на Darwin пропускается (skipIf) с причиной; (C) канал test_ac9 меняется с FIFO на иной (правка фикстуры ReportSandbox без смены имён и сигнатур AC-10)? Дефолт — (A).; AC-8: тот же вопрос, что AC-7: на macOS ожидание EOF FIFO через poll/kqueue на дескрипторе ≥ 1100 не наступает (select.select на ≥ 1024 — ValueError), test_ac9 при выполненном AC-8 красен на машине пульта; черновик теста ниже (draft_ac8_…) прогнан стабом — красен именно этим. Применять AC-8 только вне Darwin (дефолт, вариант (A) AC-7), пропускать test_ac9 на Darwin (B) или сменить канал (C)?

Приёмочные тесты: 23 тест(ов), 0 manual, 0 skip
