from datetime import datetime

from PyQt5 import uic
from PyQt5.QtCore import QDate, QSize
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QDialog, QDateEdit, QDoubleSpinBox, QLineEdit, QDialogButtonBox, QLabel, QPushButton, \
    QGridLayout, QWidget, QComboBox, QMessageBox

from MyBudget import MainWidget


class SimpleDialog(QDialog):  # Базовый класс для диалогов

    main: MainWidget = None  # Главный виджет приложения
    button_box: QDialogButtonBox = None  # Кнопки ОК|Отмена

    def __init__(self, main: MainWidget):
        super().__init__()

        self.main = main
        self.setup_ui()

    def setup_ui(self):
        self.button_box.accepted.connect(self.on_accept)
        self.button_box.rejected.connect(self.on_cancel)

    def on_accept(self):
        self.close()

    def on_cancel(self):
        self.close()


class AccountDialog(QDialog):  # Диалог для добавления/изменения/удаления счёта

    main: MainWidget = None  # Главный виджет приложения

    name_input: QLineEdit = None  # Поле для ввода названия счёта
    balance_input: QDoubleSpinBox = None  # Поле для ввода баланса счёта
    left_button: QPushButton = None  # Кнопка Добавить/Сохранить
    right_button: QPushButton = None  # Кнопка Отмена/Удалить счёт

    account_id: int = -1  # ID счёта

    def __init__(self, main: MainWidget, account_index: int):
        super().__init__()

        self.main = main
        if account_index > 0:
            self.account_id = main.db.cursor().execute("SELECT * FROM accounts").fetchall()[account_index - 1][0]
        self.setup_ui()

    def setup_ui(self):
        uic.loadUi("ui/account_dialog.ui", self)
        self.setWindowIcon(QIcon("images/app_icon.png"))

        if self.account_id != -1:
            cursor = self.main.db.cursor()
            account = cursor.execute("SELECT * FROM accounts WHERE id = " + str(self.account_id)).fetchall()[0]

            # id - 0, balance - 1, name - 2
            self.name_input.setText(str(account[2]))
            self.balance_input.setValue(account[1])
            self.left_button.setText("Сохранить")
            self.right_button.setText("Удалить счёт")
            self.right_button.setStyleSheet("color: red")

        self.left_button.clicked.connect(self.left_click)
        self.right_button.clicked.connect(self.right_click)

    def left_click(self):
        balance = str(self.balance_input.value())
        name = self.name_input.text().upper()

        if name == "":
            message = QMessageBox(QMessageBox.Warning, "Ошибка", "Поле 'Название' не может быть пустым!")
            message.setWindowIcon(QIcon("images/app_icon.png"))
            message.show()
            message.exec_()
            return

        cursor = self.main.db.cursor()
        accounts = cursor.execute(
            "SELECT * FROM accounts WHERE name = '" + name + "' AND id != " + str(self.account_id)).fetchall()
        if len(accounts) != 0:
            message = QMessageBox(QMessageBox.Warning, "Ошибка", "Счёт с таким названием уже существует!")
            message.setWindowIcon(QIcon("images/app_icon.png"))
            message.show()
            message.exec_()
            return

        if self.account_id == -1:
            cursor.execute("INSERT INTO accounts(balance, name) VALUES(" + balance + ", '" + name + "')")
            self.main.next_button.setIcon(QIcon("images/next_account.png"))
        else:
            cursor.execute("UPDATE accounts SET balance = " + balance + ", name = '" + name + "' WHERE id = "
                           + str(self.account_id))

        self.main.db.commit()
        self.main.update_balance()
        self.close()

    def right_click(self):
        if self.account_id != -1:
            message = QMessageBox(QMessageBox.Question, "Мой бюджет",
                                  "Вы действительно хотите удалить счёт?\n\nТакже удалится вся история транзакций")
            message.setWindowIcon(QIcon("images/app_icon.png"))
            message.addButton(QMessageBox.Yes)
            message.addButton(QMessageBox.No)
            message.show()
            message.exec_()

            if message.result() == QMessageBox.Yes:
                cursor = self.main.db.cursor()

                # При удалении счёта автоматически удаляются все транзакции связанные с этим счётом
                cursor.execute("DELETE FROM accounts WHERE id = " + str(self.account_id))
                cursor.execute("DELETE FROM incomes WHERE account = " + str(self.account_id))
                cursor.execute("DELETE FROM expenses WHERE account = " + str(self.account_id))
                self.main.db.commit()

                if len(cursor.execute("SELECT * FROM accounts").fetchall()) > 0:
                    self.main.next_button.setIcon(QIcon("images/next_account.png"))
                else:
                    self.main.next_button.setIcon(QIcon("images/add_account.png"))

                self.main.last_button.setEnabled(False)
                self.main.account_index = 0
                self.main.update_all()

                self.close()
        else:
            self.close()


