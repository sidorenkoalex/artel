"""AC-6 (tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/SPEC.md): опрос CI уже идущего
`verifying`, получив от GitHub API ответ «коммит не найден» (HTTP 422),
записывает в журнал причину как «голова ветки не в origin» с подсказкой
команды push — вместо нейтрального «статус неизвестен».

Источник — tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/SPEC.md, «Критерии
приёмки», AC-6.

Юнит-уровень `orchestrator/ci.py::verifying_status` напрямую (не через
`fsm_advance.verifying`/полный advance): журналирование самого факта
опроса уже существует и безусловно (`fsm_advance.verifying`
журналирует ЛЮБОЙ `note`, который вернёт `verifying_status`) — то, что
добавляет эта задача, целиком в СОДЕРЖИМОМ `note`, и его удобнее и
надёжнее проверять напрямую на границе `ci.py`, не разворачивая всю
цепочку FSM до состояния `verifying`.

`ci.gh` подменяется так, чтобы вызов, адресованный `.../check-runs`
(тот же путь, что `check_runs_page`), отвечал реальным по форме
текстом ошибки `gh api` на несуществующий на GitHub коммит: ненулевой
код возврата и `HTTP 422: No commit found for SHA: ...` в stderr —
вызов `gh run list` (fallback на «проверок нет вовсе») отвечает пустым
списком, как и было бы для ветки без единого прогона CI, привязанного
к этому sha.

Первый тест (`test_ac6_http_422_...`) красен до реализации: сегодня
`check_runs_page` разбирает ЛЮБОЙ ненулевой ответ `gh` одинаково — «gh
не ответил: <сырой stderr>» — и `verifying_status` заворачивает это в
нейтральное «статус check-runs коммита ... неизвестен (...), и `gh run
list` ... не показывает запусков — проверок нет вовсе». В этом тексте
нет ни «голова ветки не в origin», ни подсказки `git push` — только
сырой текст ошибки GitHub внутри чужой фразы. Проверено прогоном на
немодифицированном коде при подготовке файла.

Второй тест (`test_ac6_other_gh_failures_...`) зелёный с рождения:
контроль на НЕ-422 сбой уже сегодня не содержит слова «push» (никакой
подсказки нет вовсе) — тест фиксирует это как регрессионный барьер
против реализации, которая по ошибке распознает любую ошибку `gh` как
«голова не в origin», а не именно 422.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import ci  # noqa: E402

FAKE_SHA = "a" * 40


def _fake_gh_422(*args, timeout=None):
    if any("check-runs" in a for a in args):
        return subprocess.CompletedProcess(
            list(args), 1, "",
            f"HTTP 422: No commit found for SHA: {FAKE_SHA} "
            f"(https://api.github.com/repos/x/y/commits/{FAKE_SHA}/check-runs)")
    if "run" in args and "list" in args:
        return subprocess.CompletedProcess(list(args), 0, "[]", "")
    return subprocess.CompletedProcess(list(args), 0, "", "")


class Ac6CiPoll422Test(unittest.TestCase):

    def test_ac6_http_422_note_names_head_not_in_origin_with_push_hint(self):
        """GitHub отвечает 422 «коммит не найден» на опрос check-runs
        головы ветки задачи в состоянии `verifying` — `note` обязан
        назвать причину «голова не в origin» и подсказать команду push,
        не свернуть её в нейтральное «статус неизвестен».

        Ловит мутацию: обработчик, который замечает HTTP 422, но не
        меняет ТЕКСТ note (например, только меняет `outcome`, оставляя
        старую фразу) — assertIn на «голова»/«push» ниже поймает это,
        как и обработчик, срабатывающий на любую ошибку gh одинаково
        (без разбора именно 422).
        """
        with mock.patch.object(ci, "head_sha",
                               lambda branch: (FAKE_SHA, "")), \
             mock.patch.object(ci, "gh", _fake_gh_422):
            outcome, note = ci.verifying_status("task/some-branch")

        self.assertNotEqual(
            outcome, ci.VERIFYING_GREEN,
            "предпосылка теста: коммит, которого GitHub не знает, не "
            "может считаться зелёным")
        lowered = note.lower()
        self.assertIn(
            "голова", lowered,
            f"AC-6: note обязан назвать причину «голова не в origin», "
            f"не нейтральное «статус неизвестен»: {note!r}")
        self.assertIn("origin", lowered, f"note: {note!r}")
        self.assertIn(
            "push", lowered,
            f"AC-6: note обязан нести подсказку команды push: {note!r}")

    def test_ac6_other_gh_failures_keep_the_neutral_unknown_wording(self):
        """Контроль: НЕ-422 сбой опроса (сеть легла, `gh` не установлен)
        обязан остаться нейтральным «статус неизвестен» — 422 не имеет
        права стать общим кодом для ЛЮБОЙ ошибки `gh`.

        Ловит мутацию: обработчик, который различает не именно 422, а
        любой ненулевой код возврата `gh` — эта проверка красна ровно
        когда обработчик слишком жаден.
        """
        def fake_gh_network_down(*args, timeout=None):
            return subprocess.CompletedProcess(list(args), 1, "",
                                               "gh молчал дольше 10 с")

        with mock.patch.object(ci, "head_sha",
                               lambda branch: (FAKE_SHA, "")), \
             mock.patch.object(ci, "gh", fake_gh_network_down):
            _outcome, note = ci.verifying_status("task/some-branch")

        self.assertNotIn(
            "push", note.lower(),
            f"контроль AC-6: сбой без 422 не обязан нести подсказку "
            f"push, это не тот случай: {note!r}")


if __name__ == "__main__":
    unittest.main()
