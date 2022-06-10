import locale
import sqlite3
import sys
from sqlite3 import Connection

from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QGroupBox, QTabWidget, QHBoxLayout

from Dialogs import *
from Widgets import *


# Очистка списка транзакций
def clear_list(layout: QVBoxLayout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()


# Преобразует список транзакций за текущий месяц в словарь сортируя по датам
# Список переданный в качестве аргумента изначально отсортирован в порядке убывания дат
# Пример результата выполнения метода:
# {'2022.06.06': [[], [], []], '2022.06.05': [[], []]}
def parse_transactions(data: list, account: int) -> dict:
    transactions = {}

    date = ""
    # id - 0, account - 1, sum - 2, date - 3, comment - 4
    for item in data:
        if item[1] != account and account != 0:
            continue

        if item[3] != date:
            date = item[3]
            transactions[date] = []

        transactions[date].append(item)

    return transactions


class MainWidget(QWidget):

    account_index: int = 0  # Текущий счёт - по умолчанию отображает общий баланс и историю транзакций
    account_button: QPushButton = None  # Кнопка для взаимодействия со счётом, на ней же отображается информация
    last_button: QPushButton = None  # Кнопка для выбора предыдущего счёта
    next_button: QPushButton = None  # Кнопка для выбора следующего счёта либо добавления нового

    date: datetime = datetime.today()  # Текущая дата
    date_label: QLabel = None  # Строка для отображения текущего месяца и года
    date_button: QPushButton = None  # Кнопка для открытия диалога изменения текущей даты

    income_button: QPushButton = None  # Кнопка для добавления дохода
    expense_button: QPushButton = None  # Кнопка для добавления расхода

    transactions: QTabWidget = None  # Виджет для отображения всех транзакций за текущий месяц
    incomes: QWidget = None  # Поле с доходами за текущий месяц
    incomes_list: QVBoxLayout = None  # Список доходов
    expenses: QWidget = None  # Поле с расходами за текущий месяц
    expenses_list: QVBoxLayout = None  # Список расходов

    db: Connection = None  # База данных

    def __init__(self):
        super().__init__()

        locale.setlocale(locale.LC_TIME, "ru")  # Изменение языка для корректного отображения даты
        self.db = sqlite3.connect("database.db")

        self.setup_ui()
        self.update_all()

    def setup_ui(self):
        uic.loadUi("ui/main.ui", self)
        self.setWindowIcon(QIcon("images/app_icon.png"))

        cursor = self.db.cursor()
        if len(cursor.execute("SELECT * FROM accounts").fetchall()) > 0:
            self.next_button.setIcon(QIcon("images/next_account.png"))
        else:
            self.next_button.setIcon(QIcon("images/add_account.png"))

        self.account_button.setStyleSheet("background-color: transparent")
        self.last_button.setIcon(QIcon("images/last_account.png"))
        self.last_button.setStyleSheet("background-color: transparent")
        self.next_button.setStyleSheet("background-color: transparent")

        self.date_label.setText(self.date.strftime("%B %Y").upper())
        self.date_button.setIcon(QIcon("images/calendar.png"))
        self.date_button.setStyleSheet("background-color: transparent")

        self.account_button.clicked.connect(self.account_dialog)
        self.last_button.clicked.connect(self.last_account)
        self.next_button.clicked.connect(self.next_account)
        self.date_button.clicked.connect(self.date_dialog)
        self.income_button.clicked.connect(lambda: self.income_dialog())
        self.expense_button.clicked.connect(lambda: self.expense_dialog())

    def account_dialog(self):  # Открытие диалога для добавления/изменения/удаления счёта
        if self.account_index > 0:
            dialog = AccountDialog(self, self.account_index)
            dialog.show()
            dialog.exec_()

    def date_dialog(self):  # Открытие диалога для изменения текущей даты
        dialog = DateDialog(self)
        dialog.show()
        dialog.exec_()

    def income_dialog(self, income_id: int = -1):  # Открытия диалога для добавления/изменения дохода
        if self.has_accounts():
            dialog = IncomeDialog(self, "incomes", income_id)
            dialog.show()
            dialog.exec_()

    def expense_dialog(self, expense_id: int = -1):  # Открытие диалога для добавления/изменения расхода
        if self.has_accounts():
            dialog = ExpenseDialog(self, "expenses", expense_id)
            dialog.show()
            dialog.exec_()

    def has_accounts(self) -> bool:  # Проверяет есть ли счета у пользователя
        cursor = self.db.cursor()
        if len(cursor.execute("SELECT * FROM accounts").fetchall()) == 0:
            message = QMessageBox(QMessageBox.Warning, "Ошибка", "У вас нет ни одного счёта!")
            message.setWindowIcon(QIcon("images/app_icon.png"))
            message.show()
            message.exec_()
            return False

        return True

    def last_account(self):  # Предыдущий счёт
        self.account_index -= 1
        if self.account_index == 0:
            self.last_button.setEnabled(False)

        self.next_button.setIcon(QIcon("images/next_account.png"))
        self.update_all()

    def next_account(self):  # Следующий счёт/добавить счёт
        cursor = self.db.cursor()
        accounts = cursor.execute("SELECT * FROM accounts").fetchall()

        if len(accounts) <= self.account_index:
            dialog = AccountDialog(self, 0)
            dialog.show()
            dialog.exec_()
        else:
            self.account_index += 1
            if len(cursor.execute("SELECT * FROM accounts").fetchall()) <= self.account_index:
                self.next_button.setIcon(QIcon("images/add_account.png"))

            self.last_button.setEnabled(True)
            self.update_all()

    # Добавляет сумму на указанный id счёта (можно использовать для вычитания, добавляя "-" перед суммой)
    def add_money(self, account_id: int, money: float):
        self.db.cursor().execute("UPDATE accounts SET balance = balance + " + str(money) + " WHERE id = " + str(account_id))
        self.db.commit()

    def delete_transaction(self, table: str, tr_id: int):  # Удаление транзакции из базы данных
        cursor = self.db.cursor()

        # id - 0, account - 1, sum - 2, date - 3, comment - 4
        transaction = cursor.execute("SELECT * FROM " + table + " WHERE id = " + str(tr_id)).fetchall()[0]
        cursor.execute("DELETE FROM " + table + " WHERE id = " + str(tr_id))
        self.db.commit()

        if table == "incomes":
            self.add_money(transaction[1], -transaction[2])
            self.update_incomes()
        else:
            self.add_money(transaction[1], transaction[2])
            self.update_expenses()

        self.update_balance()

    # Все лямбды в Python создаются в одной области видимости. Поэтому приходится так изощряться
    # Следующие 4 метода возвращают лямбды, которые будут вызываться при нажатии кнопок
    def edit_income(self, income_id: int) -> callable:
        return lambda: self.income_dialog(income_id)

    def delete_income(self, income_id: int) -> callable:
        return lambda: self.delete_transaction("incomes", income_id)

    def edit_expense(self, expense_id: int) -> callable:
        return lambda: self.expense_dialog(expense_id)

    def delete_expense(self, expense_id: int) -> callable:
        return lambda: self.delete_transaction("expenses", expense_id)

    def update_all(self):  # Обновление всей информации в главном окне
        self.update_balance()
        self.update_incomes()
        self.update_expenses()

    def update_balance(self):  # Обновляет отображаемый счёт и баланс
        cursor = self.db.cursor()

        if self.account_index == 0:
            account_name = "ОБЩИЙ БАЛАНС"
            account_balance = 0

            accounts = cursor.execute("SELECT * FROM accounts").fetchall()
            # id - 0, sum - 1, name - 2
            for account in accounts:
                account_balance += account[1]
        else:
            # id - 0, sum - 1, name - 2
            account = cursor.execute("SELECT * FROM accounts").fetchall()[self.account_index - 1]
            account_name = str(account[2])
            account_balance = account[1]

        self.account_button.setText(account_name + " " + str(account_balance) + "₽")

    def update_incomes(self):  # Обновляет историю доходов для счёта
        clear_list(self.incomes_list)

        cursor = self.db.cursor()
        result = cursor.execute("SELECT * FROM incomes WHERE date BETWEEN '" + self.date.strftime("%Y-%m-01") +
                                "' AND '" + self.date.strftime("%Y-%m-31") + "' ORDER BY date DESC").fetchall()
        account = 0 if self.account_index == 0 else cursor.execute("SELECT id FROM accounts").fetchall()[self.account_index - 1][0]
        incomes = parse_transactions(result, account)

        total = 0
        for date in incomes:
            group_box = QGroupBox(self.incomes)
            group_box.setTitle(datetime.strptime(date, "%Y-%m-%d").strftime("%d %A").upper())
            box_layout = QVBoxLayout(group_box)

            # id - 0, account - 1, sum - 2, date - 3, comment - 4
            for income in incomes[date]:
                income_layout = QHBoxLayout()

                income_layout.addWidget(TransactionIcon(group_box, "images/income.png"))
                income_layout.addWidget(QLabel(str(income[2]) + "₽", group_box))
                income_layout.addWidget(QLabel(str(income[4]), group_box))

                edit_button = TransactionButton(group_box, "images/edit.png")
                edit_button.clicked.connect(self.edit_income(income[0]))
                income_layout.addWidget(edit_button)

                del_button = TransactionButton(group_box, "images/trash.png")
                del_button.clicked.connect(self.delete_income(income[0]))
                income_layout.addWidget(del_button)

                box_layout.addLayout(income_layout)
                total += income[2]

            self.incomes_list.addWidget(group_box)

        self.transactions.setTabText(0, "Доходы " + str(total) + "₽")

    def update_expenses(self):  # Обновляет историю расходов для счёта
        clear_list(self.expenses_list)

        cursor = self.db.cursor()
        categories = cursor.execute("SELECT * FROM categories").fetchall()
        icon_list = {}
        # id - 0, name - 1, icon_path - 2
        for category in categories:
            icon_list[category[0]] = category[2]

        result = cursor.execute("SELECT * FROM expenses WHERE date BETWEEN '" + self.date.strftime("%Y-%m-01") +
                                "' AND '" + self.date.strftime("%Y-%m-31") + "' ORDER BY date DESC").fetchall()
        account = 0 if self.account_index == 0 else cursor.execute("SELECT id FROM accounts").fetchall()[self.account_index - 1][0]
        expenses = parse_transactions(result, account)

        total = 0
        for date in expenses:
            group_box = QGroupBox(self.expenses)
            group_box.setTitle(datetime.strptime(date, "%Y-%m-%d").strftime("%d %A").upper())
            box_layout = QVBoxLayout(group_box)

            # id - 0, account - 1, sum - 2, date - 3, comment - 4, category - 5
            for expense in expenses[date]:
                expense_layout = QHBoxLayout()

                expense_layout.addWidget(TransactionIcon(group_box, icon_list[expense[5]]))
                expense_layout.addWidget(QLabel(str(expense[2]) + "₽", group_box))
                expense_layout.addWidget(QLabel(str(expense[4]), group_box))

                edit_button = TransactionButton(group_box, "images/edit.png")
                edit_button.clicked.connect(self.edit_expense(expense[0]))
                expense_layout.addWidget(edit_button)

                del_button = TransactionButton(group_box, "images/trash.png")
                del_button.clicked.connect(self.delete_expense(expense[0]))
                expense_layout.addWidget(del_button)

                box_layout.addLayout(expense_layout)
                total += expense[2]

            self.expenses_list.addWidget(group_box)

        self.transactions.setTabText(1, "Расходы " + str(total) + "₽")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = MainWidget()
    widget.show()
    sys.exit(app.exec_())
