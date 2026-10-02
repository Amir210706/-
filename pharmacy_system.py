#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Автоматизированная система аптеки «Здоровье+» — Python-аналог
дипломного проекта на C# (магазин «Медтехника»), адаптированный
под аптеку.

Совместимо с Python 3.6+. Используются только встроенные модули:
- sqlite3   (замена Access .accdb — база данных)
- tkinter   (графический интерфейс)
Ничего дополнительно устанавливать не нужно.

Запуск: python pharmacy_system.py
Работает и в Visual Studio 2019/2022 (кнопка "Запуск" / Start),
и в VS Code, и просто из командной строки.

Структура (по аналогии с оригинальным проектом):
- Авторизация.cs        -> LoginWindow
- Регистрация Аккаунта  -> RegisterDialog
- Клиент.cs             -> ClientWindow   (роль "Клиент")
- Сотрудник.cs          -> EmployeeWindow (роль "Сотрудник")
- Адмистратор.cs        -> AdminWindow    (роль "Администратор")
- Директор.cs           -> DirectorWindow (роль "Директор")
- controller/Query.cs   -> класс Database
- Отчеты_по_заказам/    -> папка REPORTS_DIR с текстовыми отчётами

База данных создаётся автоматически в файле pharmacy_system.db
при первом запуске, вместе с демонстрационными данными.
"""

import os
import sqlite3
import datetime

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    import Tkinter as tk
    import ttk
    import tkMessageBox as messagebox


# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

DB_FILE = "pharmacy_system.db"
REPORTS_DIR = "Отчеты_по_заказам"

ROLE_CLIENT = "Клиент"
ROLE_EMPLOYEE = "Сотрудник"
ROLE_ADMIN = "Администратор"
ROLE_DIRECTOR = "Директор"
ALL_ROLES = [ROLE_CLIENT, ROLE_EMPLOYEE, ROLE_ADMIN, ROLE_DIRECTOR]
STAFF_ROLES = [ROLE_EMPLOYEE, ROLE_ADMIN, ROLE_DIRECTOR]  # роли, назначаемые администратором

ORDER_STATUSES = ["Новый", "В обработке", "Выполнен", "Отменён"]


# ---------------------------------------------------------------------------
# Слой базы данных (аналог controller/Query.cs, но на SQLite)
# ---------------------------------------------------------------------------

class Database(object):
    def __init__(self, path=DB_FILE):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()
        self._seed()

    # ---------- инициализация ----------

    def _create_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                login    TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                phone    TEXT,
                role     TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS medicines (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                name                   TEXT UNIQUE NOT NULL,
                category               TEXT NOT NULL,
                price                  REAL NOT NULL,
                quantity               INTEGER NOT NULL,
                requires_prescription  INTEGER NOT NULL DEFAULT 0,
                description            TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                client_login TEXT NOT NULL,
                order_date   TEXT NOT NULL,
                status       TEXT NOT NULL,
                total        REAL NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id       INTEGER NOT NULL,
                medicine_name  TEXT NOT NULL,
                price          REAL NOT NULL,
                qty            INTEGER NOT NULL,
                subtotal       REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            )
        """)
        self.conn.commit()

    def _seed(self):
        cur = self.conn.cursor()

        cur.execute("SELECT COUNT(*) FROM accounts")
        if cur.fetchone()[0] == 0:
            default_accounts = [
                ("admin",      "admin123", "",              ROLE_ADMIN),
                ("sotrudnik",  "pharm123", "",              ROLE_EMPLOYEE),
                ("director",   "dir123",   "",              ROLE_DIRECTOR),
                ("client",     "client123", "+7(900)000-00-00", ROLE_CLIENT),
            ]
            cur.executemany(
                "INSERT INTO accounts (login, password, phone, role) VALUES (?,?,?,?)",
                default_accounts
            )

        cur.execute("SELECT COUNT(*) FROM medicines")
        if cur.fetchone()[0] == 0:
            demo = [
                ("Парацетамол", "Жаропонижающее", 60, 50, 0,
                 "Снижает температуру и боль"),
                ("Ибупрофен", "Обезболивающее", 90, 40, 0,
                 "Противовоспалительное средство"),
                ("Амоксициллин", "Антибиотик", 220, 15, 1,
                 "Антибиотик широкого спектра"),
                ("Валидол", "Сердечные", 45, 30, 0,
                 "При лёгких сердечных недомоганиях"),
                ("Активированный уголь", "ЖКТ", 25, 100, 0,
                 "Сорбент при отравлениях"),
                ("Инсулин", "Гормональные", 850, 8, 1,
                 "Требуется рецепт врача"),
            ]
            cur.executemany(
                "INSERT INTO medicines "
                "(name, category, price, quantity, requires_prescription, description) "
                "VALUES (?,?,?,?,?,?)",
                demo
            )
        self.conn.commit()

    # ---------- аккаунты ----------

    def authenticate(self, login, password):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT role FROM accounts WHERE login=? AND password=?",
            (login, password)
        )
        row = cur.fetchone()
        return row[0] if row else None

    def register(self, login, password, phone):
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM accounts WHERE login=?", (login,))
        if cur.fetchone():
            return False
        cur.execute(
            "INSERT INTO accounts (login, password, phone, role) VALUES (?,?,?,?)",
            (login, password, phone, ROLE_CLIENT)
        )
        self.conn.commit()
        return True

    def list_accounts(self):
        cur = self.conn.cursor()
        cur.execute("SELECT login, phone, role FROM accounts ORDER BY role, login")
        return cur.fetchall()

    def update_role(self, login, role):
        cur = self.conn.cursor()
        cur.execute("UPDATE accounts SET role=? WHERE login=?", (role, login))
        self.conn.commit()

    def delete_account(self, login):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM accounts WHERE login=?", (login,))
        self.conn.commit()

    # ---------- лекарства ----------

    def list_medicines(self, category=None, query=None):
        sql = ("SELECT name, category, price, quantity, "
               "requires_prescription, description FROM medicines")
        conditions = []
        params = []
        if category and category != "Все категории":
            conditions.append("category = ?")
            params.append(category)
        if query:
            conditions.append("LOWER(name) LIKE ?")
            params.append("%" + query.lower() + "%")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY name"
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()

    def categories(self):
        cur = self.conn.cursor()
        cur.execute("SELECT DISTINCT category FROM medicines ORDER BY category")
        return [row[0] for row in cur.fetchall()]

    def add_or_update_medicine(self, name, category, price, qty,
                                requires_prescription, description, restock):
        cur = self.conn.cursor()
        cur.execute("SELECT quantity FROM medicines WHERE name=?", (name,))
        row = cur.fetchone()
        if row:
            new_qty = row[0] + qty if restock else qty
            cur.execute(
                "UPDATE medicines SET category=?, price=?, quantity=?, "
                "requires_prescription=?, description=? WHERE name=?",
                (category, price, new_qty, int(requires_prescription), description, name)
            )
        else:
            cur.execute(
                "INSERT INTO medicines "
                "(name, category, price, quantity, requires_prescription, description) "
                "VALUES (?,?,?,?,?,?)",
                (name, category, price, qty, int(requires_prescription), description)
            )
        self.conn.commit()

    def delete_medicine(self, name):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM medicines WHERE name=?", (name,))
        self.conn.commit()

    # ---------- заказы ----------

    def create_order(self, client_login, cart_items):
        """cart_items: список кортежей (name, price, qty, subtotal)"""
        total = round(sum(item[3] for item in cart_items), 2)
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO orders (client_login, order_date, status, total) VALUES (?,?,?,?)",
            (client_login, date_str, "Новый", total)
        )
        order_id = cur.lastrowid
        for name, price, qty, subtotal in cart_items:
            cur.execute(
                "INSERT INTO order_items "
                "(order_id, medicine_name, price, qty, subtotal) VALUES (?,?,?,?,?)",
                (order_id, name, price, qty, subtotal)
            )
            cur.execute(
                "UPDATE medicines SET quantity = quantity - ? WHERE name=?",
                (qty, name)
            )
        self.conn.commit()
        return order_id, date_str, total

    def list_orders(self, client_login=None):
        cur = self.conn.cursor()
        if client_login:
            cur.execute(
                "SELECT order_id, client_login, order_date, status, total "
                "FROM orders WHERE client_login=? ORDER BY order_id DESC",
                (client_login,)
            )
        else:
            cur.execute(
                "SELECT order_id, client_login, order_date, status, total "
                "FROM orders ORDER BY order_id DESC"
            )
        return cur.fetchall()

    def order_items(self, order_id):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT medicine_name, price, qty, subtotal FROM order_items WHERE order_id=?",
            (order_id,)
        )
        return cur.fetchall()

    def update_order_status(self, order_id, status):
        cur = self.conn.cursor()
        cur.execute("UPDATE orders SET status=? WHERE order_id=?", (status, order_id))
        self.conn.commit()

    def total_revenue(self):
        cur = self.conn.cursor()
        cur.execute("SELECT SUM(total) FROM orders WHERE status != 'Отменён'")
        row = cur.fetchone()
        return row[0] or 0.0


