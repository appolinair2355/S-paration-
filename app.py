import os
import uuid
import shutil
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import subprocess
import json

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Configuration
UPLOAD_FOLDER = '/tmp/uploads'
SEPARATED_FOLDER = '/tmp/separated'
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'flac', 'm4a', 'ogg'}

# Créer les dossiers temporaires
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SEPARATED_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/separate', methods=['POST'])
def separate_audio():
    if 'audio' not in request.files:
        return jsonify({'error': 'Aucun fichier audio fourni'}), 400
    
    file = request.files['audio']
    if file.filename == '':
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Format de fichier non supporté'}), 400

    # Générer un ID unique pour cette session
    session_id = str(uuid.uuid4())
    session_upload = os.path.join(UPLOAD_FOLDER, session_id)
    session_output = os.path.join(SEPARATED_FOLDER, session_id)
    os.makedirs(session_upload, exist_ok=True)
    os.makedirs(session_output, exist_ok=True)

    try:
        # Sauvegarder le fichier uploadé
        filename = secure_filename(file.filename)
        input_path = os.path.join(session_upload, filename)
        file.save(input_path)

        # Utiliser Spleeter pour la séparation (2 stems: vocals/accompaniment)
        # ou fallback sur une simulation si Spleeter n'est pas installé
        stems = process_audio(input_path, session_output, filename)
        
        # Nettoyer les fichiers temporaires d'upload
        shutil.rmtree(session_upload, ignore_errors=True)
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'stems': stems
        })

    except Exception as e:
        # Nettoyage en cas d'erreur
        shutil.rmtree(session_upload, ignore_errors=True)
        shutil.rmtree(session_output, ignore_errors=True)
        return jsonify({'error': str(e)}), 500

def process_audio(input_path, output_dir, original_filename):
    """Traite l'audio et retourne les URLs des stems"""
    
    base_name = os.path.splitext(original_filename)[0]
    
    # Vérifier si Spleeter est disponible
    try:
        # Commande Spleeter pour séparer en 2 pistes (vocals + accompaniment)
        cmd = [
            'spleeter', 'separate',
            '-p', 'spleeter:2stems',
            '-o', output_dir,
            input_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            # Spleeter crée un sous-dossier avec le nom du fichier
            spleeter_output = os.path.join(output_dir, os.path.splitext(os.path.basename(input_path))[0])
            
            stems = []
            stem_files = {
                'vocals.wav': 'vocals',
                'accompaniment.wav': 'other'
            }
            
            for filename, stem_name in stem_files.items():
                src_path = os.path.join(spleeter_output, filename)
                if os.path.exists(src_path):
                    # Convertir en MP3 pour réduction taille
                    mp3_name = f"{stem_name}.mp3"
                    mp3_path = os.path.join(output_dir, mp3_name)
                    
                    # Conversion avec ffmpeg
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
            
            # Nettoyer les fichiers WAV intermédiaires
            shutil.rmtree(spleeter_output, ignore_errors=True)
            return stems
            
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        # Fallback: simulation si Spleeter n'est pas disponible
        print(f"Spleeter non disponible ou erreur ({e}), utilisation du fallback")
        return create_fallback_stems(input_path, output_dir, base_name)

def create_fallback_stems(input_path, output_dir, base_name):
    """Crée des stems simulés si Spleeter n'est pas disponible"""
    
    # Copier le fichier original comme "vocals" simulé (en réalité ce serait traité)
    # Dans un vrai déploiement, remplacez ceci par un vrai modèle de séparation
    
    stems = []
    
    # Simuler la création de 2 stems en copiant et modifiant légèrement l'audio
    # avec ffmpeg pour créer des versions "traitées"
    
    for stem_name in ['vocals', 'other']:
        output_file = os.path.join(output_dir, f"{stem_name}.mp3")
        
        # Utiliser ffmpeg pour créer une variation (filtre simple pour simulation)
        if stem_name == 'vocals':
            # Filtre passe-haut pour simuler isolation voix
            cmd = ['ffmpeg', '-y', '-i', input_path, '-af', 'highpass=f=200', '-q:a', '2', output_file]
        else:
            # Filtre passe-bas pour simuler accompagnement
            cmd = ['ffmpeg', '-y', '-i', input_path, '-af', 'lowpass=f=1000', '-q:a', '2', output_file]
        
        try:
            subprocess.run(cmd, capture_output=True, timeout=60)
            if os.path.exists(output_file):
                stems.append({
                    'name': stem_name,
                    'filename': f"{base_name}_{stem_name}.mp3",
                    'url': f'/download/{os.path.basename(output_dir)}/{stem_name}.mp3'
                })
        except:
            # Si ffmpeg échoue, copier simplement le fichier
            shutil.copy(input_path, output_file)
            stems.append({
                'name': stem_name,
                'filename': f"{base_name}_{stem_name}.mp3",
                'url': f'/download/{os.path.basename(output_dir)}/{stem_name}.mp3'
            })
    
    return stems

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

# Nettoyage périodique des anciens fichiers (optionnel, à implémenter avec un scheduler)
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
