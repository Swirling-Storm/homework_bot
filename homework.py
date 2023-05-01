import logging
import os
import time
from logging.handlers import RotatingFileHandler

import requests
from dotenv import load_dotenv
from telegram import Bot, TelegramError

from exceptions import GetApiAnswerError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
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
        else:
            logger.info(f'С токеном {token_key} все ОК.')
    for token_key, token_value in tokens.items():
        if not token_value:
            logger.critical('Экстренный выход!!!')
            exit(1)


def send_message(bot, message):
    """Отправка сообщения в Телеграм чат."""
    logger.info('Отправка сообщения в Telegram')
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logger.debug('Сообщение отправилось в Telegram!')


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
    if not isinstance(response['homeworks'], list):
        raise TypeError('Ответ API не список.'
                        f'Передан {type(response["homeworks"])}.')


def parse_status(homework):
    """Извлечение ответа API."""
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
    logger.info('Запуск бота.')
    check_tokens()

    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp_now = int(time.time() - SPRINT_PERIOD)
    status = None

    while True:
        try:
            response = get_api_answer(timestamp_now)
            check_response(response)
            homework, *_ = response.get('homeworks')
            logger.info('Проверка прошлого статуса!')
            if parse_status(homework) != status:
                logger.debug('Изменение прошлого статуса!')
                status = parse_status(homework)
                timestamp_now = int(time.time() - SPRINT_PERIOD)
                try:
                    send_message(bot, status)
                except TelegramError:
                    logger.error('Ошибка отправки сообщения!')
            else:
                logger.debug('Статус не изменился!')
        except Exception:
            logger.exception('Сбой в программе:')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
