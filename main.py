from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, Message, Bot, BotCommandScopeAllPrivateChats
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, Application
import logging
import json
from datetime import datetime
from types import SimpleNamespace

import meshapi
import tg_cal

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING
)

print('Starting bot')

calendars = {}
token_messages = {}


def mark_to_string(value, weight, is_exam) -> str:
    WEIGHT_CHARS = ['₁', '₂', '₃', '₄', '₅']

    txt = ''
    if is_exam:
        txt += '<b><i>'
    txt += f'{value}{WEIGHT_CHARS[weight - 1] if weight != 1 else ""}'
    if is_exam:
        txt += '</i></b>'

    return txt


async def start(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton('Расписание', callback_data='schedule'), InlineKeyboardButton('ДЗ', callback_data='homework')],
        [InlineKeyboardButton('Оценки по дате', callback_data='marksdate'), InlineKeyboardButton('Все оценки', callback_data='marks')],
        [InlineKeyboardButton('Ответы на тест МЭШ', callback_data='testanswers'),
         InlineKeyboardButton('Уведомления', callback_data='notifications')],
        [InlineKeyboardButton('Профиль', callback_data='profile'), InlineKeyboardButton('Обновить токен', callback_data='refreshtoken')]
    ])

    await ctx.bot.send_message(upd.effective_chat.id, 'Выберите действие', reply_markup=markup)


