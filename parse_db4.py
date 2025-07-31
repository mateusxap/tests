import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from collections import defaultdict

# --- НОВЫЕ ИМПОРТЫ ДЛЯ ВИЗУАЛИЗАЦИИ ---
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from skimage.measure import block_reduce # Для max-пулингаА
# =====================================================================================
#  ФИНАЛЬНАЯ ВЕРСИЯ с обработкой 0D и 1D тензоров
# =====================================================================================
class TensorViewer(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)

        self.tensor = None
        self.current_slice = None
        self.dim_labels = []
        self.is_reshaped = False
        
        self.slice_sliders = {}
        
        self.x_axis_var = tk.StringVar()
        self.y_axis_var = tk.StringVar()
        self._prev_x_axis = ""
        self._prev_y_axis = ""

        # --- UI Элементы ---
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        self.ax.format_coord = self._format_coord

        toolbar_frame = ttk.Frame(self)
        toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # --- ИЗМЕНЕНИЕ 1: Сохраняем тулбар как атрибут класса ---
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()

        controls_area = ttk.Frame(self)
        controls_area.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        axis_selection_frame = ttk.Frame(controls_area)
        axis_selection_frame.pack(pady=5)
        
        ttk.Label(axis_selection_frame, text="Y-Axis:").pack(side=tk.LEFT, padx=(0, 5))
        self.y_axis_combo = ttk.Combobox(axis_selection_frame, textvariable=self.y_axis_var, state='disabled', width=12)
        self.y_axis_combo.pack(side=tk.LEFT)
        
        ttk.Label(axis_selection_frame, text="X-Axis:").pack(side=tk.LEFT, padx=(10, 5))
        self.x_axis_combo = ttk.Combobox(axis_selection_frame, textvariable=self.x_axis_var, state='disabled', width=12)
        self.x_axis_combo.pack(side=tk.LEFT)

        self.y_axis_combo.bind("<<ComboboxSelected>>", self._on_axis_selection_change)
        self.x_axis_combo.bind("<<ComboboxSelected>>", self._on_axis_selection_change)

        reset_button = ttk.Button(controls_area, text="Reset View", command=self._reset_view)
        reset_button.pack(pady=5)

        self.sliders_frame = ttk.Frame(controls_area)
        self.sliders_frame.pack(fill=tk.X, expand=True)

        self._create_sliders_placeholders()

        self.canvas.mpl_connect('scroll_event', self._on_zoom)

    def _format_coord(self, x, y):
        if self.current_slice is None: return ""
        col, row = int(round(x)), int(round(y))
        h, w = self.current_slice.shape
        if 0 <= col < w and 0 <= row < h:
            value = self.current_slice[row, col]
            return f'x={col}, y={row}  value={value:.4f}'
        else:
            return f'x={col}, y={row}'

    def _get_dim_labels(self, ndim):
        if ndim == 1: return ('W',)
        if ndim == 2: return ('H', 'W')
        if ndim == 3: return ('C', 'H', 'W')
        if ndim == 4: return ('N', 'C', 'H', 'W')
        if ndim == 5: return ('N', 'C', 'D', 'H', 'W')
        return tuple(f"Dim {i}" for i in range(ndim))

    def _create_sliders_placeholders(self):
        max_sliders = 5 
        for i in range(max_sliders):
            frame = ttk.Frame(self.sliders_frame)
            var = tk.IntVar(value=0)
            label = ttk.Label(frame, text=f"Dim {i}:")
            scale = tk.Scale(frame, from_=0, to=0, orient=tk.HORIZONTAL, resolution=1, variable=var, command=self._on_slider_change)
            value_label = ttk.Label(frame, textvariable=var, width=4)
            label.pack(side=tk.LEFT)
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            value_label.pack(side=tk.LEFT)
            self.slice_sliders[i] = {'frame': frame, 'var': var, 'scale': scale, 'label': label}
            frame.pack_forget()

    def set_tensor(self, tensor_data):
        self.tensor = tensor_data
        self.is_reshaped = False
        if self.tensor is None:
            self.x_axis_combo.config(state='disabled', values=[])
            self.y_axis_combo.config(state='disabled', values=[])
            self.x_axis_var.set('')
            self.y_axis_var.set('')
            self.dim_labels = []
        else:
            if self.tensor.ndim == 0:
                self.tensor = self.tensor.reshape(1, 1)
                self.is_reshaped = True
            elif self.tensor.ndim == 1:
                self.tensor = self.tensor.reshape(1, -1)
                self.is_reshaped = True
            ndim = self.tensor.ndim
            self.dim_labels = self._get_dim_labels(ndim)
            axis_choices = [f"{name} (Dim {i})" for i, name in enumerate(self.dim_labels)]
            if self.is_reshaped:
                self.x_axis_combo.config(state='disabled', values=axis_choices)
                self.y_axis_combo.config(state='disabled', values=axis_choices)
            else:
                self.x_axis_combo.config(state='readonly', values=axis_choices)
                self.y_axis_combo.config(state='readonly', values=axis_choices)
            y_default_idx = ndim - 2
            x_default_idx = ndim - 1
            self.y_axis_var.set(axis_choices[y_default_idx])
            self.x_axis_var.set(axis_choices[x_default_idx])
            self._prev_y_axis = self.y_axis_var.get()
            self._prev_x_axis = self.x_axis_var.get()
            
            # --- ИЗМЕНЕНИЕ 2: Активируем режим панорамирования по умолчанию ---
            if self.toolbar.mode != 'pan/zoom':
                self.toolbar.pan()

        self._setup_sliders()
        self._update_view()

    def _setup_sliders(self):
        if self.tensor is None or self.is_reshaped:
            for slider_pack in self.slice_sliders.values():
                slider_pack['frame'].pack_forget()
            return
        try:
            y_idx = int(self.y_axis_var.get().split(' ')[-1][:-1])
            x_idx = int(self.x_axis_var.get().split(' ')[-1][:-1])
        except (ValueError, IndexError): return
        plot_axes = {y_idx, x_idx}
        visible_slider_count = 0
        for dim_idx in range(self.tensor.ndim):
            if dim_idx not in plot_axes:
                slider_pack = self.slice_sliders[visible_slider_count]
                frame = slider_pack['frame']
                dim_shape = self.tensor.shape[dim_idx]
                if dim_shape > 1:
                    slider_pack['label'].config(text=f"{self.dim_labels[dim_idx]}:")
                    slider_pack['var'].set(0)
                    slider_pack['scale'].config(from_=0, to=dim_shape - 1, state='normal')
                    frame.pack(fill=tk.X, padx=5, pady=2)
                else:
                    slider_pack['var'].set(0)
                    frame.pack_forget()
                visible_slider_count += 1
        for i in range(visible_slider_count, len(self.slice_sliders)):
            self.slice_sliders[i]['frame'].pack_forget()

    def _on_axis_selection_change(self, event=None):
        y_val, x_val = self.y_axis_var.get(), self.x_axis_var.get()
        if y_val == x_val:
            messagebox.showwarning("Invalid Selection", "X and Y axes cannot be the same.")
            self.y_axis_var.set(self._prev_y_axis)
            self.x_axis_var.set(self._prev_x_axis)
            return
        self._prev_y_axis, self._prev_x_axis = y_val, x_val
        self._setup_sliders()
        self._update_view()

    def _on_slider_change(self, event=None):
        self._update_view()

    def _on_zoom(self, event):
        if event.xdata is None or event.ydata is None: return
        factor = 1.2 if event.button == 'up' else 1/1.2
        cur_xlim, cur_ylim = self.ax.get_xlim(), self.ax.get_ylim()
        xdata, ydata = event.xdata, event.ydata
        new_width = (cur_xlim[1] - cur_xlim[0]) / factor
        new_height = (cur_ylim[1] - cur_ylim[0]) / factor
        rel_x = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
        rel_y = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])
        self.ax.set_xlim([xdata - new_width * (1 - rel_x), xdata + new_width * rel_x])
        self.ax.set_ylim([ydata - new_height * (1 - rel_y), ydata + new_height * rel_y])
        self.canvas.draw_idle()

    def _reset_view(self):
        self._update_view()

    def _center_and_set_view(self):
        if self.current_slice is None: return
        h, w = self.current_slice.shape
        ax_bbox = self.ax.get_window_extent()
        if not (ax_bbox.width > 0 and ax_bbox.height > 0):
            self.canvas.get_tk_widget().after(10, self._center_and_set_view)
            return
        aspect_data = w / h if h > 0 else 1
        aspect_ax = ax_bbox.width / ax_bbox.height
        self.ax.set_aspect('equal')
        if aspect_data > aspect_ax:
            self.ax.set_xlim(-0.5, w - 0.5)
            required_height = w / aspect_ax
            margin_y = (required_height - h) / 2
            self.ax.set_ylim(h - 0.5 + margin_y, -0.5 - margin_y)
        else:
            self.ax.set_ylim(h - 0.5, -0.5)
            required_width = h * aspect_ax
            margin_x = (required_width - w) / 2
            self.ax.set_xlim(-0.5 - margin_x, w - 0.5 + margin_x)
        self.canvas.draw_idle()

    def _update_view(self):
        self.ax.clear()
        if self.tensor is None:
            self.ax.set_aspect('auto')
            self.ax.set_xlim(0, 1); self.ax.set_ylim(0, 1)
            self.ax.text(0.5, 0.5, "No Tensor Data", ha="center", va="center", transform=self.ax.transAxes)
            self.ax.set_xticks([]); self.ax.set_yticks([])
            self.canvas.draw()
            return
        if self.is_reshaped:
            self.current_slice = self.tensor
        else:
            try:
                y_idx = int(self.y_axis_var.get().split(' ')[-1][:-1])
                x_idx = int(self.x_axis_var.get().split(' ')[-1][:-1])
            except (ValueError, IndexError): return
            slicer = [0] * self.tensor.ndim
            slicer[y_idx] = slice(None)
            slicer[x_idx] = slice(None)
            plot_axes = {y_idx, x_idx}
            visible_slider_count = 0
            for dim_idx in range(self.tensor.ndim):
                if dim_idx not in plot_axes:
                    slider_pack = self.slice_sliders[visible_slider_count]
                    slicer[dim_idx] = slider_pack['var'].get()
                    visible_slider_count += 1
            self.current_slice = self.tensor[tuple(slicer)]
        vmin = 0
        vmax = np.max(self.current_slice)
        if vmax == 0: vmax = 1.0
        im = self.ax.imshow(self.current_slice, cmap='viridis', interpolation='nearest', vmin=vmin, vmax=vmax)
        if not hasattr(self, 'colorbar') or self.colorbar.ax is None or self.colorbar.ax.figure != self.fig:
             self.colorbar = self.fig.colorbar(im, ax=self.ax)
        else:
            self.colorbar.update_normal(im)
        if self.is_reshaped:
            self.ax.set_title("Tensor Value")
            self.ax.set_xlabel("")
            self.ax.set_ylabel("")
        else:
            y_label = self.y_axis_var.get()
            x_label = self.x_axis_var.get()
            self.ax.set_title(f"Slice Y:{y_label}, X:{x_label}")
            self.ax.set_xlabel(x_label)
            self.ax.set_ylabel(y_label)
        self.canvas.get_tk_widget().after(1, self._center_and_set_view)

