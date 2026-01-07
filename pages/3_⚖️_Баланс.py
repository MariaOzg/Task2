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
# ⚙️ НАСТРОЙКИ (КЛЮЧЕВЫЕ СТРОКИ)
# ==========================================
SHEET_NAME = "Баланс"
# Названия строк, как они написаны в Столбце А (частичное совпадение)
ROW_ASSETS = "Активы"        # Итого Активы
ROW_LIABILITIES = "Пассивы"  # Итого Пассивы
ROW_EQUITY = "Капитал"       # Собственный капитал
ROW_CASH = "Денежные средства"
ROW_DEBT_TO_US = "Дебиторская задолженность" # Нам должны
ROW_DEBT_WE_OWE = "Кредиторская задолж-ть"   # Мы должны
ROW_ROE = "Рентабельность месячная ROE"      # Показатель эффективности
# ==========================================

st.set_page_config(page_title="Управленческий Баланс", layout="wide")

# --- 1. ЗАГРУЗКА ДАННЫХ ---
@st.cache_data(ttl=600)
def load_balance_data():
    # 👇 Вставьте вашу ссылку
    sheet_url = "https://docs.google.com/spreadsheets/d/1lXHUU5r8aq-S0c3fH0rY4Sh9lmiM9YT7ARp4lwEvgvA/edit?gid=1208323973#gid=1208323973"
    
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
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

# --- 2. ОЧИСТКА ---
def clean_financial_number(x):
    if not isinstance(x, str): return x
    # Убираем пробелы, %, заменяем запятые
    clean = x.replace(' ', '').replace(',', '.').replace('%', '').replace('\xa0', '')
    if clean == '' or clean == '-': return 0.0
    try:
        return float(clean)
    except:
        return 0.0

def process_data(df_raw):
    df = df_raw.copy()
    month_cols = df.columns[1:]
    for col in month_cols:
        df[col] = df[col].apply(clean_financial_number)
    return df, month_cols

# Поиск данных строки
def get_row_data(df, search_term):
    # Ищем строку, которая НАЧИНАЕТСЯ с search_term или полностью совпадает
    # (чтобы "Активы" не перепутались с "Внеоборотные активы")
    mask = df[df.columns[0]].astype(str).str.contains(search_term, case=False, na=False)
    row = df[mask]
    if not row.empty:
        # Берем первую найденную (обычно это итоговая строка)
        return row.iloc[0, 1:].values.astype(float)
    return None

# --- 3. ИНТЕРФЕЙС ---
st.title("⚖️ Управленческий Баланс")

df_raw = load_balance_data()
if df_raw.empty:
    st.warning("Данные не загружены")
    st.stop()

df, month_cols = process_data(df_raw)

# Извлекаем ряды данных для графиков
assets_data = get_row_data(df, ROW_ASSETS)
equity_data = get_row_data(df, ROW_EQUITY)
# Пассивы в балансе часто равны активам, но нам нужны именно Обязательства
# Если в таблице есть строка "Обязательства", лучше искать её. 
# Если нет, можно вычислить: Пассивы - Капитал.
# В вашем примере есть строка "Обязательства", попробуем найти её или "Пассивы"
liabilities_total_data = get_row_data(df, ROW_LIABILITIES) # Это сумма Капитал + Обязательства
obligations_data = get_row_data(df, "Обязательства") # Это чистые долги

cash_data = get_row_data(df, ROW_CASH)
receivables_data = get_row_data(df, ROW_DEBT_TO_US)
payables_data = get_row_data(df, ROW_DEBT_WE_OWE)
roe_data = get_row_data(df, ROW_ROE)

# --- KPI ПОСЛЕДНЕГО МЕСЯЦА ---
last_idx = -1
cur_assets = assets_data[last_idx] if assets_data is not None else 0
cur_equity = equity_data[last_idx] if equity_data is not None else 0
cur_cash = cash_data[last_idx] if cash_data is not None else 0
cur_roe = roe_data[last_idx] if roe_data is not None else 0

