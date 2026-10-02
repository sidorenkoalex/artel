"""Юнит-тесты наборов моделей в `orchestrator/models.py` (SPEC
01M3YCHP14179R32SFJVKQB32G, требования 3-6) — свойства, которых не
покрывает долгоживущий файл задачи
`tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`: правило вины на
текстах, построенных самими производителями отказа, разбор сводки прогона
канарейки, обратный разбор пересобранного `model_sets.yaml`, отказ
`admit` до записи на опечатке роли или модели, неизвестный набор.
"""
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import acceptance, models, notes, roles, store, yamlmini  # noqa: E402


def canary_row(**fields) -> dict:
    """Строка `canary_runs` чистого прогона; `fields` — отступления."""
    row = {"verdict": "green", "review_iterations": 0, "escalations": 0,
           "expected_escalation": None, "actual_escalation": 0,
           "marker_mismatch": 0, "autogate_refusal": None}
    row.update(fields)
    return row


class AutogateRefusalBlameTest(unittest.TestCase):

    def test_producer_texts_of_pult_causes_blame_pult(self):
        """Тексты отказа «пульт/пул», собранные самими производителями.

        Сценарий: причина «tests/ нет в worktree» и таймаут прогона берутся
        из `orchestrator/acceptance.py` (константа и функция, которыми
        пишет их `fsm_autogate`), ошибки источника планки — в форме
        `fsm_autogate._plank_sources`; каждая — с префиксом автогейта.

        Ловит мутацию: текст производителя поменялся (или запись снята из
        `_PULT_BLAME_STARTS`), а перечень правила вины — нет: причина
        уходит в «не установлена», и прогон, испорченный пультом,
        перестаёт засчитываться в допуск пары."""
        texts = (
            acceptance.FULL_SUITE_NO_TESTS_NOTE,
            acceptance._full_suite_timeout_note(),
            "перечень долгоживущих файлов не прочитан: нет файла "
            "(источник планки: ветка artifacts/x, sha 0123abc)",
            "долгоживущий файл планки не прочитан: tests/test_x.py (нет "
            "в ветке) (источник планки: ветка artifacts/x, sha 0123abc)",
        )
        for text in texts:
            self.assertEqual(
                models.autogate_refusal_blame(f"автогейт: {text}"),
                models.BLAME_PULT, text)

    def test_producer_text_of_red_suite_blames_role(self):
        """Красный полный набор в форме `acceptance._full_suite_detail`.

        Сценарий: строка исхода красного прогона собирается функцией
        производителя, в выжимке — имя упавшего теста, несущее текст
        причины пульта («бюджет задачи исчерпан»), с префиксом автогейта.

        Ловит мутацию: перечень пульта сверяется подстрокой по всему
        тексту раньше перечня роли — красный набор с текстом причины
        пульта в выжимке уходит пульту, и прогон с красным набором
        засчитывается чистым; либо производитель сменил начало строки, а
        перечень роли — нет."""
        detail = acceptance._full_suite_detail(
            acceptance.FULL_SUITE_RED, "FAILED tests/test_a.py::T::"
            "test_budget — AssertionError: бюджет задачи исчерпан; 1 failed",
            Path("/tmp/x-fullsuite-1.log"))
        self.assertEqual(models.autogate_refusal_blame(f"автогейт: {detail}"),
                         models.BLAME_ROLE)

    def test_classifier_only_for_texts_without_autogate_prefix(self):
        """Классификатор попытки роли — только для строки без префикса.

        Сценарий: причина вне перечней с префиксом автогейта, в которой
        sha содержит сигнатуру класса «403», — «не установлена»; текст
        отказа попытки без префикса с той же сигнатурой — «пульт/пул»;
        пустая причина — `None` (отказа не было).

        Ловит мутацию: классификатор зовётся на любой строке (sha в
        скобках засчитывает пульту неизвестную причину); классификатор не
        зовётся вовсе (отказ попытки роли уходит в «не установлена»);
        пустая причина считается «не установлена» — чистый прогон без
        отказа автогейта перестаёт быть чистым."""
        self.assertEqual(models.autogate_refusal_blame(
            "автогейт: что-то новое (источник планки: ветка a, sha 403abc)"),
            models.BLAME_UNKNOWN)
        self.assertEqual(models.autogate_refusal_blame(
            "API Error: 403 forbidden"), models.BLAME_PULT)
        for empty in (None, "", "  \n "):
            self.assertIsNone(models.autogate_refusal_blame(empty))
        self.assertTrue(models.clean_run(canary_row(autogate_refusal="")))


