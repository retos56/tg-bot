import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bookings.db")

def init_db():
    """Инициализация базы данных и создание таблицы"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            name TEXT,
            event TEXT,
            date TEXT,
            days_count INTEGER,
            guests_count TEXT,
            extra_info TEXT,
            phone TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_booking(user_id, username, name, event, date, days_count, guests_count, extra_info, phone):
    """Добавление новой записи в БД"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO bookings (user_id, username, name, event, date, days_count, guests_count, extra_info, phone)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, name, event, date, days_count, guests_count, extra_info, phone))
    conn.commit()
    conn.close()

def get_all_bookings():
    """Получение всех записей из БД"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM bookings')
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_booking(booking_id):
    """Удаление записи по ID"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM bookings WHERE id = ?', (booking_id,))
    conn.commit()
    changes = conn.total_changes
    conn.close()
    return changes > 0

def is_date_occupied(check_date_str):
    """Проверяет, перекрывает ли конкретная дата какую-либо забронированную запись"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT date, days_count FROM bookings')
    rows = cursor.fetchall()
    conn.close()

    target_date = datetime.strptime(check_date_str, "%d.%m.%Y").date()

    for start_date_str, days in rows:
        try:
            start_date = datetime.strptime(start_date_str, "%d.%m.%Y").date()
            days = days if days else 1
            end_date = start_date + timedelta(days=days - 1)

            if start_date <= target_date <= end_date:
                return True
        except ValueError:
            continue

    return False

def check_date_range_availability(start_date_str, days_count):
    """Проверяет, свободен ли весь диапазон дат"""
    start_date = datetime.strptime(start_date_str, "%d.%m.%Y").date()
    for i in range(days_count):
        current_date = start_date + timedelta(days=i)
        current_date_str = current_date.strftime("%d.%m.%Y")
        if is_date_occupied(current_date_str):
            return False, current_date_str
    return True, None

def find_next_available_start_date(start_from_date_str, days_count):
    """Ищет ближайшую свободную дату старта для указанного количества дней"""
    curr_date = datetime.strptime(start_from_date_str, "%d.%m.%Y").date() + timedelta(days=1)
    
    # Ищем свободное окно в пределах года вперед
    for _ in range(365):
        curr_str = curr_date.strftime("%d.%m.%Y")
        is_free, _ = check_date_range_availability(curr_str, days_count)
        if is_free:
            return curr_str
        curr_date += timedelta(days=1)
        
    return None