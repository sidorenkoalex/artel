# Записка test_author — 01M6TT4FKD1JWSJFVJ7328K03Y

## Выяснено
- Планка: acceptance_tests/test_ci_base_push.py (разовый) — AC-10, AC-11, AC-12, AC-14 (белый список/хук/политика).
  Разовый, т.к. guard (`scripts/guard.py:4134`, «git-модуль»/«git-вызов») не пускает `gitcmd` и
  `subprocess`-git в долгоживущий файл, а предмет — сама единая точка отправки.
- Долгоживущие (кодовая ветка): tests/test_01m6tt4fkd1jwsjfvj7328k03y_ci_base_gate.py (AC-1..AC-8, AC-14 гейт),
  _fields.py (AC-9, локальный слой description.components), _doctor.py (AC-13, AC-14 doctor).
- Гейт-тесты — `VerifyingBox` из tests/test_01m6bmg29kzv1rx21hfaxzg3cm_verifying_outcome_gate.py, плоская
  запись repo-слоя (gitlab+operator, без белого списка), `push_options` в плоской записи; голый origin с
  `receive.advertisePushOptions=true` (иначе `-o` отвергается). Отказ белого списка — подмена
  `targets.push_whitelisted` на «да» (адрес origin клона ≠ url записи).
- AC-8: `approve` отказывает паре gitlab+operator до гейта → тест зовёт `outcome_integrity.merge_gate_escalates`.
- AC-6 «подменённые часы» — сдвиг `steps.ts` первой задачи старше `VERIFYING_CEILING_SEC`.
- Валидация стабом (удалён `git checkout --`): все 63 теста зелёные; мутации пойманы: проверка по
  локальной ссылке, хук не пропускает, policy.push_options в отправке, нет очереди, давность не
  учитывается, эскалация при отказе отправки, ожидание при окончательной негодности.
- Без стаба: краснота везде — «неизвестное поле 'ci_base'»; зелёные с рождения — записи без ci_base.
- preflight: все проверки «пройдена».

## Не сработало
- Многооператорные bash-команды и mkdir/cp недоступны — копирование через python3 -c, правки — Edit.

## Где остановился
- Шаг завершён: планка и долгоживущие файлы готовы, стаб удалён, рабочая копия — только 3 новых файла tests/.

## Чего не хватило
- Правило «долгоживущий без gitcmd» отрезает тесты самой точки отправки — в скиле не сказано, куда их класть.
