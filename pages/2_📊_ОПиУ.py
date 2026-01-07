import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.graph_objects as go
import plotly.express as px

# --- БЛОК БЕЗОПАСНОСТИ ---
if "authentication_status" not in st.session_state or st.session_state["authentication_status"] is not True:
    st.warning("🔒 Доступ закрыт. Пожалуйста, войдите в систему на главной странице.")
    st.stop()

# ==========================================
# ⚙️ НАСТРОЙКИ
# ==========================================
SHEET_NAME = "ОПиУ"   # Имя вкладки в Google Таблице
# Ключевые слова для поиска строк (должны быть в Столбце А)
ROW_REVENUE = "Выручка"
ROW_NET_PROFIT = "Чистая прибыль"
ROW_MARGIN = "Маржинальный доход"
# ==========================================

st.set_page_config(page_title="P&L Отчет", layout="wide")

# --- 1. ЗАГРУЗКА ДАННЫХ ---
@st.cache_data(ttl=600)
def load_pnl_data():
    # 👇 Вставьте вашу ссылку
    sheet_url = "https://docs.google.com/spreadsheets/d/1lXHUU5r8aq-S0c3fH0rY4Sh9lmiM9YT7ARp4lwEvgvA/edit?gid=690406538#gid=690406538" 
    
    # --- Вставляем внутрь функции ---

    # 1. Обязательно определяем scope (иначе будет ошибка NameError)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    # 2. БЕРЕМ КЛЮЧИ ИЗ СЕЙФА
    creds_dict = dict(st.secrets["gcp_service_account"])

    # 3. Принудительно указываем тип (лечит ошибку "Unexpected credentials type")
    creds_dict["type"] = "service_account"

    # 4. Чиним переносы строк в ключе (лечит "Invalid JWT Signature")
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

    # 5. Создаем объект авторизации
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
# 2. Чиним переносы строк в ключе
if "private_key" in creds_dict:
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

# Создаем объект авторизации
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
        
    try:
        sheet = client.open_by_url(sheet_url).worksheet(SHEET_NAME)
    except:
        st.error(f"❌ Вкладка '{SHEET_NAME}' не найдена.")
        st.stop()
    
    all_values = sheet.get_all_values()
    if len(all_values) < 2: return pd.DataFrame()
    
    headers = all_values[0]
    if headers[0] == "": headers[0] = "Статья"
    
    df = pd.DataFrame(all_values[1:], columns=headers)
    return df

# --- 2. ОЧИСТКА ДАННЫХ ---
def clean_financial_number(x):
    if not isinstance(x, str): return x
    clean = x.replace(' ', '').replace(',', '.').replace('%', '').replace('\xa0', '')
    if clean == '' or clean == '-': return 0.0
    try:
        return float(clean)
    except:
        return 0.0

def process_pnl(df_raw):
    df = df_raw.copy()
    month_cols = df.columns[1:] # Все колонки, кроме первой (Статья)
    
    # Конвертируем цифры
    for col in month_cols:
        df[col] = df[col].apply(clean_financial_number)
        
    return df, month_cols

# --- 3. ИНТЕРФЕЙС ---
st.title("📊 Отчет о Прибылях и Убытках (P&L)")

df_raw = load_pnl_data()
if df_raw.empty:
    st.warning("Данные не загружены")
    st.stop()

df, month_cols = process_pnl(df_raw)

# --- ВЫДЕЛЕНИЕ КЛЮЧЕВЫХ СТРОК (Для графиков) ---
def get_row_data(df, search_term):
    # Ищем строку, содержащую ключевое слово
    row = df[df[df.columns[0]].astype(str).str.contains(search_term, case=False, na=False)]
    if not row.empty:
        # Возвращаем цифры первой найденной строки
        return row.iloc[0, 1:].values.astype(float)
    return None

revenue_data = get_row_data(df, ROW_REVENUE)
profit_data = get_row_data(df, ROW_NET_PROFIT)

# --- KPI ---
last_month_name = month_cols[-1]
last_col_idx = -1 

current_revenue = revenue_data[last_col_idx] if revenue_data is not None else 0
current_profit = profit_data[last_col_idx] if profit_data is not None else 0
profit_margin_percent = (current_profit / current_revenue * 100) if current_revenue != 0 else 0

st.subheader(f"Итоги за последний месяц ({last_month_name})")
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

kpi1.metric("💰 Выручка", f"{current_revenue:,.0f}".replace(",", " "))
kpi2.metric("📉 Чистая прибыль", f"{current_profit:,.0f}".replace(",", " "), 
            delta_color="normal" if current_profit > 0 else "inverse")
kpi3.metric("📊 Рентабельность", f"{profit_margin_percent:.1f}%")

total_year_profit = profit_data.sum() if profit_data is not None else 0
kpi4.metric("🏆 Прибыль (Год)", f"{total_year_profit:,.0f}".replace(",", " "))

st.divider()

# --- КОМБО-ГРАФИК ---
st.subheader("Динамика: Выручка vs Прибыль")

if revenue_data is not None and profit_data is not None:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=month_cols, y=revenue_data, name='Выручка', marker_color='#A7C7E7', opacity=0.6))
    fig.add_trace(go.Scatter(x=month_cols, y=profit_data, name='Чистая прибыль', 
                             line=dict(color='#2E86C1', width=4), mode='lines+markers'))

    fig.update_layout(height=500, xaxis_title="Месяц", yaxis_title="Сумма", template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("Не удалось найти строки для графика. Проверьте названия в коде (строки 18-20).")

# --- ТАБЛИЦА С ТЕПЛОВОЙ КАРТОЙ (ИСПРАВЛЕННАЯ) ---
st.subheader("📋 Детальная матрица")

with st.expander("🔎 Фильтр столбцов"):
    selected_months = st.multiselect("Выберите месяцы", month_cols, default=month_cols)

# Подготовка данных (берем столбцы: Статья + выбранные месяцы)
cols_to_show = [df.columns[0]] + list(selected_months)
df_display = df[cols_to_show]

# Функция раскраски (Проверяем, что значение - число)
def highlight_vals(val):
    if isinstance(val, (int, float)):
        if val < 0: return 'color: #D0312D; font-weight: bold' # Красный для убытков
        elif val > 0: return 'color: #228B22' # Зеленый для прибыли
    return ''

# Применяем стили ТОЛЬКО к колонкам с цифрами (selected_months)
# hide_index=True убирает номера строк 0, 1, 2...
st.dataframe(
    df_display.style
    .map(highlight_vals, subset=selected_months)
    .format("{:,.0f}", subset=selected_months),
    use_container_width=True,
    height=600,
    hide_index=True 
)
