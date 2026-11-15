"""Скрипт для совместного анализа логов и диагностики MOXXI разработчиком.

Использование:
  python inspect_diagnostics.py                 # Общая сводка за 24 часа
  python inspect_diagnostics.py --hours 12      # Сводка за 12 часов
  python inspect_diagnostics.py --errors        # Показать последние ошибки со стеком
  python inspect_diagnostics.py --blocks        # Показать где и почему бот не ответил
  python inspect_diagnostics.py --chat <id>     # Анализ конкретного чата
  python inspect_diagnostics.py --tail 30       # Последние 30 записей с полным текстом
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time

import config
import db
import core_telemetry as telemetry


async def run(args):
    await db.init()
    try:
        hours = args.hours
        since_ts = int(time.time() - (hours * 3600))
        chat_id = args.chat

        print("=" * 70)
        print(f"📊 MOXXI DIAGNOSTICS & TELEMETRY REPORT (Период: {hours} ч.)")
        print(f"База данных: {config.DB_PATH}")
        print("=" * 70)

        if args.tail:
            limit = args.tail
            where_chat = "AND chat_id = ?" if chat_id else ""
            params = [since_ts, chat_id, limit] if chat_id else [since_ts, limit]
            rows = await db.fetchall(f"""
                SELECT dt, status, event_type, chat_id, chat_title, thread_id,
                       user_id, user_name, command_key, full_text, reason, execution_ms
                FROM bot_diagnostics
                WHERE ts >= ? {where_chat}
                ORDER BY id DESC LIMIT ?
            """, tuple(params))
            print(f"\n📋 ПОСЛЕДНИЕ {len(rows)} ЗАПИСЕЙ В ЖУРНАЛЕ:\n")
            for r in reversed(rows):
                dur = f" ({r['execution_ms']}ms)" if r['execution_ms'] else ""
                tid = f" [topic:{r['thread_id']}]" if r['thread_id'] else ""
                st = f"[{r['status'].upper()}]"
                print(f"{r['dt']} {st}{dur} | Чат: {r['chat_title']} ({r['chat_id']}){tid}")
                print(f"  От: {r['user_name']} ({r['user_id']}) | Команда: {r['command_key']}")
                print(f"  Текст: {r['full_text']}")
                if r['reason']:
                    print(f"  Инфо/Причина: {r['reason']}")
                print("-" * 60)
            return

        if args.errors:
            rows = await db.fetchall("""
                SELECT dt, chat_id, chat_title, thread_id, user_id, user_name,
                       command_key, full_text, reason, stack_trace
                FROM bot_diagnostics
                WHERE ts >= ? AND status = 'error'
                ORDER BY id DESC LIMIT 15
            """, (since_ts,))
            print(f"\n🚨 ОШИБКИ И СБОИ ЗА ПОСЛЕДНИЕ {hours} ЧАСОВ ({len(rows)} шт.):\n")
            if not rows:
                print("✅ За выбранный период ошибок не зафиксировано!")
            for i, r in enumerate(rows, 1):
                print(f"#{i} [{r['dt']}] в чате '{r['chat_title']}' ({r['chat_id']})")
                print(f"   Пользователь: {r['user_name']} ({r['user_id']})")
                print(f"   Команда: {r['command_key']} | Текст: {r['full_text']}")
                print(f"   Ошибка: {r['reason']}")
                if r['stack_trace']:
                    print("   Стек ошибки:")
                    for line in r['stack_trace'].splitlines()[-4:]:
                        print(f"     {line}")
                print("-" * 60)
            return

        if args.blocks:
            rows = await db.fetchall("""
                SELECT dt, chat_title, user_name, user_id, command_key, full_text, reason
                FROM bot_diagnostics
                WHERE ts >= ? AND status = 'blocked'
                ORDER BY id DESC LIMIT 20
            """, (since_ts,))
            print(f"\n🚫 ГДЕ БОТ НЕ ОТВЕТИЛ / ЗАБЛОКИРОВАЛ ({len(rows)} шт.):\n")
            if not rows:
                print("✅ За выбранный период блокировок и отказов нет!")
            for i, r in enumerate(rows, 1):
                print(f"#{i} [{r['dt']}] в чате '{r['chat_title']}' от {r['user_name']}")
                print(f"   Команда: {r['command_key']} | Текст: {r['full_text']}")
                print(f"   Причина отказа: {r['reason']}")
                print("-" * 60)
            return

        # Общая сводка
        summary = await telemetry.get_diagnostics_summary(hours=hours, chat_id=chat_id)
        total = summary["total"]
        ok_cnt = summary["ok_count"]
        blocked = summary["blocked_count"]
        errors = summary["error_count"]
        avg_ms = summary["avg_ms"]
        max_ms = summary["max_ms"]

        print(f"\n📈 СВОДКА ПО БОТУ ЗА {hours} ЧАСОВ:")
        print(f"  • Всего зафиксировано событий:  {total}")
        print(f"  • Успешно обработано команд:    {ok_cnt} ({round(ok_cnt/total*100, 1) if total else 100}%)")
        print(f"  • Отклонено / заблокировано:     {blocked}")
        print(f"  • Критических ошибок/крашей:    {errors}")
        print(f"  • Среднее время отклика:        {avg_ms} мс (макс: {max_ms} мс)")

        if summary["top_cmds"]:
            print("\n🏆 ТОП-5 КОМАНД:")
            for r in summary["top_cmds"]:
                print(f"  - {r['command_key']}: {r['cnt']} раз")

        if summary["top_blocks"]:
            print("\n⚠️ ТОП-5 ПРИЧИН ОТКАЗОВ / БЛОКИРОВОК:")
            for r in summary["top_blocks"]:
                print(f"  - {r['reason']}: {r['cnt']} раз")

        if summary["top_errors"]:
            print("\n🚨 ТОП ОШИБОК:")
            for r in summary["top_errors"]:
                print(f"  - {r['reason']}: {r['cnt']} раз")

        if summary["top_chats"]:
            print("\n💬 ТОП ЧАТОВ ПО АКТИВНОСТИ:")
            for r in summary["top_chats"]:
                print(f"  - {r['chat_title']} ({r['chat_id']}): {r['cnt']} ком. [ошибок: {r['errs']}, блоков: {r['blocks']}]")

        print("\n" + "=" * 70)
        print("💡 Подсказки:")
        print("  python inspect_diagnostics.py --errors   -> смотреть ошибки детально")
        print("  python inspect_diagnostics.py --blocks   -> смотреть отказы детально")
        print("  python inspect_diagnostics.py --tail 20  -> смотреть последние сырые сообщения")
        print("=" * 70)
    finally:
        await db.close()


def main():
    parser = argparse.ArgumentParser(description="MOXXI Diagnostics & Telemetry Inspector")
    parser.add_argument("--hours", type=int, default=24, help="Период в часах (по умолчанию 24)")
    parser.add_argument("--errors", action="store_true", help="Показать детальные ошибки")
    parser.add_argument("--blocks", action="store_true", help="Показать детальные блокировки")
    parser.add_argument("--chat", type=int, default=None, help="Фильтр по ID чата")
    parser.add_argument("--tail", type=int, default=0, help="Вывести N последних записей")
    args = parser.parse_args()

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
