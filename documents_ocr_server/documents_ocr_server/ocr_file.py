import uuid
import os
import re
from shutil import copyfile, rmtree
from datetime import datetime

import ocrmypdf
import pdfplumber
from pdf2image import convert_from_path
import cv2
import pytesseract
import PyPDF2
from PIL import Image, ImageSequence

import settings


if not settings.DEBUG:
    ocrmypdf.configure_logging(verbosity=-1)

class OCRSupportedExts:
    PDF = '.pdf'
    JPG = '.jpg'
    JPEG = '.jpeg'
    PNG = '.png'
    TIFF = '.tiff'
    TIF = '.tif'
    BMP = '.bmp'
    GIF = '.gif'

    SUPPORTED_EXTS = (PDF, JPG, JPEG, PNG, TIFF, TIF, BMP, GIF)
    SUPPORTED_IMAGES_EXTS = (JPG, JPEG, PNG, BMP, GIF)


class OCRFile:
    def __init__(self, file_bytes, extension, language, forced_rotation, temp_files_dir,
                    orientation_confidence_threshold) -> None:
        self.unprocessed_file_bytes = file_bytes
        self.extension = extension
        self.language = language
        self.forced_rotation = forced_rotation
        self.id = uuid.uuid4().hex
        self.temp_files_dir = os.path.join(
                                temp_files_dir, 
                                self.id + '_' + datetime.now().strftime('%Y%m%d-%H%M%S')
                            )
        self.unprocessed_temp_file_path = os.path.join(self.temp_files_dir, 'unprocessed' + extension)
        self.processed_temp_file_path = os.path.join(self.temp_files_dir, 'processed' + OCRSupportedExts.PDF)
        self.orientation_confidence_threshold = orientation_confidence_threshold

        self.extracted_pages_text = []
        self.processed_file_bytes = None
    
    def __str__(self) -> str:
        string = f'Unprocessed file bytes: {len(self.unprocessed_file_bytes)}\n' + \
                    f'Extension: {self.extension}\n' + \
                    f'Language: {self.language}\n' + \
                    f'ID: {self.id}\n' + \
                    f'TEMP FILES DIR: {self.temp_files_dir}\n' + \
                    f'Unprocessed temp file path: {self.unprocessed_temp_file_path}\n' + \
                    f'Processed temp file path: {self.processed_temp_file_path}\n' + \
                    f'Processed file bytes:' + \
                    f'{len(self.processed_file_bytes) if self.processed_file_bytes is not None else 0}\n' + \
                    'PAGES: \n'

        for index, page in enumerate(self.extracted_pages_text):
            string += f'PAGE {index+1}\n'
            string += page + '\n'

        return string

    def process(self):
        try:
            self.create_temp_files_dir()
            self.write_unprocessed_to_temp_file()
            
            if self.conversion_to_pdf_needed():
                self.convert_to_pdf()

            self.ensure_document_orientation()
            
            if self.extension == OCRSupportedExts.PDF:
                pages_paths = self.split_pdf_into_single_pages()

                for page_path in pages_paths:
                    ocrmypdf.ocr(
                        page_path,
                        page_path,
                        deskew=True,
                        clean_final=True,
                        language=self.language,
                        force_ocr=True,
                        progress_bar=True if settings.DEBUG else False
                    )

                self.merge_processed_pages_into_processed_pdf(pages_paths)
            else:
                ocrmypdf.ocr(
                    self.unprocessed_temp_file_path,
                    self.processed_temp_file_path,
                    deskew=True,
                    clean_final=True,
                    language=self.language,
                    force_ocr=True,
                    image_dpi=400,
                    progress_bar=True if settings.DEBUG else False
                )

            self.extract_data_from_processed_file()
            self.save_processed_bytes()
        except Exception as e:
            self.clean_temp_files()
            raise e
        else:
            self.clean_temp_files()
    
    def create_temp_files_dir(self):
        os.mkdir(self.temp_files_dir)

    def ensure_document_orientation(self):
        if self.extension == OCRSupportedExts.PDF:
            self.ensure_pdf_pages_orientation()
        elif self.extension in OCRSupportedExts.SUPPORTED_IMAGES_EXTS:
            self.ensure_image_orientation()
        else:
            raise ValueError(f'Wrong file extension ({self.extension}).')
    
    def ensure_pdf_pages_orientation(self):
        if self.forced_rotation:
            pages_rotations = self.get_pdf_pages_rotations_with_forced_rotation()
        else:
            pages_rotations = self.get_pages_rotations()

        self.rotate_pages(pages_rotations)
    
    def get_pages_rotations(self):
        pages_rotations = []
        pages = convert_from_path(self.unprocessed_temp_file_path)

        for index, page in enumerate(pages):
            page_path = os.path.join(
                self.temp_files_dir,
                f'{index}_{datetime.now().strftime("%Y%m%d-%H%M%S")}.jpg'
            )

            page.save(page_path, 'JPEG')
            page_rotation = OCRFile.get_image_rotation(
                page_path,
                self.orientation_confidence_threshold
            )
            pages_rotations.append(page_rotation)
        
        return pages_rotations

    def get_pdf_pages_rotations_with_forced_rotation(self):
        number_of_pages = 0

        with open(self.unprocessed_temp_file_path, 'rb') as pdf_in:
            pdf_reader = PyPDF2.PdfFileReader(pdf_in)
            number_of_pages = pdf_reader.numPages

        return [self.forced_rotation for x in range(0, number_of_pages)]
    
    def rotate_pages(self, pages_rotations):
        unprocessed_copy_path = os.path.join(
            self.temp_files_dir,
            f'b4_rotation_copy_{datetime.now().strftime("%Y%m%d-%H%M%S")}{OCRSupportedExts.PDF}'
        )

        copyfile(self.unprocessed_temp_file_path, unprocessed_copy_path)

        with open(unprocessed_copy_path, 'rb') as pdf_in:
            pdf_reader = PyPDF2.PdfFileReader(pdf_in)
            pdf_writer = PyPDF2.PdfFileWriter()

            for page_number in range(pdf_reader.numPages):
                page = pdf_reader.getPage(page_number)

                if pages_rotations[page_number] != 0:
                    page.rotateClockwise(pages_rotations[page_number])
                
                pdf_writer.addPage(page)
            
            with open(self.unprocessed_temp_file_path, 'wb') as pdf_out:
                pdf_writer.write(pdf_out)
        
    def ensure_image_orientation(self):
        if self.forced_rotation:
            image_rotation = self.forced_rotation
        else:
            image_rotation = OCRFile.get_image_rotation(
                self.unprocessed_temp_file_path,
                self.orientation_confidence_threshold
            )

        if image_rotation != 0:
            self.rotate_image(image_rotation)
    
    @staticmethod
    def get_image_rotation(image_path, orientation_confidence_threshold):
        image = cv2.imread(image_path, cv2.IMREAD_COLOR)

        try:
            image_info = pytesseract.image_to_osd(image)
        except Exception:
            return 0
        else:
            orientation_confidence = re.search('(?<=Orientation confidence: )\d+\.\d+', image_info).group(0)
            rotate = re.search('(?<=Rotate: )\d+', image_info).group(0)

            if orientation_confidence and rotate:
                if float(orientation_confidence) > orientation_confidence_threshold:
                    return int(rotate)

        return 0

    def rotate_image(self, rotation):
        with Image.open(self.unprocessed_temp_file_path) as img:
            rotated_image = img.rotate(rotation)

        rotated_image.save(self.unprocessed_temp_file_path)

    def conversion_to_pdf_needed(self):
        return True if self.extension in (OCRSupportedExts.TIF, OCRSupportedExts.TIFF) else False

    def convert_to_pdf(self):
        if self.extension in (OCRSupportedExts.TIF, OCRSupportedExts.TIFF):
            self.convert_tiff_to_pdf()
        else:
            raise ValueError(f'Wrong file extension ({self.extension}), nothing to convert to pdf.')

    def convert_tiff_to_pdf(self):
        pdf_path = self.unprocessed_temp_file_path.replace(self.extension, OCRSupportedExts.PDF)

        image = Image.open(self.unprocessed_temp_file_path)
        images = []

        for i, page in enumerate(ImageSequence.Iterator(image)):
            page = page.convert('RGB')
            images.append(page)

        if len(images) == 1:
            images[0].save(pdf_path)
        else:
            images[0].save(pdf_path, save_all=True, append_images=images[1:])
        
        self.extension = OCRSupportedExts.PDF
        self.unprocessed_temp_file_path = pdf_path
        
    def write_unprocessed_to_temp_file(self):
        with open(self.unprocessed_temp_file_path, 'wb') as f:
            f.write(self.unprocessed_file_bytes)

    def split_pdf_into_single_pages(self):
        pages_paths = []

        with open(self.unprocessed_temp_file_path, 'rb') as pdf:
            unprocessed_pdf = PyPDF2.PdfFileReader(pdf)

            for i in range(unprocessed_pdf.numPages):
                page = PyPDF2.PdfFileWriter()
                page.addPage(unprocessed_pdf.getPage(i))

                page_path = os.path.join(
                    self.temp_files_dir,
                    f'{i}_{self.id}{OCRSupportedExts.PDF}'
                )

                with open(page_path, 'wb') as output:
                    page.write(output)

                pages_paths.append(page_path)
        
        return pages_paths

    def merge_processed_pages_into_processed_pdf(self, pages_paths):
        merger = PyPDF2.PdfFileMerger()

        for page in pages_paths:
            merger.append(page)

        merger.write(self.processed_temp_file_path)
        merger.close()

    def extract_data_from_processed_file(self):
        with pdfplumber.open(self.processed_temp_file_path) as pdf:
            for page in pdf.pages:
                self.extracted_pages_text.append(page.extract_text())

    def save_processed_bytes(self):
        with open(self.processed_temp_file_path, 'rb') as f:
            self.processed_file_bytes = f.read()

    def clean_temp_files(self):
        try:
            rmtree(self.temp_files_dir)
        except OSError:
            pass
