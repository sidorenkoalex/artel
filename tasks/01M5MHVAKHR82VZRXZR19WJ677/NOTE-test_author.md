# Записка test_author

## Выяснено
- AC-1, AC-2 — долгоживущий `tests/test_01m5mhvakhr82vzrxzr19wj677_dead_definitions.py`;
  AC-3..AC-9 — разовый `acceptance_tests/test_branch_facts.py`. Ветка — файлы
  на диске CODE_ROOT (не HEAD), база — `git show DIFF_BASE:<путь>`; AC-7 —
  `git diff --no-renames --name-status DIFF_BASE -- tests/` по рабочей копии.
- AC-8: карта строится `build_modules`/`render` из `scripts/codebase_map.py` без записи файла
  и сверяется с `docs/codebase-map.md` на диске без строк `built_at_sha:`. Карта включает
  `tests/`, поэтому после добавления долгоживущего файла её нужно перегенерировать.
- До кода: долгоживущий файл красен по 13 парам (AC-1) и только по `retro_rel_path` (AC-2) —
  как и ожидает SPEC. В планке красны AC-4/5/8/9, зелены AC-3/6/7.
- Временный стаб (удаление 13 определений, правка 3 абзацев и комментария над
  VERDICT_RETURN, перегенерация карты): всё зелёное (7 + 2). Ни одного импорта
  при этом удалять не пришлось. Мутация «снят `config` из fixation.py» красит AC-3.
  Стаб откатан `git checkout`, git status чист (кроме моего нового файла tests/).
- preflight: все проверки пройдены.

## Не сработало
- В Bash нет `cat`/`ls`; heredoc с `{'` и `cd …&& git` спрашивают подтверждение — используй
  `git -C` и скрипт-файл.

## Где остановился
Шаг готов к сдаче.

## Чего не хватило
- Не было готового способа пересобрать карту без перезаписи `docs/codebase-map.md` —
  пришлось взять функции модуля `build_modules`/`render`.
