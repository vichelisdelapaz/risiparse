#!/usr/bin/python3

"""This module takes care of the html to pdf conversion using QWebEngine"""

from typing import List, Iterator
import logging
import pathlib

from PySide6.QtCore import QUrl
from PySide6.QtGui import QPageLayout, QPageSize
from PySide6 import QtWidgets
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings


class PdfPage(QWebEnginePage):
    """Produce a pdf from an html file"""
    def __init__(self, output_dir: pathlib.Path) -> None:
        super().__init__()
        self._htmls: Iterator[pathlib.Path] = iter([pathlib.Path()])
        self.output_dir = output_dir
        self.current_file: pathlib.Path = pathlib.Path()

        self.pdf_folder_path: pathlib.Path = output_dir / "risitas-pdf"
        self.pdf_files: List[pathlib.Path] = []

        self.settings().setAttribute(
            QWebEngineSettings.JavascriptEnabled, False
        )

        self.setZoomFactor(1)
        self.layout = QPageLayout()
        self.layout.setPageSize(QPageSize(QPageSize.A4))
        self.layout.setOrientation(QPageLayout.Portrait)
        # Need to open issue on pylint tracker
        self.loadFinished.connect(  # pylint: disable=no-member
            self._handle_load_finished
        )
        self.pdfPrintingFinished.connect(  # pylint: disable=no-member
            self._handle_printing_finished
        )

    def convert(self, htmls: List[pathlib.Path]) -> None:
        """Processing html file one by one"""
        self._htmls = iter(htmls)
        self._fetch_next()

    def get_pdfs_path(self) -> List['pathlib.Path']:
        """Return pdfs path"""
        return self.pdf_files

    def _fetch_next(self) -> bool:
        try:
            self.current_file = next(self._htmls)
            self.load(QUrl.fromLocalFile(self.current_file.as_posix()))
        except StopIteration:
            return False
        return True

    def _handle_load_finished(self) -> None:
        pdf_file = self.current_file.with_suffix(".pdf").name
        output_file: pathlib.Path = self.pdf_folder_path / pdf_file
        self.printToPdf(str(output_file), layout=self.layout)
        logging.info("Creating %s", output_file)

    def _handle_printing_finished(self, html_file: str) -> None:
        file_path = pathlib.Path(html_file)
        logging.info("Created %s", html_file)
        self.pdf_files.append(file_path)
        if not self._fetch_next():
            QtWidgets.QApplication.quit()
