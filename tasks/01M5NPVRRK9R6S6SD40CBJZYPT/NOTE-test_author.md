# Записка test_author — 01M5NPVRRK9R6S6SD40CBJZYPT

## Выяснено
- Все AC-1…AC-7 — свойства кода `pull.evaluate` → один долгоживущий файл
  `tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py`, в
  `acceptance_tests/` черновика файлов нет (планка целиком долгоживущая;
  preflight — все проверки пройдены; plank-run отвечает «планки нет» —
  ожидаемо, перечень сумм пульт кладёт на выходе).
- Вход — публичный `pull.evaluate` на настоящем git
  (GitignoreCommittedRealGitSandbox, образец
  `tests/test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix.py`); документы —
  `checkpoint.commit_step_artifacts` (роль developer), лок —
  `tests_locked_sha` = голова ссылки документов.
- Сбой git (AC-3, fixable=False) — обёртка `git` первой в PATH, отказ на
  `worktree add` (патч gitcmd в долгоживущем файле запрещён).
- На текущем коде: красны ac1, ac3, ac4, ac5, ac6, ac7 (планка в рабочей
  копии без правок приложений); ac2 зелёный с рождения.
- Стаб (suite_tree + отказ по fixable + plank_in_code_copy при
  tree.root != wt_path) — 7/7 зелёные на 3 зёрнах, стаб снят
  (`git checkout -- orchestrator/pull.py`).

## Не сработало
- Составные Bash-команды с `;`/циклами требуют подтверждения — по одной.

## Где остановился
- Готово: файл тестов написан, провалидирован, preflight пройден.
- Карту `docs/codebase-map.md` не регенерировал (правка вне tests/ у
  test_author откатывается) — регенерирует разработчик.

## Чего не хватило
- Не было явно сказано, можно ли сдать планку без `acceptance_tests/test_*.py`
  (целиком долгоживущую); ответ дал preflight.