# ---------------------------------------------------------------------------
# Общий стиль интерфейса
# ---------------------------------------------------------------------------

def apply_style(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("Treeview", rowheight=26, font=("Segoe UI", 10))
    style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
    style.configure("TButton", font=("Segoe UI", 10), padding=6)
    style.configure("TLabel", font=("Segoe UI", 10))
    style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))


# ---------------------------------------------------------------------------
# Авторизация.cs -> LoginWindow
# ---------------------------------------------------------------------------

class LoginWindow(tk.Tk):
    def __init__(self, db):
        tk.Tk.__init__(self)
        self.db = db
        self.result_role = None
        self.result_login = None

        self.title("Вход в систему — Аптека «Здоровье+»")
        self.geometry("380x320")
        self.resizable(False, False)
        apply_style(self)

        ttk.Label(self, text="Аптека «Здоровье+»",
                  style="Header.TLabel").pack(pady=(24, 4))
        ttk.Label(self, text="Введите логин и пароль").pack(pady=(0, 16))

        form = ttk.Frame(self)
        form.pack(padx=30, fill="x")

        ttk.Label(form, text="Логин:").grid(row=0, column=0, sticky="w", pady=6)
        self.login_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.login_var, width=22).grid(row=0, column=1, pady=6)

        ttk.Label(form, text="Пароль:").grid(row=1, column=0, sticky="w", pady=6)
        self.password_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.password_var, show="*", width=22).grid(
            row=1, column=1, pady=6)

        btns = ttk.Frame(self)
        btns.pack(pady=(20, 6))
        ttk.Button(btns, text="Войти", command=self._login).pack(side="left", padx=4)
        ttk.Button(btns, text="Регистрация", command=self._open_register).pack(
            side="left", padx=4)

        ttk.Label(
            self,
            text=("Тестовые входы:\n"
                  "Клиент: client / client123\n"
                  "Сотрудник: sotrudnik / pharm123\n"
                  "Администратор: admin / admin123\n"
                  "Директор: director / dir123"),
            font=("Segoe UI", 8), foreground="#666666", justify="left"
        ).pack(pady=(10, 0))

        self.bind("<Return>", lambda e: self._login())

    def _login(self):
        login = self.login_var.get().strip()
        password = self.password_var.get()
        if not login or not password:
            messagebox.showerror("Ошибка", "Введите логин и пароль.")
            return
        role = self.db.authenticate(login, password)
        if role is None:
            messagebox.showerror("Ошибка входа", "Неверный логин или пароль.")
            return
        self.result_role = role
        self.result_login = login
        self.destroy()

    def _open_register(self):
        dialog = RegisterDialog(self, self.db)
        self.wait_window(dialog)
        if dialog.created_login:
            self.login_var.set(dialog.created_login)
            self.password_var.set("")


