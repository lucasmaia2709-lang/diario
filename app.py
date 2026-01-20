import tkinter as tk
from tkinter import ttk, messagebox
import requests
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime

class WeatherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Histórico Climático - Open-Meteo")
        self.root.geometry("900x700")
        
        # Configuração de estilo
        style = ttk.Style()
        style.theme_use('clam')
        
        # --- Frame de Entrada (Input) ---
        input_frame = ttk.LabelFrame(root, text="Dados da Pesquisa", padding="20")
        input_frame.pack(fill="x", padx=15, pady=10)
        
        # Cidade
        ttk.Label(input_frame, text="Cidade:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.city_entry = ttk.Entry(input_frame, width=30)
        self.city_entry.grid(row=0, column=1, padx=5, pady=5)
        self.city_entry.insert(0, "São Paulo") # Valor padrão

        # Data Inicial
        ttk.Label(input_frame, text="Data Inicial (AAAA-MM-DD):").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.start_date_entry = ttk.Entry(input_frame, width=15)
        self.start_date_entry.grid(row=0, column=3, padx=5, pady=5)
        self.start_date_entry.insert(0, "2023-01-01")

        # Data Final
        ttk.Label(input_frame, text="Data Final (AAAA-MM-DD):").grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.end_date_entry = ttk.Entry(input_frame, width=15)
        self.end_date_entry.grid(row=1, column=3, padx=5, pady=5)
        self.end_date_entry.insert(0, "2023-01-31")

        # Botão Buscar
        search_btn = ttk.Button(input_frame, text="Buscar Histórico", command=self.fetch_data)
        search_btn.grid(row=0, column=4, rowspan=2, padx=15, ipady=10)

        # --- Frame de Resultados ---
        self.result_frame = ttk.Frame(root)
        self.result_frame.pack(fill="both", expand=True, padx=15, pady=5)
        
        # Área de texto para status/resumo
        self.status_label = ttk.Label(self.result_frame, text="Insira os dados e clique em buscar.", font=("Arial", 10))
        self.status_label.pack(pady=5)

        # Placeholder para o gráfico
        self.canvas = None

    def get_coordinates(self, city_name):
        """Busca latitude e longitude da cidade usando a API de Geocoding."""
        try:
            url = "https://geocoding-api.open-meteo.com/v1/search"
            params = {"name": city_name, "count": 1, "language": "pt", "format": "json"}
            response = requests.get(url, params=params)
            data = response.json()
            
            if "results" in data and len(data["results"]) > 0:
                result = data["results"][0]
                return result["latitude"], result["longitude"], result["country"]
            else:
                return None, None, None
        except Exception as e:
            messagebox.showerror("Erro de Conexão", f"Erro ao buscar coordenadas: {e}")
            return None, None, None

    def fetch_data(self):
        """Busca os dados históricos e gera o gráfico."""
        city = self.city_entry.get()
        start_date = self.start_date_entry.get()
        end_date = self.end_date_entry.get()

        # Validação básica
        if not city or not start_date or not end_date:
            messagebox.showwarning("Aviso", "Por favor, preencha todos os campos.")
            return

        # 1. Obter Coordenadas
        lat, lon, country = self.get_coordinates(city)
        if lat is None:
            messagebox.showerror("Erro", f"Cidade '{city}' não encontrada.")
            return

        self.status_label.config(text=f"Buscando dados para {city}, {country}...")
        self.root.update()

        # 2. Obter Histórico Climático
        try:
            archive_url = "https://archive-api.open-meteo.com/v1/archive"
            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": start_date,
                "end_date": end_date,
                "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"],
                "timezone": "auto"
            }
            
            response = requests.get(archive_url, params=params)
            data = response.json()

            if "error" in data:
                messagebox.showerror("Erro API", f"Erro na API: {data['reason']}")
                return

            # Processar dados com Pandas
            daily_data = data["daily"]
            df = pd.DataFrame({
                "Data": pd.to_datetime(daily_data["time"]),
                "Máxima (°C)": daily_data["temperature_2m_max"],
                "Mínima (°C)": daily_data["temperature_2m_min"],
                "Precipitação (mm)": daily_data["precipitation_sum"]
            })

            self.plot_graph(df, city, country)
            self.status_label.config(text=f"Dados carregados para {city}, {country} ({start_date} a {end_date})")

        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro ao processar os dados: {e}")

    def plot_graph(self, df, city, country):
        """Desenha o gráfico usando Matplotlib dentro do Tkinter."""
        
        # Limpar gráfico anterior se existir
        if self.canvas:
            self.canvas.get_tk_widget().destroy()

        # Criar a figura
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
        fig.suptitle(f"Clima Histórico: {city}, {country}", fontsize=14)

        # Gráfico de Temperatura (Máxima e Mínima)
        ax1.plot(df["Data"], df["Máxima (°C)"], color="red", label="Máxima", marker="o", markersize=4)
        ax1.plot(df["Data"], df["Mínima (°C)"], color="blue", label="Mínima", marker="o", markersize=4)
        ax1.set_ylabel("Temperatura (°C)")
        ax1.legend(loc="upper right")
        ax1.grid(True, linestyle="--", alpha=0.6)

        # Gráfico de Precipitação (Barras)
        ax2.bar(df["Data"], df["Precipitação (mm)"], color="skyblue", label="Chuva")
        ax2.set_ylabel("Precipitação (mm)")
        ax2.set_xlabel("Data")
        ax2.legend(loc="upper right")
        ax2.grid(True, linestyle="--", alpha=0.6, axis='y')

        # Formatar datas no eixo X
        fig.autofmt_xdate()

        # Integrar no Tkinter
        self.canvas = FigureCanvasTkAgg(fig, master=self.result_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

if __name__ == "__main__":
    root = tk.Tk()
    app = WeatherApp(root)
    root.mainloop()
