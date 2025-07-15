import sqlite3
import random
import os
import struct
import numpy as np

DB_NAME = "debug.db"

if os.path.exists(DB_NAME):
    os.remove(DB_NAME)
    print(f"Old database '{DB_NAME}' removed.")

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

# ИЗМЕНЕНИЕ 1: Заранее определенные, фиксированные размерности для каждого слоя
# Чтобы продемонстрировать все размерности от 1 до 5
layer_shapes = {
    'Input Layer': (10,),                                  # 1D
    'Embedding Layer': (10, 16),                           # 2D
    'Attention Layer': (4, 10, 16),                        # 3D
    'Conv Layer': (1, 3, 32, 32),                          # 4D
    'Video Conv Layer': (1, 3, 16, 32, 32),                # 5D
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
    print(f"Generating data for Record #{record_id}...")
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
        
        # ИЗМЕНЕНИЕ 2: Для RecordID=3 делаем размерность немного другой
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
        
        # ИЗМЕНЕНИЕ 3: Генерируем разные данные для разных RecordID
        blob_data = generate_tensor_data(current_shape, record_id)

        tensor_name = f"{layer_name.replace(' ', '_')}_output"
        
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

print(f"\nDatabase '{DB_NAME}' has been successfully created with structured tensor data.")
print("Tensors for Record #1 and #2 are compatible.")
print("Tensors for Record #3 have different shapes.")
print("You can now run the main application file.")