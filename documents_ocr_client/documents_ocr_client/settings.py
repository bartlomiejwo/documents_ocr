import os
import logging.config


SERVER_IP = '192.168.1.3'
SERVER_PORT = 5050
SERVER_ENCODING = 'UTF-8'

HEADER_SIZE_IN_BYTES = 4
HEADER_BYTE_ORDER = 'big'

PACKET_SIZE_READ = 4096

CONNECTION_ONLINE_CHECK_INTERVAL = 60 * 10

SUPPORTED_EXTS = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif']

FILES_LIMIT_IN_QUEUE = 10

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INCOMING_PATH = os.path.join(BASE_DIR, 'to_process')
QUEUE_PATH = os.path.join(BASE_DIR, 'queue')
PROCESSED_PATH = os.path.join(BASE_DIR, 'processed')
ERROR_PATH = os.path.join(BASE_DIR, 'error')
DUPLICATES_PATH = os.path.join(BASE_DIR, 'duplicates')

PATH_MOD_CURRENT_YEAR = '{CURRENT_YEAR}'
PATH_MOD_DOCUMENT_YEAR = '{DOCUMENT_YEAR}'

ARCHIVE_PROCESSED_FILES = True
DAYS_TO_KEEP_ARCHIVE = 90

DOCUMENT_PATTERN_MATCH_THRESHOLD = 0.4

DOCUMENT_WZ = 'WZ'
DOCUMENT_WZ_PEPCO = 'PEPCO_WZ'
DOCUMENT_RS = 'RS'
DOCUMENT_WYS = 'WYS'
DOCUMENT_WW = 'WW'
DOCUMENT_FVS = 'FVS'
DOCUMENT_KVS = 'KVS'
DOCUMENT_AM = 'AM'

