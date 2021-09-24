#!/usr/bin/python3

"""This module takes care of the html to pdf conversion using QWebEngine"""

import os
import logging

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QPageLayout, QPageSize
from PyQt5 import QtWidgets, QtWebEngineWidgets


class PdfPage(QtWebEngineWidgets.QWebEnginePage):
    def __init__(self, output_dir):
        super().__init__()
        self._htmls = []
        self.output_dir = output_dir

        self.pdf_folder_path = output_dir / "risitas-pdf"
        self.pdf_files = []

        self.settings = (
            QtWebEngineWidgets.QWebEngineSettings.globalSettings()
        )
        self.settings.setAttribute(
            QtWebEngineWidgets.QWebEngineSettings.JavascriptEnabled, False
        )

        self.setZoomFactor(1)
        self.layout = QPageLayout()
        self.layout.setPageSize(QPageSize(QPageSize.A4))
        self.layout.setOrientation(QPageLayout.Portrait)
        self.loadFinished.connect(self._handleLoadFinished)
        self.pdfPrintingFinished.connect(self._handlePrintingFinished)

    def convert(self, htmls):
        self._htmls = iter(htmls)
        self._fetchNext()

    def get_pdfs_path(self):
        return self.pdf_files

    def _fetchNext(self):
        try:
            self.current_file = next(self._htmls)
            self.load(QUrl.fromLocalFile(self.current_file.as_posix()))
        except StopIteration:
            return False
        return True

    def _handleLoadFinished(self):
        pdf_file = self.current_file.name[:-5] + ".pdf"
        output_file = str(self.pdf_folder_path) + os.sep + pdf_file
        self.pdf_files.append(output_file)
        self.printToPdf(output_file, pageLayout=self.layout)
        logging.info(f"Creating {output_file}")

    def _handlePrintingFinished(self, file, bol):
        logging.info(f"Created {file}")
        if file not in self.pdf_files:
            self.pdf_files.append(file)
        if not self._fetchNext():
            QtWidgets.QApplication.quit()
