import telebot
import json
from datetime import datetime
from types import SimpleNamespace
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, Message
import calendar
from dateutil.relativedelta import relativedelta
import asyncio

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
# print(telebot.types.MenuButtonCommands('commands').to_json())
# print(bot.get_chat_menu_button())
res = bot.set_chat_menu_button(None, telebot.types.MenuButtonWebApp('web_app', 'hello world', telebot.types.WebAppInfo('https://google.com')))
print(res)

class Calendar():
    def __init__(self, msg, callback) -> None:
        self.callback = callback
        self.msg_text = 'Выберите начальную дату'
        self.msg = msg
        self.date = datetime.today()
        self.date1 = None
        self.setup_buttons()

    def setup_buttons(self):
        btns = [[InlineKeyboardButton(self.date.strftime('%B %Y'), callback_data='ignore')]]
        day_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        btns.append([InlineKeyboardButton(x, callback_data='ignore') for x in day_names])
        cal = calendar.monthcalendar(self.date.year, self.date.month)
        today = datetime.today()
        for week in cal:
            week_btns = []
            for day in week:
                if day == 0:
                    week_btns.append(InlineKeyboardButton(' ', callback_data='ignore'))
                else:
                    txt = str(day)
                    if day == today.day and self.date.month == today.month:
                        txt = '[' + txt + ']'
                    week_btns.append(InlineKeyboardButton(txt, callback_data=f'date {self.date.year}/{self.date.month}/{day}'))
            btns.append(week_btns)

        btns.append([InlineKeyboardButton('◀️', callback_data='cal_left'), InlineKeyboardButton(
            '❌', callback_data='cal_close'), InlineKeyboardButton('▶️', callback_data='cal_right')])

        bot.edit_message_text(self.msg_text, self.msg.chat.id, self.msg.message_id, reply_markup=InlineKeyboardMarkup(btns))

    def forward(self):
        self.date += relativedelta(months=1)
        self.setup_buttons()

    def backward(self):
        self.date -= relativedelta(months=1)
        self.setup_buttons()

    def close(self):
        bot.delete_message(self.msg.chat.id, self.msg.message_id)

    def on_date(self, date):
        if self.date1 is None:
            self.date1 = date
            self.msg_text = 'Выберите конечную дату'
            self.setup_buttons()
        else:
            self.callback(self.msg, self.date1, date)


active_cal: Calendar = None


@bot.callback_query_handler(func=lambda x: x.message)
def callback(callback: telebot.types.CallbackQuery):
    global active_cal
    match callback.data:
        case 'profile':
            bot.edit_message_text('Загрузка...', callback.message.chat.id, callback.message.message_id)
            profile(callback.message)
        case 'schedule':
            active_cal = Calendar(callback.message, schedule)
        case 'homework':
            homework(callback.message)
        case 'marksdate':
            marksdate(callback.message)
        case 'marks':
            marks(callback.message)
        case 'cal_left':
            if active_cal:
                active_cal.backward()
        case 'cal_right':
            if active_cal:
                active_cal.forward()
        case 'cal_close':
            if active_cal:
                active_cal.close()
                active_cal = None
        case _:
            if callback.data.startswith('date') and active_cal:
                active_cal.on_date(datetime.strptime(callback.data, 'date %Y/%m/%d'))


@bot.message_handler(commands=['profile'])
def profile_cmd(message):
    msg = bot.send_message(message.chat.id, 'Загрузка...')
    profile(msg)


def profile(message: Message):
    data = meshapi.profile(env['mesh_token'], env['student_id'])
    data = json.loads(data, object_hook=lambda d: SimpleNamespace(**d)).children[0]

    txt = f'''Здравствуйте, {data.last_name} {data.first_name} {data.middle_name}!
Дата рождения: {data.birth_date or 'Не указана'}
Дата создания аккаунта: {data.enrollment_date or 'Не указана'}
Номер телефона: {data.phone or 'Не указан'}
Email: {data.email or 'Не указан'}
Школа: {data.school.short_name or data.school.name or 'Не указана'}
Класс: {data.class_name or 'Не указан'}
Снилс: <tg-spoiler>{data.snils or 'Не указан'}</tg-spoiler>

person_id: {data.contingent_guid}
id: {data.id}
school_id: {data.school.id}

<b>Внимание! Мы не храним вашу информацию, вся эта информация получена из МЭШ!</b>'''

    bot.edit_message_text(txt, message.chat.id, message.message_id, parse_mode='HTML')


@bot.message_handler(commands=['schedule'])
def schedule_cmd(message):
    global active_cal
    msg = bot.send_message(message.chat.id, 'Выберите начальную дату')
    active_cal = Calendar(msg, schedule)


def schedule(message: Message, date1, date2):
    bot.edit_message_text('Загрузка...', message.chat.id, message.message_id)

    data_all = asyncio.run(meshapi.schedule(env['mesh_token'], env['student_id'], date1, date2))
    i = 0
    for data in data_all:
        data = json.loads(data, object_hook=lambda d: SimpleNamespace(**d))
        date = datetime.strptime(data.date, '%Y-%m-%d')

        msg = f'<b>{date.strftime("%d.%m.%Y")}</b>: {data.summary}\n\n'

        cur_lesson = 1
        for event in data.activities:
            if event.type == 'LESSON':
                msg += f'<i>{cur_lesson} урок 🕒 {datetime.fromtimestamp(event.begin_utc).strftime("%H:%M")} - {datetime.fromtimestamp(event.end_utc).strftime("%H:%M")}'
                if event.room_number is not None:
                    msg += f' 🚪каб. {event.room_number}'
                if event.lesson.replaced:
                    msg += ' (зам.)'
                msg += '</i>\n'
                msg += f'📖 <b>{event.lesson.subject_name}</b>'
                if event.lesson.homework:
                    msg += f'\n🏠 {event.lesson.homework}'
                cur_lesson += 1
            else:
                msg += f'🏃 <i>Перемена {datetime.fromtimestamp(event.begin_utc).strftime("%H:%M")} - {datetime.fromtimestamp(event.end_utc).strftime("%H:%M")}</i>'
            msg += '\n\n'

        if i == 0:
            bot.edit_message_text(msg, message.chat.id, message.message_id, parse_mode='HTML', disable_web_page_preview=True)
        else:
            bot.send_message(message.chat.id, msg, parse_mode='HTML', disable_web_page_preview=True)
        i += 1


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
    print(message.chat.id)
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton('Расписание', callback_data='schedule'), InlineKeyboardButton('ДЗ', callback_data='homework')],
        [InlineKeyboardButton('Оценки по дате', callback_data='marksdate'), InlineKeyboardButton('Все оценки', callback_data='marks')],
        [InlineKeyboardButton('Профиль', callback_data='profile'), InlineKeyboardButton('Обновить токен', callback_data='refreshtoken')]
    ])

    bot.send_message(message.chat.id, 'Выберите действие', reply_markup=markup)


bot.infinity_polling()
