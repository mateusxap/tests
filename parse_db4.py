import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from collections import defaultdict

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from skimage.measure import block_reduce

# =====================================================================================
#  НОВЫЙ, ИСПРАВЛЕННЫЙ виджет для визуализации тензора с правильной логикой ползунков
# =====================================================================================
class TensorViewer(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)

        self.tensor = None
        self.slice_indices_vars = []
        self.current_slice = None

        # --- UI Элементы ---
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        plot_frame = ttk.Frame(self)
        plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        
        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        toolbar.update()
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.sliders_frame = ttk.Frame(self)
        self.sliders_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        self.canvas.mpl_connect('scroll_event', self._on_zoom)
        self.canvas.mpl_connect('draw_event', self._on_draw)
        self.is_drawing = False

    def set_tensor(self, tensor_data):
        self.tensor = tensor_data
        self._setup_sliders()
        self._update_view(is_new_tensor=True)

    def _setup_sliders(self):
        for widget in self.sliders_frame.winfo_children():
            widget.destroy()
        self.slice_indices_vars = []
        if self.tensor is None or self.tensor.ndim <= 2: return
        num_sliceable_dims = self.tensor.ndim - 2
        for i in range(num_sliceable_dims):
            dim_shape = self.tensor.shape[i]
            var = tk.IntVar(value=0)
            self.slice_indices_vars.append(var)
            frame = ttk.Frame(self.sliders_frame)
            frame.pack(fill=tk.X, padx=5, pady=2)
            ttk.Label(frame, text=f"Dim {i}:").pack(side=tk.LEFT)
            scale = ttk.Scale(frame, from_=0, to=dim_shape - 1, orient=tk.HORIZONTAL, variable=var, command=self._on_slider_change)
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            ttk.Label(frame, textvariable=var, width=4).pack(side=tk.LEFT)
            if dim_shape <= 1:
                scale.config(state="disabled")

    def _on_slider_change(self, event=None):
        for var in self.slice_indices_vars:
            var.set(round(var.get()))
        self._update_view(is_new_tensor=True)

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

    def _on_draw(self, event):
        if self.is_drawing: return
        self._update_view(is_new_tensor=False)

    # --- ИЗМЕНЕНИЕ: Заменяем самописный пулинг на вызов из библиотеки scikit-image ---
    def _adaptive_pool(self, data, pool_size):
        """
        Выполняет 2D Max Pooling с помощью функции block_reduce из scikit-image.
        """
        # block_reduce ожидает кортеж для размера блока
        block_shape = (pool_size, pool_size)
        
        # Защита от ошибки, если данные меньше, чем окно пулинга
        if data.shape[0] < pool_size or data.shape[1] < pool_size:
            return data

        # Вызываем функцию, передавая ей наш массив, размер блока и функцию np.max
        return block_reduce(data, block_size=block_shape, func=np.max)

    def _update_view(self, is_new_tensor=False):
        if self.is_drawing: return
        self.is_drawing = True

        if not is_new_tensor:
            xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()

        self.ax.clear()

        if self.tensor is None:
            self.ax.text(0.5, 0.5, "No Tensor Data", ha="center", va="center", transform=self.ax.transAxes)
            self.ax.set_xticks([]); self.ax.set_yticks([])
            self.canvas.draw()
            self.is_drawing = False
            return

        if len(self.slice_indices_vars) != self.tensor.ndim - 2:
            self._setup_sliders()

        slicer = tuple(var.get() for var in self.slice_indices_vars)
        self.current_slice = self.tensor[slicer]
        
        view_xlim = self.ax.get_xlim() if not is_new_tensor else (-0.5, self.current_slice.shape[1] - 0.5)
        view_width_data = view_xlim[1] - view_xlim[0]
        ax_width_pixels = self.ax.get_window_extent().width
        data_pixels_per_screen_pixel = view_width_data / ax_width_pixels if ax_width_pixels > 0 else 1
        
        pool_size = 1
        if data_pixels_per_screen_pixel > 1.5:
            pool_size = int(np.ceil(data_pixels_per_screen_pixel))
        
        if pool_size > 1:
            display_data = self._adaptive_pool(self.current_slice, pool_size)
            title = f"Slice at {slicer} (Pooled {pool_size}x{pool_size})"
            extent = (-0.5, self.current_slice.shape[1] - 0.5, self.current_slice.shape[0] - 0.5, -0.5)
        else:
            display_data = self.current_slice
            title = f"Slice at {slicer} (Original)"
            extent = None

        im = self.ax.imshow(display_data, cmap='viridis', interpolation='nearest', extent=extent)
        
        if not hasattr(self, 'colorbar') or self.colorbar.ax is None or self.colorbar.ax.figure != self.fig:
             self.colorbar = self.fig.colorbar(im, ax=self.ax)
        else:
            self.colorbar.update_normal(im)

        self.ax.set_title(title)
        
        if is_new_tensor:
            self._reset_view()
        else:
            self.ax.set_xlim(xlim)
            self.ax.set_ylim(ylim)

        self.canvas.draw()
        self.is_drawing = False

    def _reset_view(self):
        if self.current_slice is not None:
            h, w = self.current_slice.shape
            self.ax.set_xlim(-0.5, w - 0.5)
            self.ax.set_ylim(h - 0.5, -0.5)
            self.canvas.draw_idle()
class TensorTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)

        self.tensor_map = {}

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 20))
        
        load_button = ttk.Button(control_frame, text="Load Tensors from DB", command=self._load_tensors)
        load_button.pack(side=tk.LEFT)

        selection_frame = ttk.LabelFrame(main_frame, text="Tensor Selection", padding="10")
        selection_frame.pack(fill=tk.X)

        ttk.Label(selection_frame, text="1. Select First Tensor:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.first_tensor_combo = ttk.Combobox(selection_frame, state="readonly", width=50)
        self.first_tensor_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.first_tensor_combo.bind("<<ComboboxSelected>>", self._on_first_tensor_select)

        ttk.Label(selection_frame, text="2. Select Second Tensor (for comparison):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.second_tensor_combo = ttk.Combobox(selection_frame, state="disabled", width=50)
        self.second_tensor_combo.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.second_tensor_combo.bind("<<ComboboxSelected>>", self._on_second_tensor_select)
        
        selection_frame.columnconfigure(1, weight=1)

        result_frame = ttk.LabelFrame(main_frame, text="Resulting Difference Tensor", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

        self.tensor_viewer = TensorViewer(result_frame)

    def _load_tensors(self):
        try:
            conn = sqlite3.connect('debug.db')
            cursor = conn.cursor()
            query = """
                SELECT
                    T.Name, N.RecordID, T.ID as TensorID, T.Datatype, T.NumDims,
                    T.Shape0, T.Shape1, T.Shape2, T.Shape3, T.Shape4, T.Data
                FROM Tensors T
                JOIN TensorMap TM ON T.ID = TM.TensorID
                JOIN Nodes N ON TM.NodeID = N.id
                WHERE T.Name IS NOT NULL AND T.Name != ''
                ORDER BY T.Name, N.RecordID
            """
            cursor.execute(query)
            tensor_data = cursor.fetchall()
            conn.close()
        except sqlite3.OperationalError as e:
            messagebox.showerror("Database Error", f"Could not read tensor data from 'debug.db'.\nError: {e}")
            return

        if not tensor_data:
            messagebox.showinfo("No Data", "No tensors found in the database.")
            return

        self.tensor_map.clear()
        display_names = []
        for row in tensor_data:
            display_name = f"{row[0]} (Record: {row[1]})"
            display_names.append(display_name)
            self.tensor_map[display_name] = {
                "name": row[0], "record_id": row[1], "tensor_id": row[2],
                "datatype": row[3], "dims": row[4], 
                "shape": tuple(s for s in row[5:10] if s > 0 and s is not None),
                "blob": row[10]
            }
        
        self.first_tensor_combo['values'] = display_names
        self.first_tensor_combo.set('')
        self.second_tensor_combo.set('')
        self.second_tensor_combo['values'] = []
        self.second_tensor_combo.config(state="disabled")
        self.tensor_viewer.set_tensor(None)
        messagebox.showinfo("Success", f"{len(display_names)} tensors loaded successfully.")

    def _on_first_tensor_select(self, event=None):
        selected_display_name = self.first_tensor_combo.get()
        if not selected_display_name: return

        base_name = self.tensor_map[selected_display_name]["name"]
        compatible_tensors = [dn for dn, info in self.tensor_map.items() if info["name"] == base_name]
        
        self.second_tensor_combo['values'] = compatible_tensors
        self.second_tensor_combo.config(state="readonly")
        self.second_tensor_combo.set('')
        self.tensor_viewer.set_tensor(None)

    def _on_second_tensor_select(self, event=None):
        tensor1_name = self.first_tensor_combo.get()
        tensor2_name = self.second_tensor_combo.get()
        if not tensor1_name or not tensor2_name: return
        self._calculate_and_display_diff(tensor1_name, tensor2_name)

    def _get_tensor_as_numpy(self, name):
        info = self.tensor_map[name]
        blob, shape = info['blob'], info['shape']
        dtype = np.float32 if info['datatype'] == 0 else np.int32
        
        try:
            arr_1d = np.frombuffer(blob, dtype=dtype)
            return arr_1d.reshape(shape)
        except Exception as e:
            messagebox.showerror("Tensor Conversion Error", f"Failed to convert tensor '{name}'.\nShape: {shape}, Blob size: {len(blob)}\nError: {e}")
            return None

    def _calculate_and_display_diff(self, name1, name2):
        tensor1 = self._get_tensor_as_numpy(name1)
        tensor2 = self._get_tensor_as_numpy(name2)

        if tensor1 is None or tensor2 is None:
            self.tensor_viewer.set_tensor(None)
            return

        if tensor1.shape != tensor2.shape:
            messagebox.showerror("Shape Mismatch", f"Tensors have incompatible shapes.\n"
                                                   f"{name1}: {tensor1.shape}\n"
                                                   f"{name2}: {tensor2.shape}")
            self.tensor_viewer.set_tensor(None)
            return

        diff_tensor = np.abs(tensor1 - tensor2)
        self.tensor_viewer.set_tensor(diff_tensor)
# =====================================================================================
#  Старая вкладка с диаграммой Ганта (инкапсулирована в класс)
# =====================================================================================
class GanttTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)
        
        # Копируем всю логику из старого класса сюда
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

        # Создаем виджет Notebook (вкладки)
        notebook = ttk.Notebook(root)
        notebook.pack(expand=True, fill='both', padx=10, pady=10)

        # Создаем фреймы для каждой вкладки
        gantt_frame = GanttTab(notebook)
        tensor_frame = TensorTab(notebook)

        # Добавляем фреймы как вкладки
        notebook.add(gantt_frame, text='Gantt Chart')
        notebook.add(tensor_frame, text='Tensor Analysis')

if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()