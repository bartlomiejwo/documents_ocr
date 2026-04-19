import settings
from ocr_server import OCRServer


if __name__ == "__main__":
    ocr_server = OCRServer(
        settings.SERVER_IP,
        settings.SERVER_PORT,
        settings.HEADER_SIZE_IN_BYTES,
        settings.HEADER_BYTE_ORDER,
        settings.SERVER_ENCODING,
        settings.PACKET_SIZE_READ,
        settings.CLIENTS_WHITE_LIST,
        settings.CLIENTS_BLACK_LIST,
        settings.CONNECTIONS_LIMIT,
        settings.CONNECTION_ONLINE_CHECK_INTERVAL,
        settings.CONNECTION_IDLE_TIMEOUT,
        settings.TEMP_FILES_PATH,
        settings.ORIENTATION_CONFIDENCE_THRESHOLD,
    )

    ocr_server.listen()
