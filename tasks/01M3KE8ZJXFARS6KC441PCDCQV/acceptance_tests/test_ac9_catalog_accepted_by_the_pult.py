"""AC-9 — 01M3KE8ZJXFARS6KC441PCDCQV: на новом каталоге `artel.py models`
и `artel.py doctor` не дают красных строк, которых не было до правки.

Источник — SPEC.md, «Критерии приёмки»:

AC-9. Полный набор `tests/` зелёный; `artel.py models` и `artel.py
doctor` на новом каталоге не дают красных строк, которых не было до
правки.

Редакция 2 планки по ANSWER-1, вопрос 1, вариант (а). Прежняя редакция
брала «не было до правки» буквально: гоняла те же две строки `doctor`
ДВАЖДЫ — на каталоге базы сравнения и на каталоге после приложения
PLAN — и сравнивала вердикты. Коммит `ae3370c5` внёс каталог в main
вперёд задачи, оба каталога сравнения совпали, и сравнение выродилось в
тождество: зелёное всегда, не меряющее ничего (докстринг `_catalog.py`).
Предметом стал каталог ВЕТКИ, а «не хуже, чем до правки» — требованием
`ok` на обеих строках: до правки обе были `ok` (`doctor` на каталоге,
который пульт и читал каждым шагом), поэтому требовать `ok` — то же
условие, взятое своей сильной стороной, а не ослабленное.

Всё остальное, от чего зависят `models` и `doctor` (локальный слой
`.artel/models.yaml` вне git и карта исполнителей `roles.yaml`), берётся
фикстурой во временном каталоге: это крутилки Оператора, и тест,
читающий их настоящие файлы, краснел бы от правки, не связанной с
задачей (skills/test-authoring.md, «Окружение теста»).

Первую половину критерия — «полный набор `tests/` зелёный» — планка не
повторяет: его на этом же гейте гоняет сам пульт
(`orchestrator/acceptance.py::full_suite`) и CI ветки; вторым прогоном
внутри планки он ничего бы не добавил. То, что литерал состава каталога
сходится с новым каталогом (единственное место набора, которое ломает
именно эта задача), проверяет `test_ac4_composition_literal.py`.

Красен до реализации: пока каталог не правлен, `artel.py models` не
печатает ни одной из трёх новых записей и печатает снимаемую — второй
тест файла падает на каждой из них.
"""
import io
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _catalog  # noqa: E402

from orchestrator import config, doctor, models  # noqa: E402

#: Карта исполнителей сценария: одна agent-роль с ярусом — этого хватает,
#: чтобы `doctor` прошёл цепочку «роль → ярус → модель → провайдер».
ROLES_TEXT = """\
roles:
  developer:
    executor: agent
    token_slot: artel-developer
    skills: [conventions-core]
    model_tier: strong
token_fallback: artel-token
"""

LOCAL_TEMPLATE = """\
tiers:
  strong: {model}
  standard: {model}
  cheap: {model}
"""


class CatalogAcceptedByThePultTest(unittest.TestCase):
    """Каталог ветки читается пультом так же, как читался каталог до
    правки."""

    def setUp(self):
        self.subject = _catalog.catalog()
        self.tdir = Path(tempfile.mkdtemp(prefix="artel-plank-ac9-"))
        self.addCleanup(self._drop)

        roles_path = self.tdir / "roles.yaml"
        roles_path.write_text(ROLES_TEXT, encoding="utf-8")
        local_path = self.tdir / "models-local.yaml"
        local_path.write_text(
            LOCAL_TEMPLATE.format(model=self.shared_model()), encoding="utf-8")

        for attr, value in (("ROLES", roles_path),
                            ("MODELS_LOCAL", local_path)):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _drop(self):
        shutil.rmtree(self.tdir, ignore_errors=True)

    def shared_model(self) -> str:
        """Модель каталога ветки со статусом `supported`: ярус фикстуры
        обязан разрешаться, иначе обе строки `doctor` покраснели бы не от
        каталога, а от самой фикстуры."""
        supported = [
            model_id for model_id in sorted(self.subject.catalog.models)
            if self.subject.catalog.models[model_id].status
            == models.STATUS_SUPPORTED]
        self.assertTrue(supported, "в каталоге ветки нет ни одной модели "
                                   "статуса supported — ярусу пульта не на "
                                   "что указывать")
        return supported[0]

    def verdicts(self, catalog_path: Path) -> dict:
        """{имя строки doctor: (статус, текст)} по двум строкам о слоях
        моделей, посчитанным на каталоге `catalog_path`."""
        with mock.patch.object(config, "MODELS", catalog_path):
            checks = [doctor.check_models_catalog(), doctor.check_models_local()]
        return {check.name: (check.status, check.detail) for check in checks}

    def test_ac9_doctor_gains_no_red_line_from_the_new_catalog(self):
        """Строки `models-catalog` и `models-local` на каталоге ветки —
        `ok`, то есть не хуже, чем были на каталоге до правки.

        Ловит мутацию: у новой записи пропущена одна из четырёх цен или
        проставлен ноль (в таблице требования 1 у `gpt-6-luna` стоит
        0.125 и 0.01 — цифры, на которых легко потерять разряд):
        `models.load_catalog` отказывает `IncompletePriceError`/
        `ZeroPriceError`, и `doctor` даёт `fail` «каталог моделей не
        разобран», которого до правки не было.
        """
        verdicts = self.verdicts(self.subject.path)

        self.assertEqual(["models-catalog", "models-local"],
                         sorted(verdicts),
                         "doctor посчитал не те строки — сверять нечего")
        for name in sorted(verdicts):
            status, detail = verdicts[name]
            with self.subTest(check=name):
                self.assertEqual(
                    "ok", status,
                    f"строка {name} на каталоге ветки — {status} "
                    f"(до правки обе строки были ok): {detail}")

    def test_ac9_models_command_prints_the_new_catalog(self):
        """`artel.py models` на новом каталоге печатает таблицу: команда
        не отказывает, новые записи в ней есть, снятой — нет.

        Ловит мутацию: правка положила запись мимо раздела `models:`
        провайдера (отступ на два пробела меньше — форма файла
        ограничена `orchestrator/yamlmini.py`, блочные отображения
        вложены отступом): каталог разберётся, но модели в таблице не
        будет, и ярус на неё не разрешится.
        """
        buffer = io.StringIO()
        with mock.patch.object(config, "MODELS", self.subject.path):
            with redirect_stdout(buffer):
                models.cmd_models()
        printed = buffer.getvalue()

        for model_id in sorted(_catalog.NEW_RECORDS):
            with self.subTest(model=model_id):
                self.assertIn(model_id, printed)
        self.assertNotIn(_catalog.WITHDRAWN_MODEL, printed)
        self.assertIn(self.shared_model(), printed)


if __name__ == "__main__":
    unittest.main()