# ---------------------------------------------------------------------------
# Регистрация Аккаунта.cs -> RegisterDialog
# ---------------------------------------------------------------------------

class RegisterDialog(tk.Toplevel):
    def __init__(self, parent, db):
        tk.Toplevel.__init__(self, parent)
        self.db = db
        self.created_login = None

        self.title("Регистрация аккаунта")
        self.geometry("360x320")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text="Регистрация нового покупателя",
                  font=("Segoe UI", 12, "bold")).pack(pady=(16, 12))

        form = ttk.Frame(self)
        form.pack(padx=24, fill="x")

        ttk.Label(form, text="Логин:").grid(row=0, column=0, sticky="w", pady=6)
        self.login_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.login_var, width=22).grid(row=0, column=1, pady=6)

        ttk.Label(form, text="Пароль:").grid(row=1, column=0, sticky="w", pady=6)
        self.password_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.password_var, show="*", width=22).grid(
            row=1, column=1, pady=6)

        ttk.Label(form, text="Повтор пароля:").grid(row=2, column=0, sticky="w", pady=6)
        self.password2_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.password2_var, show="*", width=22).grid(
            row=2, column=1, pady=6)

        ttk.Label(form, text="Телефон:").grid(row=3, column=0, sticky="w", pady=6)
        self.phone_var = tk.StringVar(value="+7(")
        ttk.Entry(form, textvariable=self.phone_var, width=22).grid(row=3, column=1, pady=6)

        ttk.Label(self, text="Регистрация создаёт аккаунт с ролью «Клиент».\n"
                              "Роли сотрудников назначает администратор.",
                  font=("Segoe UI", 8), foreground="#666666",
                  justify="center").pack(pady=(10, 0))

        ttk.Button(self, text="Зарегистрироваться",
                   command=self._submit).pack(pady=(16, 6))

    def _submit(self):
        login = self.login_var.get().strip()
        password = self.password_var.get()
        password2 = self.password2_var.get()
        phone = self.phone_var.get().strip()

        if not login or not password:
            messagebox.showerror("Ошибка", "Заполните логин и пароль.")
            return
        if len(login) < 3:
            messagebox.showerror("Ошибка", "Логин должен быть не короче 3 символов.")
            return
        if password != password2:
            messagebox.showerror("Ошибка", "Пароли не совпадают.")
            return
        if len(password) < 4:
            messagebox.showerror("Ошибка", "Пароль должен быть не короче 4 символов.")
            return

        ok = self.db.register(login, password, phone)
        if not ok:
            messagebox.showerror("Ошибка", "Такой логин уже занят, выберите другой.")
            return

        messagebox.showinfo("Готово", "Аккаунт создан! Теперь можно войти.")
        self.created_login = login
        self.destroy()


