import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from collections import defaultdict

class GanttChartApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gantt Chart - Zoom & Pan")
        self.root.minsize(900, 600)

        # --- Данные для отрисовки и масштабирования ---
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
        
        self.task_info = {}

        # --- Создание виджетов ---
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Верхняя панель управления ---
        top_panel = ttk.Frame(self.main_frame)
        top_panel.pack(fill=tk.X, pady=5)

        self.start_button = ttk.Button(top_panel, text="Start / Refresh", command=self.update_chart)
        self.start_button.pack(side=tk.LEFT, padx=(0, 20))

        self.mode = tk.StringVar(value="Default")
        mode_frame = ttk.LabelFrame(top_panel, text="Display Mode")
        mode_frame.pack(side=tk.LEFT)
        
        ttk.Radiobutton(mode_frame, text="Default", variable=self.mode, value="Default", command=self.update_chart).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="Normalized (by Duration)", variable=self.mode, value="Normalized", command=self.update_chart).pack(side=tk.LEFT, padx=5)

        # --- Информационная панель ---
        self.info_var = tk.StringVar()
        info_label = ttk.Label(self.main_frame, textvariable=self.info_var, anchor='w', font=("Arial", 10))
        info_label.pack(fill=tk.X, pady=(5, 10))

        # --- Холст (без скроллбаров) ---
        self.canvas = tk.Canvas(self.main_frame, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # --- Привязка событий мыши ---
        self.canvas.bind("<ButtonPress-1>", self.move_start)
        self.canvas.bind("<B1-Motion>", self.move_move)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)
        self.canvas.bind("<ButtonPress-3>", self._handle_right_click)

        self.update_chart()

    def _handle_right_click(self, event):
        """Определяет, был ли клик по задаче или по фону, и действует соответственно."""
        clicked_ids = self.canvas.find_withtag("current")
        found_task = False
        if clicked_ids:
            item_id = clicked_ids[0]
            if "task_bar" in self.canvas.gettags(item_id):
                info = self.task_info.get(item_id)
                if info:
                    info_text = (f"Layer: {info['layer']} | "
                                 f"RecordID: {info['record']} | "
                                 f"Duration: {info['duration']:.4f}s "
                                 f"(Original Time: {info['start']:.3f}s - {info['end']:.3f}s)")
                    self.info_var.set(info_text)
                    found_task = True
        if not found_task:
            self._clear_info_label()

    def _clear_info_label(self, event=None):
        """Очищает информационную метку и выводит подсказку."""
        self.info_var.set("Right-click on a bar to see details. Left-click and drag to pan.")

    # --- ИЗМЕНЕНИЕ: Возвращаем старую, интуитивную логику панорамирования ---
    def move_start(self, event):
        """Запоминает начальную позицию для перемещения с помощью scan_mark."""
        self.canvas.scan_mark(event.x, event.y)

    def move_move(self, event):
        """Перемещает холст вслед за курсором."""
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_mousewheel(self, event):
        factor = 0
        if event.num == 4 or event.delta > 0: factor = 1.1
        elif event.num == 5 or event.delta < 0: factor = 0.9
        if factor: self._zoom(factor, self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))

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

    # --- Методы для работы с данными и отрисовки (без изменений) ---
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
        self.task_info.clear()
        self._clear_info_label()
        
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
        max_task_duration = 0
        for row in data:
            duration = row[2] - row[1]
            if duration > max_task_duration:
                max_task_duration = duration
        
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
                self.canvas.create_rectangle(
                    0, y_lane_start, canvas_width, y_lane_start + LANE_HEIGHT,
                    fill='#f0f0f0', outline=''
                )
            self.canvas.create_line(
                0, y_lane_start + LANE_HEIGHT, canvas_width, y_lane_start + LANE_HEIGHT,
                fill='lightgrey', dash=(2, 2)
            )

            self.canvas.create_text(
                LEFT_MARGIN - 10, y_lane_start + LANE_HEIGHT / 2, text=layer_name, anchor=tk.E,
                font=("Arial", int(self.font_sizes['layer_name'])), tags="layer_name_text"
            )
            
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

                rect_id = self.canvas.create_rectangle(x0, y0, x1, y0 + SUB_BAR_HEIGHT, fill=color, outline='black', width=1, tags=("task_bar",))
                
                duration = end - start
                self.task_info[rect_id] = {
                    'layer': layer_name,
                    'record': record_id,
                    'duration': duration,
                    'start': start,
                    'end': end
                }
                
                label_text = f"R:{record_id} ({duration:.2f}s)"
                self.canvas.create_text(
                    (x0 + x1) / 2, y0 + SUB_BAR_HEIGHT / 2, text=label_text, fill='white',
                    font=("Arial", int(self.font_sizes['bar_label']), "bold"), tags="bar_label_text"
                )

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
            self.canvas.create_text(
                x_pos, PADDING - 20, text=f"{time_val:.2f}", anchor=tk.N,
                font=("Arial", int(self.font_sizes['axis_label'])), tags="axis_label_text"
            )

    def _draw_legend(self, data, layers, num_records):
        PADDING, LEFT_MARGIN = 60, 200
        SUB_BAR_HEIGHT, SUB_BAR_PADDING = 20, 5
        LANE_HEIGHT = (SUB_BAR_HEIGHT + SUB_BAR_PADDING) * num_records
        graph_height = PADDING + len(layers) * (LANE_HEIGHT + SUB_BAR_PADDING)

        LEGEND_TOP_MARGIN, LEGEND_ITEM_HEIGHT = 40, 25
        legend_y_start = graph_height + LEGEND_TOP_MARGIN
        legend_x = LEFT_MARGIN
        self.canvas.create_text(
            legend_x, legend_y_start, text="Legend:", anchor=tk.W,
            font=("Arial", int(self.font_sizes['legend_title']), "bold"), tags="legend_title_text"
        )
        
        sorted_records = sorted(list(set(row[3] for row in data)))
        for i, record_id in enumerate(sorted_records):
            color = self.get_record_color(record_id)
            y = legend_y_start + LEGEND_ITEM_HEIGHT + i * LEGEND_ITEM_HEIGHT
            self.canvas.create_rectangle(legend_x, y, legend_x + 20, y + 20, fill=color, outline='black')
            self.canvas.create_text(
                legend_x + 30, y + 10, text=f"RecordID #{record_id}", anchor=tk.W,
                font=("Arial", int(self.font_sizes['legend_item'])), tags="legend_item_text"
            )

if __name__ == "__main__":
    root = tk.Tk()
    app = GanttChartApp(root)
    root.mainloop()