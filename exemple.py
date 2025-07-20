import tkinter as tk
from tkinter import ttk
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from skimage.measure import block_reduce # Для max-пулинга

class StandaloneTensorViewer(ttk.Frame):
    def __init__(self, parent, tensor_data):
        super().__init__(parent)
        self.pack(fill="both", expand=True)

        self.tensor = tensor_data
        self.current_slice = tensor_data # В этом примере у нас сразу 2D срез
        self.is_drawing = False

        # --- UI Элементы ---
        self.fig = Figure(figsize=(6, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        plot_frame = ttk.Frame(self)
        plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        # Добавляем стандартную панель matplotlib для навигации
        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Кнопка сброса вида
        reset_button = ttk.Button(self, text="Reset View", command=self._reset_view)
        reset_button.pack(pady=10)

        # Привязка событий мыши
        self.canvas.mpl_connect('scroll_event', self._on_zoom)
        # Этот обработчик нужен, чтобы перерисовывать с нужным пулингом при панорамировании
        self.canvas.mpl_connect('draw_event', self._on_draw)

        # Первоначальная отрисовка
        self._update_view(is_new_tensor=True)

    def _on_zoom(self, event):
        """Обрабатывает зум колесом мыши, изменяя пределы осей."""
        if event.xdata is None or event.ydata is None: return

        factor = 1.5 if event.button == 'up' else 1/1.5
        cur_xlim, cur_ylim = self.ax.get_xlim(), self.ax.get_ylim()
        xdata, ydata = event.xdata, event.ydata
        
        new_width = (cur_xlim[1] - cur_xlim[0]) / factor
        new_height = (cur_ylim[1] - cur_ylim[0]) / factor
        
        rel_x = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
        rel_y = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])
        
        self.ax.set_xlim([xdata - new_width * (1 - rel_x), xdata + new_width * rel_x])
        self.ax.set_ylim([ydata - new_height * (1 - rel_y), ydata + new_height * rel_y])
        
        # Вместо прямой перерисовки, мы вызываем _update_view, который сам решит, нужен ли пулинг
        self._update_view(is_new_tensor=False)

    def _reset_view(self):
        """Сбрасывает зум и панорамирование к исходному виду."""
        if self.current_slice is not None:
            h, w = self.current_slice.shape
            self.ax.set_xlim(-0.5, w - 0.5)
            self.ax.set_ylim(h - 0.5, -0.5) # imshow инвертирует ось Y
            self._update_view(is_new_tensor=False)

    def _on_draw(self, event):
        """Перехватывает событие перерисовки (например, после панорамирования) и обновляет пулинг."""
        # Флаг is_drawing предотвращает бесконечную рекурсию, т.к. _update_view тоже вызывает draw()
        if self.is_drawing:
            return
        self._update_view(is_new_tensor=False)

    def _adaptive_pool(self, data, pool_size):
        """Выполняет 2D Max Pooling с помощью scikit-image."""
        # Форма блока для пулинга
        block_shape = (pool_size, pool_size)
        
        # Проверяем, достаточно ли велика матрица для такого пулинга
        if data.shape[0] < pool_size or data.shape[1] < pool_size:
            return data # Возвращаем как есть, если слишком мала
            
        # block_reduce применяет функцию (np.max) к непересекающимся блокам
        return block_reduce(data, block_size=block_shape, func=np.max)

    def _update_view(self, is_new_tensor=False):
        """Основная функция отрисовки: применяет пулинг и рисует."""
        if self.is_drawing: return
        self.is_drawing = True

        # Сохраняем текущие пределы, если это не первая отрисовка
        if not is_new_tensor:
            xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()

        self.ax.clear()

        # --- Логика адаптивного пулинга ---
        # 1. Определяем, сколько "пикселей данных" приходится на один пиксель экрана
        # Если это первая отрисовка, считаем, что виден весь срез
        view_xlim = self.ax.get_xlim() if not is_new_tensor else (-0.5, self.current_slice.shape[1] - 0.5)
        view_width_data = view_xlim[1] - view_xlim[0]
        ax_width_pixels = self.ax.get_window_extent().width
        
        # Защита от деления на ноль при первом рендеринге
        data_pixels_per_screen_pixel = view_width_data / ax_width_pixels if ax_width_pixels > 0 else 1
        
        # 2. Вычисляем размер окна пулинга
        pool_size = 1
        # Если на один пиксель экрана приходится больше 1.5 пикселей данных, включаем пулинг
        if data_pixels_per_screen_pixel > 1.5:
            pool_size = int(np.ceil(data_pixels_per_screen_pixel))
        
        # 3. Применяем пулинг
        if pool_size > 1:
            display_data = self._adaptive_pool(self.current_slice, pool_size)
            pool_title = f" (Pooled {pool_size}x{pool_size})"
            # extent нужен, чтобы растянуть уменьшенное изображение на исходные координаты
            extent = (-0.5, self.current_slice.shape[1] - 0.5, self.current_slice.shape[0] - 0.5, -0.5)
        else:
            display_data = self.current_slice
            pool_title = " (Original Resolution)"
            extent = None

        # --- Отрисовка ---
        im = self.ax.imshow(display_data, cmap='viridis', interpolation='nearest', extent=extent)
        
        # Обновляем colorbar
        if not hasattr(self, 'colorbar') or self.colorbar.ax is None or self.colorbar.ax.figure != self.fig:
             self.colorbar = self.fig.colorbar(im, ax=self.ax)
        else:
            self.colorbar.update_normal(im)

        self.ax.set_title(f"Tensor Slice{pool_title}")
        
        # Восстанавливаем пределы осей, если это была перерисовка, а не первая загрузка
        if is_new_tensor:
            self._reset_view()
        else:
            self.ax.set_xlim(xlim)
            self.ax.set_ylim(ylim)

        self.canvas.draw()
        self.is_drawing = False


def create_test_matrix(size=100):
    """Создает тестовую матрицу с разными паттернами."""
    matrix = np.zeros((size, size))
    
    # Левая половина - шахматная доска
    for i in range(size):
        for j in range(size // 2):
            if (i + j) % 2 == 1:
                matrix[i, j] = 1
                
    # Правая половина - градиент
    gradient = np.linspace(0, 1, size // 2)
    for i in range(size):
        matrix[i, size // 2:] = gradient
        
    return matrix

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Standalone Tensor Viewer Test")
    root.geometry("800x800")

    # Создаем тестовую матрицу
    test_tensor = create_test_matrix(size=256)

    # Создаем и запускаем наш виджет
    viewer = StandaloneTensorViewer(root, tensor_data=test_tensor)
    
    root.mainloop()