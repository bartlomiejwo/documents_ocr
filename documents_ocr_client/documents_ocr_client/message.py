import json


class Command:
    CONNECTION_STATUS_CHECK = '100'
    CLOSE_CONNECTION = '101'
    CONNECTIONS_LIMIT_EXCEEDED = '102'
    CONNECTION_ACCEPTED = '103'


class Request:
    TEST_MESSAGE = 1000
    FILE_OCR = 1001


class Response:
    TEST_MESSAGE = 2000
    FILE_OCR = 2001
    SERVER_ERROR = 2002


class Message:
    CONTENT_TYPE_COMMAND = 'COMMAND'
    CONTENT_TYPE_TEXT = 'TEXT'
    CONTENT_TYPE_JSON = 'JSON'
    CONTENT_TYPE_FILE = 'FILE'

    def __init__(self):
        self.json_header_length = None
        self.json_header = None
        self.info = None

        self.content_length = None
        self.content_type = None

        self.content = None

    @property
    def json_header(self):
        return self.__json_header

    @json_header.setter
    def json_header(self, json_header):
        if json_header is not None:
            if 'content_length' in json_header and 'content_type' in json_header:
                self.__json_header = json_header

                self.content_length = json_header['content_length']
                self.content_type = json_header['content_type']
            else:
                raise ValueError('Wrong JSON header')
            
            if 'info' in json_header:
                self.info = json_header['info']
        else:
            self.__json_header = None

    def proto_header_processed(self):
        return self.json_header_length is not None
    
    def json_header_processed(self):
        return self.json_header is not None

    def content_processed(self):
        return self.content is not None

    def reset(self):
        self.json_header_length = None
        self.json_header = None
        self.info = None
        self.content_length = None
        self.content_type = None
        self.content = None

    def to_bytes(self, content_type, content, encoding, header_size_in_bytes, header_byte_order, info=None):
        self.content_type = content_type
        self.content = content
        self.info = info
        encoded_content = self.get_encoded_content(encoding)
        self.content_length = len(encoded_content)

        self.json_header = {
            'content_type': self.content_type,
            'content_length': self.content_length,
        }

        if self.info:
            self.json_header['info'] = self.info
        
        encoded_json_header = json.dumps(self.json_header).encode(encoding)
        self.json_header_length = len(encoded_json_header)
        encoded_json_header_length = self.json_header_length.to_bytes(
                                            header_size_in_bytes,
                                            header_byte_order,
                                            signed=False
                                        )
        
        message_bytes = encoded_json_header_length + encoded_json_header + encoded_content
        return message_bytes

    def get_encoded_content(self, encoding):
        if self.content_type == Message.CONTENT_TYPE_COMMAND:
            return self.content.encode(encoding)
        elif self.content_type == Message.CONTENT_TYPE_TEXT:
            return self.content.encode(encoding)
        elif self.content_type == Message.CONTENT_TYPE_JSON:
            return json.dumps(self.content).encode(encoding)
        elif self.content_type == Message.CONTENT_TYPE_FILE:
            return self.content
        else:
            raise ValueError('Wrong content type')

    def __str__(self) -> str:
        return f'JSON header length: {self.json_header_length}\n' + \
            f'JSON header: {self.json_header} \n' + \
            f'Content: {self.content}'

    @staticmethod
    def get_file_ocr_request_message_bytes(file_bytes, encoding, header_size_in_bytes,
            header_byte_order, extension, language, rotation=None):
        message = Message()
        info = {
            'ext': extension,
            'language': language,
            'rotation': rotation,
            'action': Request.FILE_OCR,
        }

        return message.to_bytes(
            Message.CONTENT_TYPE_FILE,
            file_bytes,
            encoding,
            header_size_in_bytes,
            header_byte_order,
            info
        )

    @staticmethod
    def get_close_connection_message_bytes(encoding, header_size_in_bytes, header_byte_order):
        message = Message()

        return message.to_bytes(
            Message.CONTENT_TYPE_COMMAND,
            Command.CLOSE_CONNECTION,
            encoding,
            header_size_in_bytes,
            header_byte_order
        )

    @staticmethod
    def get_connection_status_check_message_response_bytes(encoding, header_size_in_bytes, header_byte_order):
        message = Message()

        return message.to_bytes(
            Message.CONTENT_TYPE_COMMAND,
            Command.CONNECTION_STATUS_CHECK,
            encoding,
            header_size_in_bytes,
            header_byte_order
        )

    @staticmethod
    def get_connection_verification_message_bytes(encoding, header_size_in_bytes, header_byte_order):
        message = Message()

        return message.to_bytes(
            Message.CONTENT_TYPE_COMMAND,
            Command.CONNECTION_STATUS_CHECK,
            encoding,
            header_size_in_bytes,
            header_byte_order
        )