# ---------------------------------------------------------------------------
# Клиент.cs -> ClientWindow
# ---------------------------------------------------------------------------

class ClientWindow(tk.Tk):
    def __init__(self, db, login):
        tk.Tk.__init__(self)
        self.db = db
        self.login = login
        self.cart = []  # список (name, price, qty, subtotal)

        self.title("Аптека «Здоровье+» — Клиент: %s" % login)
        self.geometry("1000x620")
        self.minsize(880, 540)
        apply_style(self)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        shop_tab = ttk.Frame(notebook)
        orders_tab = ttk.Frame(notebook)
        notebook.add(shop_tab, text="Каталог и покупки")
        notebook.add(orders_tab, text="Мои заказы")

        self._build_shop_tab(shop_tab)
        self._build_orders_tab(orders_tab)

        self._refresh_catalog()
        self._refresh_cart()
        self._refresh_orders()

    # ---------- вкладка "Каталог и покупки" ----------

    def _build_shop_tab(self, parent):
        main = ttk.Frame(parent)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(main, width=300)
        right.pack(side="right", fill="y", padx=(10, 0))
        right.pack_propagate(False)

        filters = ttk.Frame(left)
        filters.pack(fill="x", pady=(0, 6))
        ttk.Label(filters, text="Поиск:").pack(side="left")
        self.search_var = tk.StringVar()
        entry = ttk.Entry(filters, textvariable=self.search_var, width=22)
        entry.pack(side="left", padx=(4, 12))
        entry.bind("<KeyRelease>", lambda e: self._refresh_catalog())

        ttk.Label(filters, text="Категория:").pack(side="left")
        self.category_var = tk.StringVar(value="Все категории")
        self.category_combo = ttk.Combobox(filters, textvariable=self.category_var,
                                            state="readonly", width=20)
        self.category_combo.pack(side="left", padx=(4, 0))
        self.category_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_catalog())

        columns = ("name", "category", "price", "stock", "rx")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        headings = {"name": "Название", "category": "Категория", "price": "Цена, ₽",
                    "stock": "На складе", "rx": "Рецепт"}
        widths = {"name": 220, "category": 150, "price": 90, "stock": 100, "rx": 70}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="w")
        self.tree.pack(fill="both", expand=True)

        add_row = ttk.Frame(left)
        add_row.pack(fill="x", pady=(8, 0))
        ttk.Label(add_row, text="Кол-во:").pack(side="left")
        self.qty_var = tk.StringVar(value="1")
        tk.Spinbox(add_row, from_=1, to=999, textvariable=self.qty_var, width=6).pack(
            side="left", padx=(4, 12))
        ttk.Button(add_row, text="Добавить в корзину",
                   command=self._add_to_cart).pack(side="left")

        ttk.Label(right, text="Корзина", style="Header.TLabel").pack(anchor="w")
        self.cart_list = tk.Listbox(right, height=16, font=("Segoe UI", 10))
        self.cart_list.pack(fill="both", expand=True, pady=(6, 6))
        ttk.Button(right, text="Удалить из корзины",
                   command=self._remove_from_cart).pack(fill="x")

        self.total_var = tk.StringVar(value="Итого: 0.00 ₽")
        ttk.Label(right, textvariable=self.total_var,
                  font=("Segoe UI", 12, "bold")).pack(pady=(10, 6))
        ttk.Button(right, text="Оформить заказ", command=self._checkout).pack(fill="x")

    # ---------- вкладка "Мои заказы" ----------

    def _build_orders_tab(self, parent):
        main = ttk.Frame(parent)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(main, width=320)
        right.pack(side="right", fill="y", padx=(10, 0))
        right.pack_propagate(False)

        columns = ("order_id", "date", "status", "total")
        self.orders_tree = ttk.Treeview(left, columns=columns, show="headings",
                                         selectmode="browse")
        headings = {"order_id": "№ заказа", "date": "Дата", "status": "Статус",
                    "total": "Сумма, ₽"}
        widths = {"order_id": 80, "date": 150, "status": 120, "total": 100}
        for col in columns:
            self.orders_tree.heading(col, text=headings[col])
            self.orders_tree.column(col, width=widths[col], anchor="w")
        self.orders_tree.pack(fill="both", expand=True)
        self.orders_tree.bind("<<TreeviewSelect>>", lambda e: self._show_order_items())

        ttk.Button(left, text="Обновить", command=self._refresh_orders).pack(
            fill="x", pady=(6, 0))

        ttk.Label(right, text="Состав заказа", style="Header.TLabel").pack(anchor="w")
        self.order_items_list = tk.Listbox(right, height=20, font=("Segoe UI", 10))
        self.order_items_list.pack(fill="both", expand=True, pady=(6, 0))

    # ---------- обновление данных ----------

    def _refresh_catalog(self):
        cats = ["Все категории"] + self.db.categories()
        self.category_combo["values"] = cats
        if self.category_var.get() not in cats:
            self.category_var.set("Все категории")

        for row in self.tree.get_children():
            self.tree.delete(row)

        rows = self.db.list_medicines(category=self.category_var.get(),
                                       query=self.search_var.get())
        for name, category, price, qty, rx, desc in rows:
            stock = str(qty) if qty > 0 else "нет"
            rx_text = "да" if rx else ""
            self.tree.insert("", "end", values=(name, category, "%.2f" % price, stock, rx_text))

    def _refresh_cart(self):
        self.cart_list.delete(0, tk.END)
        for name, price, qty, subtotal in self.cart:
            self.cart_list.insert(tk.END, "%s x%d = %.2f ₽" % (name, qty, subtotal))
        total = round(sum(item[3] for item in self.cart), 2)
        self.total_var.set("Итого: %.2f ₽" % total)

    def _refresh_orders(self):
        for row in self.orders_tree.get_children():
            self.orders_tree.delete(row)
        for order_id, client_login, date, status, total in self.db.list_orders(self.login):
            self.orders_tree.insert("", "end", iid=str(order_id),
                                     values=(order_id, date, status, "%.2f" % total))
        self.order_items_list.delete(0, tk.END)

    def _show_order_items(self):
        selection = self.orders_tree.selection()
        self.order_items_list.delete(0, tk.END)
        if not selection:
            return
        order_id = int(selection[0])
        for name, price, qty, subtotal in self.db.order_items(order_id):
            self.order_items_list.insert(
                tk.END, "%s x%d = %.2f ₽" % (name, qty, subtotal))

    # ---------- действия ----------

    def _selected_medicine_row(self):
        selection = self.tree.selection()
        if not selection:
            return None
        return self.tree.item(selection[0], "values")

    def _add_to_cart(self):
        values = self._selected_medicine_row()
        if not values:
            messagebox.showinfo("Выбор товара", "Сначала выберите лекарство в списке.")
            return
        name = values[0]
        medicine = None
        for m in self.db.list_medicines():
            if m[0] == name:
                medicine = m
                break
        if medicine is None:
            return
        _, category, price, stock_qty, rx, desc = medicine

        try:
            qty = int(self.qty_var.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Количество должно быть числом.")
            return
        if qty <= 0:
            messagebox.showerror("Ошибка", "Количество должно быть больше нуля.")
            return
        if qty > stock_qty:
            messagebox.showerror("Недостаточно на складе",
                                  "В наличии только %d шт." % stock_qty)
            return

        subtotal = round(price * qty, 2)
        self.cart.append((name, price, qty, subtotal))
        self._refresh_cart()

    def _remove_from_cart(self):
        selection = self.cart_list.curselection()
        if not selection:
            return
        del self.cart[selection[0]]
        self._refresh_cart()

    def _checkout(self):
        if not self.cart:
            messagebox.showinfo("Корзина пуста", "Добавьте лекарства перед оформлением заказа.")
            return

        rx_names = []
        for name, price, qty, subtotal in self.cart:
            for m in self.db.list_medicines():
                if m[0] == name and m[4]:
                    rx_names.append(name)

        if rx_names:
            confirm = messagebox.askyesno(
                "Требуется рецепт",
                "В корзине есть рецептурные препараты:\n"
                + "\n".join("- " + n for n in rx_names)
                + "\n\nПодтверждаете наличие рецепта?"
            )
            if not confirm:
                return

        total = round(sum(item[3] for item in self.cart), 2)
        if not messagebox.askyesno("Подтверждение", "Оформить заказ на %.2f ₽?" % total):
            return

        order_id, date_str, total = self.db.create_order(self.login, self.cart)
        self.cart = []
        self._refresh_cart()
        self._refresh_catalog()
        self._refresh_orders()
        messagebox.showinfo("Готово", "Заказ №%d оформлен на сумму %.2f ₽!" % (order_id, total))


# ---------------------------------------------------------------------------
# Сотрудник.cs -> EmployeeWindow (управление товаром)
# ---------------------------------------------------------------------------

class EmployeeWindow(tk.Tk):
    def __init__(self, db, login):
        tk.Tk.__init__(self)
        self.db = db
        self.login = login

        self.title("Аптека «Здоровье+» — Сотрудник: %s" % login)
        self.geometry("900x560")
        self.minsize(800, 480)
        apply_style(self)

        ttk.Label(self, text="Управление товаром", style="Header.TLabel").pack(pady=(10, 6))

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(main, width=300)
        right.pack(side="right", fill="y", padx=(10, 0))
        right.pack_propagate(False)

        columns = ("name", "category", "price", "qty", "rx")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        headings = {"name": "Название", "category": "Категория", "price": "Цена, ₽",
                    "qty": "Кол-во", "rx": "Рецепт"}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=150, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        ttk.Button(left, text="Обновить список", command=self._refresh).pack(
            fill="x", pady=(6, 0))
        ttk.Button(left, text="Удалить выбранное", command=self._delete_selected).pack(
            fill="x", pady=(4, 0))

        ttk.Label(right, text="Добавить / пополнить товар",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 8))

        self.name_var = tk.StringVar()
        self.category_var = tk.StringVar()
        self.price_var = tk.StringVar()
        self.qty_var = tk.StringVar()
        self.rx_var = tk.BooleanVar(value=False)
        self.desc_var = tk.StringVar()

        form = ttk.Frame(right)
        form.pack(fill="x")
        self._field(form, "Название:", self.name_var, 0)
        self._field(form, "Категория:", self.category_var, 1)
        self._field(form, "Цена, ₽:", self.price_var, 2)
        self._field(form, "Кол-во:", self.qty_var, 3)

        ttk.Checkbutton(right, text="Требуется рецепт", variable=self.rx_var).pack(
            anchor="w", pady=(6, 0))

        ttk.Label(right, text="Описание:").pack(anchor="w", pady=(8, 0))
        ttk.Entry(right, textvariable=self.desc_var, width=30).pack(fill="x")

        self.restock_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text="Пополнить остаток (иначе — задать заново)",
                         variable=self.restock_var).pack(anchor="w", pady=(8, 0))

        ttk.Button(right, text="Сохранить", command=self._save).pack(fill="x", pady=(14, 0))
        ttk.Button(right, text="Очистить форму", command=self._clear_form).pack(
            fill="x", pady=(6, 0))

        self._refresh()

    def _field(self, parent, label, var, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=var, width=22).grid(row=row, column=1, pady=4)

    def _refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for name, category, price, qty, rx, desc in self.db.list_medicines():
            self.tree.insert("", "end", values=(
                name, category, "%.2f" % price, qty, "да" if rx else ""))

    def _on_select(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return
        values = self.tree.item(selection[0], "values")
        self.name_var.set(values[0])
        self.category_var.set(values[1])
        self.price_var.set(values[2])
        self.qty_var.set("0")
        self.rx_var.set(values[4] == "да")

    def _clear_form(self):
        self.name_var.set("")
        self.category_var.set("")
        self.price_var.set("")
        self.qty_var.set("")
        self.rx_var.set(False)
        self.desc_var.set("")

    def _save(self):
        name = self.name_var.get().strip()
        category = self.category_var.get().strip()
        if not name or not category:
            messagebox.showerror("Ошибка", "Заполните название и категорию.")
            return
        try:
            price = float(self.price_var.get())
            qty = int(self.qty_var.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Цена и количество должны быть числами.")
            return
        if price <= 0:
            messagebox.showerror("Ошибка", "Цена должна быть больше нуля.")
            return

        self.db.add_or_update_medicine(
            name, category, price, qty, self.rx_var.get(),
            self.desc_var.get().strip(), self.restock_var.get()
        )
        self._refresh()
        messagebox.showinfo("Готово", "«%s» сохранён(а)." % name)
        self._clear_form()

    def _delete_selected(self):
        selection = self.tree.selection()
        if not selection:
            return
        name = self.tree.item(selection[0], "values")[0]
        if messagebox.askyesno("Удаление", "Удалить «%s» из каталога?" % name):
            self.db.delete_medicine(name)
            self._refresh()


# ---------------------------------------------------------------------------
# Адмистратор.cs -> AdminWindow (управление аккаунтами и ролями)
# ---------------------------------------------------------------------------

class AdminWindow(tk.Tk):
    def __init__(self, db, login):
        tk.Tk.__init__(self)
        self.db = db
        self.login = login

        self.title("Аптека «Здоровье+» — Администратор: %s" % login)
        self.geometry("760x520")
        self.minsize(680, 440)
        apply_style(self)

        ttk.Label(self, text="Управление аккаунтами", style="Header.TLabel").pack(pady=(10, 6))

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        columns = ("login", "phone", "role")
        self.tree = ttk.Treeview(main, columns=columns, show="headings", selectmode="browse")
        headings = {"login": "Логин", "phone": "Телефон", "role": "Роль"}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=200, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        bottom = ttk.Frame(main)
        bottom.pack(fill="x", pady=(10, 0))

        ttk.Label(bottom, text="Новая роль:").pack(side="left")
        self.role_var = tk.StringVar(value=ROLE_CLIENT)
        role_combo = ttk.Combobox(bottom, textvariable=self.role_var,
                                   values=ALL_ROLES, state="readonly", width=16)
        role_combo.pack(side="left", padx=(4, 12))

        ttk.Button(bottom, text="Изменить роль", command=self._change_role).pack(
            side="left", padx=4)
        ttk.Button(bottom, text="Удалить аккаунт", command=self._delete_account).pack(
            side="left", padx=4)
        ttk.Button(bottom, text="Обновить", command=self._refresh).pack(side="right")

        self._refresh()

    def _refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for login, phone, role in self.db.list_accounts():
            self.tree.insert("", "end", iid=login, values=(login, phone or "", role))

    def _on_select(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return
        values = self.tree.item(selection[0], "values")
        self.role_var.set(values[2])

    def _selected_login(self):
        selection = self.tree.selection()
        return selection[0] if selection else None

    def _change_role(self):
        login = self._selected_login()
        if not login:
            messagebox.showinfo("Выбор", "Сначала выберите аккаунт в списке.")
            return
        if login == self.login and self.role_var.get() != ROLE_ADMIN:
            if not messagebox.askyesno(
                "Внимание",
                "Вы меняете роль своего собственного аккаунта и можете "
                "потерять доступ к админ-панели. Продолжить?"
            ):
                return
        self.db.update_role(login, self.role_var.get())
        self._refresh()
        messagebox.showinfo("Готово", "Роль пользователя «%s» изменена." % login)

    def _delete_account(self):
        login = self._selected_login()
        if not login:
            messagebox.showinfo("Выбор", "Сначала выберите аккаунт в списке.")
            return
        if login == self.login:
            messagebox.showerror("Ошибка", "Нельзя удалить собственный аккаунт.")
            return
        if messagebox.askyesno("Удаление", "Удалить аккаунт «%s»?" % login):
            self.db.delete_account(login)
            self._refresh()


# ---------------------------------------------------------------------------
# Директор.cs -> DirectorWindow (заказы, статусы, отчёты)
# ---------------------------------------------------------------------------

class DirectorWindow(tk.Tk):
    def __init__(self, db, login):
        tk.Tk.__init__(self)
        self.db = db
        self.login = login

        self.title("Аптека «Здоровье+» — Директор: %s" % login)
        self.geometry("980x600")
        self.minsize(860, 520)
        apply_style(self)

        ttk.Label(self, text="Обзор заказов и отчётность",
                  style="Header.TLabel").pack(pady=(10, 6))

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(main, width=320)
        right.pack(side="right", fill="y", padx=(10, 0))
        right.pack_propagate(False)

        columns = ("order_id", "client", "date", "status", "total")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        headings = {"order_id": "№", "client": "Клиент", "date": "Дата",
                    "status": "Статус", "total": "Сумма, ₽"}
        widths = {"order_id": 50, "client": 130, "date": 150, "status": 120, "total": 100}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._show_items())

        status_row = ttk.Frame(left)
        status_row.pack(fill="x", pady=(8, 0))
        ttk.Label(status_row, text="Новый статус:").pack(side="left")
        self.status_var = tk.StringVar(value=ORDER_STATUSES[0])
        ttk.Combobox(status_row, textvariable=self.status_var, values=ORDER_STATUSES,
                     state="readonly", width=16).pack(side="left", padx=(4, 12))
        ttk.Button(status_row, text="Обновить статус",
                   command=self._update_status).pack(side="left")
        ttk.Button(status_row, text="Обновить список",
                   command=self._refresh).pack(side="right")

        ttk.Label(right, text="Состав заказа", style="Header.TLabel").pack(anchor="w")
        self.items_list = tk.Listbox(right, height=14, font=("Segoe UI", 10))
        self.items_list.pack(fill="both", expand=True, pady=(6, 10))

        self.revenue_var = tk.StringVar()
        ttk.Label(right, textvariable=self.revenue_var,
                  font=("Segoe UI", 12, "bold")).pack(pady=(0, 10))

        ttk.Button(right, text="Сформировать отчёт",
                   command=self._generate_report).pack(fill="x")

        self._refresh()

    def _refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for order_id, client_login, date, status, total in self.db.list_orders():
            self.tree.insert("", "end", iid=str(order_id),
                              values=(order_id, client_login, date, status, "%.2f" % total))
        self.revenue_var.set("Общая выручка: %.2f ₽" % self.db.total_revenue())
        self.items_list.delete(0, tk.END)

    def _show_items(self):
        selection = self.tree.selection()
        self.items_list.delete(0, tk.END)
        if not selection:
            return
        order_id = int(selection[0])
        for name, price, qty, subtotal in self.db.order_items(order_id):
            self.items_list.insert(tk.END, "%s x%d = %.2f ₽" % (name, qty, subtotal))

    def _update_status(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Выбор", "Сначала выберите заказ в списке.")
            return
        order_id = int(selection[0])
        self.db.update_order_status(order_id, self.status_var.get())
        self._refresh()

    def _generate_report(self):
        if not os.path.exists(REPORTS_DIR):
            os.makedirs(REPORTS_DIR)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(REPORTS_DIR, "Отчет_заказов_%s.txt" % timestamp)

        orders = self.db.list_orders()
        lines = []
        lines.append("ОТЧЁТ ПО ЗАКАЗАМ — Аптека «Здоровье+»")
        lines.append("Сформирован: %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        lines.append("Директор: %s" % self.login)
        lines.append("=" * 60)
        lines.append("")

        if not orders:
            lines.append("Заказов пока нет.")
        else:
            for order_id, client_login, date, status, total in orders:
                lines.append("Заказ №%d | Клиент: %s | Дата: %s | Статус: %s | Сумма: %.2f ₽" % (
                    order_id, client_login, date, status, total))
                for name, price, qty, subtotal in self.db.order_items(order_id):
                    lines.append("    - %s x%d = %.2f ₽" % (name, qty, subtotal))
                lines.append("")

        lines.append("=" * 60)
        lines.append("Всего заказов: %d" % len(orders))
        lines.append("Общая выручка (без отменённых): %.2f ₽" % self.db.total_revenue())

        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        messagebox.showinfo("Готово", "Отчёт сохранён:\n%s" % filename)


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def main():
    db = Database()

    login_window = LoginWindow(db)
    login_window.mainloop()

    if login_window.result_role is None:
        return  # окно входа закрыли без авторизации

    role = login_window.result_role
    login = login_window.result_login

    if role == ROLE_CLIENT:
        app = ClientWindow(db, login)
    elif role == ROLE_EMPLOYEE:
        app = EmployeeWindow(db, login)
    elif role == ROLE_ADMIN:
        app = AdminWindow(db, login)
    elif role == ROLE_DIRECTOR:
        app = DirectorWindow(db, login)
    else:
        messagebox.showerror("Ошибка", "Неизвестная роль: %s" % role)
        return

    app.mainloop()


if __name__ == "__main__":
    main()