class CleanRunTest(unittest.TestCase):

    def test_missing_counters_are_not_clean(self):
        """Пустой счётчик строки — не ноль.

        Сценарий: зелёная строка с `review_iterations = NULL`, затем с
        `escalations = NULL` (строка, записанная без счётчика).

        Ловит мутацию: сверка счётчика через ложность (`not value`)
        вместо `!= 0` — строка без данных засчитывается чистой."""
        self.assertTrue(models.clean_run(canary_row()))
        self.assertFalse(models.clean_run(canary_row(review_iterations=None)))
        self.assertFalse(models.clean_run(canary_row(escalations=None)))


class SummaryModelsTest(unittest.TestCase):

    def test_parses_canary_summary_forms(self):
        """Сводка `models_summary` в формах, которые пишет канарейка.

        Сценарий: сводка с источником слоя; сводка без разделителя
        источника (строка до SPEC 01M3PYMQ6N4SCAJ9WWTTKH6XNG); сводка
        «карта исполнителей не прочитана»; пустая.

        Ловит мутацию: источник не отрезается (модель последней роли
        приходит с хвостом «; источник: …» и с моделью пары не совпадает);
        строка без стрелки даёт пару с пустой моделью."""
        self.assertEqual(
            models.summary_models("analyst → m-a, developer → m-b; "
                                  "источник: слой пульта"),
            {"analyst": "m-a", "developer": "m-b"})
        self.assertEqual(models.summary_models("developer → m-b"),
                         {"developer": "m-b"})
        self.assertEqual(models.summary_models(
            "карта исполнителей не прочитана (нет файла); источник: шаблон"),
            {})
        self.assertEqual(models.summary_models(None), {})


class RenderModelSetsTest(unittest.TestCase):

    def test_round_trip_quotes_values_yamlmini_would_misread(self):
        """Пересобранный файл разбирается в те же записи.

        Сценарий: основания, которые `yamlmini.scalar` без кавычек прочёл
        бы иначе («123» — число, «a # b» — комментарий, «null», ведущая
        «[»), плюс шаблоны и набор; шапка-комментарий сохранена.

        Ловит мутацию: значение пишется как есть без проверки обратным
        разбором — основание превращается в число, обрезается
        комментарием или становится `None`/списком."""
        bases = ("123", "прогоны 41 # 44", "null", "[черновик]", " пробел ")
        document = {
            "sets": {"nabor": {"developer": "m-b"}},
            "pairs": {"developer": {f"m-{i}": {
                "date": "2026-10-02", "basis": basis, "state": "допущена"}
                for i, basis in enumerate(bases)}},
            "canary_templates": {"canary-a": "средний"},
        }
        text = models.render_model_sets(document, "# шапка\n")
        self.assertTrue(text.startswith("# шапка\n"), text)
        self.assertEqual(yamlmini.mapping(text), document, text)

    def test_unwritable_value_refused(self):
        """Значение, которое подмножество YAML не выразит, — отказ.

        Сценарий: основание с обеими кавычками и `#` после пробела; имя
        шаблона с двоеточием (разбор делит его на ключ «canary» и значение
        «x: средний» — текст разбирается без ошибки, но в другие записи).

        Ловит мутацию: значения и ключи пишутся без сверки обратным
        разбором — в файл уходит запись, которую `yamlmini` прочтёт
        обрезанной или под другим ключом."""
        for document in (
                {"pairs": {"developer": {"m": {
                    "basis": "\"а\" и 'б' # в", "state": "допущена"}}}},
                {"canary_templates": {"canary: x": "средний"}}):
            with self.assertRaises(models.ModelSetsError, msg=document):
                models.render_model_sets(document)

    def test_empty_sections_written_and_read_back(self):
        """Пустой документ — три раздела без записей, читаемые обратно.

        Ловит мутацию: пустой раздел опускается при записи — раздел
        пропадает из файла, а AC-1 требует все три."""
        text = models.render_model_sets({}, "")
        self.assertEqual(set(yamlmini.mapping(text)),
                         set(models.MODEL_SETS_SECTIONS), text)


class AdmitRefusesBeforeWriteTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "model_sets.yaml"
        self.text = "sets:\npairs:\ncanary_templates:\n"
        self.path.write_text(self.text, encoding="utf-8")
        patchers = (
            mock.patch.object(models, "model_sets_path",
                              return_value=self.path),
            mock.patch.object(models, "pair_admission",
                              return_value=([], [])),
            mock.patch.object(notes, "doc_commit_content"))
        started = []
        for patcher in patchers:
            started.append(patcher.start())
            self.addCleanup(patcher.stop)
        self.commit = started[-1]

    def test_model_outside_catalog_refused_without_commit(self):
        """`admit` на модели вне каталога — отказ до записи.

        Сценарий: каталог без модели пары; чисел «хватает» (сводка
        подменена); и выдача, и `--revoke`.

        Ловит мутацию: модель с каталогом не сверяется — опечатка в id
        модели записывается в `pairs:` и коммитится."""
        with mock.patch.object(roles, "model_tier", return_value="strong"), \
                mock.patch.object(models, "load_catalog",
                                  return_value=models.Catalog({}, {})):
            for argv in (["developer", "model-opechatka", "--basis", "x"],
                         ["--revoke", "developer", "model-opechatka",
                          "--basis", "x"]):
                with self.assertRaises(SystemExit) as caught:
                    models.cmd_admit(argv)
                self.assertIn("model-opechatka", str(caught.exception))
        self.commit.assert_not_called()
        self.assertEqual(self.path.read_text(encoding="utf-8"), self.text)

    def test_unknown_role_and_empty_basis_refused_without_commit(self):
        """Роль вне карты исполнителей и пустое основание — отказ до записи.

        Ловит мутацию: роль не сверяется с картой исполнителей (опечатка
        роли записывается парой, которую никто не прочтёт), либо основание
        из пробелов принимается — запись решения без основания."""
        with mock.patch.object(roles, "model_tier",
                               side_effect=roles.RolesError("нет роли")):
            with self.assertRaises(SystemExit) as caught:
                models.cmd_admit(["razrabotchik", "m", "--basis", "x"])
            self.assertIn("razrabotchik", str(caught.exception))
        with self.assertRaises(SystemExit) as caught:
            models.cmd_admit(["developer", "m", "--basis", "   "])
        self.assertIn("--basis", str(caught.exception))
        self.commit.assert_not_called()


class SetAdmittedUnknownSetTest(unittest.TestCase):

    def test_unknown_set_not_admitted(self):
        """Набора нет в `sets:` — «не допущен» с причиной, без исключения.

        Ловит мутацию: отсутствующий набор трактуется как пустой — цикл по
        парам ничего не отвергает, и при любом зелёном трудном прогоне
        набор «допущен»."""
        document = {"sets": {}, "pairs": {},
                    "canary_templates": {"canary-h": "трудный"}}
        with closing(sqlite3.connect(":memory:")) as conn:
            conn.row_factory = sqlite3.Row
            store.insert_canary_run(conn, "s", "canary-h", "T", 1, 1.0, 0, 0,
                                    "merge_gate", None, False, False,
                                    verdict="green", models_summary="")
            with mock.patch.object(models, "load_model_sets",
                                   return_value=document):
                admitted, reason = models.set_admitted(conn, "nabor-x")
        self.assertIs(admitted, False)
        self.assertIn("nabor-x", reason)


class SetAdmittedUnknownOutsideRoleTest(unittest.TestCase):

    def test_unknown_outside_role_does_not_confirm_set(self):
        """Неизвестная роль сводки не подтверждает прогон набора.

        Ловит мутацию: роль вне набора без разрешимой боевой модели
        пропущена при сверке — зелёный трудный прогон засчитан."""
        document = {"sets": {"nabor-x": {"developer": "m-dev"}},
                    "pairs": {}, "canary_templates": {"canary-h": "трудный"}}
        with closing(sqlite3.connect(":memory:")) as conn:
            conn.row_factory = sqlite3.Row
            store.insert_canary_run(
                conn, "unknown-role-run", "canary-h", "T", 1, 1.0,
                0, 0, "merge_gate", None, False, False, verdict="green",
                models_summary="developer → m-dev, ghost → m-other")
            with (mock.patch.object(models, "load_model_sets",
                                    return_value=document),
                  mock.patch.object(models, "_combat_model",
                                    side_effect=lambda role: {
                                        "developer": "m-dev"}.get(role))):
                admitted, reason = models.set_admitted(conn, "nabor-x")
        self.assertIs(admitted, False)
        self.assertIn("роли вне набора — на боевых моделях", reason)


if __name__ == "__main__":
    unittest.main()