DOCUMENTS_CONFIG = {
    DOCUMENT_WZ: {
        'patterns': ['WZ/[0-9]+/[0-9]+', 'wydanie', 'zewnętrzne', 'wydanie.*zewnętrzne', 'numer[ :]+wz', 'numer[ :]+w2', 'waga.*brutto', 'palety.*euro', 'palety.*zwykłe', 'potwierdzam.*odbiór',],
        'exact_pattern': 'WZ/[0-9]+/[0-9]+',
        'similar_pattern': '[^ ]*/[0-9 ]+/[0-9 ]+',
        'prefix': 'WZ',
        'separator': '/',
        'number_extraction_method': 'get_document_numbers_common',
        'analyze_when_document_type_not_detected': True,
        'min_length': 11,
        'max_length': 12,
        'similar_prefixes': ['WŻ', 'WWZJ', 'WZ4', 'WWZ', 'WVZ', 'WZZ', 'WW2', 'WZJ', 'WWZZ', 'ZWWZ', 'KWZ', 'KWŻ', 'KWZZ',
                            "K'WZ", "'WZ", 'WWWZ', 'W2Ż', 'VZ', 'ALLETSWZ', 'WŻ2', 'WZ2', 'WWZ2', 'W2', 'W2;', 'WZŻ', 'WŻŻ',
                            '1NZ', 'WZ)', 'Z', 'NZ', 'MZ', 'M2', 'M7',],
        'processed_path': os.path.join(BASE_DIR, 'processed_dirs', PATH_MOD_DOCUMENT_YEAR, 'WZ'),
    },
    DOCUMENT_WZ_PEPCO: {
        'patterns': ['WZ/[0-9]+/[0-9]+', 'numer[ :]+wz', 'wz.*no', 'pepco', 'nr.*zamówienia.*pepco', 'zamówienia.*pepco'],
        'exact_pattern': 'WZ/[0-9]+/[0-9]+',
        'similar_pattern': '[^ ]*/[0-9]+/[0-9]+',
        'prefix': 'WZ',
        'separator': '/',
        'number_extraction_method': 'get_document_numbers_common',
        'analyze_when_document_type_not_detected': False,
        'min_length': 12,
        'max_length': 12,
        'similar_prefixes': ['WŻ', 'WWZJ', 'WZ4', 'WWZ', 'WVZ', 'WZZ', 'WW2', 'WZJ', 'WWZZ', 'ZWWZ', 'KWZ', 'KWŻ', 'KWZZ',
                            "K'WZ", "'WZ", 'WWWZ', 'W2Ż', 'VZ', 'ALLETSWZ', 'WŻ2', 'WZ2', 'WWZ2', 'W2', 'W2;', 'WZŻ', 'WŻŻ',
                            '1NZ', 'WZ)', 'Z', 'NZ', 'MZ', 'M2', 'M7',],
        'processed_path': os.path.join(BASE_DIR, 'processed_dirs', PATH_MOD_DOCUMENT_YEAR, 'WZ'),
    },
    DOCUMENT_WYS: {
        'patterns': ['wysyłka.*nr.*[0-9]+', 'wysyłka.*nr', 'wysy.*[0-9]+', 'użytkownik', 'miejsce.*kompletacji', 'nr.*zlecenia.*od.*klienta', 'raport.*z.*programu.*qguar', 'z.*programu', 'qguar', 'właściciel.*stella',],
        'exact_pattern': '[0-9]+',
        'similar_pattern': ['wysyłka.*nr.*[0-9 ]{6,}', 'wys.*n.*[0-9 ]{6,}', 'wys.*r.*[0-9 ]{6,}', 'wys[ ]*[0-9]{6,}'], 
        'prefix': 'WYS',
        'separator': '',
        'number_extraction_method': 'get_document_numbers_WYS',
        'analyze_when_document_type_not_detected': True,
        'min_length': 6,
        'max_length': 6,
        'similar_prefixes': [],
        'processed_path': os.path.join(BASE_DIR, 'processed_dirs', 'WYS'),
    },
    DOCUMENT_RS: {
        'patterns': ['RS/[0-9]+/[0-9]+', 'wydanie', 'zewnętrzne', 'wydanie.*zewnętrzne', 'numer[ :]+rs', 'waga.*brutto', 'palety.*euro', 'palety.*zwykłe', 'potwierdzam.*odbiór', 'stella.*pack.*rws', 'pack.*rws', ],
        'exact_pattern': 'RS/[0-9]+/[0-9]+',
        'similar_pattern': '[^ ]*/[0-9]+/[0-9]+',
        'prefix': 'RS',
        'separator': '/',
        'number_extraction_method': 'get_document_numbers_common',
        'analyze_when_document_type_not_detected': True,
        'min_length': 11,
        'max_length': 11,
        'similar_prefixes': ['R5', ],
        'processed_path': os.path.join(BASE_DIR, 'processed_dirs', PATH_MOD_DOCUMENT_YEAR, 'RS'),
    },
    DOCUMENT_WW: {
        'patterns': ['WW/[0-9]+/[0-9]+', 'wydanie', 'zewnętrzne', 'wydanie.*zewnętrzne', 'numer[ :]+ww', 'waga.*brutto', 'palety.*euro', 'palety.*zwykłe', 'potwierdzam.*odbiór', 'brak', ' 00001 ',],
        'exact_pattern': 'WW/[0-9]+/[0-9]+',
        'similar_pattern': '[^ ]*/[0-9]+/[0-9]+',
        'prefix': 'WW',
        'separator': '/',
        'number_extraction_method': 'get_document_numbers_common',
        'analyze_when_document_type_not_detected': True,
        'min_length': 11,
        'max_length': 11,
        'similar_prefixes': ['VW', 'WWW', 'WWWW',],
        'processed_path': os.path.join(BASE_DIR, 'processed_dirs', PATH_MOD_DOCUMENT_YEAR, 'WW'),
    },
    DOCUMENT_AM: {
        'patterns': ['AM[0-9]+', 'Stella.*Pack', 'arkusz', 'wiersze.*arkusza', 'arkusza.*magazynowego', 'wiersze.*arkusza.*magazynowego', 'magazynowego.*transakcja', 'transakcja',],
        'exact_pattern': 'AM[0-9]+',
        'similar_pattern': ['arkusz.*AMOB[Ó]?[0-9]+', 'AM[Ó]?[0-9]+', 'arkusz.*AN[Ó]?[0-9]+', 'AN[Ó]?[0-9]+',],
        'prefix': 'AM',
        'separator': '',
        'number_extraction_method': 'get_document_numbers_WYS',
        'analyze_when_document_type_not_detected': True,
        'min_length': 10,
        'max_length': 10,
        'similar_prefixes': [],
        'processed_path': os.path.join(BASE_DIR, 'processed_dirs', 'AM'),
    },
    DOCUMENT_FVS: {
        'patterns': ['FVS/[0-9]+/[0-9]+', 'faktura', 'vat', 'faktura.*vat', 'vat.*nr', 'faktura.*vat.*nr', 'dokumentu.*vat'],
        'exact_pattern': 'FVS/[0-9]+/[0-9]+',
        'similar_pattern': '[^ ]*/[0-9]+/[0-9]+',
        'prefix': 'FVS',
        'separator': '/',
        'number_extraction_method': 'get_document_numbers_common',
        'analyze_when_document_type_not_detected': True,
        'min_length': 11,
        'similar_prefixes': ['FVVS',],
        'processed_path': os.path.join(BASE_DIR, 'processed_dirs', PATH_MOD_DOCUMENT_YEAR, 'FVS'),
    },
    DOCUMENT_KVS: {
        'patterns': ['KVS/[0-9]+/[0-9]+', 'faktura', 'vat', 'faktura.*vat', 'korygująca', 'vat.*korygująca', 'korygująca.*nr', 'dokumentu.*vat', 'do.*fvs', ],
        'exact_pattern': 'KVS/[0-9]+/[0-9]+',
        'similar_pattern': '[^ ]*/[0-9]+/[0-9]+',
        'prefix': 'KVS',
        'separator': '/',
        'number_extraction_method': 'get_document_numbers_common',
        'analyze_when_document_type_not_detected': True,
        'min_length': 11,
        'max_length': 11,
        'similar_prefixes': [],
        'processed_path': os.path.join(BASE_DIR, 'processed_dirs', PATH_MOD_DOCUMENT_YEAR, 'KVS'),
    },
}

LANGUAGE = 'pol'

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
        'file_ocr_connection': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'formatter': 'verbose',
            'filename': os.path.join(LOGGING_PATH, 'ocr_connection.log'),
            'when': 'midnight',
            'interval': 1,
            'backupCount': 14
        },
        'file_document_processing_queue': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'formatter': 'verbose',
            'filename': os.path.join(LOGGING_PATH, 'document_processing_queue.log'),
            'when': 'midnight',
            'interval': 1,
            'backupCount': 14
        },
        'file_documents_processor': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'formatter': 'verbose',
            'filename': os.path.join(LOGGING_PATH, 'documents_processor.log'),
            'when': 'midnight',
            'interval': 1,
            'backupCount': 14
        },
    },
    'loggers': { 
        'ocr_connection': { 
            'handlers': ['console', 'file_ocr_connection'],
            'level': 'INFO',
            'propagate': True
        },
        'document_processing_queue': { 
            'handlers': ['console', 'file_document_processing_queue'],
            'level': 'INFO',
            'propagate': True
        },
        'documents_processor': { 
            'handlers': ['console', 'file_documents_processor'],
            'level': 'INFO',
            'propagate': True
        },
    } 
}

logging.config.dictConfig(LOGGING_CONFIG)