async def profile_cmd(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await ctx.bot.send_message(upd.effective_chat.id, 'Загрузка...')
    await profile(msg, ctx.bot)


async def profile(msg: Message, bot: Bot) -> None:
    data = await meshapi.profile(str(msg.chat_id))
    if not data:
        await bot.edit_message_text('Не удалось получить данные. Попробуйте обновить токен или попробуйте ещё раз позже', msg.chat_id, msg.id)
        return

    data = json.loads(data, object_hook=lambda d: SimpleNamespace(**d)).children[0]

    txt = f'''Здравствуйте, {data.last_name} {data.first_name} {data.middle_name}!
Дата рождения: {data.birth_date or 'Не указана'}
Номер телефона: {data.phone or 'Не указан'}
Email: {data.email or 'Не указан'}
Школа: {data.school.short_name or data.school.name or 'Не указана'}
Класс: {data.class_name or 'Не указан'}
Снилс: <tg-spoiler>{data.snils or 'Не указан'}</tg-spoiler>

person_id: {data.contingent_guid}
id: {data.id}
school_id: {data.school.id}

<b>Внимание! Мы не храним вашу информацию, вся эта информация получена из МЭШ!</b>'''

    await bot.edit_message_text(txt, msg.chat_id, msg.id, parse_mode='HTML')


async def schedule_cmd(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global calendars
    msg = await ctx.bot.send_message(upd.effective_chat.id, 'Выберите начальную дату')
    if not upd.effective_chat.id in calendars:
        calendars[upd.effective_chat.id] = {}
    calendars[upd.effective_chat.id][msg.id] = await tg_cal.Calendar.create(msg, schedule, ctx.bot)


async def schedule(msg: Message, bot: Bot, date1: datetime, date2: datetime) -> None:
    await bot.edit_message_text('Загрузка...', msg.chat_id, msg.id)

    data_all = await meshapi.schedule(str(msg.chat_id), date1, date2)
    if not data_all:
        await bot.edit_message_text('Не удалось получить данные. Попробуйте обновить токен или попробуйте ещё раз позже', msg.chat_id, msg.id)
        return

    i = 0
    for data in data_all:
        data = json.loads(data, object_hook=lambda d: SimpleNamespace(**d))
        date = datetime.strptime(data.date, '%Y-%m-%d')

        txt = f'🗓 <b>{date.strftime("%d.%m.%Y")}</b>: {data.summary}\n\n'

        cur_lesson = 1
        for event in data.activities:
            if event.type == 'LESSON':
                txt += f'<i>{cur_lesson} урок 🕒 {datetime.fromtimestamp(event.begin_utc).strftime("%H:%M")} - {datetime.fromtimestamp(event.end_utc).strftime("%H:%M")}'
                if event.room_number is not None:
                    txt += f' 🚪каб. {event.room_number}'
                if event.lesson.replaced:
                    txt += ' (зам.)'
                txt += '</i>\n'
                txt += f'📖 <b>{event.lesson.subject_name}</b>'
                if event.lesson.homework:
                    txt += f'\n🏠 {event.lesson.homework}'
                cur_lesson += 1
            else:
                txt += f'🏃 <i>Перемена {datetime.fromtimestamp(event.begin_utc).strftime("%H:%M")} - {datetime.fromtimestamp(event.end_utc).strftime("%H:%M")}</i>'
            txt += '\n\n'

        if i == 0:
            await bot.edit_message_text(txt, msg.chat_id, msg.id, parse_mode='HTML', disable_web_page_preview=True)
        else:
            await bot.send_message(msg.chat_id, txt, parse_mode='HTML', disable_web_page_preview=True)
        i += 1


async def homework_cmd(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global calendars
    msg = await ctx.bot.send_message(upd.effective_chat.id, 'Выберите начальную дату')
    if not upd.effective_chat.id in calendars:
        calendars[upd.effective_chat.id] = {}
    calendars[upd.effective_chat.id][msg.id] = await tg_cal.Calendar.create(msg, homework, ctx.bot)


async def homework(msg: Message, bot: Bot, date1: datetime, date2: datetime) -> None:
    await bot.edit_message_text('Загрузка...', msg.chat_id, msg.id)

    data_all = await meshapi.homework(str(msg.chat_id), date1, date2)
    if not data_all:
        await bot.edit_message_text('Не удалось получить данные. Попробуйте обновить токен или попробуйте ещё раз позже', msg.chat_id, msg.id)
        return

    i = 0

    for date, entries in data_all:
        txt = f'🗓 <b>{date}</b>\n\n'

        for entry in entries:
            txt += f'📖 <b>{entry["subject"]}</b>\n'
            txt += f'🏠 {entry["text"]}\n'
            txt += f'🕒 <i>Добавлено: {entry["created_at"]}</i>\n'
            if entry['created_at'] != entry['updated_at']:
                txt += f'🕒 <i>Изменено: {entry["updated_at"]}</i>\n'

            for att in entry['attachements']:
                txt += f'📄 <a href="{att["url"]}">{att["name"]}</a>\n'

            if len(entry['tests']['execute']) > 0:
                txt += '<i>Выполнить (см. дз!):</i>\n'
            for att in entry['tests']['execute']:
                txt += f'🏆 <a href="{att["url"]}">{att["name"]}</a>\n'

            examine = entry['tests']['examine']
            if examine > 0:
                def f1(a): return (a % 100)//10 != 1 and a % 10 == 1
                def f2(a): return (a % 100)//10 != 1 and a % 10 in [2, 3, 4]
                word = "тест" if f1(examine) else "теста" if f2(examine) else "тестов"
                txt += f'<i>Изучить: {examine} {word}...</i>\n'

            txt += '\n'

        if i == 0:
            await bot.edit_message_text(txt, msg.chat_id, msg.id, parse_mode='HTML', disable_web_page_preview=True)
        else:
            await bot.send_message(msg.chat_id, txt, parse_mode='HTML', disable_web_page_preview=True)

        i += 1


async def marksdate_cmd(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global calendars
    msg = await ctx.bot.send_message(upd.effective_chat.id, 'Выберите начальную дату')
    if not upd.effective_chat.id in calendars:
        calendars[upd.effective_chat.id] = {}
    calendars[upd.effective_chat.id][msg.id] = await tg_cal.Calendar.create(msg, marksdate, ctx.bot)


async def marksdate(msg: Message, bot: Bot, date1: datetime, date2: datetime) -> None:
    await bot.edit_message_text('Загрузка...', msg.chat_id, msg.id)

    data = await meshapi.marksdate(str(msg.chat_id), date1, date2)
    if not data:
        await bot.edit_message_text('Не удалось получить данные. Попробуйте обновить токен или попробуйте ещё раз позже', msg.chat_id, msg.id)
        return

    i = 0
    for day, entry in data:
        txt = f'🗓 <b>{day}</b>\n\n'

        for name, marks in entry.items():
            txt += f'📖 <b>{name}</b>\n'

            for mark in marks:
                txt += mark_to_string(mark['value'], mark['weight'], mark['is_exam'])

                if mark['comment'] != '':
                    txt += f' <tg-spoiler>({mark["comment"]})</tg-spoiler>'

                txt += ', '
            txt = txt[:-2]

            txt += '\n\n'

        if i == 0:
            await bot.edit_message_text(txt, msg.chat_id, msg.id, disable_web_page_preview=True, parse_mode='HTML')
        else:
            await bot.send_message(msg.chat_id, txt, disable_web_page_preview=True, parse_mode='HTML')

        i += 1


async def marks_cmd(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await ctx.bot.send_message(upd.effective_chat.id, 'Загрузка...')
    await marks(msg, ctx.bot)


async def marks(msg: Message, bot: Bot) -> None:
    data = await meshapi.marks(str(msg.chat_id))
    if not data:
        await bot.edit_message_text('Не удалось получить данные. Попробуйте обновить токен или попробуйте ещё раз позже', msg.chat_id, msg.id)
        return

    txt = ''

    for subj, entry in data.items():
        txt += f'📖 {subj}: {entry["avg"]}\n'

        for period, entry2 in entry['periods'].items():
            txt += f'<b>{period}</b>: {entry2["avg"]}'
            if entry2['final_mark']:
                txt += f' (итог: <b>{entry2["final_mark"]}</b>)'
            txt += '\n'
            for mark in entry2['marks']:
                txt += mark_to_string(mark['value'], mark['weight'], mark['is_exam'])

                txt += ', '

            txt = txt[:-2] + '\n'

        txt += '\n'

    await bot.edit_message_text(txt, msg.chat_id, msg.id, parse_mode='HTML')


async def notifications_cmd(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await ctx.bot.send_message(upd.effective_chat.id, 'Загрузка...')
    await notifications(msg, ctx.bot)


async def notifications(msg: Message, bot: Bot) -> None:
    data = await meshapi.notifications(str(msg.chat_id))
    if not data:
        await bot.edit_message_text('Не удалось получить данные. Попробуйте обновить токен или попробуйте ещё раз позже', msg.chat_id, msg.id)
        return

    last_date = ''
    txt = ''

    i = 0
    for entry in data:
        date_and_time = datetime.strptime(entry['datetime'], '%Y-%m-%d %H:%M:%S.%f')
        date = date_and_time.strftime('%d.%m.%Y')
        time = date_and_time.strftime('%H:%M:%S')

        if date != last_date:
            if txt:
                if i == 0:
                    await bot.edit_message_text(txt, msg.chat_id, msg.id, parse_mode='HTML', disable_web_page_preview=True)
                else:
                    await bot.send_message(msg.chat_id, txt, parse_mode='HTML', disable_web_page_preview=True)
                i += 1
            if i > 6:  # max. 7 messages
                break
            txt = f'🗓 <b>{date}</b>\n\n'

        lesson_date = datetime.strptime(
            entry['lesson_date'] if 'lesson_date' in entry else entry['new_date_prepared_for'], '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')

        match entry['event_type']:
            case 'update_mark':
                txt += f'📕 <i>{time}</i>: Изменение оценки ({mark_to_string(entry["new_mark_value"], entry["new_mark_weight"], entry["new_is_exam"])})\n'
                txt += f'Урок: {entry["subject_name"]} {lesson_date}\n'
            case 'create_mark':
                txt += f'📕 <i>{time}</i>: Новая оценка ({mark_to_string(entry["new_mark_value"], entry["new_mark_weight"], entry["new_is_exam"])})\n'
                txt += f'Урок: {entry["subject_name"]} {lesson_date}\n'
            case 'update_homework':
                txt += f'🏠 <i>{time}</i>: Изменение ДЗ ({entry["new_hw_description"]})\n'
                txt += f'Урок: {entry["subject_name"]} {lesson_date}\n'
            case 'create_homework':
                txt += f'🏠 <i>{time}</i>: Новое ДЗ ({entry["new_hw_description"]})\n'
                txt += f'Урок: {entry["subject_name"]} {lesson_date}\n'

        last_date = date


async def refreshtoken_cmd(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global token_messages
    bot = ctx.bot

    txt = 'Пожалуйста, перейдите по <a href="https://school.mos.ru/?backUrl=https%3A%2F%2Fschool.mos.ru%2Fv2%2Ftoken%2Frefresh%3FroleId%3D1%26subsystem%3D4">этой ссылке</a>, войдите в аккаунт, скопируйте весь текст и ответьте на это сообщение скопированным текстом'

    msg = await bot.send_message(upd.effective_chat.id, txt, parse_mode='HTML')

    token_messages[upd.effective_chat.id] = msg


async def callback(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global calendars, token_messages
    query = upd.callback_query

    try:
        if not upd.effective_chat.id in calendars:
            calendars[upd.effective_chat.id] = {}
        cal = calendars[upd.effective_chat.id][upd.effective_message.id]
    except:
        cal = None

    await query.answer()

    match query.data:
        case 'homework':
            calendars[upd.effective_chat.id][upd.effective_message.id] = await tg_cal.Calendar.create(upd.effective_message, homework, ctx.bot)
        case 'schedule':
            calendars[upd.effective_chat.id][upd.effective_message.id] = await tg_cal.Calendar.create(upd.effective_message, schedule, ctx.bot)
        case 'marksdate':
            calendars[upd.effective_chat.id][upd.effective_message.id] = await tg_cal.Calendar.create(upd.effective_message, marksdate, ctx.bot)
        case 'marks':
            await ctx.bot.edit_message_text('Загрузка...', upd.effective_chat.id, upd.effective_message.id)
            await marks(upd.effective_message, ctx.bot)
        case 'testanswers':
            await ctx.bot.send_message(upd.effective_chat.id, 'Получение ответов из теста МЭШ пока не поддерживается!')
        case 'notifications':
            await ctx.bot.edit_message_text('Загрузка...', upd.effective_chat.id, upd.effective_message.id)
            await notifications(upd.effective_message, ctx.bot)
        case 'profile':
            await ctx.bot.edit_message_text('Загрузка...', upd.effective_chat.id, upd.effective_message.id)
            await profile(upd.effective_message, ctx.bot)
        case 'refreshtoken':
            txt = 'Пожалуйста, перейдите по <a href="https://school.mos.ru/?backUrl=https%3A%2F%2Fschool.mos.ru%2Fv2%2Ftoken%2Frefresh%3FroleId%3D1%26subsystem%3D4">этой ссылке</a>, войдите в аккаунт, скопируйте весь текст и ответьте на это сообщение скопированным текстом'
            await ctx.bot.edit_message_text(txt, upd.effective_chat.id, upd.effective_message.id, parse_mode='HTML')

            token_messages[upd.effective_chat.id] = upd.effective_message
        case 'cal_left':
            if cal:
                await cal.backward()
        case 'cal_right':
            if cal:
                await cal.forward()
        case 'cal_close':
            if cal:
                await cal.close()
                calendars[upd.effective_chat.id][upd.effective_message.id] = None
        case _:
            if query.data.startswith('date') and cal:
                await cal.on_date(datetime.strptime(query.data, 'date %Y/%m/%d'))


async def reply_callback(upd: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global token_messages

    if upd.effective_chat.id in token_messages:
        new_token = upd.effective_message.text

        msg = await ctx.bot.send_message(upd.effective_chat.id, 'Пожалуйста, подождите...')

        result = await meshapi.try_add_new_token(new_token, upd.effective_chat.id)
        print(result)

        if not result:
            await ctx.bot.edit_message_text('Не получилось проверить токен, пожалуйста, попробуйте ещё раз (отвечайте на предыдущее сообщение)', msg.chat_id, msg.id)
        else:
            await ctx.bot.edit_message_text('Токен успешно изменён!', msg.chat_id, msg.id)
            del token_messages[upd.effective_chat.id]


async def post_init(application: Application) -> None:
    bot: Bot = application.bot
    await bot.set_my_commands(commands=[
        BotCommand('start', 'Start working with the bot'),
        BotCommand('profile', 'Get your Mesh profile info'),
        BotCommand('schedule', 'Get your schedule for date(s)'),
        BotCommand('homework', 'Get your homework for date(s)'),
        BotCommand('marksdate', 'Get your marks for date(s)'),
        BotCommand('marks', 'Get all your marks'),
        BotCommand('refreshtoken', 'Refresh/change your Mesh token'),
        BotCommand('testanswers', 'Get answers for a Mesh test'),
        BotCommand('notifications', 'Get latest notifications')
    ], scope=BotCommandScopeAllPrivateChats(), language_code='')
    await bot.set_my_commands(commands=[
        BotCommand('start', 'Начать работать с ботом'),
        BotCommand('profile', 'Получить информацию о профиле МЭШ'),
        BotCommand('schedule', 'Получить расписание на дату (даты)'),
        BotCommand('homework', 'Получить домашнее задание к дате (датам)'),
        BotCommand('marksdate', 'Получить оценки за дату (даты)'),
        BotCommand('marks', 'Получить все оценки'),
        BotCommand('refreshtoken', 'Обновить/изменить свой токен МЭШ'),
        BotCommand('testanswers', 'Получить ответы на тест МЭШ'),
        BotCommand('notifications', 'Получить последние уведомления')
    ], scope=BotCommandScopeAllPrivateChats(), language_code='ru')

if __name__ == '__main__':
    meshapi.load_db()

    app = ApplicationBuilder().token('6555791717:AAFJ8qLx_0GKywIAoF_tWsnDc25E1sTe8QY').post_init(post_init).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('profile', profile_cmd))
    app.add_handler(CommandHandler('schedule', schedule_cmd))
    app.add_handler(CommandHandler('homework', homework_cmd))
    app.add_handler(CommandHandler('marksdate', marksdate_cmd))
    app.add_handler(CommandHandler('marks', marks_cmd))
    app.add_handler(CommandHandler('notifications', notifications_cmd))
    app.add_handler(CommandHandler('refreshtoken', refreshtoken_cmd))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.REPLY, reply_callback))

    app.run_polling()
