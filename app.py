import streamlit as st
import requests
import pandas as pd
# Removido matplotlib para evitar erros de dependência
from datetime import datetime, date

# Configuração da página
st.set_page_config(page_title="Histórico Climático", page_icon="🌦️")

st.title("🌦️ Histórico Climático - Open-Meteo")
st.markdown("""
Consulte dados históricos de temperatura e chuva de qualquer cidade.
Dados fornecidos por: [Open-Meteo Archive API](https://open-meteo.com/en/docs/historical-weather-api)
""")

# --- Entrada de Dados (Sidebar) ---
with st.sidebar:
    st.header("Configurações")
    city = st.text_input("Cidade", value="São Paulo")
    
    # Definindo limites da API (1940 até hoje)
    min_date = date(1940, 1, 1)
    max_date = date.today()

    # Datas padrão
    default_start = date(2023, 1, 1)
    default_end = date(2023, 1, 31)
    
    # Seletores de data com restrição de intervalo para evitar erros na API
    start_date = st.date_input(
        "Data Inicial", 
        value=default_start, 
        min_value=min_date, 
        max_value=max_date
    )
    
    end_date = st.date_input(
        "Data Final", 
        value=default_end, 
        min_value=min_date, 
        max_value=max_date
    )
    
    search_btn = st.button("Buscar Histórico")

# --- Funções ---
def get_coordinates(city_name):
    """Busca latitude e longitude da cidade."""
    try:
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {"name": city_name, "count": 1, "language": "pt", "format": "json"}
        response = requests.get(url, params=params)
        data = response.json()
        
        if "results" in data and len(data["results"]) > 0:
            result = data["results"][0]
            return result["latitude"], result["longitude"], result["country"]
        return None, None, None
    except Exception as e:
        st.error(f"Erro ao buscar coordenadas: {e}")
        return None, None, None

def plot_graph(df, city, country):
    """Gera os gráficos usando componentes nativos do Streamlit (sem Matplotlib)."""
    
    # Prepara os dados definindo a Data como índice para o eixo X
    chart_data = df.set_index("Data")
    
    st.subheader(f"🌡️ Temperatura em {city}, {country}")
    # Gráfico de Linha para Temperaturas
    st.line_chart(chart_data[["Máxima (°C)", "Mínima (°C)"]])

    st.subheader(f"🌧️ Precipitação em {city}, {country}")
    # Gráfico de Barra para Chuva
    st.bar_chart(chart_data[["Precipitação (mm)"]])

# --- Lógica Principal ---
if search_btn:
    if not city:
        st.warning("Por favor, digite o nome de uma cidade.")
    elif start_date > end_date:
        st.error("A data inicial não pode ser maior que a data final.")
    else:
        with st.spinner(f"Buscando dados para {city}..."):
            lat, lon, country = get_coordinates(city)
            
            if lat is None:
                st.error(f"Cidade '{city}' não encontrada.")
            else:
                try:
                    # API Request
                    archive_url = "https://archive-api.open-meteo.com/v1/archive"
                    params = {
                        "latitude": lat,
                        "longitude": lon,
                        "start_date": start_date.strftime("%Y-%m-%d"),
                        "end_date": end_date.strftime("%Y-%m-%d"),
                        "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"],
                        "timezone": "auto"
                    }
                    
                    response = requests.get(archive_url, params=params)
                    data = response.json()

                    if "error" in data:
                        st.error(f"Erro na API: {data['reason']}")
                    else:
                        # Processamento
                        daily_data = data["daily"]
                        df = pd.DataFrame({
                            "Data": pd.to_datetime(daily_data["time"]),
                            "Máxima (°C)": daily_data["temperature_2m_max"],
                            "Mínima (°C)": daily_data["temperature_2m_min"],
                            "Precipitação (mm)": daily_data["precipitation_sum"]
                        })

                        st.success(f"Dados encontrados para {city}, {country}!")
                        
                        # Exibir Gráficos
                        plot_graph(df, city, country)
                        
                        # Exibir Tabela de Dados (Opcional)
                        with st.expander("Ver dados brutos em tabela"):
                            st.dataframe(df)

                except Exception as e:
                    st.error(f"Ocorreu um erro: {e}")
else:
    st.info("Utilize a barra lateral para configurar sua pesquisa e clique em 'Buscar Histórico'.")