class DateDialog(SimpleDialog):  # Диалог для изменения даты в главном окне

    date_edit: QDateEdit = None  # Поле для выбора даты

    def setup_ui(self):
        uic.loadUi("ui/date_dialog.ui", self)
        self.setWindowIcon(QIcon("images/calendar.png"))

        date = self.main.date
        today = datetime.today()
        self.date_edit.setDate(QDate(date.year, date.month, 1))
        self.date_edit.setMaximumDate(QDate(today.year, today.month, today.day))  # Нельзя выбрать будущую дату

        super().setup_ui()

    def on_accept(self):
        date = self.date_edit.date().toPyDate()

        self.main.date = date
        self.main.date_label.setText(date.strftime("%B %Y").upper())
        self.main.update_incomes()
        self.main.update_expenses()

        self.close()


class TransactionDialog(SimpleDialog):  # Базовый класс для транзакций

    account_list: QComboBox = None  # Список счетов
    sum_input: QDoubleSpinBox = None  # Поле для ввода суммы ₽
    date_edit: QDateEdit = None  # Поле для выбора даты
    comment_input: QLineEdit = None  # Поле для ввода комментария

    table: str  # Название таблицы в базе данных
    tr_id: int  # ID транзакции

    def __init__(self, main: MainWidget, table: str, tr_id: int = -1):
        self.table = table
        self.tr_id = tr_id

        super().__init__(main)

    def setup_ui(self):
        cursor = self.main.db.cursor()

        result = cursor.execute("SELECT * FROM accounts").fetchall()
        accounts = {}
        for account in result:
            accounts[account[0]] = self.account_list.count()
            self.account_list.addItem(account[2])

        date = self.main.date
        today = datetime.today()
        if self.tr_id == -1:
            if today.year == date.year and today.month == date.month:
                self.date_edit.setDate(QDate(date.year, date.month, today.day))
            else:
                self.date_edit.setDate(QDate(date.year, date.month, 1))

            if self.main.account_index > 1:
                self.account_list.setCurrentIndex(self.main.account_index - 1)
        else:
            transaction = cursor.execute("SELECT * FROM " + self.table +
                                         " WHERE id = '" + str(self.tr_id) + "'").fetchall()[0]

            # id - 0, account - 1, sum - 2, date - 3, comment - 4
            self.account_list.setCurrentIndex(accounts[transaction[1]])
            self.sum_input.setValue(transaction[2])
            date = datetime.strptime(transaction[3], "%Y-%m-%d")
            self.date_edit.setDate(QDate(date.year, date.month, date.day))
            self.comment_input.setText(str(transaction[4]))

        self.date_edit.setMaximumDate(QDate(today.year, today.month, today.day))  # Нельзя выбрать будущую дату

        super().setup_ui()


class IncomeDialog(TransactionDialog):  # Диалог для добавления/изменения дохода

    def setup_ui(self):
        uic.loadUi("ui/income_dialog.ui", self)
        self.setWindowIcon(QIcon("images/income.png"))

        super().setup_ui()

    def on_accept(self):
        cursor = self.main.db.cursor()

        account = self.account_list.currentIndex()
        account = cursor.execute("SELECT * FROM accounts").fetchall()[account][0]
        income = self.sum_input.value()
        date = self.date_edit.date().toPyDate().strftime("%Y-%m-%d")
        comment = self.comment_input.text()

        if self.tr_id == -1:
            cursor.execute("INSERT INTO incomes(account, sum, date, comment) VALUES("
                           + str(account) + ", " + str(income) + ", '" + date + "', '" + comment + "')")
            self.main.add_money(account, income)
        else:
            old_income = cursor.execute("SELECT * FROM incomes WHERE id = " + str(self.tr_id)).fetchone()
            cursor.execute("UPDATE incomes SET account = " + str(account) + ", sum = " + str(income) + ", date = '"
                           + date + "', comment = '" + comment + "' WHERE id = " + str(self.tr_id))

            # id - 0, account - 1, sum - 2, date - 3, comment - 4
            if old_income[1] == account:
                self.main.add_money(account, income - old_income[2])
            else:
                self.main.add_money(old_income[1], -old_income[2])
                self.main.add_money(account, income)

        self.main.db.commit()
        self.main.update_incomes()
        self.main.update_balance()
        self.close()


