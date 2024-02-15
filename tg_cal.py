from datetime import datetime
import calendar
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot, Message
from dateutil.relativedelta import relativedelta


class Calendar():
    def __init__(self, msg, callback, bot: Bot) -> None:
        self.callback = callback
        self.msg_text = 'Выберите начальную дату'
        self.msg: Message = msg
        self.date = datetime.today()
        self.date1 = None
        self.bot: Bot = bot

    @classmethod
    async def create(cls, msg, callback, bot):
        self = Calendar(msg, callback, bot)
        await self.setup_buttons()
        return self

    async def setup_buttons(self):
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
                    this_date = datetime(day=day, month=self.date.month, year=self.date.year)
                    if self.date1 and this_date < self.date1:
                        week_btns.append(InlineKeyboardButton(' ', callback_data='ignore'))
                    else:
                        txt = str(day)
                        if day == today.day and self.date.month == today.month and self.date.year == today.year:
                            txt = '[' + txt + ']'
                        week_btns.append(InlineKeyboardButton(txt, callback_data=f'date {self.date.year}/{self.date.month}/{day}'))
            btns.append(week_btns)

        btns.append([InlineKeyboardButton('◀️', callback_data='cal_left'), InlineKeyboardButton(
            '❌', callback_data='cal_close'), InlineKeyboardButton('▶️', callback_data='cal_right')])

        await self.bot.edit_message_text(self.msg_text, self.msg.chat_id, self.msg.id, reply_markup=InlineKeyboardMarkup(btns))

    async def forward(self):
        self.date += relativedelta(months=1)
        await self.setup_buttons()

    async def backward(self):
        self.date -= relativedelta(months=1)
        await self.setup_buttons()

    async def close(self):
        await self.bot.delete_message(self.msg.chat_id, self.msg.id)

    async def on_date(self, date):
        if self.date1 is None:
            self.date1 = date
            self.msg_text = 'Выберите конечную дату'
            await self.setup_buttons()
        else:
            await self.callback(self.msg, self.bot, self.date1, date)
