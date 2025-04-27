# Сервер
import socket
import select
import time
import math
import json
from threading import Thread


class SineWaveServer:
    def __init__(self, host='localhost', port=5000):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)

        self.clients = []
        self.running = False

        self.amplitude = 1.0
        self.frequency = 1.0
        self.phase = 0
        self.sampling_rate = 100

    def start(self):
        self.running = True
        print(f"Server started on {self.host}:{self.port}")

        # Запускаем поток для генерации данных
        data_thread = Thread(target=self.generate_data)
        data_thread.daemon = True
        data_thread.start()

        # Основной цикл сервера
        try:
            while self.running:
                read_sockets, _, _ = select.select([self.server_socket], [], [], 0.1)

                for sock in read_sockets:
                    if sock == self.server_socket:
                        client_socket, client_address = self.server_socket.accept()
                        print(f"New connection from {client_address}")
                        self.clients.append(client_socket)

                self.check_client_messages()

        except KeyboardInterrupt:
            print("Server shutting down...")
        finally:
            self.stop()

    def generate_data(self):
        while self.running:
            t = time.time()
            value = self.amplitude * math.sin(2 * math.pi * self.frequency * t + self.phase)

            message = {
                'time': t,
                'value': value,
                'amplitude': self.amplitude,
                'frequency': self.frequency
            }
            message_str = json.dumps(message) + '\n'

            self.broadcast(message_str)
            time.sleep(1.0 / self.sampling_rate)

    def broadcast(self, message):
        disconnected_clients = []

        for client in self.clients:
            try:
                client.send(message.encode('utf-8'))
            except (ConnectionResetError, BrokenPipeError):
                disconnected_clients.append(client)

        for client in disconnected_clients:
            self.clients.remove(client)
            print(f"Client disconnected: {client.getpeername()}")

    def check_client_messages(self):
        if not self.clients:
            return

        read_sockets, _, _ = select.select(self.clients, [], [], 0)

        for sock in read_sockets:
            try:
                data = sock.recv(1024)
                if data:
                    self.handle_client_message(data.decode('utf-8').strip())
                else:
                    self.clients.remove(sock)
                    print(f"Client disconnected: {sock.getpeername()}")
            except (ConnectionResetError, BrokenPipeError):
                self.clients.remove(sock)
                print(f"Client disconnected: {sock.getpeername()}")

    def handle_client_message(self, message):
        try:
            params = json.loads(message)
            if 'amplitude' in params:
                self.amplitude = float(params['amplitude'])
            if 'frequency' in params:
                self.frequency = float(params['frequency'])

            print(f"Parameters updated: amplitude={self.amplitude}, frequency={self.frequency}")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error processing client message: {e}")

    def stop(self):
        self.running = False
        for client in self.clients:
            client.close()
        self.server_socket.close()
        print("Server stopped")


if __name__ == '__main__':
    server = SineWaveServer()
    server.start()