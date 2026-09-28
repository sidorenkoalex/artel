"""Юнит-тесты синтетического ответа канарейки на эскалацию
(01M3MHBNMT1VDXSRQNV1GX30BV): текст, который
`canary._pass_escalated_with_synthetic_answer` отдаёт каналу ANSWER.

Прежний текст называл номер задачи, которая ВВЕЛА механизм, и «вариант
A» — роль читала его как ответ по другой задаче на развилку, которой в её
вопросах не было: на замере 28.09 это стоило двух прогонов
(20260928T165337Z, 20260928T162501Z). Ни одним тестом `tests/` прежний
текст зафиксирован не был, поэтому здесь фиксируются наблюдаемые свойства
нового: чего в тексте нет (идентификатор задачи, ссылка на вариант,
строки мандата Оператора), что в нём есть дословно (четыре
константы-якоря), куда он адресует допущение и почему он один на все
роли.

Канал записи ANSWER подменяется (`_answer_text`): настоящий
`answer.cmd_answer` требует lease, артефактной ветки и origin — предмет
тестов здесь текст, который канарейка в этот канал отдаёт, а не
устройство канала.
"""
import inspect
import io
import re
import sys
import tokenize
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import canary, config, idgen, store  # noqa: E402
from orchestrator.advance_gates import mandate  # noqa: E402
from tests.sandbox import SchemaConnTmpRootTest  # noqa: E402

TASK = "T930"

#: Состояния, из которых канарейка возвращает задачу синтетическим
#: ответом — по одной agent-роли на каждое (требование 6: текст не
#: ветвится ни по роли, ни по состоянию).
ESCALATED_FROM_STATES = ("spec_writing", "tests_writing", "in_dev", "review")

#: ИМЕНА констант-якорей модуля, не их значения: утверждения требования 4
#: живут в `canary.py` в одном экземпляре, и тест адресует их именем —
#: своя копия фразы была бы вторым экземпляром той же истины.
ANCHOR_NAMES = ("_SYNTHETIC_ANSWER_NO_OPERATOR",
                "_SYNTHETIC_ANSWER_ROLE_DECIDES",
                "_SYNTHETIC_ANSWER_WRITE_ASSUMPTION",
                "_SYNTHETIC_ANSWER_SAME_ANSWER_AGAIN")

#: Алфавит Crockford base32 — внешняя константа спецификации ULID, на
#: которой стоит `orchestrator/idgen.py`; длина берётся от самого
#: генератора, чтобы тест не нёс своего числа символов формата id.
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ID_IN_TEXT = re.compile("(?<![{a}])[{a}]{{{n}}}(?![{a}])".format(
    a=_CROCKFORD, n=len(idgen.new_task_id())))

#: Заголовок вида `## <название>`, названный внутри произвольного текста:
#: `###` и глубже — не он, название обрывается на конце строки, обратной
#: кавычке или кавычке-ёлочке.
_HEADING_IN_TEXT = re.compile(r"(?<!#)##(?!#)[ \t]*([^\n`»\"']+)")


