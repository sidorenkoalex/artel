# Записка spec_auditor — 01M6TR3Q3SQSS1ZNGA4T7V39RW

## Выяснено
- artel.py:2797-2798 передаёт plank-run только rest[0], rest[1]: `plank-run <id> --wait 5` даёт file_arg="--wait", минуты теряются; artel.py вне зон SPEC.
- Треб. 1 SPEC («запрос несёт время») против треб. 7 («поле сверх вида, файла и id — отказ») — противоречие, унаследовано из ТЗ пп. 1/3.
- «Путь прерванного прогона гейта со снятием стенда» в коде нет: снятие — только finally `_compose_report_run` (acceptance.py:1464-1473); опыт: SIGTERM процессу Python без обработчика finally не исполняет (rc -15). Забытые стенды снимает doctor --fix (doctor/orphans.py:387).
- suite_lock.deferrable (suite_lock.py:212-222) — закрытый перечень; новое действие журнала туда не входит, defer_journal вернёт False.
- Песочница Codex открывает на запись только suite_lock.directory() (providers/codex.py:416-440, вне зон).
- suite-run --wait читает run.json/result.json (suite_run.py:824-857): до взятия запроса исполнителем вернёт итог прошлого прогона или «прогона нет».
- tests/sandbox.py:930-938 FakeProc — только wait(), без poll/pid.

## Не сработало
- Составные bash-команды с cd/переменными отклоняются — только одиночные команды с абсолютными путями.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict fail, guard — ок. Восемь отклонений и замечания перечислены в «Вердикте».

## Чего не хватило
- Явного места «хозяйства пульта задачи» для запросов в SPEC.