class ExpenseDialog(TransactionDialog):  # Диалог для добавления/изменения расхода

    category_label: QLabel = None  # Строка для отображения выбранной категории

    categories: QWidget = None  # Поле с доступными категориями
    category_grid: QGridLayout = None  # Табличный layout, куда добавляются кнопки с категориями

    sel_category: int  # ID выбранной категории

    def setup_ui(self):
        uic.loadUi("ui/expense_dialog.ui", self)
        self.setWindowIcon(QIcon("images/expense.png"))

        if self.tr_id == -1:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)
        else:
            cursor = self.main.db.cursor()
            # id - 0, account - 1, sum - 2, date - 3, comment - 4, category - 5
            expense = cursor.execute("SELECT * FROM expenses WHERE id = '" + str(self.tr_id) + "'").fetchall()[0]
            # id - 0, name - 1, icon_path - 2
            category = cursor.execute("SELECT * FROM categories WHERE id = " + str(expense[5])).fetchall()[0]

            self.category_label.setText("Категория - " + category[1])
            self.sel_category = expense[5]

        row = 0
        col = 0
        cursor = self.main.db.cursor()
        categories = cursor.execute("SELECT * FROM categories").fetchall()
        # id - 0, name - 1, icon_path - 2
        for category in categories:
            button = QPushButton(self.categories)
            button.setMinimumSize(80, 80)
            button.setMaximumSize(80, 80)
            button.setIconSize(QSize(76, 76))
            button.setIcon(QIcon(category[2]))
            button.clicked.connect(self.click_category(category[0]))
            self.category_grid.addWidget(button, row, col)

            col += 1
            if col > 2:  # кнопки располагаются в 3 столбца
                col = 0
                row += 1

        super().setup_ui()

    # Все лямбды в Python создаются в одной области видимости. Поэтому приходится так изощряться
    def click_category(self, arg: int):
        return lambda: self.select_category(arg)

    def select_category(self, category: int):
        cursor = self.main.db.cursor()
        category = cursor.execute("SELECT * FROM categories WHERE id = " + str(category)).fetchall()[0]
        self.category_label.setText("Категория - " + category[1])
        self.sel_category = category[0]

        self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)

    def on_accept(self):
        cursor = self.main.db.cursor()

        account = self.account_list.currentIndex()
        account = cursor.execute("SELECT * FROM accounts").fetchall()[account][0]
        expense = self.sum_input.value()
        date = self.date_edit.date().toPyDate().strftime("%Y-%m-%d")
        category = str(self.sel_category)
        comment = self.comment_input.text()

        if self.tr_id == -1:
            cursor.execute("INSERT INTO expenses(account, sum, date, comment, category) VALUES("
                           + str(account) + ", " + str(expense) + ", '" + date + "', '"
                           + comment + "', " + category + ")")
            self.main.add_money(account, -expense)
        else:
            old_expense = cursor.execute("SELECT * FROM expenses WHERE id = " + str(self.tr_id)).fetchone()
            cursor.execute("UPDATE expenses SET account = " + str(account) + ", sum = " + str(expense) +
                           ", date = '" + date + "', comment = '" + comment +
                           "', category = " + category + " WHERE id = " + str(self.tr_id))

            # id - 0, account - 1, sum - 2, date - 3, comment - 4, category - 5
            if old_expense[1] == account:
                self.main.add_money(account, -(expense - old_expense[2]))
            else:
                self.main.add_money(old_expense[1], old_expense[2])
                self.main.add_money(account, -expense)

        self.main.db.commit()
        self.main.update_expenses()
        self.main.update_balance()
        self.close()
