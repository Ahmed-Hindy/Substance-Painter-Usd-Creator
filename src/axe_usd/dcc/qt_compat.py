"""
Qt compatibility layer for Substance Painter.

Supports PySide2 (SP < 10.1) and PySide6 (SP >= 10.1).
"""
from __future__ import annotations

try:
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore
    PYSIDE_VERSION = 6
except Exception:
    from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore
    PYSIDE_VERSION = 2

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
    "QPushButton",
    "QScrollArea",
    "QSizePolicy",
    "QVBoxLayout",
    "QWidget",
]
