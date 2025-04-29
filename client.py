import sys
import socket
import json
import time
from collections import deque
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QDoubleSpinBox, QPushButton,
                             QSlider, QSplitter)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.animation import FuncAnimation
from threading import Thread


class RealTimePlot(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('Sine Wave Visualizer')
        self.setGeometry(100, 100, 1200, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(10, 10, 10, 10)

        # Элементы управления
        self.amp_label = QLabel('Amplitude:')
        self.amp_spin = QDoubleSpinBox()
        self.amp_spin.setRange(0.1, 10.0)
        self.amp_spin.setValue(1.0)
        self.amp_spin.setSingleStep(0.1)

        self.freq_label = QLabel('Frequency (Hz):')
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0.1, 10.0)
        self.freq_spin.setValue(1.0)
        self.freq_spin.setSingleStep(0.1)

        self.update_btn = QPushButton('Update Parameters')
        self.update_btn.clicked.connect(self.update_parameters)

        # Слайдер для прокрутки
        self.scroll_label = QLabel('Time Scroll:')
        self.scroll_slider = QSlider()
        self.scroll_slider.setOrientation(1)
        self.scroll_slider.setRange(0, 100)
        self.scroll_slider.setValue(0)
        self.scroll_slider.valueChanged.connect(self.update_scroll)

        control_layout.addWidget(self.amp_label)
        control_layout.addWidget(self.amp_spin)
        control_layout.addWidget(self.freq_label)
        control_layout.addWidget(self.freq_spin)
        control_layout.addWidget(self.update_btn)
        control_layout.addWidget(self.scroll_label)
        control_layout.addWidget(self.scroll_slider)
        control_layout.addStretch()

        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_xlabel('Time (relative)')
        self.ax.set_ylabel('Amplitude')
        self.ax.set_title('Sine Wave')
        self.ax.grid(True)

        self.x_data = deque()
        self.y_data = deque()
        self.line, = self.ax.plot([], [], 'b-', linewidth=2)

        splitter = QSplitter()
        splitter.addWidget(control_panel)
        splitter.addWidget(self.canvas)
        splitter.setSizes([300, 900])
        main_layout.addWidget(splitter)

        self.start_time = time.time()
        self.current_xlim = [-10, 0]  # Начинаем с -10 до 0 (право-лево)
        self.auto_scroll = True

        # Подключение к серверу
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False
        self.connect_to_server()

        # Анимация
        self.animation = FuncAnimation(self.figure, self.update_plot,
                                       interval=50, blit=True)

    def connect_to_server(self):
        try:
            self.client_socket.connect(('localhost', 5000))
            self.connected = True

            self.receive_thread = Thread(target=self.receive_data)
            self.receive_thread.daemon = True
            self.receive_thread.start()
        except ConnectionRefusedError:
            print("Failed to connect to server")
            self.connected = False

    def receive_data(self):
        buffer = ""
        while self.connected:
            try:
                data = self.client_socket.recv(4096)
                if not data:
                    break

                buffer += data.decode('utf-8')

                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    self.process_message(message)

            except (ConnectionResetError, BrokenPipeError):
                print("Disconnected from server")
                self.connected = False
                break
            except Exception as e:
                print(f"Error receiving data: {e}")
                self.connected = False
                break

    def process_message(self, message):
        try:
            data = json.loads(message)
            rel_time = data['time'] - self.start_time

            # Добавляем данные (новые точки появляются справа)
            self.x_data.append(rel_time)
            self.y_data.append(data['value'])

            # Автопрокрутка, если слайдер в крайнем левом положении
            if self.scroll_slider.value() == 0:
                self.current_xlim = [rel_time - 10, rel_time]

        except json.JSONDecodeError as e:
            print(f"Error decoding message: {e}")

    def update_plot(self, frame):
        if self.x_data and self.y_data:
            self.line.set_data(self.x_data, self.y_data)

            if len(self.x_data) > 1:
                if self.auto_scroll:
                    latest_time = self.x_data[-1]
                    self.ax.set_xlim(latest_time - 10, latest_time)
                else:
                    self.ax.set_xlim(self.current_xlim[0], self.current_xlim[1])

                visible_indices = [i for i, x in enumerate(self.x_data)
                                   if self.current_xlim[0] <= x <= self.current_xlim[1]]
                if visible_indices:
                    visible_y = [self.y_data[i] for i in visible_indices]
                    y_min = min(visible_y) * 1.1
                    y_max = max(visible_y) * 1.1
                    self.ax.set_ylim(y_min, y_max)

        self.canvas.draw()
        return self.line,

    def update_scroll(self, value):
        if value == 0:
            self.auto_scroll = True
        else:
            self.auto_scroll = False
            if len(self.x_data) > 1:
                total_range = self.x_data[-1] - self.x_data[0]
                ratio = value / self.scroll_slider.maximum()
                window_start = self.x_data[0] + ratio * (total_range - 10)
                self.current_xlim = [window_start, window_start + 10]
                self.canvas.draw()

    def update_parameters(self):
        if not self.connected:
            return

        params = {
            'amplitude': self.amp_spin.value(),
            'frequency': self.freq_spin.value()
        }

        try:
            self.client_socket.send((json.dumps(params) + '\n').encode('utf-8'))
        except Exception as e:
            print(f"Error sending parameters: {e}")
            self.connected = False

    def closeEvent(self, event):
        if self.connected:
            self.client_socket.close()
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = RealTimePlot()
    window.show()
    sys.exit(app.exec_())