import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Crypto Commander Pro",
    page_icon="📈",
    layout="wide"
)

# --- 1. LOGIC TÍNH TOÁN & HÀM HỖ TRỢ ---

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50.0
    gains, losses = [], []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i-1]
        if delta > 0: gains.append(delta); losses.append(0)
        else: gains.append(0); losses.append(abs(delta))
    avg_gain = sum(gains[:period])/period
    avg_loss = sum(losses[:period])/period
    for i in range(period, len(prices)-1):
        avg_gain = (avg_gain*(period-1)+gains[i])/period
        avg_loss = (avg_loss*(period-1)+losses[i])/period
    if avg_loss == 0: return 100.0
    rs = avg_gain/avg_loss
    return 100 - (100/(1+rs))

def analyze_market_data(price, low_24h, high_24h, rsi_15m, rsi_4h):
    result = {}
    # A. Nhận định xu hướng
    action = "QUAN SÁT"
    color = "gray" 
    reason = "Thị trường đi ngang (Sideway)."
    
    if rsi_15m < 30:
        action = "MUA (Bắt đáy)"
        color = "green"
        reason = f"RSI 15m thấp ({rsi_15m:.1f}). Giá đang quá bán."
    elif rsi_15m > 70:
        action = "BÁN (Chốt lời)"
        color = "red"
        reason = f"RSI 15m cao ({rsi_15m:.1f}). Giá đang quá mua."
    
    # B. Entry/SL/TP
    entry_price = price
    if action == "QUAN SÁT": 
        entry_price = price * 0.99
        
    sl_price = low_24h * 0.99
    if entry_price <= sl_price: sl_price = entry_price * 0.95
    
    tp_price = entry_price + (entry_price - sl_price) * 1.5
    if tp_price > high_24h: tp_price = high_24h

    # C. Limit & Trailing
    limit_buy = low_24h * 1.005
    limit_sell = high_24h * 0.995
    activation_price = price * 1.01
    
    result.update({
        'action': action, 'color': color, 'reason': reason,
        'entry': entry_price, 'sl': sl_price, 'tp': tp_price,
        'limit_buy': limit_buy, 'limit_sell': limit_sell,
        'act_price': activation_price, 'callback': 2.0
    })
    return result

def fetch_usdt_rate():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=vnd"
        res = requests.get(url, timeout=5).json()
        return float(res['tether']['vnd'])
    except:
        return 26700.0

def run_analysis_logic(symbol):
    """Hàm chạy chính để lấy dữ liệu và phân tích"""
    pair = symbol if "-" in symbol else f"{symbol}-USDT"
    try:
        # Lấy dữ liệu OKX
        tick = requests.get(f"https://www.okx.com/api/v5/market/ticker?instId={pair}", timeout=5).json()['data'][0]
        last = float(tick['last']); low = float(tick['low24h']); high = float(tick['high24h'])
        
        c15 = requests.get(f"https://www.okx.com/api/v5/market/candles?instId={pair}&bar=15m&limit=25", timeout=5).json()['data']
        rsi_15 = calculate_rsi([float(c[4]) for c in c15][::-1])
        
        c4h = requests.get(f"https://www.okx.com/api/v5/market/candles?instId={pair}&bar=4H&limit=25", timeout=5).json()['data']
        rsi_4h = calculate_rsi([float(c[4]) for c in c4h][::-1])
        
        # Phân tích
        data_analysis = analyze_market_data(last, low, high, rsi_15, rsi_4h)
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Lưu vào Session State hiện tại
        st.session_state['last_analysis'] = {
            'data': data_analysis,
            'price': last,
            'rsi15': rsi_15,
            'rsi4h': rsi_4h,
            'time': timestamp
        }

        # --- LƯU VÀO NHẬT KÝ (LOGS) ---
        if 'history_log' not in st.session_state:
            st.session_state['history_log'] = []
        
        # Thêm bản ghi mới vào đầu danh sách
        new_log = {
            "Thời gian": timestamp,
            "Giá": last,
            "RSI 15m": round(rsi_15, 2),
            "Hành động": data_analysis['action'],
            "Lý do": data_analysis['reason']
        }
        st.session_state['history_log'].insert(0, new_log)
        
        # Giới hạn chỉ giữ 50 bản ghi gần nhất để nhẹ bộ nhớ
        if len(st.session_state['history_log']) > 50:
            st.session_state['history_log'] = st.session_state['history_log'][:50]

        return True
    except Exception as e:
        st.error(f"Lỗi kết nối OKX: {e}")
        return False

# --- 2. GIAO DIỆN STREAMLIT ---

# Khởi tạo Session State cho Logs
if 'history_log' not in st.session_state:
    st.session_state['history_log'] = []

# Sidebar: Cấu hình đầu vào
st.sidebar.title("⚙️ Cấu hình")
symbol = st.sidebar.text_input("Mã Coin (Ví dụ: ETH)", value="ETH").upper()
von_input = st.sidebar.number_input("Vốn đầu tư (VND)", value=10000000, step=500000)

# Cấu hình Auto Update
st.sidebar.divider()
st.sidebar.subheader("🔄 Tự động")
auto_update = st.sidebar.checkbox("Bật tự động cập nhật (30s)", value=False)

# Nút cập nhật tỷ giá USDT
col_tg1, col_tg2 = st.sidebar.columns([3, 1])
with col_tg1:
    ty_gia_default = 26700.0
    if 'usdt_rate' not in st.session_state:
        st.session_state['usdt_rate'] = ty_gia_default
    ty_gia = st.number_input("Tỷ giá USDT", value=st.session_state['usdt_rate'], step=100.0)
