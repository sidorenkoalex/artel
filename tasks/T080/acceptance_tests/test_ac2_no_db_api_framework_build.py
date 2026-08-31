"""AC-2 (tasks/T080/SPEC.md): ни один из HTML-файлов макета не содержит
обращений к БД оркестратора, HTTP-вызовов к API, подключений
JS-фреймворков/библиотек (React, Vue и т.п.) и шагов сборки (bundler,
npm build и подобных) — только HTML-разметка и CSS-стили (inline или
локальные, без внешних сетевых ресурсов).

Красен до реализации: HTML-файлов ещё нет вовсе (см. AC-1) — сканировать
нечего, и первый тест падает с понятным сообщением вместо ложного
зелёного «нет файлов — нечего нарушать».
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import unittest  # noqa: E402

import _html_utils as h  # noqa: E402

# Каждый паттерн — (regex, человеческое объяснение, за что зацепился).
# Требование 1/AC-2 SPEC: «только HTML-разметка и CSS-стили» — читаем как
# исчерпывающий список разрешённого, поэтому запрещаем ЛЮБОЙ <script>, не
# только фреймворки.
FORBIDDEN = [
    (re.compile(r"<script\b", re.I),
     "тег <script> — SPEC допускает только HTML-разметку и CSS-стили"),
    (re.compile(r"\bfetch\s*\(", re.I), "вызов fetch() — HTTP к API"),
    (re.compile(r"XMLHttpRequest", re.I), "XMLHttpRequest — HTTP к API"),
    (re.compile(r"\baxios\b", re.I), "библиотека axios"),
    (re.compile(r"\breact(?:dom)?\b", re.I), "фреймворк/библиотека React"),
    (re.compile(r"\bvue(?:\.js)?\b", re.I), "фреймворк Vue"),
    (re.compile(r"\bangular\b", re.I), "фреймворк Angular"),
    (re.compile(r"\bsvelte\b", re.I), "фреймворк Svelte"),
    (re.compile(r"\bjquery\b", re.I), "библиотека jQuery"),
    (re.compile(r"state\.db", re.I), "обращение к БД оркестратора state.db"),
    (re.compile(r"\bsqlite3?\b", re.I), "обращение к БД (sqlite)"),
    (re.compile(r"\bselect\b[^<>{}]{0,200}\bfrom\b", re.I), "SQL-запрос"),
    (re.compile(r"\bwebpack\b|\brollup\b|\bbrowserify\b|\bparcel\b|vite\.config",
                re.I), "шаг сборки (bundler)"),
    (re.compile(r"npm\s+(run\s+build|install)|yarn\s+build|pnpm\s+build",
                re.I), "команда сборки (npm/yarn/pnpm)"),
    (re.compile(r"https?://", re.I), "внешний сетевой ресурс (http(s)://)"),
    (re.compile(r"\bcdn\.|jsdelivr|unpkg\.com|cdnjs\.", re.I),
     "подключение библиотеки с CDN"),
]

BUILD_CONFIG_NAMES = {
    "package.json", "package-lock.json", "webpack.config.js",
    "vite.config.js", "vite.config.ts", "rollup.config.js",
    "tsconfig.json", ".babelrc", "babel.config.js",
}


class NoDbApiFrameworkBuildTest(unittest.TestCase):

    def test_ac2_no_forbidden_content_in_any_html_file(self):
        files = h.html_files()
        if not files:
            self.fail(
                "в tasks/T080/ нет HTML-файлов макета — проверять AC-2 "
                "не на чем (см. AC-1)")
        violations = []
        for path in files:
            text = path.read_text(encoding="utf-8")
            for pattern, why in FORBIDDEN:
                m = pattern.search(text)
                if m:
                    violations.append(
                        f"{path.relative_to(h.TASK_DIR)}: {why} "
                        f"(совпадение: {m.group(0)!r})")
        self.assertFalse(
            violations,
            "AC-2 нарушен — найдены запрещённые обращения/зависимости:\n"
            + "\n".join(violations))

    def test_ac2_no_build_tool_config_files_present(self):
        found = [p for p in h.TASK_DIR.rglob("*")
                 if p.is_file() and p.name in BUILD_CONFIG_NAMES
                 and h.ACCEPTANCE_DIR not in p.parents]
        self.assertFalse(
            found,
            "найдены конфиги инструментов сборки в tasks/T080/ (AC-2 — "
            "«без шагов сборки»): "
            + ", ".join(str(p.relative_to(h.TASK_DIR)) for p in found))


if __name__ == "__main__":
    unittest.main()
