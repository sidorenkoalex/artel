# Записка developer — 01M6ZEMZB8Q1PKRXMJBJSTPR7T

## Выяснено
- Реализация (config.py, acceptance.py, tests/sandbox.py) — в ветке с прошлых шагов, не менялась.
- По мандату ANSWER-2 в tests/test_01m4xrcmd4fr2zbwyxf5774yvd_timeout_integrations.py строка 65
  `run_real` заменена помощником `assert_prefix_admitted` (pycache_source + template_admits с
  исключённым self.root, ни одного исходника под self.root; пустой префикс проходит). Добавлены
  `import site` и заявка мутации в докстринг test_ac1. Файл: 3 passed; с залоченным pycache — 9 passed.
- Мутация «в префикс копируется байткод self.root/tests/test_case.py» (_copy_into) — test_ac1 красный; код возвращён.
- Карта перегенерирована. PLAN.md status: ready, раздел «Эскалация» заменён «Ответ Оператора (ANSWER-2)».

## Не сработало
- guard.py на каталоге документов падает «Is a directory» — передавать путь PLAN.md файлом.

## Где остановился
- Шаг сдан: PLAN ready. Замер требования 12 — на приёмке у Оператора (ANSWER-2, ответ 2).

## Чего не хватило
- Ничего существенного.
