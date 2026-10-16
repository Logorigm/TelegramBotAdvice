import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyParameters,
)


# ============================================================
# НАСТРОЙКИ
# ============================================================

# <<< ИЗМЕНИТЬ >>>
# Токен, который выдаёт @BotFather
BOT_TOKEN = "8985064942:AAGeLx_sPYBE-Wg9MBQX73rkaSextneqTiU"


# <<< ИЗМЕНИТЬ >>>
# Telegram ID модераторов, которые
# одобряют или отклоняют присланный контент
ADMIN_IDS = {
    1769899996,
}


# <<< ИЗМЕНИТЬ >>>
# ID Telegram-канала
CHANNEL_ID = -1003521280801


# ============================================================
# ЛОГИ
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# ============================================================
# ПРОВЕРКА АДМИНА
# ============================================================

def is_admin(user_id):

    return user_id in ADMIN_IDS


# ============================================================
# КНОПКИ
# ============================================================

def moderation_keyboard(user_id, message_id):

    # В кнопке храним, кто прислал и какое сообщение,
    # чтобы потом уведомить автора о решении
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="✅ Опубликовать",
                callback_data=f"ok:{user_id}:{message_id}"
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"no:{user_id}:{message_id}"
            ),
        ]]
    )


def status_keyboard(text):

    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=text,
                callback_data="done"
            )
        ]]
    )


# ============================================================
# ИМЯ АВТОРА
# ============================================================

def describe_user(user):

    name = user.full_name

    if user.username:
        name += f" (@{user.username})"

    return f"{name}, id {user.id}"


# ============================================================
# BOT
# ============================================================

bot = Bot(BOT_TOKEN)

dp = Dispatcher()


# ============================================================
# /start
# ============================================================

@dp.message(CommandStart(), F.chat.type == "private")
async def start(message: Message):

    await message.answer(
        "Привет! Пришли мне фото, видео или гифку — "
        "после проверки модератором она появится в канале."
    )


# ============================================================
# ПОЛУЧЕНИЕ КОНТЕНТА ОТ ПОЛЬЗОВАТЕЛЯ
# ============================================================

@dp.message(
    F.photo | F.video | F.animation,
    F.chat.type == "private"
)
async def receive_media(message: Message):

    keyboard = moderation_keyboard(
        message.from_user.id,
        message.message_id
    )


    for admin_id in ADMIN_IDS:

        try:

            # Копия без пометки «переслано».
            # Именно её потом и опубликуем в канал.
            await bot.copy_message(
                chat_id=admin_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=keyboard
            )

            await bot.send_message(
                admin_id,
                f"⬆️ Прислал: {describe_user(message.from_user)}"
            )

        except Exception as error:

            logging.error(
                f"Не удалось отправить модератору {admin_id}: {error}"
            )


    await message.reply(
        "Спасибо! Отправил на модерацию 🙌"
    )


# ============================================================
# ВСЁ ОСТАЛЬНОЕ В ЛИЧКЕ
# ============================================================

@dp.message(F.chat.type == "private")
async def other(message: Message):

    await message.answer(
        "Я принимаю только фото, видео и гифки."
    )


# ============================================================
# РЕШЕНИЕ МОДЕРАТОРА
# ============================================================

@dp.callback_query(F.data.startswith("ok:") | F.data.startswith("no:"))
async def decide(call: CallbackQuery):

    if not is_admin(call.from_user.id):

        await call.answer("Нет прав", show_alert=True)
        return


    action, user_id, user_message_id = call.data.split(":")


    if action == "ok":

        try:

            # Публикуем копию, которая пришла модератору
            await bot.copy_message(
                chat_id=CHANNEL_ID,
                from_chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )

        except Exception as error:

            logging.error(
                f"Ошибка публикации: {error}"
            )

            await call.answer(
                f"Не удалось опубликовать: {error}",
                show_alert=True
            )
            return


        status = "✅ Опубликовано"
        user_text = "Твой пост опубликован в канале! 🎉"

    else:

        status = "❌ Отклонено"
        user_text = "К сожалению, модератор отклонил твой пост."


    # Меняем кнопки на статус, чтобы не нажать повторно
    try:

        await call.message.edit_reply_markup(
            reply_markup=status_keyboard(status)
        )

    except Exception:
        pass


    # Уведомляем автора
    try:

        await bot.send_message(
            int(user_id),
            user_text,
            reply_parameters=ReplyParameters(
                message_id=int(user_message_id),
                allow_sending_without_reply=True
            )
        )

    except Exception as error:

        logging.info(
            f"Не удалось уведомить пользователя {user_id}: {error}"
        )


    await call.answer(status)
    logging.info(f"{status}: пост от {user_id}")


@dp.callback_query(F.data == "done")
async def already_done(call: CallbackQuery):

    await call.answer("Решение уже принято")


# ============================================================
# ЗАПУСК БОТА
# ============================================================

async def main():

    logging.info(
        "Бот запускается..."
    )

    await dp.start_polling(bot)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())
