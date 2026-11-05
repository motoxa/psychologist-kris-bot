import json
from aiogram import Router, F, types
import secrets
import sqlite3
from aiogram.filters import Command
import aiohttp
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import BufferedInputFile
import os
from aiogram.types import Message, CallbackQuery
import asyncio
from aiogram.types import FSInputFile
from keyboards import (get_request_type_panel, get_result_panel,
    get_first_base_question_panel, get_second_base_question_panel,
    get_first_health_question_panel, get_first_relationship_question_panel,
    get_first_finance_question_panel, get_second_finance_question_panel,
    get_final_panel)
from ai_service import get_ai_analysis
from aiogram.utils.media_group import MediaGroupBuilder
from sheet_start import sheet_start
from datetime import datetime
from zoneinfo import ZoneInfo
from sheet_final import sheet_final
import html
import re

router = Router()

RESULTS_DIR = "/app/.results"

FINAL_SHEET_HEADERS = [
    "USER_ID", "USERNAME", "FULLNAME", "DATE/TIME", "Тема запроса",
    "Первый базовый", "Второй базовый", "Третий базовый",
    "Первый по здоровью", "Второй по здоровью",
    "Первый по отношениям", "Второй по отношениям",
    "Первый по финансам", "Второй по финансам",
]

TELEGRAM_MESSAGE_LIMIT = 4096

def filled_fields(row: list):
    for header, value in zip(FINAL_SHEET_HEADERS, row):
        value = "" if value is None else str(value)
        if value:
            yield header, value

async def notify_recipients(bot, row: list, sheet_ok: bool):
    notify_ids = [i for i in re.split(r"[,;\s]+", os.getenv("NOTIFY_IDS", "")) if i]

    if not notify_ids:
        return

    status = "✅ записано в таблицу" if sheet_ok else "⚠️ НЕ записано в таблицу!"
    blocks = []

    for header, value in filled_fields(row):
        chunk_size = 3000
        parts = [value[i:i + chunk_size] for i in range(0, len(value), chunk_size)]

        for n, part in enumerate(parts):
            title = header if n == 0 else f"{header} (продолжение)"
            blocks.append(f"<b>{html.escape(title)}:</b> {html.escape(part)}")

    first = f"📝 <b>Новая анкета</b> ({status})"
    messages, current = [], ""

    for block in blocks:
        if not messages and not current:
            candidate = f"{first}\n\n{block}"
        else:
            candidate = f"{current}\n{block}"
        if len(candidate) > TELEGRAM_MESSAGE_LIMIT:
            messages.append(current or first)
            current = block
        else:
            current = candidate

    messages.append(current or first)

    for notify_id in notify_ids:
        try:
            for text in messages:
                await bot.send_message(int(notify_id), text, parse_mode="HTML")
        except Exception as e:
            print(f"Не удалось отправить анкету получателю {notify_id}: {e}")

def save_result_file(row: list, now: datetime, ai_result: str):
    text = "\n".join(f"{header}: {value}" for header, value in filled_fields(row))
    text += f"\n\n{ai_result}\n"

    try:
        os.makedirs(RESULTS_DIR, exist_ok=True)
        name = now.strftime("%Y-%m-%d-%H-%M-%S")
        path = os.path.join(RESULTS_DIR, f"{name}.txt")

        try:
            f = open(path, "x", encoding="utf-8")
        except FileExistsError:
            path = os.path.join(RESULTS_DIR, f"{name}-{row[0]}.txt")
            f = open(path, "w", encoding="utf-8")

        with f:
            f.write(text)
    except Exception as e:
        print(f"Не удалось сохранить результат в файл: {e}")

start_video = FSInputFile("video1.mp4")
final_video = FSInputFile("video2.mp4")

class QuestionState (StatesGroup):
    waiting_for_first_base_question = State()
    waiting_for_second_base_question = State()
    waiting_for_third_base_question = State()
    waiting_for_first_health_question = State()
    waiting_for_second_health_question = State()
    waiting_for_first_relationship_question = State()
    waiting_for_second_relationship_question = State()
    waiting_for_first_finance_question = State()
    waiting_for_second_finance_question = State()

@router.message(Command("start"))
async def start(message: Message, state : FSMContext):
    await message.answer_video_note(
        video_note=start_video)
    await message.answer( """
<b>Кристина Шабанова | психолог</b>\n
➡️ <a href='https://www.instagram.com/psyholog.shabanova'>Instagram</a>
➡️ <a href='https://t.me/izmeni_gzizn'>Telegram</a>
➡️ <a href='https://www.instagram.com/retreat_kris'>Ретриты</a>

Помогаю увидеть причины повторяющихся сценариев в
<b>отношениях, деньгах, реализации и внутреннем состоянии </b> и
найти то, что мешает прийти к желаемому результату.

В работе мне важно не просто поговорить о проблеме, а помочь тебе <b>увидеть её глубже и запустить здоровое изменение.</b>

🤍 Эта диагностика — первый шаг
    """, disable_web_page_preview=True, parse_mode='HTML'
    )
    await state.clear()
    user_id = str(message.from_user.id)
    try:
        existing_ids = sheet_start.col_values(1)
        if user_id not in existing_ids:
            username=f"@{message.from_user.username}" if message.from_user.username else "None"
            fullname = message.from_user.full_name
            now = datetime.now(ZoneInfo("Asia/Makassar"))
            created_at = now.strftime("%d.%m.%Y %H:%M:%S")
            sheet_start.append_row([user_id, username, fullname, created_at])
    except Exception as e:
        print(e)
    await asyncio.sleep(3)
    await message.answer(
        'Выбери тему своего запроса, нажав на кнопку ниже ⬇️',
        reply_markup=get_request_type_panel()
    )

