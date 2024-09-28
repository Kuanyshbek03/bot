from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram import F
from aiogram import Router
from aiogram.utils import executor

bot = Bot(token="7360169582:AAGflab9qc-zgy1GtidVJI5jT_0rYBAHMag")


dp = Dispatcher()


router = Router()  # Используется Router в новой версии

@router.message(Command('start'))
async def start(message: types.Message):
    keyboard = web_app_keyboard()
    await message.answer("Запустите Web App", reply_markup=keyboard)

def web_app_keyboard():
    # Создание клавиатуры с Web App кнопкой
    keyboard_builder = ReplyKeyboardBuilder()
    web_app = WebAppInfo(url="https://yourwebsite.com/wheel/")  # Укажите правильный URL
    keyboard_builder.button(text="Испытай удачу", web_app=web_app)
    keyboard_builder.adjust(1)
    return keyboard_builder.as_markup(resize_keyboard=True)

@router.message(F.content_types == types.ContentType.WEB_APP_DATA)
async def web_app_data_handler(message: types.Message):
    discount = int(message.web_app_data.data)
    original_price = 1000  # Например, исходная цена товара
    final_price = original_price - (original_price * discount / 100)
    await message.answer(f"Ваша скидка: {discount}%. Итоговая цена: {final_price} руб.")

# Добавляем роутер в диспетчер
dp.include_router(router)

if __name__ == "__main__":
    # Запуск поллинга
    dp.run_polling(bot)