import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import random
from collections import defaultdict

class GanttChartApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Диаграмма Ганта для слоев")
        # ИЗМЕНЕНИЕ 1: Убираем фиксированный размер, задаем минимальный
        # self.root.geometry("1200x800") # <-- Удалено
        self.root.minsize(800, 600) # <-- Добавлено

        # --- Цвета для разных записей (Record) ---
        self.record_colors = {}
        self.color_palette = [
            '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
            '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac'
        ]

        # --- Создание виджетов ---
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
            if len(self.color_palette) > 0:
                # Берем цвет из палитры по кругу, чтобы они не заканчивались
                self.record_colors[record_id] = self.color_palette[len(self.record_colors) % len(self.color_palette)]
            else:
                r = lambda: random.randint(0, 255)
                self.record_colors[record_id] = f'#{r():02x}{r():02x}{r():02x}'
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

        # --- 1. Подготовка данных и параметров ---
        
        # ИЗМЕНЕНИЕ 2: Группируем задачи по слоям, чтобы управлять наложением
        tasks_by_layer = defaultdict(list)
        all_records = set()
        for name, start, end, record in data:
            tasks_by_layer[name].append({'start': start, 'end': end, 'record': record})
            all_records.add(record)

        layers = sorted(tasks_by_layer.keys())
        if not layers: return

        # Создаем карту для вертикального смещения каждого Record ID
        sorted_records = sorted(list(all_records))
        record_to_v_index = {rec_id: i for i, rec_id in enumerate(sorted_records)}
        num_records = len(sorted_records)

        min_time = min(row[1] for row in data)
        max_time = max(row[2] for row in data)
        total_duration = max_time - min_time if max_time > min_time else 1

        # Параметры отрисовки
        PADDING = 60
        LEFT_MARGIN = 200
        
        # ИЗМЕНЕНИЕ 3: Динамический расчет высоты "дорожки" слоя
        SUB_BAR_HEIGHT = 20  # Высота одного прямоугольника
        SUB_BAR_PADDING = 5   # Отступ между прямоугольниками внутри одной дорожки
        LANE_HEIGHT = (SUB_BAR_HEIGHT + SUB_BAR_PADDING) * num_records # Общая высота дорожки
        
        canvas_width = self.root.winfo_width() + 1000 # Делаем холст широким для скролла
        canvas_height = PADDING * 2 + len(layers) * (LANE_HEIGHT + SUB_BAR_PADDING)
        self.canvas.config(scrollregion=(0, 0, canvas_width, canvas_height))

        # --- 2. Отрисовка осей и сетки ---
        for i, layer_name in enumerate(layers):
            y_lane_start = PADDING + i * (LANE_HEIGHT + SUB_BAR_PADDING)
            
            # Центрируем название слоя по вертикали в его "дорожке"
            self.canvas.create_text(LEFT_MARGIN - 10, y_lane_start + LANE_HEIGHT / 2, 
                                    text=layer_name, anchor=tk.E, font=("Arial", 10))
            # Рисуем границы "дорожки"
            self.canvas.create_line(LEFT_MARGIN, y_lane_start, canvas_width, y_lane_start, fill='lightgrey')
        # Нижняя граница последней дорожки
        last_y = PADDING + len(layers) * (LANE_HEIGHT + SUB_BAR_PADDING)
        self.canvas.create_line(LEFT_MARGIN, last_y, canvas_width, last_y, fill='lightgrey')

        # Ось времени (X-axis)
        num_ticks = 10
        time_axis_y = PADDING - 5
        scale_width = canvas_width - LEFT_MARGIN - PADDING
        for i in range(num_ticks + 1):
            time_val = min_time + (total_duration * i / num_ticks)
            x_pos = LEFT_MARGIN + (time_val - min_time) / total_duration * scale_width
            
            self.canvas.create_line(x_pos, time_axis_y - 10, x_pos, canvas_height - PADDING, fill='lightgrey', dash=(2, 2))
            self.canvas.create_text(x_pos, time_axis_y - 15, text=f"{time_val:.2f}", anchor=tk.N, font=("Arial", 8))

        # --- 3. Отрисовка блоков (задач) ---
        for i, layer_name in enumerate(layers):
            y_lane_start = PADDING + i * (LANE_HEIGHT + SUB_BAR_PADDING)
            
            for task in tasks_by_layer[layer_name]:
                record = task['record']
                color = self.get_record_color(record)
                
                # ИЗМЕНЕНИЕ 4: Вычисляем вертикальное смещение для каждого Record
                v_index = record_to_v_index.get(record, 0)
                y0 = y_lane_start + v_index * (SUB_BAR_HEIGHT + SUB_BAR_PADDING)
                
                x0 = LEFT_MARGIN + (task['start'] - min_time) / total_duration * scale_width
                x1 = LEFT_MARGIN + (task['end'] - min_time) / total_duration * scale_width

                self.canvas.create_rectangle(x0, y0, x1, y0 + SUB_BAR_HEIGHT, fill=color, outline='black', width=1)
                
                duration = task['end'] - task['start']
                label_text = f"R:{record} ({duration:.2f}s)"
                # Уменьшаем шрифт, если блок слишком узкий
                font_size = 9 if (x1 - x0) > 50 else 7
                self.canvas.create_text((x0 + x1) / 2, y0 + SUB_BAR_HEIGHT / 2, text=label_text, fill='white', font=("Arial", font_size, "bold"))

        # --- 4. Отрисовка легенды ---
        legend_y = last_y + 40
        legend_x = LEFT_MARGIN
        self.canvas.create_text(legend_x, legend_y, text="Легенда:", anchor=tk.W, font=("Arial", 12, "bold"))
        
        for i, record_id in enumerate(sorted_records):
            color = self.record_colors[record_id]
            y = legend_y + 25 + i * 25
            self.canvas.create_rectangle(legend_x, y, legend_x + 20, y + 20, fill=color, outline='black')
            self.canvas.create_text(legend_x + 30, y + 10, text=f"Запись (Record) #{record_id}", anchor=tk.W)


if __name__ == "__main__":
    root = tk.Tk()
    app = GanttChartApp(root)
    root.mainloop()