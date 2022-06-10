from PyQt5.QtCore import QSize
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QPushButton, QWidget, QLabel


class TransactionButton(QPushButton):  # Кнопка для взаимодействия с транзакциями (Изменить/Удалить)

    def __init__(self, parent: QWidget, icon_path: str):
        super().__init__(parent)

        self.setMinimumSize(40, 40)
        self.setMaximumSize(40, 40)
        self.setIcon(QIcon(icon_path))
        self.setIconSize(QSize(36, 36))

class TransactionIcon(QLabel):  # Иконка для транзакций

    def __init__(self, parent: QWidget, icon_path: str):
        super().__init__(parent)

        self.setMinimumSize(40, 40)
        self.setMaximumSize(40, 40)
        self.setPixmap(QIcon(icon_path).pixmap(36, 36))
