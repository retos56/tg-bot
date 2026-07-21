import os
import sys
import subprocess
from datetime import datetime

# --- БЛОК АВТОПОДКАЧКИ БИБЛИОТЕК ---
def install_requirements():
    required_packages = ["aiogram", "python-dotenv"]
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            print(f"Библиотека {package} не найдена. Устанавливаю...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

install_requirements()
# ----------------------------------------------

import asyncio
import logging
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, 
    CallbackQuery,
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

import database

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None

if not API_TOKEN or not ADMIN_ID:
    sys.exit("Ошибка: Переменные API_TOKEN или ADMIN_ID не найдены в файле .env!")

database.init_db()

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Состояния FSM
class BookingForm(StatesGroup):
    name = State()
    event = State()
    event_custom = State()
    start_date = State()         # Стартовая дата
    days_count = State()         # Количество дней
    guests_count = State()
    want_extra = State()
    extra_info = State()
    phone = State()

class AdminStates(StatesGroup):
    waiting_for_admin_date = State()
    waiting_for_admin_days = State()


# --- КНОПКИ ---

def get_start_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏡 Забронировать домик", callback_data="start_booking")]
    ])

def get_event_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💕 Романтический отдых на двоих", callback_data="event_romance")],
        [InlineKeyboardButton(text="👨‍👩‍👧‍👦 Отдых семьей / друзьями", callback_data="event_family")],
        [InlineKeyboardButton(text="🎂 День рождения", callback_data="event_birthday")],
        [InlineKeyboardButton(text="💍 Свадьба", callback_data="event_wedding")],
        [InlineKeyboardButton(text="🏢 Корпоратив", callback_data="event_corporate")],
        [InlineKeyboardButton(text="🧖 Посещение бани", callback_data="event_bath")],
        [InlineKeyboardButton(text="✏️ Свой вариант", callback_data="event_custom")]
    ])

def get_yes_no_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Просмотр записей"), KeyboardButton(text="📅 Занять дату")],
            [KeyboardButton(text="❌ Удаление записей")]
        ],
        resize_keyboard=True
    )


# --- ХЕНДЛЕРЫ КЛИЕНТСКОЙ ЧАСТИ ---

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n"
        "Добро пожаловать в бота бронирования нашего уютного домика. "
        "Нажми на кнопку ниже, чтобы оставить заявку.",
        reply_markup=get_start_keyboard()
    )

