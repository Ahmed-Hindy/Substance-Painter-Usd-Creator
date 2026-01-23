"""
Qt compatibility layer for Substance Painter.

Supports PySide2 (SP < 10.1.0) and PySide6 (SP >= 10.1.0).
"""
from __future__ import annotations

import substance_painter as sp

use_pyside2 = sp.application.version_info() < (10, 1, 0)

if use_pyside2:
    from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore

    PYSIDE_VERSION = 2
else:
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore

    PYSIDE_VERSION = 6

Qt = QtCore.Qt

QIcon = QtGui.QIcon
QPalette = QtGui.QPalette

QCheckBox = QtWidgets.QCheckBox
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
QScrollArea = QtWidgets.QScrollArea
QSizePolicy = QtWidgets.QSizePolicy
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

__all__ = [
    "PYSIDE_VERSION",
    "Qt",
    "QIcon",
    "QPalette",
    "QCheckBox",
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
    "QScrollArea",
    "QSizePolicy",
    "QVBoxLayout",
    "QWidget",
]