k1, k2, k3, k4 = st.columns(4)
k1.metric("💎 Всего Активов", f"{cur_assets:,.0f}".replace(",", " "))
k2.metric("🏛 Собственный Капитал", f"{cur_equity:,.0f}".replace(",", " "))
k3.metric("💵 Денег на счетах", f"{cur_cash:,.0f}".replace(",", " "))
k4.metric("📈 ROE (Рентабельность)", f"{cur_roe:.1f}%")

st.divider()

# --- ГРАФИКИ ВЕРХНЕГО УРОВНЯ ---
c1, c2 = st.columns(2)

with c1:
    st.subheader("Структура Баланса")
    # Сравниваем Активы vs (Капитал + Обязательства)
    if assets_data is not None and equity_data is not None:
        fig_bal = go.Figure()
        
        # Столбец 1: Активы
        fig_bal.add_trace(go.Bar(
            x=month_cols, y=assets_data, 
            name='Активы', marker_color='#2E86C1'
        ))
        
        # Столбец 2: Капитал + Обязательства (Стек)
        fig_bal.add_trace(go.Bar(
            x=month_cols, y=equity_data, 
            name='Капитал', marker_color='#27AE60'
        ))
        
        # Если нашли чистые обязательства, добавим их
        if obligations_data is not None:
             fig_bal.add_trace(go.Bar(
                x=month_cols, y=obligations_data, 
                name='Обязательства (Долги)', marker_color='#E74C3C'
            ))
        
        fig_bal.update_layout(barmode='group', height=400, title="Активы vs Пассивы")
        st.plotly_chart(fig_bal, use_container_width=True)
    else:
        st.info("Не найдены строки Активов или Капитала.")

with c2:
    st.subheader("Оборотный капитал")
    # Деньги + Дебиторка vs Кредиторка
    if receivables_data is not None and payables_data is not None:
        fig_work = go.Figure()
        
        fig_work.add_trace(go.Scatter(
            x=month_cols, y=receivables_data, fill='tozeroy',
            name='Дебиторка (Нам должны)', line=dict(color='#F1C40F')
        ))
        fig_work.add_trace(go.Scatter(
            x=month_cols, y=payables_data, fill='tozeroy',
            name='Кредиторка (Мы должны)', line=dict(color='#E74C3C')
        ))
        fig_work.add_trace(go.Scatter(
            x=month_cols, y=cash_data, 
            name='Деньги', line=dict(color='#2ECC71', width=3, dash='dot')
        ))
        
        fig_work.update_layout(height=400, title="Деньги и Долги")
        st.plotly_chart(fig_work, use_container_width=True)

# --- ГРАФИК ROE ---
if roe_data is not None:
    st.subheader("Эффективность собственников (ROE)")
    fig_roe = px.line(x=month_cols, y=roe_data, markers=True)
    fig_roe.update_traces(line_color='#8E44AD', line_width=3)
    fig_roe.update_layout(yaxis_title="%", xaxis_title="Месяц", height=300)
    # Добавляем зону "Хорошо" (например, выше 20%)
    fig_roe.add_hrect(y0=20, y1=100, line_width=0, fillcolor="green", opacity=0.1, annotation_text="Целевая зона")
    st.plotly_chart(fig_roe, use_container_width=True)

# --- ТАБЛИЦА ---
st.subheader("📋 Детальный Баланс")

with st.expander("🔎 Фильтр столбцов"):
    selected_months = st.multiselect("Выберите месяцы", month_cols, default=month_cols)

cols_to_show = [df.columns[0]] + list(selected_months)

# Функция раскраски
def highlight_balance(val):
    if isinstance(val, (int, float)):
        # В балансе минусов мало, но можно выделить 0 серым
        if val == 0: return 'color: lightgray'
    return ''

st.dataframe(
    df[cols_to_show].style
    .map(highlight_balance, subset=selected_months)
    .format("{:,.0f}", subset=selected_months),
    use_container_width=True,
    height=600,
    hide_index=True
)
