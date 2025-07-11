import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from collections import defaultdict

# Импорты для Matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.patches as mpatches

class GanttChartApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Диаграмма Ганта (Matplotlib)")
        self.root.minsize(900, 700)

        # --- Цвета для разных записей (Record) ---
        # Matplotlib имеет свои встроенные палитры, которые мы будем использовать
        self.color_map = plt.get_cmap('tab10') # Популярная палитра на 10 цветов

        # --- Создание виджетов ---
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.start_button = ttk.Button(self.main_frame, text="Start / Обновить диаграмму", command=self.update_chart)
        self.start_button.pack(pady=5)

        # --- Создание холста для Matplotlib ---
        # Создаем фигуру и оси Matplotlib
        self.fig, self.ax = plt.subplots(figsize=(10, 6), dpi=100)
        
        # Создаем специальный холст Tkinter для встраивания фигуры Matplotlib
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.main_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Первоначальная загрузка и отрисовка
        self.update_chart()

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
        """Основная функция: получает данные и вызывает отрисовку."""
        data = self.fetch_data_from_db()
        if data:
            self.draw_gantt_matplotlib(data)
        else:
            # Очищаем оси, если данных нет
            self.ax.clear()
            self.ax.text(0.5, 0.5, "Нет данных для отображения", 
                         horizontalalignment='center', verticalalignment='center', 
                         transform=self.ax.transAxes, fontsize=16)
            self.canvas.draw()

    def draw_gantt_matplotlib(self, data):
        """Отрисовывает диаграмму Ганта с помощью Matplotlib."""
        
        # --- 1. Очистка и подготовка данных ---
        self.ax.clear() # Очищаем предыдущий график

        tasks_by_layer = defaultdict(list)
        all_records = sorted(list(set(row[3] for row in data)))
        
        for name, start, end, record in data:
            tasks_by_layer[name].append({'start': start, 'end': end, 'record': record})

        layer_names = sorted(tasks_by_layer.keys(), reverse=True) # reverse=True, чтобы первый слой был наверху
        
        # --- 2. Отрисовка блоков (задач) ---
        y_ticks = []
        y_labels = []

        for i, layer_name in enumerate(layer_names):
            y_pos = i * 10 # Основная позиция Y для дорожки слоя
            y_ticks.append(y_pos)
            y_labels.append(layer_name)

            for task in tasks_by_layer[layer_name]:
                record_id = task['record']
                start_time = task['start']
                duration = task['end'] - start_time
                
                # Matplotlib для Ганта использует (y_position, start_time), duration
                # Мы добавляем небольшое смещение для каждого record, чтобы они не накладывались
                record_index = all_records.index(record_id)
                vertical_offset = (record_index - (len(all_records) - 1) / 2) * 1.5
                
                self.ax.barh(
                    y=y_pos + vertical_offset, 
                    width=duration, 
                    left=start_time, 
                    height=1.2, 
                    align='center',
                    color=self.color_map(record_index),
                    edgecolor='black'
                )

        # --- 3. Настройка внешнего вида графика ---
        self.ax.set_yticks(y_ticks)
        self.ax.set_yticklabels(y_labels)
        
        self.ax.set_xlabel('Время (с)')
        self.ax.set_title('Диаграмма Ганта выполнения слоев')
        
        # Улучшаем сетку
        self.ax.grid(True, which='major', axis='x', linestyle='--', linewidth=0.5)
        self.ax.grid(False, which='major', axis='y')

        # --- 4. Создание легенды ---
        legend_patches = []
        for i, record_id in enumerate(all_records):
            patch = mpatches.Patch(color=self.color_map(i), label=f'Record #{record_id}')
            legend_patches.append(patch)
        
        self.ax.legend(handles=legend_patches, bbox_to_anchor=(1.02, 1), loc='upper left', borderaxespad=0.)

        # Оптимизируем расположение элементов, чтобы ничего не обрезалось
        self.fig.tight_layout(rect=[0, 0, 0.9, 1]) # Оставляем место справа для легенды

        # --- 5. Обновление холста Tkinter ---
        self.canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    app = GanttChartApp(root)
    root.mainloop()