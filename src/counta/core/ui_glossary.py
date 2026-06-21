"""Метаописания UI-строк для глоссария (контекст для ИИ-перевода).

UI-ключей много (~120), и описывать каждый вручную дорого. Но осмысленный
перевод требует знать РОЛЬ строки. Решение: описываем по ПРЕФИКС-ГРУППАМ ключа
(f_, t_, e_, cf_, edit_, flt_, tab_, op_, set_, …) — это даёт ИИ достаточный
контекст («это подпись поля формы» / «это короткий тост-уведомление» / «это
текст кнопки подтверждения»), а точечные важные ключи описываем отдельно.

Применяется на старте к UI-ключам, у которых ещё нет своего desc.
"""

# Точечные описания для ключей, где роль не очевидна из префикса.
EXACT: dict[str, str] = {
    "f_money_from":        "Form field label: which account the money was paid FROM (expense source).",
    "f_money_to_in":       "Form field label: which account the money came IN to (income destination).",
    "f_money_from_transfer":"Form field label: source account in a transfer between own accounts.",
    "f_income_src":        "Form field label: the income source (where incoming money comes from).",
    "f_category":          "Form field label for picking an expense category (what money is spent on).",
    "f_occurred_toggle":   "Toggle label to set when the transaction actually happened, vs when it was recorded.",
    "op_expense":          "Transaction type option: spending money (an expense).",
    "op_income":           "Transaction type option: receiving money (income).",
    "op_transfer":         "Transaction type option: moving money between the user's own accounts.",
    "edit_journal":        "Menu item: edit the journal / list of recorded transactions.",
    "edit_accounts":       "Menu item: edit the user's money accounts (cash, bank, cards).",
    "edit_categories":     "Menu item: edit expense categories.",
    "edit_incomes":        "Menu item: edit income sources.",
    "tab_entry":           "Bottom navigation tab: home / new transaction entry. Shown as a house icon.",
    "trash_restore":       "Button to restore (un-hide / un-cancel) a previously hidden or cancelled item.",
    "flt_hide_cancelled":  "Checkbox to hide cancelled transactions from the journal list.",
    "wz3_b":               "First-run wizard step: instruction to record current real balances (cash in various currencies, cards, credit card) as 'income' operations so balances reflect reality. Keep it concrete and encouraging.",
    "wz4_b":               "First-run wizard step explaining DEBT modeling: create an account for money borrowed from someone, do NOT fund it, just record an expense from it so the balance goes negative — the negative balance IS the debt; repaying funds it back to zero. Translate the concept clearly, the example name is illustrative.",
}

# Описание по префиксу группы ключей (берётся, если нет точечного).
PREFIX: list[tuple[str, str]] = [
    ("f_",    "Label or placeholder for an input field in the transaction entry form."),
    ("t_",    "Short toast/snackbar confirmation message shown briefly after an action."),
    ("e_",    "Short inline error message shown when input is invalid."),
    ("cf_",   "Text of a confirmation dialog/prompt before a destructive or important action."),
    ("pr_",   "Prompt asking the user to type a value (e.g. a new name)."),
    ("edit_", "Label in the 'edit / manage' hub for choosing what to edit."),
    ("acc_",  "Label/button in the accounts editor (money accounts: cash, bank, cards)."),
    ("inc_",  "Label/button in the income-sources editor."),
    ("cur_",  "Label related to currency selection."),
    ("flt_",  "Label/control in the journal filter & sorting panel."),
    ("jf_",   "Journal filter quick option."),
    ("tab_",  "Bottom navigation tab label (often icon-only)."),
    ("scr_",  "Screen/page title heading."),
    ("op_",   "Transaction type option (expense / income / transfer)."),
    ("rv_",   "Word used when assembling a human-readable review line of a transaction before saving."),
    ("set_",  "Label in the Settings section."),
    ("sec_",  "Collapsible section heading in the 'More' menu."),
    ("ai_",   "Text in the AI analyst chat screen (read-only money questions)."),
    ("v_",    "Status text during voice input (speech-to-text prefill)."),
    ("kstep", "Step label in the 3-step entry progress indicator (input → review → saved)."),
    ("per_",  "Recurrence period option (monthly / weekly / etc.)."),
    ("widget_","Name of a home-screen widget (balances / journal)."),
    ("notif_","Word in the notifications area."),
    ("wz",    "Step text in the first-run getting-started wizard: a short step title (_t) or a paragraph of instructions (_b) for a personal-finance app newcomer."),
]

GENERIC = ("Short UI string in a personal-finance mobile app (Counta). Translate "
           "concisely as an everyday app-interface term, not literally.")


def describe(key: str) -> str:
    if key in EXACT:
        return EXACT[key]
    for pfx, d in PREFIX:
        if key.startswith(pfx):
            return d
    return GENERIC


def apply_descriptions() -> int:
    """Проставить метаописания UI-ключам глоссария, у которых desc пуст.
    Не трогаем уже описанные (в т.ч. вручную). Возвращает число обновлённых."""
    from counta.core import glossary
    updated = 0
    for row in glossary.entries():
        if row["kind"] != "ui" or row["desc"]:
            continue
        glossary.set_desc(row["key"], describe(row["key"]))
        updated += 1
    return updated
