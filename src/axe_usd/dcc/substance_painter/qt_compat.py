"""
Qt compatibility layer for Substance Painter.

Supports PySide2 (SP < 10.1.0) and PySide6 (SP >= 10.1.0).
"""
from __future__ import annotations

from substance_painter.application import version_info

use_pyside2: bool = version_info() < (10, 1, 0)

if use_pyside2:
    from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore

    PYSIDE_VERSION = 2
else:
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore

    PYSIDE_VERSION = 6

Qt = QtCore.Qt

QIcon = QtGui.QIcon
QPalette = QtGui.QPalette
QDesktopServices = QtGui.QDesktopServices
QUrl = QtCore.QUrl

QCheckBox = QtWidgets.QCheckBox
QComboBox = QtWidgets.QComboBox
QApplication = QtWidgets.QApplication
QDialog = QtWidgets.QDialog
QFileDialog = QtWidgets.QFileDialog
QFormLayout = QtWidgets.QFormLayout
QFrame = QtWidgets.QFrame
QGroupBox = QtWidgets.QGroupBox
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QMessageBox = QtWidgets.QMessageBox
QMenuBar = QtWidgets.QMenuBar
QPushButton = QtWidgets.QPushButton
QToolButton = QtWidgets.QToolButton
QInputDialog = QtWidgets.QInputDialog
QScrollArea = QtWidgets.QScrollArea
QSizePolicy = QtWidgets.QSizePolicy
QStyle = QtWidgets.QStyle
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

__all__ = [
    "PYSIDE_VERSION",
    "Qt",
    "QIcon",
    "QPalette",
    "QDesktopServices",
    "QUrl",
    "QCheckBox",
    "QComboBox",
    "QApplication",
    "QDialog",
    "QFileDialog",
    "QFormLayout",
    "QFrame",
    "QGroupBox",
    "QHBoxLayout",
    "QLabel",
    "QLineEdit",
    "QMessageBox",
    "QMenuBar",
    "QPushButton",
    "QToolButton",
    "QInputDialog",
    "QScrollArea",
    "QSizePolicy",
    "QStyle",
    "QVBoxLayout",
    "QWidget",
]
