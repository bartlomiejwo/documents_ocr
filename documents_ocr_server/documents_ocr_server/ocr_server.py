import socket
import multiprocessing

from ocr_connection import OCRConnection
from message import Message

import logging

logger = logging.getLogger(__name__)


class OCRServer:
    
    def __init__(self, ip, port, header_size_in_bytes, header_byte_order, encoding,
                        packet_size_read, clients_white_list, clients_black_list,
                        connections_limit, connection_online_check_interval,
                        connection_idle_timeout, temp_files_dir,
                        orientation_confidence_threshold):
        self.ip = ip
        self.port = port
        self.header_size_in_bytes = header_size_in_bytes
        self.header_byte_order = header_byte_order
        self.encoding = encoding
        
        self.packet_size_read = packet_size_read

        self.clients_white_list = clients_white_list
        self.clients_black_list = clients_black_list

        self.connections_limit = connections_limit

        self.connection_online_check_interval = connection_online_check_interval
        self.connection_idle_timeout = connection_idle_timeout

        self.temp_files_dir = temp_files_dir

        self.orientation_confidence_threshold = orientation_confidence_threshold

        self.address = (self.ip, self.port)
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(self.address)

    def active_connections(self):
        return len(multiprocessing.active_children())

    def listen(self):
        self.server.listen()
        logger.info(f'LISTENING ON {self.ip}:{self.port}')

        try:
            while True:
                self.handle_incoming_connections()
        except KeyboardInterrupt:
            print('Keyboard interrupt, exiting.')
        finally:
            self.server.close()

    def handle_incoming_connections(self):
        connection, address = self.server.accept()

        if self.active_connections() < self.connections_limit:
            connection = self.accept_incoming_connection_if_allowed(connection, address)

            if connection:
                self.start_processing_connection(connection, address)
        else:
            self.reject_incoming_connection_due_to_exceeded_limit(connection, address)

        logger.info(f'ACTIVE CONNECTIONS {self.active_connections()}/{self.connections_limit}')

    def accept_incoming_connection_if_allowed(self, connection, address):
        if self.clients_white_list:
            if address[0] in self.clients_white_list:
                logger.info(f'CONNECTION ACCEPTED DUE TO {address} BEING LISTED IN WHITELIST')
                self.send_connection_accepted_message(connection)
                return connection
            else:
                logger.info(f'CONNECTION REJECTED DUE TO {address} NOT BEING LISTED IN WHITELIST')
                connection.close()
                return False

        if address[0] not in self.clients_black_list:
            logger.info(f'CONNECTION ACCEPTED DUE TO {address} NOT BEING LISTED IN BLACKLIST')
            self.send_connection_accepted_message(connection)
            return connection
        
        logger.info(f'CONNECTION REJECTED DUE TO {address} BEING LISTED IN BLACKLIST')
        connection.close()
        return False

    def start_processing_connection(self, connection, address):
        process = multiprocessing.Process(target=self.handle_connection, args=(connection, address))
        process.start()

    def send_connection_accepted_message(self, connection):
        message_bytes = Message.get_connection_accepted_message_bytes(
            self.encoding,
            self.header_size_in_bytes,
            self.header_byte_order,
            self.connections_limit - self.active_connections() - 1,
        )

        connection.sendall(message_bytes)

    def reject_incoming_connection_due_to_exceeded_limit(self, connection, address):
        message_bytes = Message.get_connections_limit_exceeded_message_bytes(
            self.encoding,
            self.header_size_in_bytes,
            self.header_byte_order
        )

        connection.sendall(message_bytes)
        connection.close()

        logger.info(f'CONNECTION {address} REJECTED DUE TO EXCEEDED LIMIT')

    def handle_connection(self, connection, address):
        logger.info(f'HANDLING NEW CONNECTION {address} STARTED')

        ocr_connection = OCRConnection(
            connection,
            self.header_size_in_bytes, 
            self.header_byte_order,
            self.encoding,
            self.packet_size_read,
            self.connection_online_check_interval,
            self.connection_idle_timeout,
            self.temp_files_dir,
            self.orientation_confidence_threshold,
        )
        
        try:
            ocr_connection.process_connection()
        except Exception as e:
            logger.exception(f'An unknown exception occurred: {repr(e)}')
            raise e
        else:
            logger.info(f'CONNECTION HANDLING {address} FINISHED')
