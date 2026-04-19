import os
import time
import glob
import logging
import uuid

import general
from document_processing_queue import DocumentProcessingQueue
import settings


logger = logging.getLogger(__name__)


class DocumentsProcessor:

    def __init__(self) -> None:
        self.incoming_path = settings.INCOMING_PATH
        self.queue_path = settings.QUEUE_PATH
        self.processed_path = settings.PROCESSED_PATH
        self.error_path = settings.ERROR_PATH
        self.duplicates_path = settings.DUPLICATES_PATH
        self.archive_processed_files = settings.ARCHIVE_PROCESSED_FILES
        self.days_to_keep_archive = settings.DAYS_TO_KEEP_ARCHIVE
        self.document_pattern_match_threshold = settings.DOCUMENT_PATTERN_MATCH_THRESHOLD
        self.documents_config = settings.DOCUMENTS_CONFIG
        self.supported_exts = settings.SUPPORTED_EXTS
        self.files_limit_in_queue = settings.FILES_LIMIT_IN_QUEUE

        self.queue = DocumentProcessingQueue(
            self.processed_path,
            self.error_path,
            self.duplicates_path,
            self.archive_processed_files,
            self.days_to_keep_archive,
            self.document_pattern_match_threshold,
            self.documents_config,
            self.supported_exts
        )

    def start(self):
        try:
            while True:
                self.move_incoming_documents_to_queue_path()
                self.fill_queue()
                self.queue.process()
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.exception(f'Unexpected exception: {str(e)}')

    def move_incoming_documents_to_queue_path(self):
        if not os.path.isdir(general.get_path(self.incoming_path)):
            os.makedirs(general.get_path(self.incoming_path))

        files_to_move = glob.iglob(os.path.join(general.get_path(self.incoming_path), '*'))

        for file_to_move in files_to_move:
            if os.path.isfile(file_to_move):
                file_to_move_size = os.stat(file_to_move).st_size

                if file_to_move_size > 0:
                    self.move_file_to_queue(file_to_move)
                else:
                    try:
                        os.remove(file_to_move)
                    except Exception:
                        continue
    
    def move_file_to_queue(self, file_path):
        filename = uuid.uuid4().hex
        general.move_file_to_new_dir(file_path, general.get_path(self.queue_path), filename, logger)

    def fill_queue(self):
        files_to_add = self.files_limit_in_queue - len(self.queue)

        if files_to_add <= 0:
            return

        files_to_process = glob.iglob(os.path.join(general.get_path(self.queue_path), '*'))
        file_paths_in_queue = self.queue.file_paths_in_queue()
        added_files = 0

        for file_to_process in files_to_process:
            if added_files >= files_to_add:
                break
                
            if not os.path.isfile(file_to_process):
                continue
                
            if file_to_process in file_paths_in_queue:
                continue

            self.queue.add_document(file_to_process)
            added_files += 1
