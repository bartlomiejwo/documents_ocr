import logging
import json
from datetime import datetime

from message import Message, Command, Request
from ocr_file import OCRFile, OCRSupportedExts


logger = logging.getLogger(__name__)

class OCRConnection:
    def __init__(self, connection, header_size_in_bytes, header_byte_order, encoding,
                        packet_size_read, connection_online_check_interval,
                        connection_idle_timeout, temp_files_dir, orientation_confidence_threshold):
        self.connection = connection
        self.header_size_in_bytes = header_size_in_bytes
        self.header_byte_order = header_byte_order
        self.encoding = encoding

        self.packet_size_read = packet_size_read
        self.buffer_in = b''

        self.last_action_time = datetime.now()
        self.connection_online_check_interval = connection_online_check_interval

        self.last_client_request_time = datetime.now()
        self.connection_idle_timeout = connection_idle_timeout

        self.temp_files_dir = temp_files_dir
        self.connected = True

        self.orientation_confidence_threshold = orientation_confidence_threshold
    
    def process_connection(self):
        message = Message()

        while self.connected:
            self.fill_buffer_in()

            if self.connection_idle_for_too_long():
                break

            if self.connection_online_check_needed():
                if self.connection_online():
                    self.last_action_time = datetime.now()
                else:
                    break

            if not message.proto_header_processed():
                proto_header_processed = self.process_proto_header(message)

                if not proto_header_processed:
                    continue

            if not message.json_header_processed():
                json_header_processed = self.process_json_header(message)

                if not json_header_processed:
                    continue

            if not message.content_processed():
                message_content_processed = self.process_message_content(message)

                if message_content_processed:
                    self.process_message(message)
                    message.reset()
                else:
                    continue
            else:
                message.reset()

        self.connection.close()

    def fill_buffer_in(self):
        try:
            received_data = self.connection.recv(self.packet_size_read)
        except BlockingIOError:
            pass
        else:
            if received_data:
                self.buffer_in += received_data
                self.last_action_time = datetime.now()
                self.last_client_request_time = datetime.now()

    def connection_idle_for_too_long(self):
        return (datetime.now() - self.last_client_request_time).seconds >= \
            self.connection_idle_timeout

    def connection_online_check_needed(self):
        return (datetime.now() - self.last_action_time).seconds >= \
            self.connection_online_check_interval

    def connection_online(self):
        try:
            message_bytes = Message.get_connection_verification_message_bytes(
                self.encoding,
                self.header_size_in_bytes,
                self.header_byte_order
            )

            self.connection.sendall(message_bytes)
            self.connection.sendall(message_bytes)
        except Exception as e:
            return False
        else:
            return True

    def process_proto_header(self, message):
        if self.buffer_in_ready(self.header_size_in_bytes):
            header_bytes = self.read_buffer_in(self.header_size_in_bytes)
            message.json_header_length = int.from_bytes(
                                            header_bytes,
                                            byteorder=self.header_byte_order,
                                            signed=False
                                        )

            return True
        return False

    def process_json_header(self, message):
        if self.buffer_in_ready(message.json_header_length):
            json_header_bytes = self.read_buffer_in(message.json_header_length)
            message.json_header = json.loads(json_header_bytes.decode(self.encoding))

            return True
        return False

    def process_message_content(self, message):
        if self.buffer_in_ready(message.content_length):
            content_bytes = self.read_buffer_in(message.content_length)

            if message.content_type == Message.CONTENT_TYPE_COMMAND:
                message.content = content_bytes.decode(self.encoding)
            elif message.content_type == Message.CONTENT_TYPE_TEXT:
                message.content = content_bytes.decode(self.encoding)
            elif message.content_type == Message.CONTENT_TYPE_JSON:
                message.content = json.loads(content_bytes.decode(self.encoding))
            elif message.content_type == Message.CONTENT_TYPE_FILE:
                message.content = content_bytes
            else:
                self.send_server_error_message('Wrong content type')
                self.disconnect()

            return True
        return False

    def buffer_in_ready(self, bytes_to_read):
        return len(self.buffer_in) >= bytes_to_read

    def read_buffer_in(self, bytes_to_read):
        bytes_read = self.buffer_in[:bytes_to_read]
        self.buffer_in = self.buffer_in[bytes_to_read:]

        return bytes_read

    def disconnect(self):
        self.connected = False

    def process_message(self, message):
        if message.content_type == Message.CONTENT_TYPE_COMMAND:
            self.handle_command_message(message.content)
        elif message.content_type == Message.CONTENT_TYPE_TEXT:
            self.handle_text_message(message)
        elif message.content_type == Message.CONTENT_TYPE_JSON:
            self.handle_json_message(message)
        elif message.content_type == Message.CONTENT_TYPE_FILE:
            self.handle_file_message(message)
        else:
            self.send_server_error_message('Wrong content type')
            self.disconnect()

    def handle_command_message(self, command):
        if command == Command.CONNECTION_STATUS_CHECK:
            pass
        elif command == Command.CLOSE_CONNECTION:
            self.disconnect()
        else:
            self.send_server_error_message('Wrong command')
            self.disconnect()

    def handle_text_message(self, message):
        if message.info['action'] == Request.TEST_MESSAGE:
            self.handle_test_message(message)
        else:
            self.send_server_error_message('Wrong action')
            self.disconnect()

    def handle_test_message(self):
        test_response_bytes = Message.get_test_response_message_bytes(
            self.encoding,
            self.header_size_in_bytes,
            self.header_byte_order,
        )

        self.connection.sendall(test_response_bytes)
    
    def handle_json_message(self, message):
        pass

    def handle_file_message(self, message):
        if message.info['action'] == Request.FILE_OCR:
            if message.info['ext'].lower() in OCRSupportedExts.SUPPORTED_EXTS:
                self.handle_file_ocr(message)
            else:
                self.send_server_error_message('Wrong file extension')
                self.disconnect()
        else:
            self.send_server_error_message('Wrong action')
            self.disconnect()

    def handle_file_ocr(self, message):
        ocr_file = OCRFile(
            message.content,
            message.info['ext'],
            message.info['language'],
            message.info['rotation'],
            self.temp_files_dir,
            self.orientation_confidence_threshold
        )

        try:
            ocr_file.process()
        except Exception as e:
            logger.exception(repr(e))
            self.send_server_error_message(str(e))
            self.disconnect()
        else:
            response_bytes = Message.get_file_ocr_response_message_bytes(
                ocr_file.processed_file_bytes,
                self.encoding,
                self.header_size_in_bytes,
                self.header_byte_order,
                ocr_file.extracted_pages_text
            )

            self.connection.sendall(response_bytes)
            self.disconnect()

    def send_server_error_message(self, error_text):
        server_error_response_bytes = Message.get_server_error_message_bytes(
            error_text,
            self.encoding,
            self.header_size_in_bytes,
            self.header_byte_order,
        )

        self.connection.sendall(server_error_response_bytes)
