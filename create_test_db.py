import sqlite3
import random
import os
import struct
import numpy as np

DB_NAME = "debug.db"

if os.path.exists(DB_NAME):
    os.remove(DB_NAME)
    print(f"Старая база данных '{DB_NAME}' удалена.")

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# --- Создание таблиц ---
cursor.execute('''
CREATE TABLE IF NOT EXISTS Nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, RecordID INTEGER, SeqNum INTEGER,
    Name TEXT, Start REAL, End REAL
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS Tensors (
    ID INTEGER PRIMARY KEY AUTOINCREMENT, Datatype INTEGER, Format INTEGER, NumDims INTEGER,
    Shape0 INTEGER, Shape1 INTEGER, Shape2 INTEGER, Shape3 INTEGER, Shape4 INTEGER,
    ElementsSize INTEGER, Data BLOB, DataSizeBytes INTEGER, Name TEXT
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS TensorMap (
    id INTEGER PRIMARY KEY AUTOINCREMENT, NodeID INTEGER, TensorID INTEGER,
    IOType INTEGER, IOidx INTEGER,
    FOREIGN KEY(NodeID) REFERENCES Nodes(id), FOREIGN KEY(TensorID) REFERENCES Tensors(ID)
)''')

# --- Генерация тестовых данных ---

# ИЗМЕНЕНИЕ 1: Добавляем разные типы 2D тензоров с запоминающимися именами
layer_shapes = {
    'Слой с 1D тензором': (10,),                                      # 1D
    'Слой с широким тензором (горизонтальный)': (8, 32),               # 2D (ширина > высота)
    'Слой с высоким тензором (вертикальный)': (32, 8),                # 2D (высота > ширина)
    'Слой с квадратным тензором': (16, 16),                           # 2D (высота == ширина)
    'Слой с 3D тензором': (4, 10, 16),                                # 3D
    'Слой с 4D тензором (картинка)': (10, 3, 32, 32),                   # 4D
    'Слой с 5D тензором (видео)': (10, 3, 16, 32, 32),                  # 5D
}
layers = list(layer_shapes.keys())

def generate_tensor_data(shape, record_id):
    """Генерирует данные для тензора в зависимости от RecordID."""
    size = np.prod(shape)
    if record_id == 1:
        # Данные на основе синуса
        arr = np.sin(np.arange(size) * 0.1).astype(np.float32)
    elif record_id == 2:
        # Данные на основе косинуса (чтобы разница была ненулевой)
        arr = np.cos(np.arange(size) * 0.1).astype(np.float32)
    else: # record_id == 3
        # Случайные данные
        arr = np.random.rand(size).astype(np.float32)
    return arr.tobytes()

records_to_generate = 3

for record_id in range(1, records_to_generate + 1):
    print(f"Генерация данных для Записи #{record_id}...")
    current_time = 0.0
    for i, layer_name in enumerate(layers):
        # --- Генерация данных для Nodes ---
        start_time = current_time + random.uniform(0.05, 0.3)
        duration = random.uniform(0.4, 1.8)
        end_time = start_time + duration
        
        cursor.execute(
            "INSERT INTO Nodes (RecordID, SeqNum, Name, Start, End) VALUES (?, ?, ?, ?, ?)",
            (record_id, i, layer_name, start_time, end_time)
        )
        current_node_id = cursor.lastrowid
        current_time = end_time

        # --- Генерация данных для Tensors ---
        base_shape = layer_shapes[layer_name]
        
        # Для RecordID=3 делаем размерность немного другой
        if record_id == 3:
            # Превращаем кортеж в список, изменяем, и обратно в кортеж
            shape_list = list(base_shape)
            shape_list[-1] += random.randint(1, 5) # Меняем последнее измерение
            current_shape = tuple(shape_list)
        else:
            current_shape = base_shape

        num_dims = len(current_shape)
        
        # Заполняем shape до 5 элементов нулями для записи в БД
        db_shape = list(current_shape) + [0] * (5 - num_dims)
        
        element_size = 4 # float32
        data_size_bytes = np.prod(current_shape) * element_size
        
        # Генерируем разные данные для разных RecordID
        blob_data = generate_tensor_data(current_shape, record_id)

        # ИЗМЕНЕНИЕ 2: Имя тензора теперь будет очень описательным благодаря имени слоя
        tensor_name = f"{layer_name.replace(' ', '_').replace('(', '').replace(')', '')}_output"
        
        cursor.execute(
            """INSERT INTO Tensors 
               (Datatype, Format, NumDims, Shape0, Shape1, Shape2, Shape3, Shape4, ElementsSize, Data, DataSizeBytes, Name) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (0, -1, num_dims, *db_shape, element_size, blob_data, data_size_bytes, tensor_name)
        )
        current_tensor_id = cursor.lastrowid

        # --- Связываем их в TensorMap ---
        cursor.execute(
            "INSERT INTO TensorMap (NodeID, TensorID, IOType, IOidx) VALUES (?, ?, ?, ?)",
            (current_node_id, current_tensor_id, 1, 0)
        )

conn.commit()
conn.close()

print(f"\nБаза данных '{DB_NAME}' успешно создана со структурированными данными.")
print("Теперь генерируются горизонтальные, вертикальные и квадратные 2D тензоры.")
print("Тензоры для Записи #1 и #2 совместимы.")
print("Тензоры для Записи #3 имеют немного другие размерности.")
print("Можно запускать основной файл приложения.")