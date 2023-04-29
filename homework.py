import logging
import os
import time

import requests
from dotenv import load_dotenv
from telegram import Bot
from logging.handlers import RotatingFileHandler
from exceptions import GetApiAnswerError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 6
SPRINT_PERIOD = 1209600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('main.log', encoding='utf-8')
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Проверка доступности переменных окружения."""
    logger.info('Проверка передаваемых переменных.')
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    for token_key, token_value in tokens.items():
        if not token_value:
            logger.critical(f'Отсутствует переменная: {token_key}.')
            exit()


def send_message(bot, message):
    """Отправка сообщения в Телеграм чат."""
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logger.debug('Отправка сообщения в Telegram')


def get_api_answer(timestamp_now):
    """Запрос к единственному эндпоинту API-сервиса."""
    timestamp = timestamp_now
    payload = {'from_date': timestamp}
    try:
        logger.info('Запрос к эндпоинту API-сервиса.')
        response = requests.get(url=ENDPOINT,
                                headers=HEADERS,
                                params=payload
                                )
    except Exception as error:
        logger.error('Ошибка при запросе к API')
        raise GetApiAnswerError(error)
    if response.status_code != 200:
        logger.error('Эндпоинт недоступен')
        raise GetApiAnswerError('Эндппоинт недоступен')
    return response.json()


def check_response(response):
    """Проверка ответа API."""
    logger.info('Проверка ответа API.')
    if not isinstance(response, dict):
        raise TypeError(f'Запрос API не словарь. Передан {type(response)}.')
    keys = ['homeworks', 'current_date']
    for key in keys:
        if key not in response:
            logger.error(f'В ответе API нет ключа {key}')
            raise KeyError(f'В ответе API нет ключа {key}')
    homework, *_ = response.get('homeworks')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError(f'Ответ API не список. Передан {type(homework)}.')
    return homework


def parse_status(homework):
    """Извлечение ответа API."""
    logger.info('Извлечение статуса конкретной домашней работы.')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if not homework_name:
        logger.error(f'Отсутствует поле: {homework_name}')
        raise KeyError(f'Отсутствует поле: {homework_name}')
    if homework_status not in HOMEWORK_VERDICTS:
        logger.error(f'Неожиданный статус: {homework_status}.')
        raise KeyError(f'Неожиданный статус: {homework_status}.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp_now = int(time.time() - SPRINT_PERIOD)
    status = None

    while True:
        try:
            response = get_api_answer(timestamp_now)
            homework = check_response(response)
            if parse_status(homework) != status:
                status = parse_status(homework)
                send_message(bot, status)
            else:
                logger.debug('Статус не изменился!')
        except Exception as error:
            logger.error(f'Сбой в программе: {error}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
