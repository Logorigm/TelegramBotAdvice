"""Бот-предложка: пользователи присылают фото/видео/гифки,
модератор одобряет или отклоняет, одобренное публикуется в канал."""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart
from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyParameters,
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
MODERATOR_IDS = {int(x) for x in os.environ["MODERATOR_IDS"].replace(" ", "").split(",") if x}
CHANNEL_ID = int(os.environ["CHANNEL_ID"])

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("moderation-bot")

dp = Dispatcher()

MEDIA_FILTER = F.photo | F.video | F.animation


class Decision(CallbackData, prefix="mod"):
    action: str  # "ok" | "no"
    user_id: int
    user_msg_id: int


def moderation_keyboard(user_id: int, user_msg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Опубликовать",
                    callback_data=Decision(action="ok", user_id=user_id, user_msg_id=user_msg_id).pack(),
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=Decision(action="no", user_id=user_id, user_msg_id=user_msg_id).pack(),
                ),
            ]
        ]
    )


def status_keyboard(text: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data="noop")]])


def describe_user(message: Message) -> str:
    u = message.from_user
    name = u.full_name
    if u.username:
        name += f" (@{u.username})"
    return f"{name}, id {u.id}"


@dp.message(CommandStart(), F.chat.type == "private")
async def start(message: Message) -> None:
    await message.answer(
        "Привет! Пришли мне фото, видео или гифку — после проверки модератором "
        "она появится в канале."
    )


@dp.message(MEDIA_FILTER, F.chat.type == "private")
async def submission(message: Message, bot: Bot) -> None:
    kb = moderation_keyboard(message.from_user.id, message.message_id)
    for mod_id in MODERATOR_IDS:
        try:
            # Копия без подписи автора — именно её потом и опубликуем в канал.
            await bot.copy_message(
                chat_id=mod_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=kb,
            )
            await bot.send_message(mod_id, f"⬆️ Прислал: {describe_user(message)}")
        except TelegramAPIError as e:
            log.warning("Не удалось отправить модератору %s: %s", mod_id, e)
    await message.reply("Спасибо! Отправил на модерацию 🙌")


@dp.message(F.chat.type == "private")
async def other(message: Message) -> None:
    await message.answer("Я принимаю только фото, видео и гифки.")


@dp.callback_query(Decision.filter())
async def decide(call: CallbackQuery, callback_data: Decision, bot: Bot) -> None:
    if call.from_user.id not in MODERATOR_IDS:
        await call.answer("Нет прав", show_alert=True)
        return

    if callback_data.action == "ok":
        try:
            await bot.copy_message(
                chat_id=CHANNEL_ID,
                from_chat_id=call.message.chat.id,
                message_id=call.message.message_id,
            )
        except TelegramAPIError as e:
            log.exception("Ошибка публикации")
            await call.answer(f"Не удалось опубликовать: {e.message}", show_alert=True)
            return
        status, user_text = "✅ Опубликовано", "Твой пост опубликован в канале! 🎉"
    else:
        status, user_text = "❌ Отклонено", "К сожалению, модератор отклонил твой пост."

    try:
        await call.message.edit_reply_markup(reply_markup=status_keyboard(status))
    except TelegramAPIError:
        pass
    try:
        await bot.send_message(
            callback_data.user_id,
            user_text,
            reply_parameters=ReplyParameters(
                message_id=callback_data.user_msg_id, allow_sending_without_reply=True
            ),
        )
    except TelegramAPIError as e:
        log.info("Не удалось уведомить пользователя %s: %s", callback_data.user_id, e)
    await call.answer(status)


@dp.callback_query(F.data == "noop")
async def noop(call: CallbackQuery) -> None:
    await call.answer("Решение уже принято")


async def main() -> None:
    bot = Bot(BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=False)
    log.info("Бот запущен, модераторы: %s, канал: %s", MODERATOR_IDS, CHANNEL_ID)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
