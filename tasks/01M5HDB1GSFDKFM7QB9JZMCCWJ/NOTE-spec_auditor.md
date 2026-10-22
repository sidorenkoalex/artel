# Записка spec_auditor

## Выяснено
- Круг 2 (spec_sha f1e2a7df…): О1–О4 гейта перенесены в SPEC (AC-1 ro-подмена + deliver_journal + mode=ro + полный id; AC-2 позитивная форма; AC-4 --wait 0/--failed под ro).
- Факты о коде снова подтверждены: suite_run.py:771–838, подсказки _pult_command без флагов — :744, :760, :797, :801; role_prompt.py:413/:134, ревьювер внешнего проекта :335; test_ac25 :1441 — подстрока-префикс, останется зелёным.
- readonly_db: role_process :216–222 подменяет store.db на readonly_db и ставит ARTEL_ROLE=self.role.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready, guard ок.
- Остаточные пункты: 1) позитивная часть AC-5 без формы; 2) deliver_journal в случае «уже идёт» не определён (ТЗ п.3 «без новых записей»); 3) матрица ANSWER-1 ссылается на «AC-3 SPEC» старой нумерации (теперь AC-1).

## Не сработало
- `ls`/`$VAR` в Bash недоступны; `git grep -A` — опции до шаблона.

## Чего не хватило
- Ничего существенного.
