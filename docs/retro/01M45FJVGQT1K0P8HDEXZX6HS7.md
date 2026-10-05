# RETRO: 01M45FJVGQT1K0P8HDEXZX6HS7 — Этап 3 ADR-0021, часть 1 из 3: профиль тестов проекта и проверки тестов на repo_context

Итог: done, sha ea074d0f921969311957e5b952fb7202f53e26d5
Адрес артефактов: ea074d0f921969311957e5b952fb7202f53e26d5:tasks/01M45FJVGQT1K0P8HDEXZX6HS7/
Суть: Этап 3 ADR-0021, часть 1 из 3: профиль тестов проекта и проверки тестов на repo_context — Проверки тестов пункта 8 ADR-0021 (неослабление тестов, «Ловит мутацию», долгоживущие файлы, строки группы, перечень сумм) сегодня включаются сравнением `target` с `config.DEFAULT_TARGET` или признаком `repo_context.is_artel`.

Стоимость итого: $80.10
  analyst: $3.32, токенов 3855627 (input=72, output=36873, cache_write=232766, cache_read=3585916), провайдер claude, модель claude-opus-5-5
  test_author: $11.21, токенов 26495692 (input=218, output=143286, cache_write=393651, cache_read=25958537), провайдер claude, модель claude-opus-5-5
  developer: $20.52, токенов 218615286 (input=1714, output=174625, cache_write=2643395, cache_read=215795552), провайдер claude, модель claude-opus-5-5
  reviewer: $2.83, токенов 3166347 (input=54, output=21842, cache_write=226392, cache_read=2918059), провайдер claude, модель claude-opus-5-5

Ревью: 1 итераций; приёмка: 0 отказ(ов)

Эскалации: 2 (последняя): эскалация от разработчика: **Вопросы** (по блокирующести):…

Приёмочные тесты: 33 тест(ов), 0 manual, 0 skip

Приложения Оператора применены: targets.yaml, tests/test_invariants.py
