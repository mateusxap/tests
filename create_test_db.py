import sqlite3
import random
import os

DB_NAME = "debug.db"

# Удаляем старую БД, если она существует, для чистоты эксперимента
if os.path.exists(DB_NAME):
    os.remove(DB_NAME)

# Подключаемся к БД (она будет создана)
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# Создаем таблицу Nodes
cursor.execute('''
CREATE TABLE IF NOT EXISTS Nodes (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Record INTEGER,
    SeqNum INTEGER,
    Name TEXT,
    Start REAL,
    End REAL
)
''')

# --- Генерируем тестовые данные ---
layers = ['Загрузка данных', 'Предобработка', 'Слой свертки 1', 'Слой пулинга 1', 'Слой свертки 2', 'Полносвязный слой']
records_to_generate = 2  # Сгенерируем данные для двух "проходок" (Record 1 и 2)

current_time = 0.0
seq_num_counter = 0

for record_id in range(1, records_to_generate + 1):
    print(f"Генерация данных для Записи (Record) #{record_id}...")
    current_time = 0.0 # Сбрасываем время для каждой новой записи
    for i, layer_name in enumerate(layers):
        seq_num_counter += 1
        start_time = current_time + random.uniform(0.05, 0.2) # Небольшая пауза между слоями
        duration = random.uniform(0.5, 2.0) # Длительность работы слоя
        end_time = start_time + duration
        
        cursor.execute(
            "INSERT INTO Nodes (Record, SeqNum, Name, Start, End) VALUES (?, ?, ?, ?, ?)",
            (record_id, i, layer_name, start_time, end_time)
        )
        
        current_time = end_time

# Сохраняем изменения и закрываем соединение
conn.commit()
conn.close()

print(f"\nБаза данных '{DB_NAME}' успешно создана и заполнена тестовыми данными.")
print("Теперь вы можете запустить основной файл приложения: gantt_chart_app.py")