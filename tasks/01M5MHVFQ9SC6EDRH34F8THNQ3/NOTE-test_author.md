## Выяснено
- Все AC — свойства кода, поэтому планка — два долгоживущих файла в tests/, acceptance_tests/ пуст:
  `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly.py` (AC-1…AC-5, требование 4) и
  `tests/test_01m5mhvfq9sc6edrh34f8thnq3_db_readonly_callers.py` (AC-6, AC-7).
- AC-6 проверяется через публичные входы (закрытые имена в долгоживущем файле запрещены):
  `store.db_usable`, `knowledge_cards.cmd_knowledge`, `preflight.cmd_preflight`,
  `suite_run.cmd_suite_run` под ARTEL_ROLE=developer (маршрут
  `_refuse_developer_full_run` → `_readonly_db`), `journal` скрипта через `runpy.run_path`.
  Шпион `store.db_readonly` (autospec) поднимает своё исключение `Opened`; аргументы
  связываются по сигнатуре настоящей функции, так что `path` можно передать и позиционно, и именем.
- Шпион ловит только вызов через атрибут `store.db_readonly` (`from orchestrator import store`);
  `from orchestrator.store import db_readonly` шпион не увидит.
- Проверка стабом сделана: минимальная реализация по требованиям 1–2 → 9 passed; стаб откачен (`git checkout`).
- На текущем коде красные AC-1/2/3/5 (AttributeError), AC-4 (5 копий), AC-6; AC-7 зелёный с рождения.
- preflight: все проверки пройдены.

## Не сработало
- `plank-run` отказывает «планки нет» — acceptance_tests/ пуст по замыслу; долгоживущие файлы гонял pytest напрямую.
- Bash с `;`-цепочкой и `sed -i` требует подтверждения — правил через Edit.

## Где остановился
- Шаг сделан. docs/codebase-map.md не регенерировал: правка вне tests/ test_author откатывается — карту обновит разработчик.

## Чего не хватило
- Ничего существенного.
