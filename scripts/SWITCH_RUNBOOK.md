# Переключение движка книги: ERPNext → sqlledger (шаг 4)

Прод читает `ledger_backend` из `.env` (pydantic, env_prefix `COUNTA_`,
`--reload` подхватывает изменения). Дефолт в коде — `erpnext`.

## Перед переключением (обязательно)
1. Свежая сверка: `.venv/bin/python scripts/migrate_to_sqlledger.py`
   (бэкап + перенос + сверка балансов до копейки). Должно быть «✅ МИГРАЦИЯ ВЕРНА».
   Если есть НОВЫЕ записи в ERPNext с прошлого переноса — этот прогон их захватит.

## Переключение
2. Добавить в `.env`: `COUNTA_LEDGER_BACKEND=sqlledger`
3. `--reload` перечитает (или вручную: launchctl bootout/bootstrap counta-web).
4. Проверить: `/api/balances` и форма отдают те же цифры, что на ERPNext.

## Откат (мгновенный, безопасный)
- Убрать строку `COUNTA_LEDGER_BACKEND` из `.env` (или = `erpnext`) → reload.
- Данные ERPNext НЕ тронуты переключением — он остаётся валидным источником.
- ВНИМАНИЕ: записи, созданные ПОСЛЕ переключения, живут только в sqlledger
  (id «JE-...»). При откате назад на erpnext они «исчезнут» из прода (но
  останутся в counta.db). Поэтому откат безопасен только в первые минуты, пока
  не наделано новых записей. Решать сразу: остаёмся или откат.

## После уверенного перехода (отдельно, по «да» Дэна)
- Погасить frappe_docker: `docker compose -f <frappe_docker>/... down` (контейнеры
  mariadb/redis/воркеры). ERPNext-данные в его mariadb-томе остаются как архив.
- Бэкап counta.db: `~/.counta/counta.db.pre-migrate-*`.
