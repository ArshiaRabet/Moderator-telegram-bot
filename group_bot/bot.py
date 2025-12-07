"""Telegram group management bot implementation."""
from datetime import timedelta
from typing import Iterable, List, Optional

from telegram import Bot, ChatPermissions, MessageEntity, Update, User
from telegram.constants import ChatMemberStatus, ParseMode
from telegram.ext import (
    AIORateLimiter,
    Application,
    ApplicationBuilder,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import Settings
from .storage import WarningStore


def _is_admin(user: Optional[User], admin_ids: Iterable[int]) -> bool:
    if user is None:
        return False
    return user.id in admin_ids


async def _get_admin_ids(bot: Bot, chat_id: int) -> List[int]:
    admins = await bot.get_chat_administrators(chat_id)
    return [admin.user.id for admin in admins]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        """
✨ ربات مدیریت گروه فعال است!

/ کمک بگیر | /help یا /komak
/ قوانین | /rules
/ هشدار | /warn (ریپلای کنید)
/ سکوت | /mute (ریپلای کنید)
/ آزادسازی | /unmute (ریپلای کنید)
/ قفل گروه | /lock
/ آزاد کردن گروه | /unlock
/ بن | /ban (ریپلای کنید)
/ پاک هشدار | /resetwarns (ریپلای کنید)
/ تعداد هشدار | /warns (ریپلای کنید)
/ پین پیام | /pin (ریپلای کنید)
/ آمار | /stats
""".strip()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        """
دستورات اصلی:
• /warn – اضافه کردن هشدار به کاربر (ریپلای)
• /warns – مشاهده تعداد هشدار کاربر ریپلای‌شده
• /mute <دقیقه> – سکوت موقت برای کاربر پاسخ داده شده
• /unmute – آزاد کردن کاربر از سکوت (ریپلای)
• /lock – قفل کردن گروه و محدود کردن چت اعضا
• /unlock – آزاد کردن چت اعضا
• /ban – حذف و مسدود کردن کاربر (ریپلای)
• /resetwarns – پاک کردن هشدارهای کاربر (ریپلای)
• /pin – پین کردن پیام ریپلای شده
• /stats – مشاهده تعداد هشدارهای ثبت‌شده
• /rules – نمایش قوانین گروه
• /help یا /komak – نمایش همین راهنما
• ارسال لینک برای کاربران غیرادمین در صورت فعال بودن محدود می‌شود.
""".strip()
    )


async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        """
قوانین کلی:
1. احترام به اعضا
2. بدون اسپم و لینک‌های مشکوک
3. از ریپلای برای درخواست کمک استفاده کنید
""".strip()
    )


async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    for member in update.message.new_chat_members:
        await update.message.reply_text(
            f"خوش آمدی {member.mention_html()}! قوانین را با /rules بخوان.",
            parse_mode=ParseMode.HTML,
        )


async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.message.reply_to_message is None:
        await update.message.reply_text("برای هشدار، پیام کاربر را ریپلای کنید.")
        return

    target = update.message.reply_to_message.from_user
    if target is None:
        return

    chat_id = update.effective_chat.id
    admin_ids = await _get_admin_ids(context.application.bot_data["bot"], chat_id)
    if not _is_admin(update.effective_user, admin_ids):
        await update.message.reply_text("فقط ادمین‌ها می‌توانند هشدار دهند.")
        return

    store: WarningStore = context.application.bot_data["warnings"]
    new_count = store.increment(chat_id, target.id)
    limit = context.application.bot_data["settings"].warnings_limit

    await update.message.reply_text(
        f"هشدار #{new_count} برای {target.mention_html()} ثبت شد.",
        parse_mode=ParseMode.HTML,
    )

    if new_count >= limit:
        await mute_user(update, context, duration_minutes=60)
        store.reset(chat_id, target.id)
        await update.message.reply_text(
            f"{target.mention_html()} به دلیل هشدارهای متوالی به مدت یک ساعت میوت شد.",
            parse_mode=ParseMode.HTML,
        )


