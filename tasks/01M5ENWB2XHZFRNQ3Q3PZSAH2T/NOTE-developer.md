# Записка developer

## Выяснено
- Правка только в orchestrator/brief.py (`_project_conventions_parts` и помощники).
- project_profile импортируется внутри функции: на уровне модуля круговой импорт
  brief → project_profile → acceptance → suite_lock → knowledge_cards → brief.

## Не сработало
- `cd … ; sed` в Bash требует подтверждения — читать Read-ом.

## Где остановился
- Код в brief.py готов (`_tree_entries`, `_read_blob`, `_knowledge_of`,
  `_knowledge_parts`, `_knowledge_dir_parts`); долгоживущий файл 24/24 зелёный,
  тесты брифа/ревью/knowledge зелёные; карта регенерирована.
- suite-run №1: зелёный (6282 прошло, 0 упало, 2 пропущено). guard ок,
  PLAN status: ready. Шаг завершён; код оставлен незакоммиченным для пульта.
- Толкования, записанные в PLAN: n «не обычных файлов» — все ссылки/подмодули
  под каталогом (не только *.md); M — число отобранных после повторов и
  предела, номер k сохраняется и у файла с ошибкой чтения.
- plank-run отказывает «планки нет» — ожидаемо, acceptance_tests/ нет.

## Чего не хватило
- Ничего существенного: долгоживущий файл и докстринг project_profile хватило.
