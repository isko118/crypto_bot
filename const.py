import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")

BOT_TOKEN = os.getenv("BOT_TOKEN")

URL = 'https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest?slug='

BTC_SLUG = 'bitcoin'

ETC_SLUG = 'ethereum'

HEADERS = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': API_KEY,
}
URL_BTC = 'https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest?slug=bitcoin'

URL_ETC = 'https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest?slug=ethereum'
