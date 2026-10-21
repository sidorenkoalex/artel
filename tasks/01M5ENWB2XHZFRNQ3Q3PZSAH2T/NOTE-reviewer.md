# NOTE reviewer, итерация 1

## Выяснено
- Планки в refs/artifacts нет (plank-run: «нет файлов test_*.py»); проверка — долгоживущий tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py: 24 passed, 53 subtests.
- Соседние тесты (external_brief, review_conventions, test_brief) — 46 passed.
- Мутация «ls-tree без -z» красит AC-7; карта кода свежа.
- Вердикт approved, реестр пуст; наблюдения (M включает нечитаемый файл каталога; irregular — все ссылки/подмодули) — не дефекты.

## Не сработало
- /bin/ls каталога документов требует подтверждения; $(...) в Bash тоже.

## Где остановился
- REVIEW.md записан (approved).

## Чего не хватило
- Указания, чем заменить plank-run, когда у задачи только долгоживущий файл в tests/.