@dp.callback_query(F.data == "start_booking")
async def start_booking(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await callback_query.message.answer(
        "Отлично! Давайте заполним небольшую анкету.\n\n"
        "Шаг 1: Как к вам обращаться? Введите ваше Имя:",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(BookingForm.name)

@dp.message(BookingForm.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Шаг 2: Укажите планируемое мероприятие:", reply_markup=get_event_keyboard())
    await state.set_state(BookingForm.event)

@dp.callback_query(BookingForm.event, F.data.startswith("event_"))
async def process_event_selection(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    events_map = {
        "event_romance": "Романтический отдых на двоих",
        "event_family": "Отдых семьей / друзьями",
        "event_birthday": "День рождения",
        "event_wedding": "Свадьба",
        "event_corporate": "Корпоратив",
        "event_bath": "Посещение бани"
    }
    choice = callback_query.data

    if choice == "event_custom":
        await callback_query.message.answer("Напишите ваш вариант мероприятия:")
        await state.set_state(BookingForm.event_custom)
    else:
        event_text = events_map.get(choice, "Неизвестное мероприятие")
        await state.update_data(event=event_text)
        await callback_query.message.edit_text(f"Выбрано мероприятие: **{event_text}**")
        await callback_query.message.answer(
            "Шаг 3: Укажите начальную дату заезда в формате ДД.ММ.ГГГГ (например: 25.07.2026):"
        )
        await state.set_state(BookingForm.start_date)

@dp.message(BookingForm.event_custom)
async def process_custom_event(message: Message, state: FSMContext):
    await state.update_data(event=message.text)
    await message.answer(
        "Шаг 3: Укажите начальную дату заезда в формате ДД.ММ.ГГГГ (например: 25.07.2026):"
    )
    await state.set_state(BookingForm.start_date)

# Ввод стартовой даты
@dp.message(BookingForm.start_date)
async def process_start_date(message: Message, state: FSMContext):
    input_date = message.text.strip()
    
    try:
        parsed_date = datetime.strptime(input_date, "%d.%m.%Y").date()
    except ValueError:
        await message.answer("❌ Неверный формат даты! Пожалуйста, введите дату в формате ДД.ММ.ГГГГ (например: 25.07.2026):")
        return

    today = datetime.now().date()
    if parsed_date < today:
        await message.answer(f"❌ Нельзя забронировать домик на прошедшую дату ({input_date})!\nВведите актуальную дату:")
        return

    await state.update_data(start_date=input_date)
    await message.answer("Укажите количество дней проживания (числом, например: 2):")
    await state.set_state(BookingForm.days_count)

# Ввод количества дней и проверка доступности
@dp.message(BookingForm.days_count)
async def process_days_count(message: Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("❌ Пожалуйста, введите корректное число дней (положительное целое число):")
        return

    days_count = int(message.text)
    user_data = await state.get_data()
    start_date_str = user_data['start_date']

    # Проверка интервала
    is_free, busy_date = database.check_date_range_availability(start_date_str, days_count)

    if not is_free:
        alt_date = database.find_next_available_start_date(start_date_str, days_count)
        alt_text = f"\n\nПредлагаем вам выбрать новую дату, например: {alt_date} на {days_count} дн." if (alt_text_condition := alt_date) else ""
        
        await message.answer(
            f"❌ Дата/период начиная с {start_date_str} на {days_count} дн. недоступны (день {busy_date} уже занят).{alt_text}\n\n"
            f"Пожалуйста, введите новую дату заезда в формате ДД.ММ.ГГГГ:"
        )
        await state.set_state(BookingForm.start_date)
        return

    await state.update_data(days_count=days_count)
    await message.answer("Шаг 4: Сколько человек планируется? (укажите число):")
    await state.set_state(BookingForm.guests_count)

@dp.message(BookingForm.guests_count)
async def process_guests(message: Message, state: FSMContext):
    await state.update_data(guests_count=message.text)
    await message.answer("Шаг 5: Желаете ли вы добавить дополнительную информацию или пожелания?", reply_markup=get_yes_no_keyboard())
    await state.set_state(BookingForm.want_extra)

@dp.message(BookingForm.want_extra)
async def process_want_extra(message: Message, state: FSMContext):
    answer = message.text.strip().lower()
    if answer == "да":
        await message.answer("Напишите ваши дополнительные пожелания или информацию:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(BookingForm.extra_info)
    elif answer == "нет":
        await state.update_data(extra_info="Не указано")
        await message.answer(
            "Шаг 6: Пожалуйста, оставьте ваш контактный номер телефона.",
            reply_markup=get_phone_keyboard()
        )
        await state.set_state(BookingForm.phone)
    else:
        await message.answer("Пожалуйста, воспользуйтесь кнопками 'Да' или 'Нет'.")

@dp.message(BookingForm.extra_info)
async def process_extra_info(message: Message, state: FSMContext):
    await state.update_data(extra_info=message.text)
    await message.answer(
        "Шаг 6: Пожалуйста, оставьте ваш контактный номер телефона.",
        reply_markup=get_phone_keyboard()
    )
    await state.set_state(BookingForm.phone)

@dp.message(BookingForm.phone)
async def process_phone(message: Message, state: FSMContext):
    phone_number = message.contact.phone_number if message.contact else message.text

    await state.update_data(phone=phone_number)
    user_data = await state.get_data()
    await state.clear()

    database.add_booking(
        user_id=message.from_user.id,
        username=message.from_user.username or "скрыт",
        name=user_data['name'],
        event=user_data['event'],
        date=user_data['start_date'],
        days_count=user_data['days_count'],
        guests_count=user_data['guests_count'],
        extra_info=user_data['extra_info'],
        phone=user_data['phone']
    )

    booking_report = (
        "🔔 Новая заявка на бронирование домика!\n\n"
        f"👤 Имя: {user_data['name']}\n"
        f"🎉 Мероприятие: {user_data['event']}\n"
        f"📅 Дата заезда: {user_data['start_date']}\n"
        f"⏳ Кол-во дней: {user_data['days_count']}\n"
        f"👥 Количество человек: {user_data['guests_count']}\n"
        f"📝 Доп. информация: {user_data['extra_info']}\n"
        f"📞 Телефон: {user_data['phone']}\n\n"
        f"🔗 Юзернейм: @{message.from_user.username or 'скрыт'}\n"
        f"🆔 ID: `{message.from_user.id}`"
    )

    await message.answer(
        "🎉 Спасибо! Ваша заявка успешно отправлена администратору.",
        reply_markup=ReplyKeyboardRemove()
    )

    try:
        await bot.send_message(chat_id=ADMIN_ID, text=booking_report, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Не удалось отправить сообщение админу: {e}")
        
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет прав для выполнения этой команды. ❌")
        return
    await message.answer("Добро пожаловать в админ-панель! 🛠", reply_markup=get_admin_keyboard())

@dp.message(F.text == "📋 Просмотр записей")
async def admin_view_bookings(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    bookings = database.get_all_bookings()
    if not bookings:
        await message.answer("В базе данных пока нет ни одной записи. 🤷‍♂️")
        return

    response = "📋 Список активных бронирований:\n\n"
    for row in bookings:
        days = row[6] if len(row) > 6 and row[6] else 1
        response += (
            f"🆔 Запись №{row[0]}\n"
            f"👤 Имя: {row[3]} (@{row[2]})\n"
            f"🎉 Событие: {row[4]}\n"
            f"📅 Заезд: {row[5]} (дней: {days})\n"
            f"👥 Кол-во: {row[7]} чел.\n"
            f"📞 Тел: {row[9]}\n"
            f"📝 Доп: {row[8]}\n"
            f"----------------------------------\n"
        )
        if len(response) > 3500:
            await message.answer(response, parse_mode="Markdown")
            response = ""

    if response:
        await message.answer(response, parse_mode="Markdown")

@dp.message(F.text == "📅 Занять дату")
async def admin_occupy_date_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("📝 Введите начальную дату в формате ДД.ММ.ГГГГ (например, `18.07.2026`):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminStates.waiting_for_admin_date)

@dp.message(AdminStates.waiting_for_admin_date)
async def admin_occupy_date_process(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.clear()
        return

    input_date = message.text.strip()
    try:
        parsed_date = datetime.strptime(input_date, "%d.%m.%Y").date()
    except ValueError:
        await message.answer("❌ Неверный формат даты! Введите дату в формате ДД.ММ.ГГГГ:")
        return

    if parsed_date < datetime.now().date():
        await message.answer("❌ Нельзя занять дату из прошлого!")
        return

    await state.update_data(admin_date=input_date)
    await message.answer("Укажите количество дней для блокировки (числом):")
    await state.set_state(AdminStates.waiting_for_admin_days)

@dp.message(AdminStates.waiting_for_admin_days)
async def admin_occupy_days_process(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.clear()
        return

    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("❌ Введите корректное целое число дней:")
        return

    days_count = int(message.text)
    user_data = await state.get_data()
    admin_date = user_data['admin_date']

    is_free, busy_date = database.check_date_range_availability(admin_date, days_count)

    if not is_free:
        await message.answer(f"⚠️ Не удалось занять: день {busy_date} уже бронирован! Попробуйте другую дату.")
        await state.set_state(AdminStates.waiting_for_admin_date)
        return

    await state.clear()
    database.add_booking(
        user_id=ADMIN_ID,
        username="admin",
        name="Администратор",
        event="Бронь администратора (Закрыто)",
        date=admin_date,
        days_count=days_count,
        guests_count="—",
        extra_info="Внесено вручную через панель управления",
        phone="—"
    )

    await message.answer(f"✅ Дата {admin_date} на {days_count} дн. успешно забронирована!", reply_markup=get_admin_keyboard())

@dp.message(F.text == "❌ Удаление записей")
async def admin_delete_menu(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    bookings = database.get_all_bookings()
    if not bookings:
        await message.answer("База данных пуста. 📭")
        return

    inline_buttons = []
    for row in bookings:
        days = row[6] if len(row) > 6 and row[6] else 1
        btn_text = f"Удалить №{row[0]} ({row[3]} - {row[5]} [{days} дн.])"
        inline_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"del_{row[0]}")])

    await message.answer("Выберите запись для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_buttons))

@dp.callback_query(F.data.startswith("del_"))
async def admin_delete_action(callback_query: CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("Доступ запрещен!", show_alert=True)
        return

    booking_id = int(callback_query.data.split("_")[1])
    if database.delete_booking(booking_id):
        await callback_query.answer(f"Запись №{booking_id} удалена!", show_alert=True)
        bookings = database.get_all_bookings()
        if bookings:
            inline_buttons = []
            for row in bookings:
                days = row[6] if len(row) > 6 and row[6] else 1
                inline_buttons.append([InlineKeyboardButton(text=f"Удалить №{row[0]} ({row[3]} - {row[5]} [{days} дн.])", callback_data=f"del_{row[0]}")])
            await callback_query.message.edit_text("Выберите запись для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_buttons))
        else:
            await callback_query.message.edit_text("Все записи удалены! 🎉")
    else:
        await callback_query.answer("Ошибка при удалении.", show_alert=True)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())