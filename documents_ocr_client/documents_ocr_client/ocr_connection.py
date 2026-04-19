import json
import pathlib
import socket
import logging
from datetime import datetime

import settings
from message import Message, Response, Command


logger = logging.getLogger(__name__)

class OCRConnection:
    SERVER_CONNECTION_LIMIT_EXCEEDED_ERROR = 2
    CONTENT_TYPE_ERROR = 3
    COMMAND_ERROR = 4
    TEXT_MESSAGE_ACTION_ERROR = 5
    FILE_MESSAGE_ACTION_ERROR = 6
    SERVER_NOT_RESPONDING_ERROR = 7
    FILE_NOT_FOUND_ERROR = 8
    SERVER_ERROR = 9

    def __init__(self):
        self.ip = settings.SERVER_IP
        self.port = settings.SERVER_PORT
        self.header_size_in_bytes = settings.HEADER_SIZE_IN_BYTES
        self.header_byte_order = settings.HEADER_BYTE_ORDER
        self.encoding = settings.SERVER_ENCODING
        self.language = settings.LANGUAGE
        self.address = (self.ip, self.port)

        self.packet_size_read = settings.PACKET_SIZE_READ
        self.buffer_in = b''
        self.buffer_out = b''

        self.last_action_time = datetime.now()
        self.connection_online_check_interval = settings.CONNECTION_ONLINE_CHECK_INTERVAL

        self.connected = False
        self.available_spots_on_server = 0

        self.success = False
        self.error = None
        self.error_details = None

        self.processed_file_bytes = None
        self.ocr_text_pages = None

    def connect(self):
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection.connect(self.address)

        message = Message()
        
        while True:
            self.fill_buffer_in()

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
                    break
                else:
                    continue

        self.process_message(message)
        return self.connected

    def disconnect(self):
        self.connected = False

        message_bytes = Message.get_close_connection_message_bytes(
            self.encoding,
            self.header_size_in_bytes,
            self.header_byte_order,
        )

        self.send_data(message_bytes)

    def process(self, document_to_process, document_to_process_bytes=None, rotation=None):
        self.add_file_ocr_request_message_to_buffer_out(
            document_to_process,
            document_to_process_bytes, 
            rotation
        )

        message = Message()
        
        while self.connected:
            self.send_buffer_out()
            self.fill_buffer_in()

            if self.connection_online_check_needed():
                if self.connection_online():
                    self.last_action_time = datetime.now()
                else:
                    self.error = OCRConnection.SERVER_NOT_RESPONDING_ERROR
                    self.error_details = 'Server not responding!'
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

    def add_file_ocr_request_message_to_buffer_out(self, document_to_process,
                                document_to_process_bytes=None, rotation=None):
        if not document_to_process_bytes:
            try:
                with open(document_to_process, 'rb') as f:
                    document_to_process_bytes = f.read()
            except FileNotFoundError:
                self.error = OCRConnection.FILE_NOT_FOUND_ERROR
                self.error_details = 'File that was meant to be processed couldnt be found'
                self.connected = False
                return
            
        extension = ''.join([s for s in pathlib.Path(document_to_process).suffixes if not ' ' in s])

        message_bytes = Message.get_file_ocr_request_message_bytes(
            document_to_process_bytes,
            self.encoding,
            self.header_size_in_bytes,
            self.header_byte_order,
            extension,
            self.language,
            rotation,
        )

        self.buffer_out += message_bytes

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

    def send_buffer_out(self):
        if self.buffer_out:
            sent_successfully = self.send_data(self.buffer_out)

            if sent_successfully:
                self.buffer_out = b''

    def send_data(self, data):
        try:
            self.connection.sendall(data)
        except (BrokenPipeError, ConnectionResetError):
            self.connected = False
            return False
        else:
            return True

    def fill_buffer_in(self):
        try:
            received_data = self.connection.recv(self.packet_size_read)
        except BlockingIOError:
            pass
        except (BrokenPipeError, ConnectionResetError):
            pass
        else:
            if received_data:
                self.buffer_in += received_data
                self.last_action_time = datetime.now()
                self.last_server_response_time = datetime.now()

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
                self.error = OCRConnection.CONTENT_TYPE_ERROR
                self.error_details = f'Wrong message content type: {message.content_type}'
                self.disconnect()

            return True
        return False

    def buffer_in_ready(self, bytes_to_read):
        return len(self.buffer_in) >= bytes_to_read

    def read_buffer_in(self, bytes_to_read):
        bytes_read = self.buffer_in[:bytes_to_read]
        self.buffer_in = self.buffer_in[bytes_to_read:]

        return bytes_read

    def process_message(self, message):
        if message.content_type == Message.CONTENT_TYPE_COMMAND:
            self.handle_command_message(message.content, message.info)
        elif message.content_type == Message.CONTENT_TYPE_TEXT:
            self.handle_text_message(message)
        elif message.content_type == Message.CONTENT_TYPE_JSON:
            self.handle_json_message(message)
        elif message.content_type == Message.CONTENT_TYPE_FILE:
            self.handle_file_message(message)
        else:
            self.error = OCRConnection.CONTENT_TYPE_ERROR
            self.error_details = f'Wrong message content type: {message.content_type}'
            self.disconnect()

    def handle_command_message(self, command, info):
        if command == Command.CONNECTION_ACCEPTED:
            self.handle_connection_accepted(info)
        elif command == Command.CONNECTION_STATUS_CHECK:
            self.handle_connection_status_check()
        elif command == Command.CLOSE_CONNECTION:
            self.disconnect()
        elif command == Command.CONNECTIONS_LIMIT_EXCEEDED:
            self.handle_connections_limit_exceeded()
        else:
            self.error = OCRConnection.COMMAND_ERROR
            self.error_details = f'Wrong message command: {command}'
            self.disconnect()

    def handle_connection_accepted(self, info):
        self.available_spots_on_server = int(info['available_spots'])
        self.connected = True

    def handle_connection_status_check(self):
        message_bytes = Message.get_connection_status_check_message_response_bytes(
            self.encoding,
            self.header_size_in_bytes,
            self.header_byte_order
        )

        self.buffer_out += message_bytes

    def handle_connections_limit_exceeded(self):
        self.success = False
        self.error = OCRConnection.SERVER_CONNECTION_LIMIT_EXCEEDED_ERROR
        self.error_details = f'Cannot connect, server full.'

        self.disconnect()

    def handle_text_message(self, message):
        if message.info['action'] == Response.TEST_MESSAGE:
            logger.info(message.content)
        if message.info['action'] == Response.SERVER_ERROR:
            self.error = OCRConnection.SERVER_ERROR
            self.error_details = message.content
            self.disconnect()
        else:
            self.error = OCRConnection.TEXT_MESSAGE_ACTION_ERROR
            self.error_details = f'Wrong text response action: {message.info["action"]}'
            self.disconnect()

    def handle_json_message(self, message):
        pass

    def handle_file_message(self, message):
        if message.info['action'] == Response.FILE_OCR:
            self.handle_file_ocr_response(message)
        else:
            self.error = OCRConnection.FILE_MESSAGE_ACTION_ERROR
            self.error_details = f'Wrong file response action: {message.info["action"]}'
            self.disconnect()

    def handle_file_ocr_response(self, message):
        self.success = True
        self.processed_file_bytes = message.content
        self.ocr_text_pages = message.info['pages']

        self.disconnect()
