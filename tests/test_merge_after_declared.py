"""Юнит-тесты заявленных зависимостей мержа в `orchestrator/merge_after.py`
(SPEC 01M45D29BQJE8FJYJA4JQWSYFZ) — углы, не покрытые долгоживущими файлами
задачи `tests/test_01m45d29bqje8fjyja4jqwsyfz_*.py`: метка не с первой
позиции и слово, лишь начинающееся с «после», пустой перечень, явный target
ещё не заведённой задачи, повторный приход на гейт SPEC после его прохода,
обоснование коротким префиксом внутри чужого id.
"""
from orchestrator import config, idgen, merge_after, store
from tests.sandbox import LightTransitionSandbox

OTHER_TARGET = "proekt"


class DeclaredSandbox(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        self.conn = store.db()

    def insert(self, state: str, target: str = config.DEFAULT_TARGET) -> str:
        task_id = idgen.new_task_id()
        store.insert_task(self.conn, task_id, f"Фикстура {task_id}", state,
                          f"task/{task_id.lower()}-x", target,
                          config.DEFAULT_BUDGET_USD)
        return task_id


class DeclaredFromTzTest(DeclaredSandbox):

    def test_label_must_start_line_and_word_must_be_whole(self):
        """Метка с отступом и «Порядок: послезавтра» зависимостей не заявляют.

        Ловит мутацию: метка ищется в любом месте строки (без `^`) либо
        слово «после» сверяется префиксом — элемент «завтра …»/строка с
        отступом дают перечень или отказ формы.
        """
        dep = self.insert("in_dev")
        for tz in (f"  Порядок: после {dep}\n",
                   f"Порядок: послезавтра {dep}\n"):
            with self.subTest(tz=tz):
                self.assertEqual(merge_after.declared_from_tz(
                    self.conn, tz, config.DEFAULT_TARGET), ([], []))

    def test_empty_list_is_refused(self):
        """«Порядок: после» без id до скобки — отказ, а не молчаливое «зависимостей нет».

        Ловит мутацию: пустой перечень возвращается как ([], []) — `new`
        заводит задачу, хотя строка заявляет зависимость.
        """
        ids, reasons = merge_after.declared_from_tz(
            self.conn, "Порядок: после (уточню позже)\n", config.DEFAULT_TARGET)

        self.assertEqual(ids, [])
        self.assertTrue(reasons)

    def test_explicit_target_of_new_task_is_used(self):
        """Зависимость того же не-основного target, что у заводимой задачи, проходит.

        Ловит мутацию: `check` берёт target из строки БД несуществующей
        задачи (`store.task_target` — target по умолчанию) — зависимость
        target'а `proekt` отказана как чужая.
        """
        dep = self.insert("in_dev", target=OTHER_TARGET)

        self.assertEqual(merge_after.declared_from_tz(
            self.conn, f"Порядок: после {dep}.\n", OTHER_TARGET), ([dep], []))


class SpecGateDeclaredRefusalTest(DeclaredSandbox):

    def spec_text(self, section: str) -> str:
        return (f"# SPEC\n\n## Обоснование зависимостей мержа\n\n{section}\n\n"
                f"## Критерии приёмки\n")

    def test_no_check_after_spec_gate_was_passed(self):
        """После прохода гейта SPEC колонка — рабочее значение, сверки с ним нет.

        Сценарий: колонка несёт зависимость, журнал задачи — переход
        `state -> tests_writing`; поле SPEC её не несёт.

        Ловит мутацию: признак «гейт SPEC уже пройден» снят — повторный
        approve отказывает как теряющий заявленную.
        """
        dep = self.insert("in_dev")
        store.update_task(self.conn, self.TASK, merge_after=dep)
        t = store.get_task(self.conn, self.TASK)
        self.assertIsNotNone(merge_after.spec_gate_declared_refusal(
            self.conn, self.TASK, t, {}, None, "")[1])

        store.journal(self.conn, self.TASK, "operator", "state -> tests_writing",
                      "гейт SPEC пройден")

        self.assertEqual(merge_after.spec_gate_declared_refusal(
            self.conn, self.TASK, t, {}, None, ""), ([], None))

    def test_short_prefix_inside_other_id_is_not_justification(self):
        """Префикс добавки, встречающийся только внутри чужого id в разделе, обоснованием не считается.

        Ловит мутацию: обоснование ищется подстрокой, а не словом целиком —
        добавка, не названная в разделе, принимается.
        """
        declared = self.insert("in_dev")
        added = self.insert("in_dev")
        shared = 0
        while declared[shared] == added[shared]:
            shared += 1
        prefix = added[:shared + 1]
        store.update_task(self.conn, self.TASK, merge_after=declared)
        t = store.get_task(self.conn, self.TASK)
        meta = {merge_after.FIELD: f"{declared}, {prefix}"}
        # Раздел называет только заявленную, но с хвостом, где префикс
        # добавки стоит внутри слова.
        text = self.spec_text(f"Заявлена {declared}; см. X{prefix}Y.")

        added_ids, reason = merge_after.spec_gate_declared_refusal(
            self.conn, self.TASK, t, meta, f"{declared}, {added}", text)

        self.assertEqual(added_ids, [])
        self.assertIn(added, reason or "")