# =====================================================================================
#  Вкладка для анализа тензоров с ИСПРАВЛЕННЫМ контекстным меню и сравнением
# =====================================================================================
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from collections import defaultdict
import numpy as np

# Предполагается, что класс TensorViewer определен в вашем файле
# Если нет, вы можете временно заменить его заглушкой для тестирования, например:
# class TensorViewer(ttk.Frame):
#     def __init__(self, parent):
#         super().__init__(parent)
#         ttk.Label(self, text="Tensor Viewer Area").pack(expand=True)
#     def set_tensor(self, tensor_data):
#         print("Tensor Viewer received data.")


# =====================================================================================
#  ФИНАЛЬНАЯ ВЕРСИЯ: TensorTab с правильным меню выбора рекордов
# =====================================================================================
class TensorTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)

        # --- Состояние класса ---
        self.tensor_map = {}
        self.mse_results = {}
        
        # Храним только простые имена рекордов (e.g., {'rec1', 'rec2'})
        self.available_records = set()
        self.record1_for_analysis = None
        self.record2_for_analysis = None

        # --- UI: Основная разметка ---
        main_paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left_pane = ttk.Frame(main_paned_window, padding="10")
        main_paned_window.add(left_pane, weight=1)

        right_pane = ttk.Frame(main_paned_window, padding="10")
        main_paned_window.add(right_pane, weight=4)

        # --- UI: Левая панель ---
        buttons_frame = ttk.Frame(left_pane)
        buttons_frame.pack(fill=tk.X, pady=(0, 10))
        
        load_button = ttk.Button(buttons_frame, text="Load Tensors from DB", command=self._load_tensors_metadata)
        load_button.pack(side=tk.LEFT, fill=tk.X, expand=True)

        analyze_button = ttk.Button(buttons_frame, text="Run Analysis", command=self._perform_record_analysis)
        analyze_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        selection_frame = ttk.LabelFrame(left_pane, text="Tensor Selection & Analysis", padding="10")
        selection_frame.pack(fill=tk.BOTH, expand=True)

        self.analysis_status_label = ttk.Label(selection_frame, text="Right-click on a record (e.g., 'rec1') to select for analysis.", wraplength=300, justify=tk.LEFT)
        self.analysis_status_label.pack(anchor='w', pady=(0, 10))

        ttk.Label(selection_frame, text="1. Select First Tensor (or right-click a record):").pack(anchor='w')
        tree_container = ttk.Frame(selection_frame)
        tree_container.pack(fill=tk.BOTH, expand=True, pady=5)
        self.tree = ttk.Treeview(tree_container, selectmode="browse")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_left_click)
        self.tree.bind("<Button-3>", self._on_tree_right_click)

        self.context_menu = tk.Menu(self, tearoff=0)

        ttk.Label(selection_frame, text="2. Select Second Tensor (for manual comparison):").pack(anchor='w', pady=(10, 0))
        self.second_tensor_combo = ttk.Combobox(selection_frame, state="disabled")
        self.second_tensor_combo.pack(fill=tk.X, expand=True, pady=5)
        self.second_tensor_combo.bind("<<ComboboxSelected>>", self._on_second_tensor_select)

        # --- UI: Правая панель ---
        result_frame = ttk.LabelFrame(right_pane, text="Resulting Difference Tensor", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        self.tensor_viewer = TensorViewer(result_frame)

    # --- Логика анализа по правому клику ---

    def _on_tree_right_click(self, event):
        """Обрабатывает правый клик, показывая в меню только простые имена рекордов."""
        iid = self.tree.identify_row(event.y)
        if not iid: return

        self.tree.selection_set(iid)
        item_text = self.tree.item(iid, 'text')

        if item_text.startswith('rec') and self.tree.get_children(iid):
            self.record1_for_analysis = item_text
            self.record2_for_analysis = None
            self._update_analysis_status_label()
            
            self.context_menu.delete(0, 'end')
            other_records = sorted([r for r in self.available_records if r != self.record1_for_analysis])

            if not other_records:
                self.context_menu.add_command(label="No other records to compare", state="disabled")
            else:
                for rec_name in other_records:
                    self.context_menu.add_command(
                        label=f"Compare with: {rec_name}",
                        command=lambda r=rec_name: self._set_comparison_record(r)
                    )
            self.context_menu.post(event.x_root, event.y_root)

    def _set_comparison_record(self, record_name):
        """Запоминает второе простое имя рекорда, выбранное из меню."""
        self.record2_for_analysis = record_name
        self._update_analysis_status_label()

    def _update_analysis_status_label(self):
        """Обновляет информационную метку о выбранных для анализа рекордах."""
        if self.record1_for_analysis and self.record2_for_analysis:
            text = f"Analysis target:\n- {self.record1_for_analysis}\n- {self.record2_for_analysis}"
        elif self.record1_for_analysis:
            text = f"Selected: {self.record1_for_analysis}.\nNow choose a comparison record."
        else:
            text = "Right-click on a record (e.g., 'rec1') to select for analysis."
        self.analysis_status_label.config(text=text)

    def _perform_record_analysis(self):
        """Выполняет анализ, используя простые имена рекордов для поиска и замены."""
        if not self.record1_for_analysis or not self.record2_for_analysis:
            messagebox.showwarning("Selection Missing", "Please select two records for analysis using the right-click context menu.")
            return

        self.mse_results.clear()
        rec1_str = self.record1_for_analysis
        rec2_str = self.record2_for_analysis
        
        compared_pairs = 0
        for name1, info1 in self.tensor_map.items():
            # Ищем точное вхождение, окруженное точками, чтобы избежать ложных срабатываний
            # (например, чтобы не сработать на 'rec10' при поиске 'rec1')
            search_str = f".{rec1_str}."
            if search_str in name1:
                name2 = name1.replace(search_str, f".{rec2_str}.")
                
                if name2 in self.tensor_map:
                    compared_pairs += 1
                    info2 = self.tensor_map[name2]
                    if info1['shape'] == info2['shape']:
                        tensor1, tensor2 = self._get_tensor_as_numpy(name1), self._get_tensor_as_numpy(name2)
                        if tensor1 is not None and tensor2 is not None:
                            mse = np.mean((tensor1 - tensor2) ** 2)
                            if mse > 1e-9: # Порог для игнорирования ошибок машинного округления
                                self.mse_results[name1] = mse
                                self.mse_results[name2] = mse
        
        self._update_tree_colors()
        messagebox.showinfo("Analysis Complete", f"Compared {compared_pairs} tensor pairs. Found {len(self.mse_results)//2} pairs with differences.")

    # --- Логика раскраски дерева ---

    def _update_tree_colors(self):
        """Запускает процесс очистки и рекурсивной раскраски дерева."""
        self._clear_tree_colors(self.tree.get_children())
        if not self.mse_results: return
        max_mse = max(self.mse_results.values()) if self.mse_results else 0
        for item_id in self.tree.get_children(""):
            self._propagate_colors(item_id, max_mse)

    def _propagate_colors(self, item_id, max_mse):
        """Рекурсивно раскрашивает узлы: листья по их MSE, родители по max MSE детей."""
        children = self.tree.get_children(item_id)
        if not children: # Это лист (тензор)
            full_name = self._get_fullname_from_tree(item_id)
            mse = self.mse_results.get(full_name)
            if mse is not None:
                color = self._get_color_from_mse(mse, max_mse)
                tag_name = f"diff_{item_id}"
                self.tree.item(item_id, tags=(tag_name,))
                self.tree.tag_configure(tag_name, background=color)
                return mse
            return 0.0
        else: # Это родительский узел
            max_child_mse = 0.0
            for child_id in children:
                child_mse = self._propagate_colors(child_id, max_mse)
                if child_mse > max_child_mse:
                    max_child_mse = child_mse
            if max_child_mse > 0:
                color = self._get_color_from_mse(max_child_mse, max_mse)
                tag_name = f"diff_parent_{item_id}"
                self.tree.item(item_id, tags=(tag_name,))
                self.tree.tag_configure(tag_name, background=color)
            return max_child_mse

    def _get_color_from_mse(self, mse, max_mse):
        """Генерирует цвет от белого до красного в зависимости от величины ошибки."""
        if max_mse == 0: return '#ffffff'
        normalized_error = min(mse / max_mse, 1.0)
        intensity = 255 - int(normalized_error * 205)
        return f'#ff{intensity:02x}{intensity:02x}'

    def _clear_tree_colors(self, item_ids):
        """Рекурсивно удаляет теги раскраски со всех элементов дерева."""
        for item_id in item_ids:
            self.tree.item(item_id, tags=())
            if children := self.tree.get_children(item_id):
                self._clear_tree_colors(children)

    # --- Загрузка данных и ручное сравнение ---

    def _load_tensors_metadata(self):
        """Загружает метаданные и отдельно собирает уникальные имена рекордов."""
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
                ORDER BY N.RecordID, T.Name
            """
            cursor.execute(query)
            tensor_metadata = cursor.fetchall()
            conn.close()
        except sqlite3.OperationalError as e:
            messagebox.showerror("Database Error", f"Could not read tensor metadata.\nError: {e}")
            return

        if not tensor_metadata:
            messagebox.showinfo("No Data", "No tensors found.")
            return

        # Полный сброс состояния
        self.mse_results.clear()
        self.tree.delete(*self.tree.get_children())
        self.tensor_map.clear()
        self.available_records.clear()
        self.record1_for_analysis = None
        self.record2_for_analysis = None
        self._update_analysis_status_label()

        node_map = {}
        for row in tensor_metadata:
            base_name, record_id, datatype, num_dims = row[0], row[1], row[3], row[4]
            
            # Ваша логика формирования полного имени
            full_name = f"dt{datatype}.rec{record_id}.{base_name}.dims{num_dims}"
            
            self.tensor_map[full_name] = {
                "base_name": base_name, "record_id": record_id, "tensor_id": row[2],
                "datatype": datatype, "dims": num_dims, 
                "shape": tuple(s for s in row[5:10] if s > 0)
            }
            
            # Находим и сохраняем простое имя рекорда
            record_name_str = f"rec{record_id}"
            self.available_records.add(record_name_str)
            
            # Построение дерева
            parent_iid = ''
            current_path = ''
            for part in full_name.split('.'):
                current_path = f"{current_path}.{part}" if current_path else part
                if current_path not in node_map:
                    iid = self.tree.insert(parent_iid, 'end', text=part, open=False)
                    node_map[current_path] = iid
                parent_iid = node_map[current_path]

        self.second_tensor_combo.set('')
        self.second_tensor_combo['values'] = []
        self.second_tensor_combo.config(state="disabled")
        self.tensor_viewer.set_tensor(None)
        messagebox.showinfo("Success", f"{len(tensor_metadata)} tensor metadata entries loaded.")

    def _on_tree_left_click(self, event=None):
        """Обрабатывает выбор тензора (листа) для ручного сравнения."""
        selection = self.tree.selection()
        if not selection: return
        selected_iid = selection[0]
        if self.tree.get_children(selected_iid): return

        full_name = self._get_fullname_from_tree(selected_iid)
        selected_info = self.tensor_map.get(full_name)
        if not selected_info: return

        base_name, current_shape = selected_info["base_name"], selected_info["shape"]
        compatible_tensors = [name for name, info in self.tensor_map.items() if info["base_name"] == base_name and info["shape"] == current_shape]
        
        self.second_tensor_combo['values'] = compatible_tensors
        self.second_tensor_combo.config(state="readonly")
        self.second_tensor_combo.set('')
        self.tensor_viewer.set_tensor(None)

    def _on_second_tensor_select(self, event=None):
        """Выполняет ручное сравнение при выборе из Combobox."""
        selection = self.tree.selection()
        if not selection: return
        tensor1_name = self._get_fullname_from_tree(selection[0])
        tensor2_name = self.second_tensor_combo.get()
        if not tensor1_name or not tensor2_name: return
        self._calculate_and_display_diff(tensor1_name, tensor2_name)

    # --- Вспомогательные методы ---

    def _get_fullname_from_tree(self, iid):
        """Собирает полный путь к элементу дерева по его iid."""
        path_parts = []
        while iid:
            path_parts.append(self.tree.item(iid, 'text'))
            iid = self.tree.parent(iid)
        return ".".join(reversed(path_parts))

    def _fetch_blob_by_id(self, tensor_id):
        """Получает BLOB-данные тензора из БД по его ID."""
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
        """Конвертирует BLOB-данные в тензор NumPy."""
        info = self.tensor_map.get(name)
        if not info: return None
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
        """Вычисляет и отображает разницу между двумя тензорами."""
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
# =====================================================================================
#  Старая вкладка с диаграммой Ганта (без изменений)
# =====================================================================================
class GanttTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)
        
        self.record_colors = {}
        self.color_palette = [
            '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
            '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac'
        ]
        self.DEFAULT_FONT_SIZES = {
            'layer_name': 10, 'axis_label': 8, 'bar_label': 9,
            'legend_title': 12, 'legend_item': 10
        }
        self.font_sizes = self.DEFAULT_FONT_SIZES.copy()

        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        top_panel = ttk.Frame(self.main_frame)
        top_panel.pack(fill=tk.X, pady=5)

        self.start_button = ttk.Button(top_panel, text="Start / Refresh", command=self.update_chart)
        self.start_button.pack(side=tk.LEFT, padx=(0, 20))

        self.mode = tk.StringVar(value="Default")
        mode_frame = ttk.LabelFrame(top_panel, text="Display Mode")
        mode_frame.pack(side=tk.LEFT)
        
        ttk.Radiobutton(mode_frame, text="Default", variable=self.mode, value="Default", command=self.update_chart).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="Normalized (by Duration)", variable=self.mode, value="Normalized", command=self.update_chart).pack(side=tk.LEFT, padx=5)

        self.canvas = tk.Canvas(self.main_frame, bg='white')
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self.move_start)
        self.canvas.bind("<B1-Motion>", self.move_move)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)

        self.update_chart()

    def move_start(self, event): self.canvas.scan_mark(event.x, event.y)
    def move_move(self, event): self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_mousewheel(self, event):
        factor = 0
        if event.num == 4 or event.delta > 0: factor = 1.1
        elif event.num == 5 or event.delta < 0: factor = 0.9
        if factor: self._zoom(factor, event.x, event.y)

    def _zoom(self, factor, x, y):
        self.canvas.scale("all", x, y, factor, factor)
        for key in self.font_sizes: self.font_sizes[key] *= factor
        self._update_text_fonts()
        bbox = self.canvas.bbox("all")
        if bbox: self.canvas.config(scrollregion=bbox)

    def _update_text_fonts(self):
        for key, size in self.font_sizes.items():
            for item_id in self.canvas.find_withtag(f"{key}_text"):
                font_name = "Arial"
                font_style = "bold" if key in ['bar_label', 'legend_title'] else ""
                self.canvas.itemconfigure(item_id, font=(font_name, int(size), font_style))

    def get_record_color(self, record_id):
        if record_id not in self.record_colors:
            self.record_colors[record_id] = self.color_palette[len(self.record_colors) % len(self.color_palette)]
        return self.record_colors[record_id]

    def fetch_data_from_db(self):
        try:
            conn = sqlite3.connect('debug.db')
            cursor = conn.cursor()
            cursor.execute("SELECT Name, Start, End, RecordID, SeqNum FROM Nodes ORDER BY RecordID, SeqNum")
            data = cursor.fetchall()
            conn.close()
            return data
        except sqlite3.OperationalError as e:
            messagebox.showerror("Database Error", f"Could not read from 'debug.db'.\nError: {e}")
            return None

    def update_chart(self):
        self.font_sizes = self.DEFAULT_FONT_SIZES.copy()
        data = self.fetch_data_from_db()
        if data:
            self.draw_gantt(data)
        else:
            self.canvas.delete("all")
            self.canvas.create_text(400, 300, text="No data to display.", font=("Arial", 16))

    def draw_gantt(self, data):
        self.canvas.delete("all")
        tasks_by_layer = defaultdict(list)
        all_records = set()
        for name, start, end, record_id, seq_num in data:
            tasks_by_layer[name].append({'start': start, 'end': end, 'record_id': record_id})
            all_records.add(record_id)
        first_record_id = sorted(list(all_records))[0]
        ordered_layers = [row[0] for row in sorted([r for r in data if r[3] == first_record_id], key=lambda x: x[4])]
        if not ordered_layers: return
        mode = self.mode.get()
        if mode == "Default":
            self._draw_default_mode(data, tasks_by_layer, ordered_layers, all_records)
        elif mode == "Normalized":
            self._draw_normalized_mode(data, tasks_by_layer, ordered_layers, all_records)
        bbox = self.canvas.bbox("all")
        if bbox: self.canvas.config(scrollregion=bbox)

    def _draw_default_mode(self, data, tasks_by_layer, ordered_layers, all_records):
        min_time = min(row[1] for row in data)
        max_time = max(row[2] for row in data)
        total_duration = max_time - min_time if max_time > min_time else 1
        self._draw_common_elements(tasks_by_layer, ordered_layers, all_records, min_time, total_duration)
        self._draw_time_axis(min_time, total_duration, ordered_layers, len(all_records))
        self._draw_legend(data, ordered_layers, len(all_records))

    def _draw_normalized_mode(self, data, tasks_by_layer, ordered_layers, all_records):
        max_task_duration = max((row[2] - row[1] for row in data), default=0)
        total_duration = max_task_duration if max_task_duration > 0 else 1
        self._draw_common_elements(tasks_by_layer, ordered_layers, all_records, 0, total_duration)
        self._draw_time_axis(0, total_duration, ordered_layers, len(all_records))
        self._draw_legend(data, ordered_layers, len(all_records))

    def _draw_common_elements(self, tasks_by_layer, ordered_layers, all_records, scale_min_time, scale_total_duration):
        sorted_records = sorted(list(all_records))
        record_to_v_index = {rec_id: i for i, rec_id in enumerate(sorted_records)}
        num_records = len(sorted_records)
        PADDING, LEFT_MARGIN, TIMELINE_WIDTH = 60, 200, 2500
        scale_width = TIMELINE_WIDTH
        SUB_BAR_HEIGHT, SUB_BAR_PADDING = 20, 5
        LANE_HEIGHT = (SUB_BAR_HEIGHT + SUB_BAR_PADDING) * num_records
        canvas_width = LEFT_MARGIN + TIMELINE_WIDTH + PADDING
        self.canvas.create_line(0, PADDING, canvas_width, PADDING, fill='lightgrey', dash=(2, 2))
        for i, layer_name in enumerate(ordered_layers):
            y_lane_start = PADDING + i * (LANE_HEIGHT + SUB_BAR_PADDING)
            if i % 2 == 1:
                self.canvas.create_rectangle(0, y_lane_start, canvas_width, y_lane_start + LANE_HEIGHT, fill='#f0f0f0', outline='')
            self.canvas.create_line(0, y_lane_start + LANE_HEIGHT, canvas_width, y_lane_start + LANE_HEIGHT, fill='lightgrey', dash=(2, 2))
            self.canvas.create_text(LEFT_MARGIN - 10, y_lane_start + LANE_HEIGHT / 2, text=layer_name, anchor=tk.E, font=("Arial", int(self.font_sizes['layer_name'])), tags="layer_name_text")
            for task in tasks_by_layer[layer_name]:
                record_id, start, end = task['record_id'], task['start'], task['end']
                color = self.get_record_color(record_id)
                v_index = record_to_v_index.get(record_id, 0)
                y0 = y_lane_start + v_index * (SUB_BAR_HEIGHT + SUB_BAR_PADDING)
                if self.mode.get() == "Normalized":
                    new_start, new_end = 0, end - start
                else:
                    new_start, new_end = start, end
                x0 = LEFT_MARGIN + (new_start - scale_min_time) / scale_total_duration * scale_width
                x1 = LEFT_MARGIN + (new_end - scale_min_time) / scale_total_duration * scale_width
                self.canvas.create_rectangle(x0, y0, x1, y0 + SUB_BAR_HEIGHT, fill=color, outline='black', width=1)
                duration = end - start
                label_text = f"R:{record_id} ({duration:.2f}s)"
                self.canvas.create_text((x0 + x1) / 2, y0 + SUB_BAR_HEIGHT / 2, text=label_text, fill='white', font=("Arial", int(self.font_sizes['bar_label']), "bold"), tags="bar_label_text")

    def _draw_time_axis(self, min_time, total_duration, layers, num_records):
        PADDING, LEFT_MARGIN, TIMELINE_WIDTH = 60, 200, 2500
        scale_width = TIMELINE_WIDTH
        SUB_BAR_HEIGHT, SUB_BAR_PADDING = 20, 5
        LANE_HEIGHT = (SUB_BAR_HEIGHT + SUB_BAR_PADDING) * num_records
        graph_height = PADDING + len(layers) * (LANE_HEIGHT + SUB_BAR_PADDING)
        num_ticks = 10
        for i in range(num_ticks + 1):
            time_val = min_time + (total_duration * i / num_ticks)
            x_pos = LEFT_MARGIN + (time_val - min_time) / total_duration * scale_width
            self.canvas.create_line(x_pos, PADDING, x_pos, graph_height, fill='lightgrey', dash=(2, 2))
            self.canvas.create_text(x_pos, PADDING - 20, text=f"{time_val:.2f}", anchor=tk.N, font=("Arial", int(self.font_sizes['axis_label'])), tags="axis_label_text")

    def _draw_legend(self, data, layers, num_records):
        PADDING, LEFT_MARGIN = 60, 200
        SUB_BAR_HEIGHT, SUB_BAR_PADDING = 20, 5
        LANE_HEIGHT = (SUB_BAR_HEIGHT + SUB_BAR_PADDING) * num_records
        graph_height = PADDING + len(layers) * (LANE_HEIGHT + SUB_BAR_PADDING)
        LEGEND_TOP_MARGIN, LEGEND_ITEM_HEIGHT = 40, 25
        legend_y_start = graph_height + LEGEND_TOP_MARGIN
        legend_x = LEFT_MARGIN
        self.canvas.create_text(legend_x, legend_y_start, text="Legend:", anchor=tk.W, font=("Arial", int(self.font_sizes['legend_title']), "bold"), tags="legend_title_text")
        sorted_records = sorted(list(set(row[3] for row in data)))
        for i, record_id in enumerate(sorted_records):
            color = self.get_record_color(record_id)
            y = legend_y_start + LEGEND_ITEM_HEIGHT + i * LEGEND_ITEM_HEIGHT
            self.canvas.create_rectangle(legend_x, y, legend_x + 20, y + 20, fill=color, outline='black')
            self.canvas.create_text(legend_x + 30, y + 10, text=f"RecordID #{record_id}", anchor=tk.W, font=("Arial", int(self.font_sizes['legend_item'])), tags="legend_item_text")

# =====================================================================================
#  Главный класс приложения, который управляет вкладками
# =====================================================================================
class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gantt & Tensor Analyzer")
        self.root.geometry("1200x800")

        notebook = ttk.Notebook(root)
        notebook.pack(expand=True, fill='both', padx=10, pady=10)

        gantt_frame = GanttTab(notebook)
        tensor_frame = TensorTab(notebook)

        notebook.add(gantt_frame, text='Gantt Chart')
        notebook.add(tensor_frame, text='Tensor Analysis')

if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()