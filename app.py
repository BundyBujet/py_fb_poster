import os
import time
import threading
import uuid
from flask import Flask, render_template, request, jsonify
import requests
from werkzeug.utils import secure_filename

app = Flask(__name__)

# مسار المجلد لتخزين الصور
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# التحقق من امتداد الصورة
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# لتتبع الخيوط النشطة
active_threads = []
schedules = []  # لتخزين الجداول النشطة في الذاكرة

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_pages', methods=['POST'])
def get_pages():
    user_access_token = request.form['user_access_token']
    
    if not user_access_token:
        return jsonify({"error": "User Access Token is required"}), 400
    
    # جلب الـ Pages باستخدام Graph API
    url = f"https://graph.facebook.com/v12.0/me/accounts?access_token={user_access_token}"
    response = requests.get(url)
    data = response.json()

    if 'data' not in data:
        return jsonify({"error": "Failed to fetch pages. Check your user token."}), 400
    
    pages = []
    for page in data['data']:
        page_info = {
            "name": page['name'],
            "access_token": page['access_token'],  # تأكد من أنك ترجع الـ Access Token الخاص بالصفحة
            "id": page['id']
        }
        pages.append(page_info)

    return jsonify({"pages": pages})

@app.route('/post_content', methods=['POST'])
def post_content():
    try:
        # استلام البيانات من النموذج
        page_id = request.form.get('page_id')
        page_token = request.form.get('page_token')
        content = request.form.get('content')
        interval = request.form.get('interval')
        delay = request.form.get('delay')
        page_name = request.form.get('page_name')  # إضافة اسم الصفحة هنا

        # التأكد من أن الحقول الأساسية موجودة
        if not page_id or not page_token or not content:
            return jsonify({"error": "Missing required fields"}), 400

        # التأكد من أن القيم هي أرقام صحيحة
        try:
            interval = int(interval)
            delay = int(delay)
        except ValueError:
            return jsonify({"error": "Interval and delay must be numbers"}), 400

        # حفظ الصورة إذا كانت موجودة
        image_file = request.files.get('image')
        image_path = None
        if image_file:
            if allowed_file(image_file.filename):
                filename = secure_filename(image_file.filename)
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(image_path)
            else:
                return jsonify({"error": "Invalid image format. Allowed formats: png, jpg, jpeg, gif"}), 400

        stop_event = threading.Event()  # إنشاء حدث إيقاف
        job_id = str(uuid.uuid4())  # إنشاء ID فريد للعملية

        def schedule_posts():
            while not stop_event.is_set():  # التوقف عندما يتم ضبط الإشارة
                try:
                    # نشر المحتوى على فيسبوك
                    if image_path:
                        # نشر صورة مع النص
                        graph_url = f"https://graph.facebook.com/{page_id}/photos"
                        with open(image_path, 'rb') as file:
                            files = {'file': file}
                            data = {'message': content, 'access_token': page_token}
                            response = requests.post(graph_url, files=files, data=data)
                    else:
                        # نشر النص فقط
                        graph_url = f"https://graph.facebook.com/{page_id}/feed"
                        data = {'message': content, 'access_token': page_token}
                        response = requests.post(graph_url, data=data)

                    # إذا كان نشر المحتوى ناجحًا
                    if response.status_code != 200:
                        return jsonify({"error": f"Failed to post: {response.text}"}), 500

                    print(f"Posted to page {page_id}: {content}")
                    time.sleep(interval * 60)  # تأخير بين كل بوست وآخر
                    
                except Exception as e:
                    return jsonify({"error": f"Error in posting: {str(e)}"}), 500

        # إضافة الجدول إلى الذاكرة مع stop_event و job_id
        schedules.append({
            'job_id': job_id,
            'page_name': page_name,  # إضافة اسم الصفحة هنا
            'page_id': page_id,  # إضافة معرف الصفحة هنا
            'interval': interval,  # إضافة الفترة الزمنية
            'content': content,  # إضافة المحتوى
            'delay': delay,  # إضافة التأخير
            'image_path': image_path,  # حفظ الصورة التي تم رفعها
            'thread': threading.Thread(target=schedule_posts),
            'stop_event': stop_event  # إضافة stop_event
        })

        # بدء الخيط
        schedules[-1]['thread'].start()

        return jsonify({"message": "Scheduled successfully", "jobId": job_id})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/stop_posting', methods=['POST'])
def stop_posting():
    try:
        for schedule in schedules:
            # التحقق من وجود stop_event وإيقافه بشكل صحيح
            if schedule.get('stop_event'):
                schedule['stop_event'].set()  # إشارة لإيقاف الخيط
                schedule['thread'].join()  # الانتظار حتى ينتهي الخيط

        # مسح الجداول بعد التوقف
        schedules.clear()

        return jsonify({"message": "All posting has been stopped."})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/delete_schedule', methods=['POST'])
def delete_schedule():
    job_id = request.form.get('job_id')
    
    if not job_id:
        return jsonify({"error": "Job ID is required"}), 400
    
    # البحث عن الجدول باستخدام job_id
    schedule_to_remove = None
    for schedule in schedules:
        if schedule['job_id'] == job_id:
            schedule_to_remove = schedule
            break
    
    if not schedule_to_remove:
        return jsonify({"error": "Schedule not found"}), 404
    
    # إيقاف الخيط وحذفه
    if schedule_to_remove.get('stop_event'):
        schedule_to_remove['stop_event'].set()
        schedule_to_remove['thread'].join()

    # مسح الجدول من الذاكرة
    schedules.remove(schedule_to_remove)

    return jsonify({"message": "Schedule deleted successfully"})

# Endpoint لتحميل الصور
@app.route('/upload_image', methods=['POST'])
def upload_image():
    image_file = request.files.get('image')
    
    if not image_file or not allowed_file(image_file.filename):
        return jsonify({"error": "Invalid image file. Allowed formats: png, jpg, jpeg, gif."}), 400

    filename = secure_filename(image_file.filename)
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    image_file.save(image_path)

    return jsonify({"message": "Image uploaded successfully", "image_path": image_path})

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)
