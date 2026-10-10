---
operator: Alexander Sidorenko
model: unknown
artel_sha: c6c9245c4a2674e96c075bea34be43171e36a2df
---

# RETRO: 01M4JN2EDQP8Q3WVYK0TS95ZVC — Сетевые адреса в tests/ — пульт ловит до CI

Итог: done, sha c6c9245c4a2674e96c075bea34be43171e36a2df
Адрес артефактов: refs/artifacts/01M4JN2EDQP8Q3WVYK0TS95ZVC
Суть: Сетевые адреса в tests/ — пульт ловит до CI — Инвариант 35 (адресов `http(s)://<DNS-имя>` в `tests/**/*.py` нет, кроме `localhost`/`127.0.0.1` и именованных исключений) живёт только в защищённом `tests/test_invariants.py::NoNetworkAddressesInTestsTest` (~1877: `_URL_RE` ~1894, `_EXEMPT_HOSTS` ~1895, `_EXCEPTIONS` ~1900–1919, `_host_of`, `_dns_addresses`) и краснеет только в CI ветки, уже после шага разработчика.

Стоимость итого: $11.32
  analyst: $0.77, токенов 615334 (input=18, output=7293, cache_write=64537, cache_read=543486), провайдер claude, модель claude-opus-5-5
  test_author: $2.14, токенов 2958838 (input=66, output=33692, cache_write=112686, cache_read=2812394), провайдер claude, модель claude-opus-5-5
  developer: $6.79, токенов 15171998 (input=236, output=70950, cache_write=300633, cache_read=14800179), провайдер claude, модель claude-opus-5-5
  reviewer: $1.63, токенов 1762545 (input=52, output=17554, cache_write=118894, cache_read=1626045), провайдер claude, модель claude-opus-5-5

Ревью: 1 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 5 тест(ов), 0 manual, 0 skip
