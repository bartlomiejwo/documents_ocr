import errno
import os
import pathlib
import shutil
import glob
import hashlib
import uuid
from datetime import datetime

import settings


def move_file_to_new_dir(file_path, new_dir, filename=None, logger=None):
    file_extension = ''.join([s for s in pathlib.Path(file_path).suffixes if not ' ' in s])

    if not filename:
        if file_extension:
            filename = f'{os.path.basename(file_path)[:-len(file_extension)]}'
        else:
            filename = f'{os.path.basename(file_path)}'

    new_path = os.path.join(new_dir, f'{filename}{file_extension}')

    try:
        shutil.copyfile(file_path, new_path)
        os.remove(file_path)
    except FileNotFoundError:
        if not os.path.exists(file_path):
            if logger:
                logger.error(f'File not found error: {file_path}')
        else:
            if not os.path.exists(new_dir):
                try:
                    os.makedirs(new_dir)
                    shutil.copyfile(file_path, new_path)
                    os.remove(file_path)
                except Exception as e:
                    if logger:
                        logger.error(f'Unexpected error: {str(e)}')
    except OSError as e:
        if e.errno == errno.EBUSY:
            os.remove(new_path)
            if logger:
                logger.warning(f'File busy: {file_path}')


def copy_file_to_new_dir(file_path, new_dir, filename=None, logger=None):
    file_extension = ''.join([s for s in pathlib.Path(file_path).suffixes if not ' ' in s])

    if not filename:
        if file_extension:
            filename = f'{os.path.basename(file_path)[:-len(file_extension)]}'
        else:
            filename = f'{os.path.basename(file_path)}'

    new_path = os.path.join(new_dir, f'{filename}{file_extension}')

    try:
        shutil.copyfile(file_path, new_path)
    except FileNotFoundError:
        if not os.path.exists(file_path):
            if logger:
                logger.error(f'File not found error: {file_path}')
        else:
            if not os.path.exists(new_dir):
                os.makedirs(new_dir)
                shutil.copyfile(file_path, new_path)
    except OSError as e:
        if e.errno == errno.EBUSY:
            if logger:
                logger.warning(f'File busy: {file_path}')


def remove_file(file_path, logger=None):
    try:
        os.remove(file_path)
    except FileNotFoundError:
        if logger:
            logger.error(f'File not found error: {file_path}')


def filename_exists(filename, path):
    files = glob.glob(os.path.join(path, filename+'.*'))

    return files[0] if files else False


def is_file_equal(file1, file2):
    file1_hash = get_file_hash_sha1(file1)
    file2_hash = get_file_hash_sha1(file2)

    if file1_hash != file2_hash:
        return False

    file1_size = os.path.getsize(file1)
    file2_size = os.path.getsize(file2)

    return file1_size == file2_size


def get_file_hash_sha1(file_to_hash):
    buffer_size = 1024
    file_hash = hashlib.sha1()

    with open(file_to_hash, 'rb') as f:
        while True:
            chunk = f.read(buffer_size)

            if not chunk:
                break

            file_hash.update(chunk)

    return file_hash.hexdigest()


def get_filename_with_unique_id(file_path):
    file_extension = ''.join([s for s in pathlib.Path(file_path).suffixes if not ' ' in s])

    if file_extension:
        filename = f'{os.path.basename(file_path)[:-len(file_extension)]}_{uuid.uuid4().hex}'
    else:
        filename = f'{os.path.basename(file_path)}_{uuid.uuid4().hex}'

    return filename


def get_datetime(date_str, format):
    try:
        return datetime.strptime(date_str, format)
    except ValueError:
        return None


def dir_empty(dir_path):
    return not next(os.scandir(dir_path), None)


def get_path(path, document_year=None):
    now = datetime.now()

    if settings.PATH_MOD_CURRENT_YEAR in path:
        path = path.replace(settings.PATH_MOD_CURRENT_YEAR, str(now.year))

    if settings.PATH_MOD_DOCUMENT_YEAR in path:
        path = path.replace(settings.PATH_MOD_DOCUMENT_YEAR, str(document_year))

    return path