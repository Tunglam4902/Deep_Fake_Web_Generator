from flask import Flask, request, jsonify, render_template, url_for
import os
import subprocess
import threading
import time
import re

app = Flask(__name__)  # Khởi tạo ứng dụng Flask

# Các thư mục lưu trữ tệp tin tạm thời và kết quả
UPLOAD_FOLDER = './static/uploads'
RESULT_FOLDER = './static/outputs'
TEMP_FOLDER = os.path.join(UPLOAD_FOLDER, 'temp')

# Tạo các thư mục nếu chưa tồn tại
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# Đường dẫn đến thư mục chứa Roop và tệp thực thi Python
ROOP_DIR = r"D:\DeepFaceWeb\Roop"
RESULT_PATH = os.path.join(RESULT_FOLDER, 'result.mp4')
PYTHON_EXECUTABLE = r"E:\DeepFakeWeb\myenv\Scripts\python.exe"

# Cấu hình Flask
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Dữ liệu tiến trình ban đầu
progress_data = {'percentage': 0, 'status': 'idle'}

@app.route('/')
def index():
    # Render giao diện HTML chính
    return render_template('index.html')

def update_progress_from_log(line):
    """
    Trích xuất phần trăm tiến trình từ log và cập nhật vào `progress_data`.
    """
    global progress_data
    # Tìm kiếm mẫu phần trăm từ log (e.g., `50%|`)
    match = re.search(r'(\d+)%\|', line)
    if match:
        progress_data['percentage'] = int(match.group(1))
        progress_data['status'] = 'processing'  # Cập nhật trạng thái thành "đang xử lý"

def run_process(command):
    """
    Chạy lệnh xử lý và cập nhật tiến trình từ log.
    """
    global progress_data
    progress_data['percentage'] = 0
    progress_data['status'] = 'processing'  # Cập nhật trạng thái ban đầu

    try:
        # Mở tiến trình chạy lệnh thông qua subprocess
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,  # Ghi nhận đầu ra từ lệnh
            stderr=subprocess.STDOUT,  # Ghi nhận lỗi từ lệnh
            text=True
        )

        # Đọc từng dòng log và cập nhật tiến trình
        for line in iter(process.stdout.readline, ''):
            print(line.strip())  # In log ra console
            update_progress_from_log(line)  # Cập nhật tiến trình

        process.stdout.close()
        process.wait()  # Chờ tiến trình kết thúc

        # Kiểm tra mã trả về để xác định trạng thái hoàn thành
        if process.returncode == 0:
            progress_data['status'] = 'done'
        else:
            progress_data['status'] = 'error'

    except Exception as e:
        # Cập nhật trạng thái lỗi nếu có ngoại lệ
        progress_data['status'] = 'error'
        print("Error during processing:", str(e))

@app.route('/upload', methods=['POST'])
def upload_files():
    """
    API tải lên tệp video và ảnh để bắt đầu xử lý.
    """
    try:
        video = request.files.get('video')  # Lấy tệp video từ request
        face = request.files.get('face')  # Lấy tệp ảnh từ request

        if not video or not face:
            # Kiểm tra nếu thiếu tệp
            return jsonify({'error': 'Both video and face files are required!'}), 400

        # Đường dẫn lưu trữ tệp đã tải lên
        video_path = os.path.join(UPLOAD_FOLDER, 'video.mp4')
        face_path = os.path.join(UPLOAD_FOLDER, 'face.jpg')

        video.save(video_path)  # Lưu tệp video
        face.save(face_path)  # Lưu tệp ảnh

        # Lệnh chạy Roop với các tham số
        command = [
            PYTHON_EXECUTABLE,
            os.path.join(ROOP_DIR, "run.py"),
            "-s", face_path,  # Đường dẫn ảnh nguồn
            "-t", video_path,  # Đường dẫn video đích
            "-o", RESULT_PATH,  # Đường dẫn kết quả
            "--execution-provider", "cuda",  # Sử dụng CUDA 
            "--execution-threads", "4",  # Số luồng thực thi
            "--keep-fps",  # Giữ nguyên FPS gốc
            "--output-video-encoder", "libx264",  # Bộ mã hóa video
            "--output-video-quality", "18",  # Chất lượng video cao
            "--temp-frame-format", "png",  # Lưu khung hình tạm thời dưới định dạng PNG
            "--temp-frame-quality", "95"  # Chất lượng ảnh tạm thời cao
        ]

        # Chạy lệnh trong một luồng riêng để không chặn ứng dụng
        process_thread = threading.Thread(target=run_process, args=(command,))
        process_thread.start()

        # Trả về phản hồi bắt đầu xử lý
        return jsonify({'message': 'Processing started.'}), 202

    except Exception as e:
        # Xử lý lỗi và trả về phản hồi lỗi
        return jsonify({'error': str(e)}), 500

@app.route('/progress', methods=['GET'])
def get_progress():
    """
    API để lấy tiến trình xử lý hiện tại.
    """
    global progress_data
    return jsonify(progress_data)  # Trả về tiến trình dưới dạng JSON

if __name__ == '__main__':
    # Khởi động ứng dụng Flask
    app.run(debug=True, host='0.0.0.0')
