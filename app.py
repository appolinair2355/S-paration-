import os
import uuid
import shutil
from flask import Flask, request, jsonify, send_from_directory, render_template_string
from flask_cors import CORS
from werkzeug.utils import secure_filename
import subprocess
import json

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = '/tmp/uploads'
SEPARATED_FOLDER = '/tmp/separated'
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'flac', 'm4a', 'ogg'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SEPARATED_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

HTML_CONTENT = open('index.html').read()

@app.route('/')
def index():
    return render_template_string(HTML_CONTENT)

@app.route('/separate', methods=['POST'])
def separate_audio():
    if 'audio' not in request.files:
        return jsonify({'error': 'Aucun fichier audio fourni'}), 400

    file = request.files['audio']
    if file.filename == '':
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Format non supporté'}), 400

    session_id = str(uuid.uuid4())
    session_upload = os.path.join(UPLOAD_FOLDER, session_id)
    session_output = os.path.join(SEPARATED_FOLDER, session_id)
    os.makedirs(session_upload, exist_ok=True)
    os.makedirs(session_output, exist_ok=True)

    try:
        filename = secure_filename(file.filename)
        input_path = os.path.join(session_upload, filename)
        file.save(input_path)

        stems = process_audio(input_path, session_output, filename)

        shutil.rmtree(session_upload, ignore_errors=True)

        return jsonify({
            'success': True,
            'session_id': session_id,
            'stems': stems
        })

    except Exception as e:
        shutil.rmtree(session_upload, ignore_errors=True)
        shutil.rmtree(session_output, ignore_errors=True)
        return jsonify({'error': str(e)}), 500

def process_audio(input_path, output_dir, original_filename):
    base_name = os.path.splitext(original_filename)[0]
    stems = []

    # Essayer d'abord avec Spleeter si disponible
    try:
        cmd = [
            'spleeter', 'separate',
            '-p', 'spleeter:2stems',
            '-o', output_dir,
            input_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            spleeter_output = os.path.join(output_dir, os.path.splitext(os.path.basename(input_path))[0])

            stem_files = {
                'vocals.wav': 'vocals',
                'accompaniment.wav': 'other'
            }

            for filename, stem_name in stem_files.items():
                src_path = os.path.join(spleeter_output, filename)
                if os.path.exists(src_path):
                    mp3_name = f"{stem_name}.mp3"
                    mp3_path = os.path.join(output_dir, mp3_name)

                    convert_cmd = [
                        'ffmpeg', '-y', '-i', src_path,
                        '-codec:a', 'libmp3lame', '-qscale:a', '2',
                        mp3_path
                    ]
                    subprocess.run(convert_cmd, capture_output=True)

                    if os.path.exists(mp3_path):
                        stems.append({
                            'name': stem_name,
                            'filename': f"{base_name}_{stem_name}.mp3",
                            'url': f'/download/{os.path.basename(output_dir)}/{mp3_name}'
                        })

            shutil.rmtree(spleeter_output, ignore_errors=True)
            return stems
    except:
        pass

    # Fallback: utiliser ffmpeg pour créer des variations
    for stem_name, filter_str in [('vocals', 'highpass=f=200'), ('other', 'lowpass=f=1000')]:
        output_file = os.path.join(output_dir, f"{stem_name}.mp3")

        cmd = ['ffmpeg', '-y', '-i', input_path, '-af', filter_str, '-q:a', '2', output_file]

        try:
            subprocess.run(cmd, capture_output=True, timeout=60)
            if os.path.exists(output_file):
                stems.append({
                    'name': stem_name,
                    'filename': f"{base_name}_{stem_name}.mp3",
                    'url': f'/download/{os.path.basename(output_dir)}/{stem_name}.mp3'
                })
        except:
            pass

    return stems if stems else []

@app.route('/download/<session_id>/<filename>')
def download_file(session_id, filename):
    directory = os.path.join(SEPARATED_FOLDER, session_id)
    return send_from_directory(directory, filename, as_attachment=True)

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'ok',
        'admin': 'Sossou Kouamé Appolinaire',
        'service': 'Sossou Audio AI',
        'port': 10000
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
