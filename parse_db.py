import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from collections import defaultdict

class GanttChartApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gantt Chart - Zoom & Pan")
        self.root.minsize(800, 600)

        self.record_colors = {}
        self.color_palette = [
            '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
            '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac'
        ]
        self.DEFAULT_FONT_SIZES = {
            'layer_name': 10,
            'axis_label': 8,
            'bar_label': 9,
            'legend_title': 12,
            'legend_item': 10
        }
        self.font_sizes = self.DEFAULT_FONT_SIZES.copy()

        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.start_button = ttk.Button(self.main_frame, text="Start / Refresh", command=self.update_chart)
        self.start_button.pack(pady=5)

        self.canvas = tk.Canvas(self.main_frame, bg='white')
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self.move_start)
        self.canvas.bind("<B1-Motion>", self.move_move)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)

        self.update_chart()

    def move_start(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def move_move(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_mousewheel(self, event):
        factor = 0
        if event.num == 4:
            factor = 1.1
        elif event.num == 5:
            factor = 0.9
        elif event.delta > 0:
            factor = 1.1
        elif event.delta < 0:
            factor = 0.9
        
        if factor:
            self._zoom(factor, event.x, event.y)

    def _zoom(self, factor, x, y):
        self.canvas.scale("all", x, y, factor, factor)
        
        for key in self.font_sizes:
            self.font_sizes[key] *= factor
        
        self._update_text_fonts()
        
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.config(scrollregion=bbox)

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
            cursor.execute("SELECT Name, Start, End, RecordID FROM Nodes ORDER BY RecordID, SeqNum")
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

        PADDING, LEFT_MARGIN, TIMELINE_WIDTH = 60, 200, 2500
        scale_width = TIMELINE_WIDTH
        
        SUB_BAR_HEIGHT, SUB_BAR_PADDING = 20, 5
        LANE_HEIGHT = (SUB_BAR_HEIGHT + SUB_BAR_PADDING) * num_records
        
        for i, layer_name in enumerate(layers):
            y_lane_start = PADDING + i * (LANE_HEIGHT + SUB_BAR_PADDING)
            self.canvas.create_text(
                LEFT_MARGIN - 10, y_lane_start + LANE_HEIGHT / 2, 
                text=layer_name, anchor=tk.E, 
                font=("Arial", int(self.font_sizes['layer_name'])), 
                tags="layer_name_text"
            )
        
        for i, layer_name in enumerate(layers):
            y_lane_start = PADDING + i * (LANE_HEIGHT + SUB_BAR_PADDING)
            for task in tasks_by_layer[layer_name]:
                record, start, end = task['record'], task['start'], task['end']
                color = self.get_record_color(record)
                
                v_index = record_to_v_index.get(record, 0)
                y0 = y_lane_start + v_index * (SUB_BAR_HEIGHT + SUB_BAR_PADDING)
                
                x0 = LEFT_MARGIN + (start - min_time) / total_duration * scale_width
                x1 = LEFT_MARGIN + (end - min_time) / total_duration * scale_width

                self.canvas.create_rectangle(x0, y0, x1, y0 + SUB_BAR_HEIGHT, fill=color, outline='black', width=1)
                
                duration = end - start
                label_text = f"R:{record} ({duration:.2f}s)"
                self.canvas.create_text(
                    (x0 + x1) / 2, y0 + SUB_BAR_HEIGHT / 2, text=label_text, fill='white', 
                    font=("Arial", int(self.font_sizes['bar_label']), "bold"),
                    tags="bar_label_text"
                )
        
        self._draw_overlays(data, layers, num_records)
        
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.config(scrollregion=bbox)

    def _draw_overlays(self, data, layers, num_records):
        min_time = min(row[1] for row in data)
        max_time = max(row[2] for row in data)
        total_duration = max_time - min_time if max_time > min_time else 1

        PADDING, LEFT_MARGIN, TIMELINE_WIDTH = 60, 200, 2500
        scale_width = TIMELINE_WIDTH
        
        SUB_BAR_HEIGHT, SUB_BAR_PADDING = 20, 5
        LANE_HEIGHT = (SUB_BAR_HEIGHT + SUB_BAR_PADDING) * num_records
        graph_height = PADDING + len(layers) * (LANE_HEIGHT + SUB_BAR_PADDING)

        num_ticks = 10
        for i in range(num_ticks + 1):
            time_val = min_time + (total_duration * i / num_ticks)
            x_pos = LEFT_MARGIN + (time_val - min_time) / total_duration * scale_width
            self.canvas.create_line(x_pos, PADDING - 10, x_pos, graph_height, fill='lightgrey', dash=(2, 2))
            self.canvas.create_text(
                x_pos, PADDING - 20, text=f"{time_val:.2f}", anchor=tk.N, 
                font=("Arial", int(self.font_sizes['axis_label'])),
                tags="axis_label_text"
            )

        LEGEND_TOP_MARGIN, LEGEND_ITEM_HEIGHT = 40, 25
        legend_y_start = graph_height + LEGEND_TOP_MARGIN
        legend_x = LEFT_MARGIN
        self.canvas.create_text(
            legend_x, legend_y_start, text="Legend:", anchor=tk.W, 
            font=("Arial", int(self.font_sizes['legend_title']), "bold"),
            tags="legend_title_text"
        )
        
        sorted_records = sorted(list(set(row[3] for row in data)))
        for i, record_id in enumerate(sorted_records):
            color = self.get_record_color(record_id)
            y = legend_y_start + LEGEND_ITEM_HEIGHT + i * LEGEND_ITEM_HEIGHT
            self.canvas.create_rectangle(legend_x, y, legend_x + 20, y + 20, fill=color, outline='black')
            self.canvas.create_text(
                legend_x + 30, y + 10, text=f"RecordID #{record_id}", anchor=tk.W,
                font=("Arial", int(self.font_sizes['legend_item'])),
                tags="legend_item_text"
            )

if __name__ == "__main__":
    root = tk.Tk()
    app = GanttChartApp(root)
    root.mainloop()