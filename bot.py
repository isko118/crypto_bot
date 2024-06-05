"""
Телеграмм бот для отслеживания курса криптовалюты.
Позволяет задавать минимальное и максимальное значение

Автор - Искандер Насыров.

Дата: 05.06.2024
"""

import sqlite3

from threading import Lock

import requests
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (CallbackContext, CallbackQueryHandler,
                          CommandHandler, Filters, MessageHandler, Updater)

from const import API_KEY, BOT_TOKEN, URL_BTC, URL_ETC

load_dotenv()

headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': API_KEY,
}

lock = Lock()


def init_db():
    """
    Инициализирует базу данных SQLite и создает таблицу alerts.
    """
    conn = sqlite3.connect('alerts.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            currency TEXT NOT NULL,
            threshold REAL NOT NULL,
            threshold_type TEXT NOT NULL,
            delivered INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()


def add_alert(chat_id, currency, threshold, threshold_type):
    """
    Добавляет новое оповещение в базу данных.

    Args:
        chat_id (int): Идентификатор чата пользователя.
        currency (str): Криптовалюта для оповещения ('bitcoin' или 'ethereum').
        threshold (float): Значение порога для оповещения.
        threshold_type (str): Тип порога ('min' или 'max').
    """
    conn = sqlite3.connect('alerts.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO alerts ('
        'chat_id, currency, threshold, threshold_type'
        ') '
        'VALUES (?, ?, ?, ?)',
        (chat_id, currency, threshold, threshold_type))
    conn.commit()
    conn.close()


def get_alerts():
    """
    Получает все недоставленные оповещения из базы данных.

    Returns:
        list: Список недоставленных оповещений.
    """
    conn = sqlite3.connect('alerts.db')
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, chat_id, currency, threshold, threshold_type '
        'FROM alerts '
        'WHERE delivered = 0'
    )
    alerts = cursor.fetchall()
    conn.close()
    return alerts


def mark_alert_delivered(alert_id):
    """
    Помечает оповещение как доставленное в базе данных.

    Args:
        alert_id (int): Идентификатор оповещения
        для пометки как доставленного.
    """
    conn = sqlite3.connect('alerts.db')
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE alerts '
        'SET delivered = 1 '
        'WHERE id = ?',
        (alert_id,)
    )
    conn.commit()
    conn.close()


def start(update: Update, context: CallbackContext):
    """
    Обрабатывает команду /start и отправляет
    сообщение с опциями выбора криптовалюты.
    """
    keyboard = [
        [InlineKeyboardButton("Bitcoin",
                              callback_data='bitcoin')],

        [InlineKeyboardButton('Ethereum',
                              callback_data='ethereum')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        update.message.reply_text(
            "Выберите криптовалюту:",
            reply_markup=reply_markup
        )
    elif update.callback_query.message:
        update.callback_query.message.reply_text(
            "Выберите криптовалюту:",
            reply_markup=reply_markup
        )


def crypto_menu(update: Update, context: CallbackContext, currency):
    """
    Отображает меню с опциями для получения курса
    или установки порогов для выбранной криптовалюты.

    Args:
        currency (str): Выбранная криптовалюта ('bitcoin' или 'ethereum').
    """
    keyboard = [
        [InlineKeyboardButton("Узнать курс",
                              callback_data=f'{currency}_price')],

        [InlineKeyboardButton("Задать минимальное значение",
                              callback_data=f'{currency}_set_min')],

        [InlineKeyboardButton("Задать максимальное значение",
                              callback_data=f'{currency}_set_max')],

        [InlineKeyboardButton('Назад', callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.callback_query.message.edit_text(
        f"Вы выбрали {currency.capitalize()}. "
        f"Выберите действие:", reply_markup=reply_markup
    )


def button(update: Update, context: CallbackContext):
    """
    Обрабатывает нажатия кнопок в inline
    клавиатуре и перенаправляет к соответствующим функциям.
    """
    query = update.callback_query
    query.answer()
    if query.data == 'bitcoin':
        crypto_menu(update, context, 'bitcoin')
    elif query.data == 'ethereum':
        crypto_menu(update, context, 'ethereum')
    elif query.data.endswith('_price'):
        currency = query.data.split('_')[0]
        price = get_price(currency)
        query.edit_message_text(
            text=f"Цена {currency.capitalize()} в долларах: {price:.2f} USD",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton('Назад',
                                       callback_data=currency)]])
        )
    elif query.data.endswith('_set_min'):
        currency = query.data.split('_')[0]
        query.edit_message_text(
            text=f"Введите минимальное значение для {currency.capitalize()} в USD:",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton('Назад',
                                       callback_data=currency)]])
        )
        context.user_data['setting_threshold'] = (currency, 'min')
    elif query.data.endswith('_set_max'):
        currency = query.data.split('_')[0]
        query.edit_message_text(
            text=f"Введите максимальное значение для {currency.capitalize()} в USD:",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton('Назад',
                                       callback_data=currency)]])
        )
        context.user_data['setting_threshold'] = (currency, 'max')
    elif query.data == 'back':
        start(update, context)


def set_threshold(update: Update, context: CallbackContext):
    """
    Устанавливает пороговое значение для
    выбранной криптовалюты и тип (min или max).
    """
    threshold_info = context.user_data.get('setting_threshold')
    if threshold_info:
        currency, threshold_type = threshold_info
        try:
            threshold = float(update.message.text)
            with lock:
                add_alert(update.message.chat_id, currency,
                          threshold, threshold_type)
            update.message.reply_text(
                f"{threshold_type.capitalize()} значение для "
                f"{currency.capitalize()} установлено на {threshold} USD"
            )
        except ValueError:
            update.message.reply_text("Пожалуйста, введите правильное число.")
        finally:
            context.user_data['setting_threshold'] = None
            start(update, context)


def check_prices(context: CallbackContext):
    """
    Проверка стоимости криптовалюты и
    отправка оповещения, если достигнуты пороги.
    """
    with lock:
        alerts = get_alerts()
        for alert in alerts:
            alert_id, chat_id, currency, threshold, threshold_type = alert
            price = get_price(currency)

            if threshold_type == 'min' and price < threshold:
                context.bot.send_message(
                    chat_id=chat_id,
                    text=f"Внимание! Цена {currency.capitalize()} упала ниже "
                         f"минимального порога и составляет {price:.2f} USD"
                )
                mark_alert_delivered(alert_id)
            elif threshold_type == 'max' and price >= threshold:
                context.bot.send_message(
                    chat_id=chat_id,
                    text=f"Внимание! Цена {currency.capitalize()} достигла "
                         f"максимального порога и составляет: {price:.2f} USD"
                )
                mark_alert_delivered(alert_id)


def get_price(currency):
    """
    Получает текущую цену указанной криптовалюты.

    Args:
        currency (str): Криптовалюта ('bitcoin' или 'ethereum').

    Returns:
        float: Текущая цена криптовалюты в USD.
    """
    url = URL_BTC if currency == 'bitcoin' else URL_ETC
    response = requests.get(url, headers=headers)
    json_data = response.json()
    data = json_data['data']['1'] if (currency ==
                                      'bitcoin') else json_data['data']['1027']
    price = data['quote']['USD']['price']
    return price


def main():
    """
    Основная функция для инициализации бота,
    настройки обработчиков и запуска polling.
    """
    init_db()
    updater = Updater(token=BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    job_queue = updater.job_queue

    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command,
                                          set_threshold))

    job_queue.run_repeating(check_prices, interval=60, first=0)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
