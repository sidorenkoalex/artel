# Записка spec_auditor — 01M5PWFGJQNV8YSAN5MF0CKHVW

## Выяснено
- Ссылки SPEC на код (mutation_run.py:51, :122, :440, :599, :657, :683, :704, :785–795; config.py:243; claude.py:193–194; guard.py:3470; artel.py:186–187) верны.
- Требование 5 (копия таблицы в каталоге документов) опрокидывает два существующих теста, которые требуют, чтобы каталог документов после прогона был байт в байт прежним:
  tests/test_01m5p2bhx6m16xxm0tsvww9hem_mutation_run_table.py:672–712 (test_ac8_docs_dir_and_artifacts_ref_untouched; в его «Ловит мутацию:» прямо названа копия mutation-run-<n>.tsv)
  и tests/test_01m5npkpwfewtymbywvr797am6_mutation_run.py:1118, 1170 (IsolationTest.test_ac6, ключ "docs" снимка).
  SPEC обещает «существующие тесты не правятся» — противоречие; правка снимка = ослабление, нужен мандат Оператора.
- Инвариант допуска роли к команде: artel.py:2185–2188 («mutation-run … документы … не меняет», SPEC 01M5NPKP… треб. 10) — после задачи станет ложным, а зона artel.py ограничена строкой «Команды:».
- config.py:241–242: одно ожидание ≤ 10 мин вызова инструмента роли; --wait-lock 9 + --wait 9 в одном вызове = 18 мин; SPEC о сочетании молчит.

## Где остановился
SPEC-AUDIT.md: verdict fail, status ready.

## Чего не хватило
Поиск по tests/ литералов снимаемого поведения (docs_dir/snapshot) — то, что аналитик пропустил; находится grep "docs_dir" по tests/test_*mutation_run*.py.
