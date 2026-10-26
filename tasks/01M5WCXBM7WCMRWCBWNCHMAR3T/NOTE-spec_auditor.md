# Записка spec_auditor

## Выяснено
- Визит 3 (spec_sha 3f74f0df…): решения гейта №2 перенесены — ключ `entry.get("ci_required_jobs") or []` (SPEC :126-131, AC-23), AC-21 с сравнением результата `forge` и членством в реестре, AC-24…AC-32 на MR/чтение.
- Строки ci.py/targets.py/gitcmd.py/github_adapter.py из SPEC сходятся с HEAD 5705cfdf8.
- Остаток: AC-21 и сторож А0 смотрят только `ast.Compare` → `match/case "gitlab"`, промежуточная переменная, второй словарь в ci.py проходят. Малые: пустое множество failed_check_names на красном конвейере без упавших заданий; AC-32 без двух конвейеров в фикстуре.
- SPEC Б1 (refs/artifacts/01M5WDB7F1…, :67, :238) ключ плоской записи всё ещё не называет — не отклонение А1.1.

## Не сработало
- `ls` в оболочке нет (command not found).

## Где остановился
- SPEC-AUDIT.md: status ready, verdict concerns; guard прогнан.

## Чего не хватило
- Ничего существенного.