@router.callback_query(F.data.contains('request_type_'))
async def start_test(callback : CallbackQuery, state : FSMContext):
    await callback.answer()
    rt = callback.data.split('_')[2]
    await state.update_data(request_type=rt)
    await callback.message.answer("""
Что сейчас больше всего забирает твою энергию и внимание?

• Выбери из вариантов ответов
• Или напиши свой вариант
    """, reply_markup=get_first_base_question_panel())

    #await callback.message.answer(rt)
    await state.set_state(QuestionState.waiting_for_first_base_question)

@router.message(QuestionState.waiting_for_first_base_question)
async def run_first_base_question (message : Message, state : FSMContext):
    client_answer = message.text
    await state.update_data(first_base_answer=client_answer)
    await message.answer(
        'Если ничего не менять в ближайшие 3–6–12 месяцев, твой вопрос/проблема решится сама?',
        reply_markup=get_second_base_question_panel()
    )
    await state.set_state(QuestionState.waiting_for_second_base_question)

@router.message(QuestionState.waiting_for_second_base_question)
async def run_second_base_question (message : Message, state : FSMContext):
    client_answer = message.text
    await state.update_data(second_base_answer=client_answer)
    await message.answer('Напиши какой результат/состояние/решение хочешь получить? ⬇️')
    await state.set_state(QuestionState.waiting_for_third_base_question)

@router.message(QuestionState.waiting_for_third_base_question)
async def run_third_base_question (message : Message, state : FSMContext):
    client_answer = message.text
    await state.update_data(third_base_answer=client_answer)

    data = await state.get_data()
    request_type = data.get('request_type')

    if request_type == 'health':
        await message.answer("""
Как твоё внутреннее состояние сейчас отражается на теле и самочувствии?

• Выбери из вариантов ответов
• Или напиши свой вариант
        """, reply_markup=get_first_health_question_panel())
        await state.set_state(QuestionState.waiting_for_first_health_question)

    elif request_type == 'relationship':
        await message.answer("""
Что чаще всего повторяется в твоих отношениях?

• Выбери из вариантов ответов
• Твой вариант
        """, reply_markup=get_first_relationship_question_panel())
        await state.set_state(QuestionState.waiting_for_first_relationship_question)

    elif request_type == 'finance':
        await message.answer("""
Что сейчас больше всего мешает тебе выйти на более высокий финансовый или профессиональный уровень?

• Выбери из вариантов ответов
• Твой вариант
        """, reply_markup=get_first_finance_question_panel())
        await state.set_state(QuestionState.waiting_for_first_finance_question)

@router.message(QuestionState.waiting_for_first_health_question)
async def run_first_health_question(message : Message, state : FSMContext):
    client_answer = message.text
    await state.update_data(first_health_answer=client_answer)
    await message.answer("""
Какие попытки решить это у тебя уже были?
    """)
    await state.set_state(QuestionState.waiting_for_second_health_question)

@router.message(QuestionState.waiting_for_first_relationship_question)
async def run_first_relationship_question(message : Message, state : FSMContext):
    client_answer = message.text
    await state.update_data(first_relationship_answer=client_answer)
    await message.answer("""
Какие попытки решить это у тебя уже были?
    """)
    await state.set_state(QuestionState.waiting_for_second_relationship_question)

@router.message(QuestionState.waiting_for_first_finance_question)
async def run_first_finance_question(message : Message, state : FSMContext):
    client_answer = message.text
    await state.update_data(first_finance_answer=client_answer)
    await message.answer("""
Как ты обычно реагируешь, когда нужно сделать шаг, который может увеличить твой доход?

• Выбери из вариантов ответов
• Или напиши свой вариант
    """, reply_markup=get_second_finance_question_panel())
    await state.set_state(QuestionState.waiting_for_second_finance_question)

@router.message(QuestionState.waiting_for_second_health_question)
async def run_second_health_question(message : Message, state : FSMContext):
    client_answer = message.text
    await state.update_data(second_health_answer=client_answer)

    await asyncio.sleep(1)
    await message.answer("""
Спасибо за уделённое время 🙏
Нажми на кнопку, чтобы получить результат
    """, reply_markup=get_result_panel())

@router.message(QuestionState.waiting_for_second_relationship_question)
async def run_second_relationship_question(message : Message, state : FSMContext):
    client_answer = message.text
    await state.update_data(second_relationship_answer=client_answer)

    await asyncio.sleep(1)
    await message.answer("""
Спасибо за уделённое время 🙏
Нажми на кнопку, чтобы получить результат
    """, reply_markup=get_result_panel())

