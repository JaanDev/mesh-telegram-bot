import telebot
import json
from datetime import datetime
from types import SimpleNamespace
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
import calendar
from dateutil.relativedelta import relativedelta

import meshapi

with open('env.json', 'r') as f:
    env = json.load(f)

print('Starting bot')

bot = telebot.TeleBot(env['token'])

bot.set_my_commands([
    BotCommand('start', 'Start working with the bot'),
    BotCommand('profile', 'Get your Mesh profile info'),
    BotCommand('schedule', 'Get your schedule for date(s)'),
    BotCommand('homework', 'Get your homework for date(s)'),
    BotCommand('marksdate', 'Get your marks for date(s)'),
    BotCommand('marks', 'Get all your marks')
])

active_cal_msg: telebot.types.Message = None
active_cal_date: datetime = None
active_cal_cb: None


def setup_calendar_buttons(message, year, month):
    date = datetime(year=year, month=month, day=1)
    btns = [[InlineKeyboardButton(date.strftime('%B %Y'), callback_data='ignore')]]
    day_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    btns.append([InlineKeyboardButton(x, callback_data='ignore') for x in day_names])
    cal = calendar.monthcalendar(date.year, date.month)
    for week in cal:
        week_btns = []
        for day in week:
            if day == 0:
                week_btns.append(InlineKeyboardButton(' ', callback_data='ignore'))
            else:
                week_btns.append(InlineKeyboardButton(str(day), callback_data=f'date {date.year}/{date.month}/{day}'))
        btns.append(week_btns)

    btns.append([InlineKeyboardButton('◀️', callback_data='cal_left'), InlineKeyboardButton(
        '❌', callback_data='cal_close'), InlineKeyboardButton('▶️', callback_data='cal_right')])

    bot.edit_message_text(message.text, message.chat.id, message.id, reply_markup=InlineKeyboardMarkup(btns))


def setup_calendar(chat_id, callback):
    global active_cal_date, active_cal_msg, active_cal_cb
    active_cal_cb = callback

    msg = bot.send_message(chat_id, 'Выберите начальную дату')
    active_cal_msg = msg
    active_cal_date = datetime.now()
    setup_calendar_buttons(msg, active_cal_date.year, active_cal_date.month)

def continue_calendar(msg, date1):


@bot.callback_query_handler(func=lambda x: x.message)
def callback(callback: telebot.types.CallbackQuery):
    global active_cal_date, active_cal_msg
    match callback.data:
        case 'profile':
            profile(callback.message)
        case 'schedule':
            schedule_cmd(callback.message)
        case 'homework':
            homework(callback.message)
        case 'marksdate':
            marksdate(callback.message)
        case 'marks':
            marks(callback.message)
        case 'cal_left':
            active_cal_date -= relativedelta(months=1)
            setup_calendar_buttons(active_cal_msg, active_cal_date.year, active_cal_date.month)
        case 'cal_right':
            active_cal_date += relativedelta(months=1)
            setup_calendar_buttons(active_cal_msg, active_cal_date.year, active_cal_date.month)
        case 'cal_close':
            bot.delete_message(active_cal_msg.chat.id, active_cal_msg.id)
            active_cal_msg = None
            active_cal_date = None
            active_cal_cb = None
        case _:
            print('callback:', callback.data)
            if callback.data.startswith('date'):
                active_cal_cb(callback.message, datetime.strptime(callback.data, 'date %Y/%m/%d'))


@bot.message_handler(commands=['profile'])
def profile(message):
    data = meshapi.profile(env['mesh_token'], env['student_id'])['children'][0]
    txt = f'''Здравствуйте, {data['last_name']} {data['first_name']} {data['middle_name']}!
Дата рождения: {data.get('birth_date', 'Не указана')}
Номер телефона: {data.get('phone', 'Не указан')}
Email: {data.get('email', 'Не указан')}
Класс: {data.get('class_name', 'Не указан')}

person_id: {data['contingent_guid']}
id: {data['id']}
school_id: {data['school']['id']}'''
    bot.send_message(message.chat.id, txt)


@bot.message_handler(commands=['schedule'])
def schedule_cmd(message):
    print('Schedule command')
    setup_calendar(message.chat.id, schedule)

def schedule(message):
    tgmsg = bot.send_message(message.chat.id, 'Загрузка...')

    data = meshapi.schedule(env['mesh_token'], env['student_id'],
                            datetime.strptime('20/12/23', '%d/%m/%y'))
    data = json.loads(data, object_hook=lambda d: SimpleNamespace(**d))

    msg = f'<b>{data.date}</b>: {data.summary}\n\n'

    for event in data.activities:
        if event.type == 'LESSON':
            msg += f'<i>{event.info} 🕒 {datetime.fromtimestamp(event.begin_utc).strftime("%H:%M")} - {datetime.fromtimestamp(event.end_utc).strftime("%H:%M")} 🚪каб. {event.room_number}'
            if event.lesson.replaced:
                msg += ' (зам.)'
            msg += '</i>\n'
            msg += f'📖 <b>{event.lesson.subject_name}</b>\n'
            msg += f'🏠 {event.lesson.homework}'
        else:
            msg += f'🏃 <i>Перемена {datetime.fromtimestamp(event.begin_utc).strftime("%H:%M")} - {datetime.fromtimestamp(event.end_utc).strftime("%H:%M")}</i>'
        msg += '\n\n'

    bot.edit_message_text(msg, tgmsg.chat.id, tgmsg.message_id, parse_mode='HTML', disable_web_page_preview=True)


@bot.message_handler(commands=['homework'])
def homework(message):
    bot.send_message(message.chat.id, 'homework')


@bot.message_handler(commands=['marksdate'])
def marksdate(message):
    bot.send_message(message.chat.id, 'marksdate')


@bot.message_handler(commands=['marks'])
def marks(message):
    bot.send_message(message.chat.id, 'marks')


@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup(row_width=2)

    btn1 = InlineKeyboardButton('Профиль', callback_data='profile')
    btn2 = InlineKeyboardButton('Расписание', callback_data='schedule')
    btn3 = InlineKeyboardButton('ДЗ', callback_data='homework')
    btn4 = InlineKeyboardButton('Оценки по дате', callback_data='marksdate')
    btn5 = InlineKeyboardButton('Все оценки', callback_data='marks')

    markup.add(btn1, btn2, btn3, btn4, btn5)

    bot.send_message(message.chat.id, 'Выберите действие', reply_markup=markup)


bot.infinity_polling()
