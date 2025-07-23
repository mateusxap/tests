import sqlite3
import random
import os
import struct
import numpy as np

DB_NAME = "debug.db"

if os.path.exists(DB_NAME):
    os.remove(DB_NAME)
    print(f"Old database '{DB_NAME}' deleted.")

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# --- Table Creation ---
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

# --- Test Data Generation ---

# CHANGE 1: Add different types of 2D tensors with memorable names
layer_shapes = {
    'Layer_with_1D_tensor': (10,),                                  # 1D
    'Layer_with_wide_tensor_horizontal': (8, 32),                   # 2D (width > height)
    'Layer_with_tall_tensor_vertical': (32, 8),                     # 2D (height > width)
    'Layer_with_square_tensor': (16, 16),                           # 2D (height == width)
    'Layer_with_3D_tensor': (4, 10, 16),                            # 3D
    'Layer_with_4D_tensor_image': (10, 3, 32, 32),                  # 4D
    'Layer_with_5D_tensor_video': (10, 3, 16, 32, 32),              # 5D
}
layers = list(layer_shapes.keys())

def generate_tensor_data(shape, record_id):
    """Generates tensor data based on the RecordID."""
    size = np.prod(shape)
    if record_id == 1:
        # Sine-based data
        arr = np.sin(np.arange(size) * 0.1).astype(np.float32)
    elif record_id == 2:
        # Cosine-based data (to ensure the difference is non-zero)
        arr = np.cos(np.arange(size) * 0.1).astype(np.float32)
    else: # record_id == 3
        # Random data
        arr = np.random.rand(size).astype(np.float32)
    return arr.tobytes()

records_to_generate = 3

for record_id in range(1, records_to_generate + 1):
    print(f"Generating data for Record #{record_id}...")
    current_time = 0.0
    for i, layer_name in enumerate(layers):
        # --- Generate data for Nodes ---
        start_time = current_time + random.uniform(0.05, 0.3)
        duration = random.uniform(0.4, 1.8)
        end_time = start_time + duration
        
        cursor.execute(
            "INSERT INTO Nodes (RecordID, SeqNum, Name, Start, End) VALUES (?, ?, ?, ?, ?)",
            (record_id, i, layer_name, start_time, end_time)
        )
        current_node_id = cursor.lastrowid
        current_time = end_time

        # --- Generate data for Tensors ---
        base_shape = layer_shapes[layer_name]
        
        # For RecordID=3, make the dimensions slightly different
        if record_id == 3:
            # Convert tuple to list, modify it, and convert back to tuple
            shape_list = list(base_shape)
            shape_list[-1] += random.randint(1, 5) # Change the last dimension
            current_shape = tuple(shape_list)
        else:
            current_shape = base_shape

        num_dims = len(current_shape)
        
        # Pad the shape with zeros up to 5 elements for DB insertion
        db_shape = list(current_shape) + [0] * (5 - num_dims)
        
        element_size = 4 # float32
        data_size_bytes = np.prod(current_shape) * element_size
        
        # Generate different data for different RecordIDs
        blob_data = generate_tensor_data(current_shape, record_id)

        # CHANGE 2: The tensor name will now be very descriptive thanks to the layer name
        tensor_name = f"{layer_name}_output"
        
        cursor.execute(
            """INSERT INTO Tensors 
               (Datatype, Format, NumDims, Shape0, Shape1, Shape2, Shape3, Shape4, ElementsSize, Data, DataSizeBytes, Name) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (0, -1, num_dims, *db_shape, element_size, blob_data, data_size_bytes, tensor_name)
        )
        current_tensor_id = cursor.lastrowid

        # --- Link them in TensorMap ---
        cursor.execute(
            "INSERT INTO TensorMap (NodeID, TensorID, IOType, IOidx) VALUES (?, ?, ?, ?)",
            (current_node_id, current_tensor_id, 1, 0)
        )

conn.commit()
conn.close()

print(f"\nDatabase '{DB_NAME}' successfully created with structured data.")
print("Horizontal, vertical, and square 2D tensors are now being generated.")
print("Tensors for Record #1 and #2 are compatible.")
print("Tensors for Record #3 have slightly different dimensions.")
print("The main application file can now be run.")