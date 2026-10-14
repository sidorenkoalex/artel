---
operator: Alexander Sidorenko
model: unknown
artel_sha: f44c261290294a0113cef94b21b0e87645f2668c
---

# RETRO: 01M4VBTTH9TT5R74W2ZGKKYZK2 — DoctorDurationTest: точная граница калибровки и устойчивость к нагрузке

Итог: done, sha daec84553c0951b8ddb9c46573c0e308d7319057
Адрес артефактов: refs/artifacts/01M4VBTTH9TT5R74W2ZGKKYZK2
Суть: DoctorDurationTest: точная граница калибровки и устойчивость к нагрузке — `DoctorDurationTest` неверно считал размер новой серии после смены числа workers: первая запись уже входила в серию, а последующий цикл добавлял ещё восемь.

Стоимость итого: $14.89
  analyst: $2.88, токенов 4884909 (input=598521, output=70324, cache_write=0, cache_read=4216064), провайдер codex, модель gpt-5.6-terra
  spec_auditor: $9.90, токенов 12955317 (input=258, output=114765, cache_write=645406, cache_read=12194888), провайдер claude, модель claude-opus-5-5
  test_author: $0.58, токенов 1412950 (input=84382, output=15160, cache_write=0, cache_read=1313408), провайдер codex, модель gpt-6-sol
  developer: $1.22, токенов 4528000 (input=98701, output=13811, cache_write=0, cache_read=4415488), провайдер codex, модель gpt-6-sol
  reviewer: $0.31, токенов 645725 (input=60481, output=5916, cache_write=0, cache_read=579328), провайдер codex, модель gpt-5.6-terra

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: 1 (последняя): analyst: батч вопросов по ТЗ — ветка refs/artifacts/01M4VBTTH9TT5R74W2ZGKKYZK2:tasks/01M4VBTTH9TT5R74W2ZGKKYZK2/QUESTIONS.md

Приёмочные тесты: 6 тест(ов), 0 manual, 0 skip
