# =====================================================================================
#  Вкладка для анализа тензоров с древовидным выбором
# =====================================================================================
class TensorTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)

        self.tensor_map = {}

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 20))
        
        load_button = ttk.Button(control_frame, text="Load Tensors from DB", command=self._load_tensors_metadata)
        load_button.pack(side=tk.LEFT)

        selection_frame = ttk.LabelFrame(main_frame, text="Tensor Selection", padding="10")
        selection_frame.pack(fill=tk.X)

        # --- ИЗМЕНЕНИЕ: Заменяем Combobox на Treeview ---
        
        # --- Строка 1: Дерево для выбора первого тензора ---
        row1_frame = ttk.Frame(selection_frame)
        row1_frame.pack(fill=tk.X, expand=True, pady=2)
        
        ttk.Label(row1_frame, text="1. Select First Tensor:").pack(side=tk.LEFT, padx=5, anchor='n')
        
        # Создаем контейнер для дерева и скроллбара
        tree_container = ttk.Frame(row1_frame)
        tree_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.tensor_tree = ttk.Treeview(tree_container, selectmode="browse")
        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tensor_tree.yview)
        self.tensor_tree.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tensor_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.tensor_tree.bind("<<TreeviewSelect>>", self._on_first_tensor_select)

        # --- Строка 2: Combobox для второго тензора (без изменений) ---
        row2_frame = ttk.Frame(selection_frame)
        row2_frame.pack(fill=tk.X, expand=True, pady=2)

        ttk.Label(row2_frame, text="2. Select Second Tensor (for comparison):").pack(side=tk.LEFT, padx=5)
        self.second_tensor_combo = ttk.Combobox(row2_frame, state="disabled", width=50)
        self.second_tensor_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.second_tensor_combo.bind("<<ComboboxSelected>>", self._on_second_tensor_select)
        
        result_frame = ttk.LabelFrame(main_frame, text="Resulting Difference Tensor", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

        self.tensor_viewer = TensorViewer(result_frame)

    def _load_tensors_metadata(self):
        try:
            conn = sqlite3.connect('debug.db')
            cursor = conn.cursor()
            query = """
                SELECT T.Name, N.RecordID, T.ID as TensorID, T.Datatype, T.NumDims,
                       T.Shape0, T.Shape1, T.Shape2, T.Shape3, T.Shape4
                FROM Tensors T
                JOIN TensorMap TM ON T.ID = TM.TensorID
                JOIN Nodes N ON TM.NodeID = N.id
                WHERE T.Name IS NOT NULL AND T.Name != ''
                ORDER BY T.Name, N.RecordID
            """
            cursor.execute(query)
            tensor_metadata = cursor.fetchall()
            conn.close()
        except sqlite3.OperationalError as e:
            messagebox.showerror("Database Error", f"Could not read tensor metadata from 'debug.db'.\nError: {e}")
            return

        if not tensor_metadata:
            messagebox.showinfo("No Data", "No tensors found in the database.")
            return

        self.tensor_map.clear()
        display_names = []
        for row in tensor_metadata:
            display_name = f"{row[0]} (Record: {row[1]})"
            display_names.append(display_name)
            self.tensor_map[display_name] = {
                "name": row[0], "record_id": row[1], "tensor_id": row[2],
                "datatype": row[3], "dims": row[4], 
                "shape": tuple(s for s in row[5:10] if s > 0)
            }
        
        # --- ИЗМЕНЕНИЕ: Логика заполнения Treeview ---
        self._populate_tensor_tree(display_names)
        
        self.second_tensor_combo.set('')
        self.second_tensor_combo['values'] = []
        self.second_tensor_combo.config(state="disabled")
        self.tensor_viewer.set_tensor(None)
        messagebox.showinfo("Success", f"{len(display_names)} tensor metadata entries loaded successfully.")

    def _populate_tensor_tree(self, display_names):
        """Очищает и заполняет Treeview иерархическими данными."""
        # Очищаем старое дерево
        self.tensor_tree.delete(*self.tensor_tree.get_children())
        
        # Словарь для отслеживания уже созданных родительских узлов (веток)
        # Ключ: путь (e.g., "add.rec1"), Значение: ID узла в Treeview
        nodes = {}

        for full_name in sorted(display_names):
            base_name = full_name.split(' (Record:')[0]
            parts = base_name.split('.')
            
            parent_iid = '' # Начинаем с корня дерева
            current_path = ''

            # Создаем родительские узлы (ветки)
            for i, part in enumerate(parts):
                if i > 0:
                    current_path += '.'
                current_path += part
                
                if current_path not in nodes:
                    # Если узел еще не создан, создаем его
                    iid = self.tensor_tree.insert(parent_iid, 'end', text=part, open=False)
                    nodes[current_path] = iid
                
                parent_iid = nodes[current_path]

            # Добавляем конечный узел (лист) с полным именем
            # Используем полное имя как ID для легкого доступа
            self.tensor_tree.insert(parent_iid, 'end', iid=full_name, text=full_name)

    def _on_first_tensor_select(self, event=None):
        """Обрабатывает выбор элемента в Treeview."""
        selection = self.tensor_tree.selection()
        if not selection:
            return
        
        selected_iid = selection[0]
        
        # --- ИЗМЕНЕНИЕ: Проверяем, является ли выбранный элемент листом ---
        # Листья мы пометили их полным именем, которое содержит "(Record:"
        if "(Record:" not in selected_iid:
            # Это родительский узел (ветка), ничего не делаем
            self.second_tensor_combo.set('')
            self.second_tensor_combo.config(state="disabled")
            return

        selected_display_name = selected_iid
        base_name = self.tensor_map[selected_display_name]["name"]
        compatible_tensors = [dn for dn, info in self.tensor_map.items() if info["name"] == base_name]
        
        self.second_tensor_combo['values'] = compatible_tensors
        self.second_tensor_combo.config(state="readonly")
        self.second_tensor_combo.set('')
        self.tensor_viewer.set_tensor(None)

    def _on_second_tensor_select(self, event=None):
        # Получаем выбор из дерева, а не из старого комбобокса
        selection = self.tensor_tree.selection()
        if not selection: return
        tensor1_name = selection[0]
        
        tensor2_name = self.second_tensor_combo.get()
        if not tensor1_name or not tensor2_name: return
        self._calculate_and_display_diff(tensor1_name, tensor2_name)

    def _fetch_blob_by_id(self, tensor_id):
        try:
            conn = sqlite3.connect('debug.db')
            cursor = conn.cursor()
            cursor.execute("SELECT Data FROM Tensors WHERE ID = ?", (tensor_id,))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except sqlite3.OperationalError as e:
            messagebox.showerror("Database Error", f"Failed to fetch BLOB for TensorID {tensor_id}.\nError: {e}")
            return None

    def _get_tensor_as_numpy(self, name):
        info = self.tensor_map[name]
        blob = self._fetch_blob_by_id(info['tensor_id'])
        if blob is None: return None
        shape = info['shape']
        dtype = np.float32 if info['datatype'] == 0 else np.int32
        try:
            return np.frombuffer(blob, dtype=dtype).reshape(shape)
        except Exception as e:
            messagebox.showerror("Tensor Conversion Error", f"Failed to convert tensor '{name}'.\nError: {e}")
            return None

    def _calculate_and_display_diff(self, name1, name2):
        tensor1 = self._get_tensor_as_numpy(name1)
        tensor2 = self._get_tensor_as_numpy(name2)
        if tensor1 is None or tensor2 is None:
            self.tensor_viewer.set_tensor(None)
            return
        if tensor1.shape != tensor2.shape:
            messagebox.showerror("Shape Mismatch", f"Tensors have incompatible shapes.\n{name1}: {tensor1.shape}\n{name2}: {tensor2.shape}")
            self.tensor_viewer.set_tensor(None)
            return
        diff_tensor = np.abs(tensor1 - tensor2)
        self.tensor_viewer.set_tensor(diff_tensor)