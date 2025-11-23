import streamlit as st
import pandas as pd
import cv2
import numpy as np
import av
from pyzbar.pyzbar import decode
from datetime import datetime
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase, WebRtcMode

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Check-in Lái Xe Pro", layout="wide", page_icon="🚗")

# --- QUẢN LÝ SESSION STATE ---
if "df_hocvien" not in st.session_state:
    cols = ["cccd", "ho_ten", "ngay_sinh", "sdt", "dia_chi", "ngay_dang_ky", "lich_thi", "trang_thai"]
    st.session_state["df_hocvien"] = pd.DataFrame(columns=cols)

if "scanned_code" not in st.session_state:
    st.session_state["scanned_code"] = None

# --- XỬ LÝ VIDEO TRỰC TIẾP (CALLBACK) ---
# Hàm này chạy liên tục trên từng khung hình video
def video_frame_callback(frame):
    img = frame.to_ndarray(format="bgr24")
    
    # Giải mã QR
    decoded_objects = decode(img)
    
    if decoded_objects:
        for obj in decoded_objects:
            qr_content = obj.data.decode("utf-8")
            # Vẽ hình chữ nhật quanh QR để biết đã nhận
            points = obj.polygon
            if len(points) == 4:
                pts = np.array(points, np.int32)
                pts = pts.reshape((-1, 1, 2))
                cv2.polylines(img, [pts], True, (0, 255, 0), 3)
            
            # Trả về mã QR tìm thấy (thông qua cơ chế queue hoặc return frame đặc biệt)
            # Ở đây ta dùng cách đơn giản là vẽ lên hình, logic xử lý data sẽ nằm ở main thread
            return av.VideoFrame.from_ndarray(img, format="bgr24")

    return av.VideoFrame.from_ndarray(img, format="bgr24")

# --- CLASS XỬ LÝ QR (Mới) ---
class QRCodeProcessor(VideoTransformerBase):
    def __init__(self):
        self.scanned_data = None

    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        decoded_objects = decode(img)
        
        if decoded_objects:
            for obj in decoded_objects:
                self.scanned_data = obj.data.decode("utf-8")
                # Vẽ khung xanh khi nhận diện được
                pts = np.array(obj.polygon, np.int32).reshape((-1, 1, 2))
                cv2.polylines(img, [pts], True, (0, 255, 0), 3)
                
        return av.VideoFrame.from_ndarray(img, format="bgr24")

# --- HÀM PHỤ TRỢ (Giữ nguyên từ code cũ) ---
def create_sample_data():
    data = {
        "cccd": ["079090000001", "001090000002"],
        "ho_ten": ["NGUYỄN VĂN A", "TRẦN THỊ B"],
        "ngay_sinh": ["01/01/1990", "15/05/1995"],
        "sdt": ["0901234567", "0909888777"],
        "dia_chi": ["Quận 1, TP.HCM", "Hà Đông, Hà Nội"],
        "ngay_dang_ky": ["2023-01-01", "2023-06-01"],
        "lich_thi": ["2025-12-31", "2023-12-31"], 
        "trang_thai": ["Hợp lệ", "Hết hạn"] 
    }
    return pd.DataFrame(data)

def parse_vietnam_cccd_qr(qr_data):
    try:
        parts = qr_data.split("|")
        if len(parts) >= 5:
            return {"cccd": parts[0], "ho_ten": parts[2]}
        return None
    except Exception:
        return None

# --- GIAO DIỆN CHÍNH ---
def main_app():
    st.sidebar.title("Admin Panel")
    if st.sidebar.button("Tạo Data Mẫu"):
        st.session_state["df_hocvien"] = create_sample_data()
        st.success("Đã tạo data mẫu!")

    st.title("📸 Check-in Tự Động (Live)")
    st.write("Chọn đúng **Camera sau (Back/Environment)** trong phần cài đặt bên dưới.")

    # Cấu hình WebRTC
    ctx = webrtc_streamer(
        key="qr-scanner",
        mode=WebRtcMode.SENDRECV,
        video_processor_factory=QRCodeProcessor,  # Sử dụng class xử lý QR
        media_stream_constraints={
            "video": {
                "facingMode": "environment", # Ưu tiên camera sau
                # "width": {"min": 1280}, # Có thể bật dòng này để ép độ phân giải cao
            } 
        },
        rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
        async_processing=True,
    )

    # --- XỬ LÝ KẾT QUẢ TỪ STREAM ---
    if ctx.video_processor:
        # Kiểm tra xem processor có quét được gì chưa
        if ctx.video_processor.scanned_data:
            qr_content = ctx.video_processor.scanned_data
            
            # Chỉ xử lý nếu mã mới khác mã cũ (tránh nháy liên tục)
            if st.session_state["scanned_code"] != qr_content:
                st.session_state["scanned_code"] = qr_content
                
                # --- LOGIC KIỂM TRA HỌC VIÊN ---
                st.divider()
                st.markdown(f"### 📡 Đã nhận tín hiệu QR:")
                
                parsed_info = parse_vietnam_cccd_qr(qr_content)
                if parsed_info:
                    cccd_check = parsed_info['cccd']
                    st.info(f"Đang kiểm tra: {parsed_info['ho_ten']} - {cccd_check}")
                    
                    df = st.session_state["df_hocvien"]
                    if not df.empty:
                        student = df[df['cccd'] == cccd_check]
                        if not student.empty:
                            info = student.iloc[0]
                            today = datetime.now().date()
                            lich_thi_date = datetime.strptime(info['lich_thi'], "%Y-%m-%d").date()
                            
                            if info['trang_thai'] == "Hợp lệ" and lich_thi_date >= today:
                                st.success("✅ HỢP LỆ - MỜI VÀO SÂN")
                                st.balloons()
                            else:
                                st.error(f"⛔ KHÔNG HỢP LỆ: {info['trang_thai']}")
                        else:
                            st.warning("⚠️ Học viên không có trong danh sách.")
                    else:
                        st.warning("Dữ liệu trống. Hãy bấm 'Tạo Data Mẫu' bên trái.")
                else:
                    st.error("QR không đúng định dạng CCCD.")

    st.caption("Nếu camera bị đen hoặc không chạy, hãy kiểm tra quyền truy cập Camera trên trình duyệt.")

if __name__ == "__main__":
    main_app()