def _template_headings() -> set:
    """Названия разделов `## <название>` всех шаблонов `templates/*.md`.

    Шаблоны читаются из РЕПОЗИТОРИЯ, а не из `config.ROOT`: песочница
    уводит корень во временный каталог, где `templates/` нет вовсе.
    """
    out = set()
    for path in sorted((REPO_ROOT / "templates").glob("*.md")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## ") and not line.startswith("### "):
                out.add(line[3:].strip())
    return out


def _headings_named_in(text: str) -> list:
    """Названия разделов вида `## <название>`, названные внутри `text`."""
    names = []
    for raw in _HEADING_IN_TEXT.findall(text):
        name = raw.strip().strip("`»«\"'.,;:!?()")
        if name:
            names.append(name)
    return names


def _heading_exists(name: str, headings: set) -> bool:
    """Название из текста существует заголовком шаблона: само либо своим
    начальным словом/словами. Текст называет раздел живой фразой («##
    Риски своего артефакта»), а проверяемое свойство — существование
    НАЗВАННОГО раздела, поэтому сверяются начальные словосочетания, а не
    одна только полная фраза."""
    words = name.split()
    return any(" ".join(words[:count]) in headings
               for count in range(len(words), 0, -1))


def _docs_and_comments(func) -> str:
    """Докстринг + комментарии тела функции, БЕЗ строковых литералов: сам
    текст ответа — константа-литерал, и требование 3 различает «номер в
    пояснении для читателя кода» от «номер в тексте, который читает
    роль». Форма пояснения (докстринг ИЛИ комментарий) требованием не
    закреплена — читаем обе."""
    parts = [inspect.getdoc(func) or ""]
    try:
        source = inspect.getsource(func)
    except OSError:  # pragma: no cover — исходник функции всегда на диске
        return parts[0]
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                parts.append(tok.string)
    except (tokenize.TokenError, IndentationError):  # pragma: no cover
        pass
    return "\n".join(parts)


class _CanaryEscalatedTest(SchemaConnTmpRootTest):
    """Канареечная задача в `escalated` и перехват канала ANSWER."""

    def setUp(self):
        super().setUp()
        store.insert_task(self.conn, TASK, "Канареечная задача прогона",
                          "escalated", f"task/{TASK.lower()}-kanareyka",
                          config.DEFAULT_TARGET, 25.0, is_canary=True)

    def _answer_text(self, escalated_from: str = "in_dev") -> str:
        """Текст файла, который канарейка отдаёт `answer.cmd_answer` при
        возврате из `escalated_from`; состояние возвращается обратно в
        `escalated`, чтобы помощник звался в одном тесте несколько раз."""
        captured = []

        def spy(_task_id, file_path, *args, **kwargs):
            captured.append(Path(file_path).read_text(encoding="utf-8"))

        state = store.get_task(self.conn, TASK)["state"]
        if state != "escalated":
            store.set_state(self.conn, TASK, "escalated", "test",
                            expected_state=state)
        store.update_task(self.conn, TASK, escalated_from=escalated_from)
        with mock.patch.object(canary.answer, "cmd_answer", side_effect=spy):
            canary._pass_escalated_with_synthetic_answer(self.conn, TASK)
        after = store.get_task(self.conn, TASK)["state"]
        if after != "escalated":
            store.set_state(self.conn, TASK, "escalated", "test",
                            expected_state=after)
        self.assertEqual(1, len(captured),
                         "канарейка отдала каналу ANSWER не ровно один файл")
        return captured[0]


class SyntheticAnswerTextTest(_CanaryEscalatedTest):

    def setUp(self):
        super().setUp()
        self.text = self._answer_text()

    def test_text_written_to_answer_channel_is_the_module_constant(self):
        """В файл ответа уходит ровно `canary._SYNTHETIC_ANSWER_TEXT`.

        Ловит мутацию: текст снова собирается литералом в теле
        `_pass_escalated_with_synthetic_answer` (или обрастает там
        припиской про задачу/роль) — записанное расходится со значением
        константы, и тест краснеет.
        """
        self.assertEqual(canary._SYNTHETIC_ANSWER_TEXT, self.text)

    def test_text_carries_no_task_identifier(self):
        """Текст не несёт ни одной подстроки формата идентификатора
        задачи пульта — ни номера задачи прогона, ни номера задачи,
        которая ввела механизм.

        Образец формата сверяется с самим генератором: если он перестанет
        узнавать выдаваемые `idgen.new_task_id` идентификаторы, «текст
        чист» означало бы «выражение ничего не ищет».

        Ловит мутацию: в текст вернули любой номер задачи (прежний
        01M1NEEWH5K1XPFRDGRMPYSBXJ, `task_id` прогона, номер соседней
        задачи) — роль снова читает ответ как относящийся к чужой задаче,
        и тест краснеет на любом из них.
        """
        for _ in range(20):
            self.assertRegex(idgen.new_task_id(), ID_IN_TEXT,
                             "образец формата не узнаёт идентификатор "
                             "собственного генератора пульта")
        self.assertEqual([], ID_IN_TEXT.findall(self.text),
                         f"текст ответа несёт идентификатор задачи:\n"
                         f"{self.text}")

    def test_text_does_not_offer_a_lettered_option(self):
        """Текст не ссылается на вариант ответа ни в одном падеже: роль
        могла не предлагать вариантов вовсе.

        Ловит мутацию: в текст вернули «вариант A» (или «первый
        вариант», «вариантом A») — ответ снова адресует развилку, которой
        в вопросах роли может не быть, и тест краснеет.
        """
        self.assertNotIn("вариант", self.text.lower(),
                         f"текст ответа ссылается на вариант:\n{self.text}")

    def test_text_carries_all_four_named_anchors_verbatim(self):
        """Все четыре константы-якоря модуля входят в текст дословно, и
        ни одна из них не пуста.

        Ловит мутацию: утверждение требования 4 выпало из текста (или
        константа осталась, но текст собран мимо неё — «Оператора нет»
        вместо значения `_SYNTHETIC_ANSWER_NO_OPERATOR») — роль
        недополучает одно из четырёх утверждений, и тест краснеет,
        называя именно выпавший якорь.
        """
        for name in ANCHOR_NAMES:
            anchor = getattr(canary, name)
            self.assertTrue(anchor.strip(), f"якорь {name} пуст")
            self.assertIn(anchor, self.text,
                          f"якорь {name} не входит в текст ответа дословно:\n"
                          f"{self.text}")

    def test_four_anchors_are_distinct_statements(self):
        """Четыре якоря — четыре РАЗНЫХ утверждения: ни один не является
        частью другого.

        Ловит мутацию: два якоря свели к одной фразе и её обрезку
        («…принимаешь ты» и «решение по вопросу принимаешь ты — в
        пределах ТЗ и SPEC задачи») — четыре утверждения требования 4
        выродились бы в три, а тест дословного вхождения выше остался бы
        зелёным; краснеет этот.
        """
        values = [getattr(canary, name) for name in ANCHOR_NAMES]
        self.assertEqual(len(ANCHOR_NAMES), len(set(values)),
                         "якоря повторяются")
        for name, value in zip(ANCHOR_NAMES, values):
            others = [v for v in values if v != value]
            self.assertFalse([v for v in others if value in v or v in value],
                             f"якорь {name} вложен в другой якорь")

    def test_assumption_addressed_to_existing_template_section(self):
        """Текст называет раздел `## Риски` — и КАЖДЫЙ названный им
        раздел `## <название>` существует заголовком хотя бы одного
        шаблона `templates/*.md`.

        Вторая половина — обобщение первой, и живёт она здесь, а не
        только в планке задачи: планку после мержа не гоняет ни один джоб
        `.github/workflows/`, а править её нельзя (лок приёмочных тестов),
        то есть сторожем следующей правки текста она быть не может
        (REVIEW.md итерации 1, R1-F1).

        Ловит мутацию: адрес допущения убрали («запиши в артефакт» без
        места) — падает первая половина; адрес заменили разделом,
        которого ни один шаблон не несёт («## Допущения», «## Открытые
        вопросы») — роль получает недостижимый адрес, `templates/` —
        защищённый путь, которым его не добавить, и падает вторая.
        """
        self.assertIn("## Риски", self.text,
                      f"текст не называет раздел `## Риски`:\n{self.text}")
        headings = _template_headings()
        self.assertIn("Риски", headings,
                      "ни один шаблон `templates/*.md` не несёт раздела "
                      "`## Риски` — адрес допущения в тексте недостижим")
        named = _headings_named_in(self.text)
        self.assertTrue(named, f"текст не называет ни одного раздела `## …`:"
                               f"\n{self.text}")
        unknown = [name for name in named
                   if not _heading_exists(name, headings)]
        self.assertEqual([], unknown,
                         f"текст называет разделы, которых нет ни в одном "
                         f"шаблоне templates/*.md: {unknown}")

    def test_text_carries_no_operator_mandate_lines(self):
        """Текст не несёт ни одной строки мандата Оператора: тот же
        `ANSWER-n.md` разбирает `advance_gates/mandate.py`.

        Ловит мутацию: в текст вписали строку вида «Расширение зон
        разрешено: …» или «Ослабление тестов разрешено: …» — синтетический
        ответ прогона молча выдавал бы роли право, которого Оператор не
        давал, и тест краснеет.
        """
        for marker in (mandate._ZONES_MANDATE_MARKER,
                       mandate.TEST_WEAKENING_MANDATE_MARKER):
            self.assertNotIn(marker, self.text,
                             f"текст ответа несёт строку мандата {marker!r}")

    def test_origin_spec_lives_in_the_code_comments_not_in_the_text(self):
        """Происхождение механизма названо пояснением для читателя кода —
        докстрингом функции ИЛИ комментарием её тела (требование 3
        допускает обе формы), — а текст, который читает роль, этого номера
        не несёт.

        Ловит мутацию: номер SPEC вычистили из кода вместе с текстом —
        читатель `canary.py` теряет происхождение механизма (падает
        первая половина); номер вернули в текст вместо пояснения — падает
        вторая. Перенос абзаца о происхождении из докстринга в комментарий
        тела свойство не ломает и тест не краснит (REVIEW.md итерации 1,
        R1-F3).
        """
        docs = _docs_and_comments(canary._pass_escalated_with_synthetic_answer)
        self.assertIn("01M1NEEWH5K1XPFRDGRMPYSBXJ", docs)
        self.assertIn("требование 6", docs)
        self.assertNotIn("01M1NEEWH5K1XPFRDGRMPYSBXJ", self.text)


class SyntheticAnswerReturnTest(_CanaryEscalatedTest):

    def test_text_is_the_same_for_every_escalated_from(self):
        """Текст один и тот же при возврате из любого состояния — то есть
        для любой роли, которая эскалировала.

        Ловит мутацию: в текст добавили ветку по `escalated_from` (или по
        роли состояния) — например отдельную приписку автору тестов;
        перехваченные тексты четырёх состояний расходятся, и тест
        краснеет.
        """
        texts = {state: self._answer_text(escalated_from=state)
                 for state in ESCALATED_FROM_STATES}
        self.assertEqual(1, len(set(texts.values())),
                         f"текст ответа ветвится по состоянию: {texts}")

    def test_return_restores_the_state_the_task_escalated_from(self):
        """Возврат ставит задачу в то состояние, из которого она
        эскалировала, и гасит `escalated_from`/`answer_baseline`.

        Ловит мутацию: правка текста задела механику возврата (задача
        уходит не в своё состояние или `escalated_from` остаётся) —
        прогон повёл бы задачу не той ролью, а следующая эскалация
        вернула бы её по устаревшему полю.
        """
        for state in ESCALATED_FROM_STATES:
            with self.subTest(state=state):
                store.update_task(self.conn, TASK, escalated_from=state,
                                  answer_baseline="whatever")
                with mock.patch.object(canary.answer, "cmd_answer"):
                    canary._pass_escalated_with_synthetic_answer(
                        self.conn, TASK)
                row = store.get_task(self.conn, TASK)
                self.assertEqual(state, row["state"])
                self.assertIsNone(row["escalated_from"])
                self.assertIsNone(row["answer_baseline"])
                store.set_state(self.conn, TASK, "escalated", "test",
                                expected_state=state)


class EscalationCapUnchangedTest(_CanaryEscalatedTest):
    """Предохранитель повторных эскалаций — прежний: новый текст не
    добавил прогону ни одного лишнего возврата задачи."""

    def setUp(self):
        super().setUp()
        store.update_task(self.conn, TASK, escalated_from="in_dev")

        def fake_auto(task_id):
            # Роль доработала, ревьювер снова вернул — задача эскалирует
            # заново, без реального прогона агентов.
            if store.get_task(self.conn, task_id)["state"] == "in_dev":
                store.set_state(self.conn, task_id, "escalated", "test",
                                expected_state="in_dev")

        patcher = mock.patch.object(canary.auto, "cmd_auto",
                                    side_effect=fake_auto)
        patcher.start()
        self.addCleanup(patcher.stop)
        for module, name in ((canary.answer, "cmd_answer"),
                             (canary.cleanup, "cmd_kill")):
            patcher = mock.patch.object(module, name)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_synthetic_answer_is_issued_no_more_than_the_cap_allows(self):
        """Синтетический ответ выдаётся ровно
        `config.CANARY_MAX_ESCALATION_CYCLES` раз, после чего задача
        снимается штатным `cleanup.cmd_kill`.

        Ловит мутацию: закрытие эскалации новым текстом перестало
        считаться циклом предохранителя (счётчик двигают не там, где
        возвращают задачу) — `_drive_task` крутил бы `escalated` <->
        `in_dev` без снятия задачи, и число выданных ответов ушло бы за
        порог.
        """
        canary._drive_task(self.conn, TASK)

        self.assertEqual(config.CANARY_MAX_ESCALATION_CYCLES,
                         canary.answer.cmd_answer.call_count,
                         "число синтетических ответов разошлось с порогом "
                         "повторных эскалаций")
        canary.cleanup.cmd_kill.assert_called_once_with(TASK)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
