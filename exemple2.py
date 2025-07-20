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
        self.current_slice = tensor_data
        self.is_drawing = False

        # --- UI Элементы ---
        self.fig = Figure(figsize=(6, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        plot_frame = ttk.Frame(self)
        plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        reset_button = ttk.Button(self, text="Reset View", command=self._reset_view)
        reset_button.pack(pady=10)

        self.canvas.mpl_connect('scroll_event', self._on_zoom)
        self.canvas.mpl_connect('draw_event', self._on_draw)

        # Вызываем первую отрисовку с небольшой задержкой, чтобы окно успело получить размеры
        self.after(100, lambda: self._update_view(is_new_tensor=True))

    def _on_zoom(self, event):
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
        
        self._update_view(is_new_tensor=False)

    def _reset_view(self):
        if self.current_slice is not None:
            self._update_view(is_new_tensor=True)

    def _on_draw(self, event):
        if self.is_drawing:
            return
        self._update_view(is_new_tensor=False)

    def _adaptive_pool(self, data, pool_size):
        block_shape = (pool_size, pool_size)
        if data.shape[0] < pool_size or data.shape[1] < pool_size:
            return data
        return block_reduce(data, block_size=block_shape, func=np.max)

    def _update_view(self, is_new_tensor=False):
        if self.is_drawing: return
        self.is_drawing = True

        # Сохраняем текущие пределы, если это не первая отрисовка
        if not is_new_tensor:
            xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()

        self.ax.clear()

        # --- Логика адаптивного пулинга ---
        # Если это первая отрисовка, устанавливаем пределы на весь срез
        if is_new_tensor:
            h, w = self.current_slice.shape
            view_xlim = (-0.5, w - 0.5)
        else:
            view_xlim = xlim
            
        view_width_data = view_xlim[1] - view_xlim[0]
        
        # --- ГЛАВНОЕ ИСПРАВЛЕНИЕ ---
        # Получаем ширину именно области графика (Axes), а не всего холста (Canvas)
        ax_width_pixels = self.ax.get_window_extent().width
        
        if ax_width_pixels <= 1: # Защита от вызова до полной отрисовки окна
            self.is_drawing = False
            return

        data_pixels_per_screen_pixel = view_width_data / ax_width_pixels
        
        pool_size = 1
        # Порог 1.1 означает, что как только мы пытаемся впихнуть больше ~1.1 пикселя данных
        # в один пиксель экрана, мы включаем пулинг.
        if data_pixels_per_screen_pixel > 1.1:
            pool_size = int(np.ceil(data_pixels_per_screen_pixel))
        
        # --- ОТЛАДОЧНЫЙ ВЫВОД В КОНСОЛЬ ---
        print(f"Data/Pixel Ratio: {data_pixels_per_screen_pixel:.2f} -> Pool Size: {pool_size}")

        if pool_size > 1:
            display_data = self._adaptive_pool(self.current_slice, pool_size)
            pool_title = f" (Pooled {pool_size}x{pool_size})"
            extent = (-0.5, self.current_slice.shape[1] - 0.5, self.current_slice.shape[0] - 0.5, -0.5)
        else:
            display_data = self.current_slice
            pool_title = " (Original Resolution)"
            extent = None

        # --- Отрисовка ---
        im = self.ax.imshow(display_data, cmap='viridis', interpolation='nearest', extent=extent)
        
        if not hasattr(self, 'colorbar') or self.colorbar.ax is None or self.colorbar.ax.figure != self.fig:
             self.colorbar = self.fig.colorbar(im, ax=self.ax)
        else:
            self.colorbar.update_normal(im)

        self.ax.set_title(f"Tensor Slice{pool_title}")
        
        if is_new_tensor:
            h, w = self.current_slice.shape
            self.ax.set_xlim(-0.5, w - 0.5)
            self.ax.set_ylim(h - 0.5, -0.5)
        else:
            self.ax.set_xlim(xlim)
            self.ax.set_ylim(ylim)

        self.canvas.draw()
        self.is_drawing = False


def create_test_matrix(size=100):
    matrix = np.zeros((size, size))
    for i in range(size):
        for j in range(size // 2):
            if (i + j) % 2 == 1:
                matrix[i, j] = 1
    gradient = np.linspace(0, 1, size // 2)
    for i in range(size):
        matrix[i, size // 2:] = gradient
    return matrix

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Standalone Tensor Viewer Test")
    root.geometry("800x800")

    test_tensor = create_test_matrix(size=256)
    viewer = StandaloneTensorViewer(root, tensor_data=test_tensor)
    
    root.mainloop()