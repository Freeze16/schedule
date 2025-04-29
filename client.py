import sys
import socket
import json
from collections import deque
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QDoubleSpinBox, QPushButton)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.animation import FuncAnimation
from threading import Thread


class RealTimePlot(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Visualizer')
        self.setGeometry(100, 100, 800, 500)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(10, 10, 10, 10)

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

        control_layout.addWidget(self.amp_label)
        control_layout.addWidget(self.amp_spin)
        control_layout.addWidget(self.freq_label)
        control_layout.addWidget(self.freq_spin)
        control_layout.addWidget(self.update_btn)
        control_layout.addStretch()

        # График
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Amplitude')
        self.ax.set_title('Real-time Sine Wave')
        self.ax.grid(True)

        self.max_points = 500
        self.x_data = deque(maxlen=self.max_points)
        self.y_data = deque(maxlen=self.max_points)
        self.line, = self.ax.plot([], [], 'b-')

        main_layout.addWidget(control_panel, stretch=1)
        main_layout.addWidget(self.canvas, stretch=3)

        # Подключение к серверу
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False
        self.connect_to_server()

        self.animation = FuncAnimation(self.figure, self.update_plot,
                                       interval=20, blit=True)

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
            self.x_data.append(data['time'])
            self.y_data.append(data['value'])
        except json.JSONDecodeError as e:
            print(f"Error decoding message: {e}")

    def update_plot(self, frame):
        if self.x_data and self.y_data:
            self.line.set_data(self.x_data, self.y_data)
            self.ax.relim()
            self.ax.autoscale_view(True, True, True)
            self.canvas.draw()

        return self.line,

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