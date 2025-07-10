import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import random
from collections import defaultdict

class GanttChartApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Диаграмма Ганта для слоев")
        self.root.minsize(800, 600)

        self.record_colors = {}
        self.color_palette = [
            '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
            '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac'
        ]

        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.start_button = ttk.Button(self.main_frame, text="Start / Обновить диаграмму", command=self.update_chart)
        self.start_button.pack(pady=10)

        self.canvas = tk.Canvas(self.main_frame, bg='white')
        
        hbar = ttk.Scrollbar(self.main_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        vbar = ttk.Scrollbar(self.main_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas.config(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.update_chart()

    def get_record_color(self, record_id):
        if record_id not in self.record_colors:
            self.record_colors[record_id] = self.color_palette[len(self.record_colors) % len(self.color_palette)]
        return self.record_colors[record_id]

    def fetch_data_from_db(self):
        try:
            conn = sqlite3.connect('debug.db')
            cursor = conn.cursor()
            cursor.execute("SELECT Name, Start, End, Record FROM Nodes ORDER BY Record, SeqNum")
            data = cursor.fetchall()
            conn.close()
            return data
        except sqlite3.OperationalError:
            messagebox.showerror("Ошибка базы данных", 
                                 "Не удалось найти таблицу 'Nodes' в 'debug.db'.\n"
                                 "Убедитесь, что база данных существует и содержит правильную таблицу.")
            return None

    def update_chart(self):
        data = self.fetch_data_from_db()
        if data:
            self.draw_gantt(data)
        else:
            self.canvas.delete("all")
            self.canvas.create_text(400, 300, text="Нет данных для отображения.", font=("Arial", 16))

    def draw_gantt(self, data):
        self.canvas.delete("all")

        # --- 1. Подготовка данных ---
        tasks_by_layer = defaultdict(list)
        all_records = set()
        for name, start, end, record in data:
            tasks_by_layer[name].append({'start': start, 'end': end, 'record': record})
            all_records.add(record)

        layers = sorted(tasks_by_layer.keys())
        if not layers: return

        sorted_records = sorted(list(all_records))
        record_to_v_index = {rec_id: i for i, rec_id in enumerate(sorted_records)}
        num_records = len(sorted_records)

        min_time = min(row[1] for row in data)
        max_time = max(row[2] for row in data)
        total_duration = max_time - min_time if max_time > min_time else 1

        # --- 2. Расчет размеров и настройка холста ---
        PADDING = 60
        LEFT_MARGIN = 200
        
        # ИСПРАВЛЕНИЕ 1: Фиксированная ширина для временной шкалы
        TIMELINE_WIDTH = 2500  # Задаем константную ширину для рисования, чтобы избежать растягивания
        scale_width = TIMELINE_WIDTH # Ширина для масштабирования теперь постоянна
        canvas_width = LEFT_MARGIN + TIMELINE_WIDTH + PADDING # Общая ширина холста

        # Параметры для дорожек и легенды
        SUB_BAR_HEIGHT = 20
        SUB_BAR_PADDING = 5
        LANE_HEIGHT = (SUB_BAR_HEIGHT + SUB_BAR_PADDING) * num_records
        
        # ИСПРАВЛЕНИЕ 2: Расчет общей высоты холста с учетом легенды
        graph_height = PADDING + len(layers) * (LANE_HEIGHT + SUB_BAR_PADDING)
        
        LEGEND_TOP_MARGIN = 40
        LEGEND_ITEM_HEIGHT = 25
        LEGEND_BOTTOM_PADDING = 20
        legend_height = LEGEND_TOP_MARGIN + len(sorted_records) * LEGEND_ITEM_HEIGHT + LEGEND_BOTTOM_PADDING
        
        total_canvas_height = graph_height + legend_height

        # Устанавливаем scrollregion с правильными, полными размерами ДО отрисовки
        self.canvas.config(scrollregion=(0, 0, canvas_width, total_canvas_height))

        # --- 3. Отрисовка осей и сетки ---
        for i, layer_name in enumerate(layers):
            y_lane_start = PADDING + i * (LANE_HEIGHT + SUB_BAR_PADDING)
            self.canvas.create_text(LEFT_MARGIN - 10, y_lane_start + LANE_HEIGHT / 2, 
                                    text=layer_name, anchor=tk.E, font=("Arial", 10))
            self.canvas.create_line(LEFT_MARGIN, y_lane_start, canvas_width, y_lane_start, fill='lightgrey')
        
        last_y_lane = PADDING + len(layers) * (LANE_HEIGHT + SUB_BAR_PADDING)
        self.canvas.create_line(LEFT_MARGIN, last_y_lane, canvas_width, last_y_lane, fill='lightgrey')

        # Ось времени (X-axis)
        num_ticks = 10
        time_axis_y = PADDING - 5
        for i in range(num_ticks + 1):
            time_val = min_time + (total_duration * i / num_ticks)
            x_pos = LEFT_MARGIN + (time_val - min_time) / total_duration * scale_width
            
            self.canvas.create_line(x_pos, time_axis_y - 10, x_pos, total_canvas_height - PADDING, fill='lightgrey', dash=(2, 2))
            self.canvas.create_text(x_pos, time_axis_y - 15, text=f"{time_val:.2f}", anchor=tk.N, font=("Arial", 8))

        # --- 4. Отрисовка блоков (задач) ---
        for i, layer_name in enumerate(layers):
            y_lane_start = PADDING + i * (LANE_HEIGHT + SUB_BAR_PADDING)
            
            for task in tasks_by_layer[layer_name]:
                record = task['record']
                color = self.get_record_color(record)
                
                v_index = record_to_v_index.get(record, 0)
                y0 = y_lane_start + v_index * (SUB_BAR_HEIGHT + SUB_BAR_PADDING)
                
                x0 = LEFT_MARGIN + (task['start'] - min_time) / total_duration * scale_width
                x1 = LEFT_MARGIN + (task['end'] - min_time) / total_duration * scale_width

                self.canvas.create_rectangle(x0, y0, x1, y0 + SUB_BAR_HEIGHT, fill=color, outline='black', width=1)
                
                duration = task['end'] - task['start']
                label_text = f"R:{record} ({duration:.2f}s)"
                font_size = 9 if (x1 - x0) > 50 else 7
                self.canvas.create_text((x0 + x1) / 2, y0 + SUB_BAR_HEIGHT / 2, text=label_text, fill='white', font=("Arial", font_size, "bold"))

        # --- 5. Отрисовка легенды ---
        legend_y_start = graph_height + LEGEND_TOP_MARGIN
        legend_x = LEFT_MARGIN
        self.canvas.create_text(legend_x, legend_y_start, text="Legend:", anchor=tk.W, font=("Arial", 12, "bold"))
        
        for i, record_id in enumerate(sorted_records):
            color = self.get_record_color(record_id)
            y = legend_y_start + LEGEND_ITEM_HEIGHT + i * LEGEND_ITEM_HEIGHT
            self.canvas.create_rectangle(legend_x, y, legend_x + 20, y + 20, fill=color, outline='black')
            self.canvas.create_text(legend_x + 30, y + 10, text=f"Record #{record_id}", anchor=tk.W)


if __name__ == "__main__":
    root = tk.Tk()
    app = GanttChartApp(root)
    root.mainloop()