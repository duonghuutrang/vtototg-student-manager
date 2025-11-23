import streamlit as st
import pandas as pd
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from datetime import datetime

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Check-in Sân Tập Lái Xe", layout="wide", page_icon="🚗")

# --- QUẢN LÝ SESSION STATE (LƯU TRỮ TẠM THỜI) ---
# Khởi tạo dataframe trong session_state nếu chưa có
if "df_hocvien" not in st.session_state:
    # Tạo dataframe rỗng với các cột chuẩn
    cols = ["cccd", "ho_ten", "ngay_sinh", "sdt", "dia_chi", "ngay_dang_ky", "lich_thi", "trang_thai"]
    st.session_state["df_hocvien"] = pd.DataFrame(columns=cols)

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# --- HÀM TẠO DỮ LIỆU MẪU ---
def create_sample_data():
    """Hàm tạo dữ liệu giả lập để test"""
    data = {
        "cccd": ["079090000001", "001090000002", "079123456789"],
        "ho_ten": ["NGUYỄN VĂN A", "TRẦN THỊ B", "LÊ VĂN C"],
        "ngay_sinh": ["01/01/1990", "15/05/1995", "20/10/2000"],
        "sdt": ["0901234567", "0909888777", "0912345678"],
        "dia_chi": ["Quận 1, TP.HCM", "Hà Đông, Hà Nội", "Thủ Đức, TP.HCM"],
        "ngay_dang_ky": ["2023-01-01", "2023-06-01", "2024-01-01"],
        "lich_thi": ["2025-12-31", "2023-12-31", "2025-10-20"], # Coi như hạn tập
        "trang_thai": ["Hợp lệ", "Hết hạn", "Hợp lệ"] 
    }
    return pd.DataFrame(data)

# --- HÀM ĐĂNG NHẬP ---
def login_screen():
    st.markdown("<h1 style='text-align: center;'>🔐 Đăng Nhập Hệ Thống</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Tên đăng nhập", placeholder="admin")
            password = st.text_input("Mật khẩu", type="password", placeholder="1234")
            submitted = st.form_submit_button("Đăng nhập", use_container_width=True)
            
            if submitted:
                if username == "admin" and password == "1234":
                    st.session_state["logged_in"] = True
                    st.success("Đăng nhập thành công!")
                    st.rerun() # Tải lại trang để vào giao diện chính
                else:
                    st.error("❌ Sai tên đăng nhập hoặc mật khẩu!")

# --- HÀM XỬ LÝ QR ---
def parse_vietnam_cccd_qr(qr_data):
    try:
        parts = qr_data.split("|")
        if len(parts) >= 5:
            return {"cccd": parts[0], "ho_ten": parts[2]}
        return None
    except Exception:
        return None

# --- GIAO DIỆN CHÍNH (SAU KHI ĐĂNG NHẬP) ---
def main_app():
    # Sidebar
    st.sidebar.title(f"Xin chào, Admin 👋")
    
    # Nút đăng xuất
    if st.sidebar.button("Đăng xuất"):
        st.session_state["logged_in"] = False
        st.rerun()
        
    menu = st.sidebar.radio("Menu chức năng", ["📸 Quét QR Check-in", "📋 Danh Sách Học Viên", "⚙️ Quản Trị Dữ Liệu"])

    # --- 1. CHỨC NĂNG QUÉT QR ---
    if menu == "📸 Quét QR Check-in":
        st.title("Kiểm Soát Ra Vào Sân")
        st.info("Hệ thống kiểm tra dựa trên số CCCD trong mã QR")

        img_file_buffer = st.camera_input("Camera")

        if img_file_buffer is not None:
            bytes_data = img_file_buffer.getvalue()
            cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
            decoded_objects = decode(cv2_img)

            if decoded_objects:
                for obj in decoded_objects:
                    qr_content = obj.data.decode("utf-8")
                    parsed_info = parse_vietnam_cccd_qr(qr_content)
                    
                    if parsed_info:
                        cccd_check = parsed_info['cccd']
                        st.subheader(f"Đã quét: {parsed_info['ho_ten']} ({cccd_check})")
                        
                        # Kiểm tra trong database (session_state)
                        df = st.session_state["df_hocvien"]
                        student = df[df['cccd'] == cccd_check]
                        
                        if not student.empty:
                            info = student.iloc[0]
                            # Logic kiểm tra
                            today = datetime.now().date()
                            lich_thi_date = datetime.strptime(info['lich_thi'], "%Y-%m-%d").date()
                            
                            if info['trang_thai'] == "Hợp lệ" and lich_thi_date >= today:
                                st.success("✅ HỢP LỆ - MỜI VÀO SÂN")
                                st.write(f"Hạn tập: {info['lich_thi']}")
                            else:
                                st.error("⛔ KHÔNG HỢP LỆ")
                                st.warning(f"Lý do: Trạng thái {info['trang_thai']} hoặc quá hạn.")
                        else:
                            st.warning("⚠️ Học viên chưa đăng ký trong hệ thống!")
                    else:
                        st.error("QR không phải CCCD chuẩn.")
            else:
                st.caption("Chưa nhận diện được QR code.")

    # --- 2. DANH SÁCH HỌC VIÊN ---
    elif menu == "📋 Danh Sách Học Viên":
        st.title("Danh Sách Học Viên")
        
        # Hiển thị thống kê nhỏ
        total = len(st.session_state["df_hocvien"])
        st.metric("Tổng số học viên", total)
        
        st.dataframe(st.session_state["df_hocvien"], use_container_width=True)

    # --- 3. QUẢN TRỊ DỮ LIỆU (TẠO DATA MẪU) ---
    elif menu == "⚙️ Quản Trị Dữ Liệu":
        st.title("Công Cụ Quản Trị")
        st.write("Tại đây bạn có thể khởi tạo dữ liệu giả để test ứng dụng.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.warning("⚠️ Lưu ý: Hành động này sẽ ghi đè danh sách hiện tại.")
            if st.button("🔄 Khởi tạo Data Mẫu (Test)", type="primary"):
                st.session_state["df_hocvien"] = create_sample_data()
                st.success("Đã tạo dữ liệu mẫu thành công! Hãy chuyển sang tab 'Danh Sách' để xem.")
        
        with col2:
             if st.button("🗑️ Xóa toàn bộ dữ liệu"):
                 st.session_state["df_hocvien"] = st.session_state["df_hocvien"].iloc[0:0] # Xóa hết row
                 st.success("Đã xóa trắng danh sách.")

# --- ĐIỀU HƯỚNG ---
if st.session_state["logged_in"]:
    main_app()
else:
    login_screen()