@router.message(QuestionState.waiting_for_second_finance_question)
async def run_second_finance_question(message : Message, state : FSMContext):
    client_answer = message.text
    await state.update_data(second_finance_answer=client_answer)

    await asyncio.sleep(1)
    await message.answer("""
Спасибо за уделённое время 🙏
Нажми на кнопку, чтобы получить результат
    """, reply_markup=get_result_panel())

@router.callback_query(F.data == 'get_result')
async def get_result(callback : CallbackQuery, state : FSMContext):
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer("Внимательно изучаю твои ответы и скоро вернусь с результатом 🤍")

    data = await state.get_data()
    request_type = data.get('request_type')

    answers = {
        'first_base_answer' : data.get('first_base_answer', ''),
        'second_base_answer' : data.get('second_base_answer', ''),
        'third_base_answer': data.get('third_base_answer', ''),
        'first_health_answer': data.get('first_health_answer', ''),
        'second_health_answer': data.get('second_health_answer', ''),
        'first_relationship_answer' : data.get('first_relationship_answer', ''),
        'second_relationship_answer': data.get('second_relationship_answer', ''),
        'first_finance_answer': data.get('first_finance_answer', ''),
        'second_finance_answer': data.get('second_finance_answer', ''),
    }

    user_id = str(callback.from_user.id)
    username=f"@{callback.from_user.username}" if callback.from_user.username else "None"
    fullname = callback.from_user.full_name
    now = datetime.now(ZoneInfo("Asia/Makassar"))
    created_at = now.strftime("%d.%m.%Y %H:%M:%S")

    row = [user_id, username, fullname, created_at, request_type, *answers.values()]
    sheet_ok = True

    try:
        sheet_final.append_row(row)
    except Exception as e:
        sheet_ok = False
        print(e)

    await notify_recipients(callback.bot, row, sheet_ok)

    async def typing():
        while True:
            await asyncio.sleep(4)
            await callback.bot.send_chat_action(chat_id=callback.message.chat.id, action="typing")

    typing_task = asyncio.create_task(typing())

    result = None

    try:
        result = await get_ai_analysis(request_type, answers)
        file_text = result or "[AI вернул пустой ответ]"
    except Exception as e:
        print(f"Ошибка AI: {e}")
        file_text = f"[Ответ AI не получен: {e}]"
    finally:
        typing_task.cancel()

    save_result_file(row, now, file_text)

    if result:
        try:
            await callback.message.answer(result, parse_mode="HTML")
        except Exception as e:
            print(f"Не удалось отправить ответ AI с HTML, отправляю без разметки: {e}")

            try:
                await callback.message.answer(result)
            except Exception as e:
                print(f"Не удалось отправить ответ AI: {e}")

    try:
        await callback.message.answer_video_note(video_note=final_video)
    except Exception as e:
        print(f"Не удалось отправить видео: {e}")

    await callback.message.answer(
        'Можешь выбрать то, что тебе больше подходит',
        reply_markup=get_final_panel()
    )


@router.callback_query(F.data == 'get_reviews')
async def run_show_reviews(callback : CallbackQuery, state : FSMContext):
    await callback.answer()
    media_group = MediaGroupBuilder(caption='Отзывы')
    media_group.add_photo(media=FSInputFile('reviews/photo_1_2026-09-09_15-15-03.jpg'))
    media_group.add_photo(media=FSInputFile('reviews/photo_2_2026-09-09_15-15-03.jpg'))
    media_group.add_photo(media=FSInputFile('reviews/photo_3_2026-09-09_15-15-03.jpg'))
    media_group.add_photo(media=FSInputFile('reviews/photo_4_2026-09-09_15-15-03.jpg'))
    media_group.add_photo(media=FSInputFile('reviews/photo_5_2026-09-09_15-15-03.jpg'))
    media_group.add_photo(media=FSInputFile('reviews/photo_6_2026-09-09_15-15-03.jpg'))
    media_group.add_photo(media=FSInputFile('reviews/photo_7_2026-09-09_15-15-03.jpg'))
    media_group.add_photo(media=FSInputFile('reviews/photo_8_2026-09-09_15-15-03.jpg'))
    media_group.add_photo(media=FSInputFile('reviews/photo_9_2026-09-09_15-15-03.jpg'))
    media_group.add_photo(media=FSInputFile('reviews/photo_10_2026-09-09_15-15-03.jpg'))

    await callback.message.answer_media_group(
        media=media_group.build()
    )

    await callback.message.answer(
        'Можешь выбрать то, что тебе больше подходит',
        reply_markup=get_final_panel()
    )

@router.callback_query(F.data == 'get_payment_of_reflection_table')
async def run_payment_of_reflection_table(callback : CallbackQuery, state : FSMContext):
    await callback.answer()
    await callback.message.answer("""
Отлично, хороший выбор!

Оплати 199 рублей по реквизитам:

[Реквизиты]

После оплаты отправь чек @kris_shabanova — я сразу пришлю тебе таблицу.
    """)