async def warn_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.message.reply_to_message is None:
        await update.message.reply_text("برای مشاهده تعداد هشدار، پیام کاربر را ریپلای کنید.")
        return

    target = update.message.reply_to_message.from_user
    if target is None:
        return

    chat_id = update.effective_chat.id
    store: WarningStore = context.application.bot_data["warnings"]
    count = store.get(chat_id, target.id)
    await update.message.reply_text(
        f"{target.mention_html()} تا کنون {count} هشدار دارد.", parse_mode=ParseMode.HTML
    )


async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await mute_user(update, context)


async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.message.reply_to_message is None:
        await update.message.reply_text("برای آزاد کردن کاربر، پیام او را ریپلای کنید.")
        return

    target = update.message.reply_to_message.from_user
    if target is None:
        return

    chat_id = update.effective_chat.id
    admin_ids = await _get_admin_ids(context.application.bot_data["bot"], chat_id)
    if not _is_admin(update.effective_user, admin_ids):
        await update.message.reply_text("فقط ادمین‌ها می‌توانند کاربر را آزاد کنند.")
        return

    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
    )
    await context.bot.restrict_chat_member(chat_id, target.id, permissions)

    await update.message.reply_text(
        f"ارسال پیام برای {target.mention_html()} مجاز شد.", parse_mode=ParseMode.HTML
    )


async def mute_user(
    update: Update, context: ContextTypes.DEFAULT_TYPE, duration_minutes: Optional[int] = None
) -> None:
    if update.message is None or update.message.reply_to_message is None:
        await update.message.reply_text("برای سکوت، پیام کاربر را ریپلای کنید.")
        return

    target = update.message.reply_to_message.from_user
    if target is None:
        return

    chat_id = update.effective_chat.id
    admin_ids = await _get_admin_ids(context.application.bot_data["bot"], chat_id)
    if not _is_admin(update.effective_user, admin_ids):
        await update.message.reply_text("فقط ادمین‌ها می‌توانند سکوت کنند.")
        return

    minutes = duration_minutes
    if minutes is None and context.args:
        try:
            minutes = max(1, int(context.args[0]))
        except ValueError:
            minutes = 10
    minutes = minutes or 10

    until_date = update.message.date + timedelta(minutes=minutes)
    permissions = ChatPermissions(can_send_messages=False)
    await context.bot.restrict_chat_member(chat_id, target.id, permissions, until_date=until_date)

    await update.message.reply_text(
        f"{target.mention_html()} برای {minutes} دقیقه به سکوت رفت.",
        parse_mode=ParseMode.HTML,
    )


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.message.reply_to_message is None:
        await update.message.reply_text("برای بن کردن، پیام کاربر را ریپلای کنید.")
        return

    target = update.message.reply_to_message.from_user
    if target is None:
        return

    chat_id = update.effective_chat.id
    admin_ids = await _get_admin_ids(context.application.bot_data["bot"], chat_id)
    if not _is_admin(update.effective_user, admin_ids):
        await update.message.reply_text("فقط ادمین‌ها می‌توانند کاربر را بن کنند.")
        return

    await context.bot.ban_chat_member(chat_id, target.id)
    await update.message.reply_text(
        f"{target.mention_html()} از گروه حذف و مسدود شد.", parse_mode=ParseMode.HTML
    )


async def lock_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    admin_ids = await _get_admin_ids(context.application.bot_data["bot"], chat_id)
    if not _is_admin(update.effective_user, admin_ids):
        await update.message.reply_text("فقط ادمین‌ها می‌توانند گروه را قفل کنند.")
        return

    permissions = ChatPermissions(can_send_messages=False)
    await context.bot.set_chat_permissions(chat_id, permissions)
    await update.message.reply_text("گروه قفل شد و ارسال پیام برای اعضا محدود شد.")


