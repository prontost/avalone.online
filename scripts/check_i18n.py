"""Линтер переводов для app.html — процессный гард против «дырявого» i18n.

Падает (exit 1), если:
  (A) в видимой разметке есть кириллический текст в теге БЕЗ data-i/data-i-ph/
      data-i-title (значит applyLang его не переведёт → останется русским в en/ko);
  (B) какой-то ключ, использованный в разметке (data-i*) или в JS через T('key'),
      отсутствует хотя бы в одном из языков ru/en/ko.

Запуск: uv run python scripts/check_i18n.py
Гонять ПЕРЕД тем как сказать «готово» (см. Definition of Done в памяти).
"""

import re
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "src/counta/web/templates/app.html"


def extract_i18n_keys(js: str) -> dict[str, set[str]]:
    """Ключи каждого языка из объекта I18N = {...}."""
    m = re.search(r"(?:const|let)\s+I18N\s*=\s*\{(.*?)\}\};", js, re.S)
    if not m:
        print("✗ не нашёл объект I18N"); sys.exit(1)
    body = m.group(1) + "}"  # вернём закрывающую скобку последнего языка
    langs: dict[str, set[str]] = {}
    # каждый язык: ru:{ ... }, en:{ ... }, ko:{ ... } — блок до закрывающей } перед
    # след. языком или концом. Имя языка в начале строки (после переноса/пробелов).
    for lm in re.finditer(r"\n\s*(ru|en|ko):\s*\{(.*?)\}(?=,\s*\n\s*(?:ru|en|ko):|\s*$)", body, re.S):
        lang, block = lm.group(1), lm.group(2)
        langs[lang] = set(re.findall(r"(\w+)\s*:", block))
    return langs


def main() -> int:
    html = TEMPLATE.read_text(encoding="utf-8")
    # В шаблоне несколько <script> (ранняя установка темы в <head> + основной).
    # script = ВСЕ их содержимое (там и I18N, и T('...')); markup = разметка БЕЗ
    # скриптов (иначе кириллица/ключи внутри JS попадут в проверку (A)).
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    script = "\n".join(scripts)
    markup = re.sub(r"<script>.*?</script>", "", html, flags=re.S)

    errors: list[str] = []

    # --- (A) кириллица в разметке без data-i* ---
    CYR = re.compile(r"[А-Яа-яЁё]")
    # теги с видимым текстом
    for m in re.finditer(r"<(h1|h2|label|button|summary|option|b|p|span|div|a)\b([^>]*)>([^<]*)", markup):
        tag, attrs, text = m.group(1), m.group(2), m.group(3)
        if not CYR.search(text):
            continue
        if "data-i" in attrs:           # покрыто (data-i / data-i-ph / data-i-title)
            continue
        # имена языков в #set-lang намеренно на своём языке (Русский/English/한국어)
        if tag == "option" and text.strip() in ("Русский", "English", "한국어"):
            continue
        # вкладка «Ещё» переводится динамически (innerHTML+badge в applyLang)
        if tag == "div" and 'data-page="more"' in attrs:
            continue
        line = markup[: m.start()].count("\n") + 1
        errors.append(f"(A) строка {line}: <{tag}> русский текст без data-i: {text.strip()[:50]!r}")
    # placeholder-атрибуты с кириллицей без data-i-ph
    for m in re.finditer(r'<(input|textarea)\b([^>]*placeholder="[^"]*[А-Яа-я][^"]*"[^>]*)>', markup):
        if "data-i-ph" not in m.group(2):
            line = markup[: m.start()].count("\n") + 1
            errors.append(f"(A) строка {line}: placeholder без data-i-ph")

    # --- (B) все использованные ключи есть во всех языках ---
    langs = extract_i18n_keys(script)
    if set(langs) != {"ru", "en", "ko"}:
        errors.append(f"(B) ожидал языки ru/en/ko, нашёл: {sorted(langs)}")
    used = set(re.findall(r'data-i(?:-ph|-title)?="([^"]+)"', markup))
    used |= set(re.findall(r"\bT\('([^']+)'\)", script))
    used |= set(re.findall(r'\bT\("([^"]+)"\)', script))
    used -= {"key", "ключ"}  # плейсхолдеры из самого определения T(k)
    for key in sorted(used):
        for lang, keys in langs.items():
            if key not in keys:
                errors.append(f"(B) ключ '{key}' отсутствует в '{lang}'")

    if errors:
        print(f"✗ i18n-линтер: {len(errors)} проблем\n")
        for e in errors:
            print(" ", e)
        return 1
    print(f"✓ i18n-линтер чист: {len(used)} ключей покрыты на ru/en/ko, "
          f"непереведённой кириллицы в разметке нет")
    return 0


if __name__ == "__main__":
    sys.exit(main())
