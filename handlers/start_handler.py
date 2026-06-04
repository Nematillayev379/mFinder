from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from utils.languages import get_message, LANGUAGES

router = Router()

VALID_LANGS = set(LANGUAGES.keys())
user_langs: dict[int, str] = {}


def get_user_lang(user_id: int) -> str:
    return user_langs.get(user_id, "en")


@router.message(CommandStart())
async def cmd_start(message: Message):
    lang = get_user_lang(message.from_user.id)
    await message.answer(get_message(lang, "start"))


@router.message(Command("help"))
async def cmd_help(message: Message):
    lang = get_user_lang(message.from_user.id)
    await message.answer(get_message(lang, "help"))


@router.message(Command("lang"))
async def cmd_lang(message: Message):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=f"lang_{code}")]
        for code, label in LANGUAGES.items()
    ])

    await message.answer("🌐 Tilni tanlang / Choose language:", reply_markup=keyboard)


@router.callback_data(F.data.startswith("lang_"))
async def callback_lang(callback_query: CallbackQuery):
    lang_code = callback_query.data.replace("lang_", "")
    if lang_code not in VALID_LANGS:
        lang_code = "en"
    user_langs[callback_query.from_user.id] = lang_code
    await callback_query.message.edit_text(get_message(lang_code, "lang_set"))
    await callback_query.answer()
