import collections
from posixpath import split
import threading
import logging
import re
import pathlib
import os
from datetime import datetime, timedelta
import glob
import shutil

from ocr_connection import OCRConnection
import general
import settings


logger = logging.getLogger(__name__)

class DocumentProcessingQueue:

    def __init__(self, processed_path, error_path, duplicates_path, archive_processed_files,
                    days_to_keep_archive, document_pattern_match_threshold, documents_config,
                    supported_exts):
        self.queue = collections.deque()
        self.documents_in_processing = []
        self.processed_path = processed_path
        self.error_path = error_path
        self.duplicates_path = duplicates_path
        self.archive_processed_files = archive_processed_files
        self.days_to_keep_archive = days_to_keep_archive
        self.document_pattern_match_threshold = document_pattern_match_threshold
        self.documents_config = documents_config
        self.supported_exts = supported_exts

        self.server_may_be_ready = True

        self.files_in_queue_mutex = threading.Lock()

    def __len__(self):
        return len(self.queue) + len(self.documents_in_processing)

    def add_document(self, path, attempt_counter=1, file_bytes=None, rotation=None):
        file_ext = ''.join([s for s in pathlib.Path(path).suffixes if not ' ' in s])

        if file_ext.lower() in self.supported_exts:
            document = {
                'path': path,
                'attempt_counter': attempt_counter,
                'file_bytes': file_bytes,
                'rotation': rotation,
            }

            self.queue.append(document)
        else:
            general.move_file_to_new_dir(path, general.get_path(self.error_path), logger=logger)

    def add_document_to_front(self, path, attempt_counter=1, file_bytes=None, rotation=None):
        file_ext = ''.join([s for s in pathlib.Path(path).suffixes if not ' ' in s])

        if file_ext.lower() in self.supported_exts:
            document = {
                'path': path,
                'attempt_counter': attempt_counter,
                'file_bytes': file_bytes,
                'rotation': rotation,
            }

            self.queue.appendleft(document)
        else:
            general.move_file_to_new_dir(path, general.get_path(self.error_path), logger=logger)

    def get_document_to_process(self):
        with self.files_in_queue_mutex:
            document_to_ocr = self.queue.popleft()
            self.documents_in_processing.append(document_to_ocr)

        return document_to_ocr

    def remove_document_from_processing(self, document):
        with self.files_in_queue_mutex:
            try:
                self.documents_in_processing.remove(document)
            except ValueError:
                pass
        
    def file_paths_in_queue(self):
        with self.files_in_queue_mutex:
            return [x['path'] for x in self.queue] + [x['path'] for x in self.documents_in_processing]

    def allowed_to_try_to_connect_to_ocr_server(self):
        return self.server_may_be_ready

    def process(self):
        while self.queue:
            if not self.allowed_to_try_to_connect_to_ocr_server():
                break
            
            ocr_connection = self.connect_to_ocr_server()

            if not ocr_connection:
                break

            thread = threading.Thread(target=self.process_document, args=(ocr_connection,))
            thread.start()

    def connect_to_ocr_server(self):
        ocr_connection = OCRConnection()

        try:
            connected = ocr_connection.connect()
        except ConnectionRefusedError:
            return None

        if connected:
            if ocr_connection.available_spots_on_server < 1:
                self.server_may_be_ready = False
            else:
                self.server_may_be_ready = True

            return ocr_connection
        else:
            if ocr_connection.error is not None:
                logger.error(f'CONNECTING ERROR - {ocr_connection.error} - {ocr_connection.error_details}')
            else:
                logger.error(f'CONNECTING ERROR - UNKNOWN ERROR')

            return None

    def process_document(self, ocr_connection):
        document_to_ocr = self.get_document_to_process()

        try:
            ocr_success = self.ocr_document(
                ocr_connection,
                document_to_ocr['path'],
                document_to_ocr['file_bytes'],
                document_to_ocr['rotation']
            )

            if not ocr_success:
                self.remove_document_from_processing(document_to_ocr)
                return

            text_processing_success, document_numbers = self.process_document_text(
                document_to_ocr,
                ocr_connection.ocr_text_pages,
                ocr_connection.processed_file_bytes
            )

            if text_processing_success:
                self.save_document_numbers(document_numbers, document_to_ocr['path'])

                if self.archive_processed_files:
                    self.save_document_to_processed_archive(document_to_ocr['path'])
                else:
                    general.remove_file(document_to_ocr['path'], logger)
        except Exception as e:
            logger.exception(f'Unexpected exception: {str(e)}')
        finally:
            self.remove_document_from_processing(document_to_ocr)

    def ocr_document(self, ocr_connection, document_to_ocr, document_to_ocr_bytes=None, rotation=None):
        try:
            ocr_connection.process(document_to_ocr, document_to_ocr_bytes, rotation)
        except Exception as e:
            general.move_file_to_new_dir(document_to_ocr, general.get_path(self.error_path), logger=logger)
            self.remove_document_from_processing(document_to_ocr)
            self.server_may_be_ready = True
            raise e
        else:
            self.server_may_be_ready = True

            if ocr_connection.success:
                return True
            else:
                self.handle_ocr_processing_errors(ocr_connection, document_to_ocr)
                return False

    def handle_ocr_processing_errors(self, ocr_connection, document_to_ocr):
        if ocr_connection.error is not None:
            logger.error(f'{document_to_ocr} - {ocr_connection.error} - {ocr_connection.error_details}')

            if ocr_connection.error == OCRConnection.SERVER_NOT_RESPONDING_ERROR:
                self.add_document_to_front(document_to_ocr)
            else:
                general.move_file_to_new_dir(document_to_ocr, general.get_path(self.error_path), logger=logger)
        else:
            logger.error(f'{document_to_ocr} - UNKNOWN ERROR')
            general.move_file_to_new_dir(document_to_ocr, general.get_path(self.error_path), logger=logger)

    def process_document_text(self, document, text_pages, processed_file_bytes):
        document_type = self.get_document_type(text_pages)
        document_numbers = self.get_document_numbers(document_type, text_pages)

        if document_numbers:
            document_numbers = self.postprocess_document_numbers(document_type, document_numbers)

        if not document_type and not document_numbers:
            if 1 <= document['attempt_counter'] <= 3:
                self.put_document_into_processing_queue_with_different_rotation(
                    document,
                    processed_file_bytes,
                )
            else:
                general.move_file_to_new_dir(document['path'], general.get_path(self.error_path), logger=logger)
            
            return False, None
        else:
            if document_numbers:
                return True, document_numbers
            else:
                general.move_file_to_new_dir(document['path'], general.get_path(self.error_path), logger=logger)
                return False, None

    def put_document_into_processing_queue_with_different_rotation(self, 
            document_to_ocr, processed_file_bytes):
        if document_to_ocr['attempt_counter'] == 1:
            rotation = 180
        elif document_to_ocr['attempt_counter'] == 2:
            rotation = 90
        elif document_to_ocr['attempt_counter'] == 3:
            rotation = 180

        self.add_document_to_front(
            document_to_ocr['path'],
            document_to_ocr['attempt_counter'] + 1,
            processed_file_bytes,
            rotation
        )

    def save_document_numbers(self, document_numbers, file_path):
        for document_number in document_numbers:
            document_type = document_number[0]
            document_config = self.documents_config[document_type]
            document_year = self.get_document_year(document_number)
            filename = document_number[1].replace('/', '_')

            if not document_year:
                general.copy_file_to_new_dir(
                    file_path,
                    general.get_path(self.error_path),
                    general.get_filename_with_unique_id(filename),
                    logger
                )
                continue

            filename_exists = general.filename_exists(filename, 
                                general.get_path(document_config['processed_path'], document_year))

            if filename_exists:
                if not general.is_file_equal(file_path, filename_exists):
                    filename = general.get_filename_with_unique_id(filename)
                    general.copy_file_to_new_dir(
                        file_path,
                        general.get_path(self.duplicates_path),
                        filename,
                        logger
                    )
            else:
                general.copy_file_to_new_dir(
                    file_path,
                    general.get_path(document_config['processed_path'], document_year),
                    filename,
                    logger
                )

    def save_document_to_processed_archive(self, document_path):
        today = datetime.now()
        processed_day_path = os.path.join(
            general.get_path(self.processed_path),
            str(today.year),
            str(today.month),
            str(today.day)
        )

        general.move_file_to_new_dir(document_path, processed_day_path, logger=logger)
        self.remove_old_files_in_processed_archive()

    def remove_old_files_in_processed_archive(self):
        if not self.days_to_keep_archive:
            return

        date_to_which_keep_archive = datetime.now() - timedelta(days=self.days_to_keep_archive)

        for year_dir in glob.iglob(os.path.join(general.get_path(self.processed_path), '*',) + os.path.sep):
            for month_dir in glob.iglob(os.path.join(year_dir, '*',) + os.path.sep):
                for day_dir in glob.iglob(os.path.join(month_dir, '*',) + os.path.sep):

                    day_dir_splitted = day_dir.split(os.path.sep)
                    if len(day_dir_splitted) >= 4:
                        dir_date_str = f'{day_dir_splitted[-4]}-{day_dir_splitted[-3]}-{day_dir_splitted[-2]}'
                        dir_date = general.get_datetime(dir_date_str, r'%Y-%m-%d')

                        if dir_date:
                            if dir_date < date_to_which_keep_archive:
                                shutil.rmtree(day_dir)

                if general.dir_empty(month_dir):
                    shutil.rmtree(month_dir)

            if general.dir_empty(year_dir):
                    shutil.rmtree(year_dir)

    def get_document_year(self, document_number):
        splitted_document_number = document_number[1].split('/')

        if len(splitted_document_number) == 3:
            year = splitted_document_number[1]
            
            if len(year) == 1:
                year = f'0{year}'

            return f'{str(datetime.now().year)[0:2]}{year}'

        return None

    def get_document_type(self, text_pages):
        matching_keywords_per_document_type = self.get_matching_keywords_per_document_type(text_pages)
        document_type_match_probability = self.get_match_probability_per_document_type(
                                            matching_keywords_per_document_type)

        most_probable_document_type = max(
            document_type_match_probability,
            key=document_type_match_probability.get
        )

        if document_type_match_probability[most_probable_document_type] >= \
            self.document_pattern_match_threshold:
            return most_probable_document_type

        return None

    def get_matching_keywords_per_document_type(self, text_pages):
        matching_keywords = {}

        for document_type in self.documents_config:
            matching_keywords[document_type] = set()

        for document_type in self.documents_config:
            for page in text_pages:
                for pattern in self.documents_config[document_type]['patterns']:
                    pattern_found = re.search(pattern, page, re.IGNORECASE)
                    
                    if pattern_found:
                        matching_keywords[document_type].add(pattern)
        
        return matching_keywords

    def get_match_probability_per_document_type(self, keywords_per_document_type):
        document_type_match_probability = {}

        for document_type in self.documents_config:
            number_of_matching_keywords = len(keywords_per_document_type[document_type])
            number_of_document_type_keywords = len(self.documents_config[document_type]['patterns'])
            probability = number_of_matching_keywords / number_of_document_type_keywords
            document_type_match_probability[document_type] = probability

            if probability >= 1.0:
                break

        return document_type_match_probability

    def get_document_numbers(self, document_type, text_pages):
        if document_type:
            document_config = self.documents_config[document_type]
            document_number_extraction_method = getattr(self,
                                                    document_config['number_extraction_method'])

            document_numbers = document_number_extraction_method(text_pages, document_config)

            if document_numbers:
                document_numbers = set([(document_type, x) for x in document_numbers])
            else:
                document_numbers = set()
        else:
            document_numbers = set()

        remaining_document_numbers = self.get_document_numbers_when_document_type_unknown(text_pages)

        if remaining_document_numbers:
            document_numbers |= remaining_document_numbers

        return document_numbers if document_numbers else None

    def get_document_numbers_when_document_type_unknown(self, text_pages):
        document_numbers = set()

        for document_type in self.documents_config:
            document_config = self.documents_config[document_type]

            if document_config['analyze_when_document_type_not_detected']:
                document_number_extraction_method = getattr(self,
                                                    document_config['number_extraction_method'])

                document_number = document_number_extraction_method(text_pages, document_config)

                if document_number:
                    document_numbers |= set([(document_type, x) for x in document_number])

        return document_numbers if document_numbers else None

    def postprocess_document_numbers(self, document_type, document_numbers):
        postprocessed = set()

        for document_number in document_numbers:
            document_config = self.documents_config[document_number[0]]
            document_number = self.postprocess_document_number_max_length(document_number,
                                                                            document_config)
            document_number = self.postprocess_document_number_min_length(document_number,
                                                                            document_config)                                                       
            document_number = self.postprocess_document_number_year(document_number)

            if document_number:
                postprocessed.add(document_number)
        
        postprocessed = self.postprocess_document_numbers_based_on_document_type(postprocessed,
                                                                                document_type)

        return postprocessed if postprocessed else None

    def postprocess_document_number_max_length(self, document_number, document_config):
        if not document_number:
            return None

        max_length = 1000
        if 'max_length' in document_config:
            max_length = document_config['max_length']
        
        if len(document_number[1]) <= max_length:
            return document_number

        return None

    def postprocess_document_number_min_length(self, document_number, document_config):
        if not document_number:
            return None

        min_length = 0
        if 'min_length' in document_config:
            min_length = document_config['min_length']
        
        if len(document_number[1]) >= min_length:
            return document_number

        return None

    def postprocess_document_number_year(self, document_number):
        if not document_number:
            return None

        splitted_document_number = document_number[1].split('/')

        if len(splitted_document_number) == 3:
            year = splitted_document_number[1]

            if len(year) == 1:
                year = f'0{year}'

            if not len(year) == 2:
                return None

            if not year.isdigit():
                return None

            year = int(f'{str(datetime.now().year)[0:2]}{year}')

            if year > datetime.now().year or year < 2012:
                return None

            return document_number

        return document_number

    def postprocess_document_numbers_based_on_document_type(self, document_numbers, document_type):
        if document_type == settings.DOCUMENT_WZ_PEPCO:
            pepco_numbers = [x[1] for x in document_numbers if x[0] == settings.DOCUMENT_WZ_PEPCO]
            document_numbers = [x for x in document_numbers if not (x[0] == settings.DOCUMENT_WZ \
                                and x[1] in pepco_numbers)]

        return set(document_numbers)

    def get_document_numbers_common(self, text_pages, config):
        matching_document_numbers = self.get_matching_document_numbers_common(text_pages, config)
        exact_matching_document_numbers = self.get_exact_matching_document_numbers_common(
                                                matching_document_numbers, config)

        if exact_matching_document_numbers:
            return exact_matching_document_numbers

        restored_matching_document_numbers = self.get_restored_matching_document_numbers_common(
                                                matching_document_numbers, config)

        if restored_matching_document_numbers:
            return restored_matching_document_numbers

        return None

    def get_matching_document_numbers_common(self, text_pages, config):
        matching_document_numbers = set()

        for page in text_pages:
            matchings = re.findall(config['similar_pattern'],page,re.IGNORECASE)

            for matching in matchings:
                matching_document_numbers.add(matching.upper())

                if ' ' in matching:
                    matching = matching.replace(' ', '')
                    matching_document_numbers.add(matching.upper())

        return matching_document_numbers

    def get_exact_matching_document_numbers_common(self, matching_document_numbers, config):
        matching_document_numbers_string = str()

        for matching in matching_document_numbers:
            matching_document_numbers_string += matching + ' '

        exact_matching_document_numbers = re.findall(
            config['exact_pattern'],
            matching_document_numbers_string,
            re.IGNORECASE
        )

        return set(exact_matching_document_numbers)

    def get_restored_matching_document_numbers_common(self, matching_document_numbers, config):
        restored_matching_document_numbers = set()

        for matching in matching_document_numbers:
            splitted_number = matching.split(config['separator'])

            if len(splitted_number) >= 3 and splitted_number[0] in config['similar_prefixes']:
                restored_matching_document_numbers.add(self.construct_document_number_common(
                                                            splitted_number, config))

        return restored_matching_document_numbers if restored_matching_document_numbers else None
    
    def construct_document_number_common(self, splitted_number, config):
        document_number = config['prefix']

        for x in splitted_number[1:]:
            document_number += config['separator']
            document_number += x
        
        return document_number

    def get_document_numbers_WYS(self, text_pages, config):
        matching_lines = self.get_matching_lines_WYS(text_pages, config)
        return self.extract_document_numbers_from_matching_lines_WYS(matching_lines, config)

    def get_matching_lines_WYS(self, text_pages, config):
        matching_lines = set()

        for page in text_pages:
            for pattern in config['similar_pattern']:
                matching = re.findall(pattern, page, re.IGNORECASE)

                matching_lines |= set(matching)

        return matching_lines

    def extract_document_numbers_from_matching_lines_WYS(self, matching_lines, config):
        document_numbers = set()

        for matching_line in matching_lines:
            matching_line = matching_line.replace(' ', '')
            document_number = re.search(config['exact_pattern'], matching_line, re.IGNORECASE)

            if document_number:
                document_numbers.add(document_number.group(0).upper())
                continue
            
            number = ''.join(filter(str.isnumeric, matching_line))
            
            if number:
                document_numbers.add(config['prefix']+number)

        return document_numbers if document_numbers else None