async def unlock_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    admin_ids = await _get_admin_ids(context.application.bot_data["bot"], chat_id)
    if not _is_admin(update.effective_user, admin_ids):
        await update.message.reply_text("فقط ادمین‌ها می‌توانند گروه را آزاد کنند.")
        return

    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
    )
    await context.bot.set_chat_permissions(chat_id, permissions)
    await update.message.reply_text("گروه آزاد شد و اعضا می‌توانند پیام ارسال کنند.")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    store: WarningStore = context.application.bot_data["warnings"]
    warnings = store.get_all(chat_id)
    if not warnings:
        await update.message.reply_text("فعلاً هشدار ثبت نشده است.")
        return

    lines = ["آمار هشدارها:"]
    for user_id, count in warnings.items():
        user_link = f"tg://user?id={user_id}"
        lines.append(f"• <a href='{user_link}'>کاربر {user_id}</a>: {count} هشدار")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def reset_warns(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.message.reply_to_message is None:
        await update.message.reply_text("برای پاک کردن هشدار، پیام کاربر را ریپلای کنید.")
        return

    target = update.message.reply_to_message.from_user
    if target is None:
        return

    chat_id = update.effective_chat.id
    admin_ids = await _get_admin_ids(context.application.bot_data["bot"], chat_id)
    if not _is_admin(update.effective_user, admin_ids):
        await update.message.reply_text("فقط ادمین‌ها می‌توانند هشدارها را پاک کنند.")
        return

    store: WarningStore = context.application.bot_data["warnings"]
    store.reset(chat_id, target.id)
    await update.message.reply_text(
        f"تمام هشدارهای {target.mention_html()} پاک شد.", parse_mode=ParseMode.HTML
    )


async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.message.reply_to_message is None:
        await update.message.reply_text("برای پین کردن، پیام مد نظر را ریپلای کنید.")
        return

    chat_id = update.effective_chat.id
    admin_ids = await _get_admin_ids(context.application.bot_data["bot"], chat_id)
    if not _is_admin(update.effective_user, admin_ids):
        await update.message.reply_text("فقط ادمین‌ها می‌توانند پیام را پین کنند.")
        return

    await update.message.reply_to_message.pin()
    await update.message.reply_text("پیام انتخاب‌شده پین شد.")


async def block_links(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.message.from_user is None:
        return
    chat_id = update.effective_chat.id
    settings: Settings = context.application.bot_data["settings"]
    if not settings.admin_only_links:
        return

    admin_ids = await _get_admin_ids(context.application.bot_data["bot"], chat_id)
    if _is_admin(update.message.from_user, admin_ids):
        return

    await update.message.delete()
    await context.bot.send_message(
        chat_id,
        f"{update.message.from_user.mention_html()} ارسال لینک برای کاربران غیرادمین ممنوع است.",
        parse_mode=ParseMode.HTML,
    )


async def track_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.chat_member is None:
        return
    chat_id = update.chat_member.chat.id
    admin_ids = context.application.bot_data.setdefault("admin_ids", {})
    if update.chat_member.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR:
        admin_ids.setdefault(chat_id, set()).add(update.chat_member.new_chat_member.user.id)


def build_application(settings: Settings) -> Application:
    store = WarningStore(settings.storage_path)
    application = (
        ApplicationBuilder()
        .token(settings.bot_token)
        .rate_limiter(AIORateLimiter())
        .build()
    )

    application.bot_data["settings"] = settings
    application.bot_data["warnings"] = store
    application.bot_data["bot"] = application.bot

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler(["help", "komak"], help_command))
    application.add_handler(CommandHandler("rules", rules))
    application.add_handler(CommandHandler("warn", warn))
    application.add_handler(CommandHandler("warns", warn_info))
    application.add_handler(CommandHandler("mute", mute))
    application.add_handler(CommandHandler("unmute", unmute))
    application.add_handler(CommandHandler("lock", lock_chat))
    application.add_handler(CommandHandler("unlock", unlock_chat))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("resetwarns", reset_warns))
    application.add_handler(CommandHandler("pin", pin))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    application.add_handler(
        MessageHandler(filters.Entity(MessageEntity.URL) | filters.Entity("text_link"), block_links)
    )
    application.add_handler(ChatMemberHandler(track_admin, ChatMemberHandler.MY_CHAT_MEMBER))

    return application


def run_bot() -> None:
    settings = Settings.from_env()
    application = build_application(settings)
    application.run_polling(close_loop=False)


__all__ = [
    "build_application",
    "run_bot",
]
