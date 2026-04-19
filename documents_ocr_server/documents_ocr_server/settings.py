import os
import multiprocessing
import logging.config


DEBUG = True

SERVER_IP = '192.168.1.2'
SERVER_PORT = 5050
CLIENTS_WHITE_LIST = []
CLIENTS_BLACK_LIST = []

CONNECTIONS_LIMIT = 1#int(multiprocessing.cpu_count() / 2)

HEADER_SIZE_IN_BYTES = 4
HEADER_BYTE_ORDER = 'big'
SERVER_ENCODING = 'UTF-8'

PACKET_SIZE_READ = 4096

CONNECTION_ONLINE_CHECK_INTERVAL = 30
CONNECTION_IDLE_TIMEOUT = 1800

ORIENTATION_CONFIDENCE_THRESHOLD = 3.51

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEMP_FILES_PATH = os.path.join(BASE_DIR, 'temp')

LOGGING_PATH = os.path.join(BASE_DIR, 'logs')

LOGGING_CONFIG = { 
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': { 
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': { 
        'console': { 
            'level': 'INFO',
            'formatter': 'simple',
            'class': 'logging.StreamHandler',
        },
        'file_ocr_server': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'formatter': 'verbose',
            'filename': os.path.join(LOGGING_PATH, 'ocr_server.log'),
            'when': 'midnight',
            'interval': 1,
            'backupCount': 14
        },
        'file_ocr_connection': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'formatter': 'verbose',
            'filename': os.path.join(LOGGING_PATH, 'ocr_connection.log'),
            'when': 'midnight',
            'interval': 1,
            'backupCount': 14,
        },
    },
    'loggers': { 
        'ocr_server': { 
            'handlers': ['console', 'file_ocr_server'],
            'level': 'INFO',
            'propagate': True
        },
        'ocr_connection': {
            'handlers': ['console', 'file_ocr_connection'],
            'level': 'INFO',
            'propagate': True,
        },
    } 
}

logging.config.dictConfig(LOGGING_CONFIG)