with col_tg2:
    st.write("")
    st.write("")
    if st.button("🌐"):
        st.session_state['usdt_rate'] = fetch_usdt_rate()
        st.rerun()

# Tiêu đề chính
st.title(f"🚀 Crypto Commander: {symbol}")

# Nút Phân Tích Thủ Công (Ẩn nếu đang auto)
if not auto_update:
    if st.button("🔍 PHÂN TÍCH NGAY", type="primary"):
        with st.spinner('Đang phân tích...'):
            run_analysis_logic(symbol)
else:
    st.info("⚡ Đang chạy chế độ tự động cập nhật mỗi 30s...")

# --- XỬ LÝ AUTO UPDATE ---
# Nếu chế độ Auto bật, kiểm tra logic chạy
if auto_update:
    # Nếu chưa có dữ liệu, chạy ngay lần đầu
    if 'last_analysis' not in st.session_state:
        run_analysis_logic(symbol)
    
    # Tạo container đếm ngược (Optional visual)
    placeholder = st.empty()
    
    # Logic: Chờ 30s rồi rerun. 
    # Lưu ý: Trong Streamlit, sleep sẽ giữ process.
    # Để user vẫn xem được tab, ta dùng time.sleep ngắn trong loop hoặc chấp nhận refresh trang.
    # Ở đây dùng cách đơn giản nhất:
    
    # Kiểm tra lần cuối update để tránh loop quá nhanh nếu rerun do tương tác khác
    # (Phần này để đơn giản ta sẽ cho chạy trực tiếp ở cuối script)
    pass

# --- HIỂN THỊ KẾT QUẢ ---
if 'last_analysis' in st.session_state:
    res = st.session_state['last_analysis']
    d = res['data']
    
    # 1. HEADER INFO
    c1, c2, c3 = st.columns(3)
    c1.metric("Giá hiện tại", f"{res['price']}", f"Time: {res['time']}")
    c2.metric("RSI 15m", f"{res['rsi15']:.1f}")
    c3.metric("RSI 4H", f"{res['rsi4h']:.1f}")
    
    # Thông báo Action
    if d['action'].startswith("MUA"):
        st.success(f"## {d['action']}")
    elif d['action'].startswith("BÁN"):
        st.error(f"## {d['action']}")
    else:
        st.warning(f"## {d['action']}")
    
    st.info(f"💡 Lý do: {d['reason']}")

    # TABS GIAO DIỆN
    tab1, tab2, tab3 = st.tabs(["📊 Tính Lời/Lỗ", "💡 Chiến Thuật", "📜 Nhật ký & Biểu đồ"])

    with tab1:
        st.subheader("Dự tính Lợi nhuận")
        c_mua, c_ban = st.columns(2)
        with c_mua:
            gia_mua = st.number_input("Giá Mua (USDT)", value=d['entry'], format="%.4f")
        with c_ban:
            gia_ban = st.number_input("Giá Bán (USDT)", value=d['tp'], format="%.4f")
            
        von_usd = (von_input * 0.999) / ty_gia
        coin_amount = von_usd / gia_mua
        thu_vnd = (coin_amount * gia_ban * ty_gia) * 0.999
        lai_lo = thu_vnd - von_input
        phantram = (lai_lo / von_input) * 100
        
        st.divider()
        col_kq1, col_kq2, col_kq3 = st.columns(3)
        col_kq1.metric("Tiền về (VND)", f"{thu_vnd:,.0f}")
        col_kq2.metric("Lãi/Lỗ (VND)", f"{lai_lo:,.0f}", delta_color="normal" if lai_lo > 0 else "inverse")
        col_kq3.metric("% Lợi nhuận", f"{phantram:.2f}%")

    with tab2:
        st.subheader("Thông số lệnh")
        col_strat1, col_strat2 = st.columns(2)
        with col_strat1:
            st.markdown("### 🛑 Stop Loss / Entry")
            st.write(f"**Entry:** `{d['entry']:.4f}`")
            st.write(f"**Stop Loss:** `{d['sl']:.4f}`")
            st.write(f"**Take Profit:** `{d['tp']:.4f}`")
        with col_strat2:
            st.markdown("### 📉 Limit & Trailing")
            st.write(f"**Limit Buy:** `{d['limit_buy']:.4f}`")
            st.write(f"**Trailing Act:** `{d['act_price']:.4f}`")

    with tab3:
        st.subheader("Nhật ký hoạt động")
        if st.session_state['history_log']:
            # Tạo DataFrame từ log
            df_log = pd.DataFrame(st.session_state['history_log'])
            
            # Hiển thị Biểu đồ giá
            st.line_chart(df_log, x="Thời gian", y="Giá", color="#00FF00")
            
            # Hiển thị bảng chi tiết
            st.dataframe(df_log, use_container_width=True)
            
            if st.button("Xóa nhật ký"):
                st.session_state['history_log'] = []
                st.rerun()
        else:
            st.text("Chưa có dữ liệu nhật ký.")

else:
    st.info("👈 Nhấn 'PHÂN TÍCH NGAY' hoặc bật 'Tự động' để bắt đầu.")

# --- AUTO UPDATE LOOP ---
# Đoạn code này nằm cuối cùng để đảm bảo UI render xong mới sleep
if auto_update:
    time.sleep(30) # Chờ 30s
    run_analysis_logic(symbol) # Cập nhật dữ liệu mới
    st.rerun() # Load lại trang để hiển thị số mới

# Footer
st.divider()
st.caption("Crypto Commander Web Edition - Auto Update Enabled")
