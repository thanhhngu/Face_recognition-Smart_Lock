# Sử dụng một image Python chính thức làm image cơ sở
FROM python:3.9-slim

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Cài đặt các phụ thuộc hệ thống cần thiết cho OpenCV
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Sao chép tệp requirements vào container
COPY requirements.txt .

# Cài đặt các gói Python được chỉ định trong requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn của ứng dụng vào container
COPY . .

# Mở cổng 8000 để có thể truy cập từ bên ngoài container
EXPOSE 8000

# Chạy ứng dụng khi container khởi động
# Lệnh này sử dụng uvicorn để chạy ứng dụng FastAPI
CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8000"]