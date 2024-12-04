import cv2
import numpy as np
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from pathlib import Path
import time  # Importamos el módulo time para gestionar la cuenta regresiva

app = Flask(__name__)
app.secret_key = 'my_secret_key'  # Necesario para flash messages

dataset_path = "dataset"
model_path = "modelo_face.xml"
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Clase para manejo de reconocimiento facial
class FaceRecognizer:
    def __init__(self, dataset_path=dataset_path, model_path=model_path):
        self.dataset_path = dataset_path
        self.model_path = model_path
        self.model = None
        self._load_model()

    def _load_model(self):
        """Carga el modelo si existe."""
        if os.path.exists(self.model_path):
            self.model = cv2.face.LBPHFaceRecognizer_create()
            self.model.read(self.model_path)
        else:
            print("Modelo no encontrado, por favor entrena el modelo antes de usarlo.")

    def capturar_rostros(self, user_id):
        """Captura rostros y los guarda en el dataset."""
        Path(self.dataset_path).mkdir(parents=True, exist_ok=True)
        cap = cv2.VideoCapture(0)
        count = 0
        while count < 30:
            ret, frame = cap.read()
            if not ret:
                flash('Error al capturar la imagen. Intenta nuevamente.', 'danger')
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

            for (x, y, w, h) in faces:
                rostro = gray[y:y + h, x:x + w]
                rostro_path = os.path.join(self.dataset_path, f"user_{user_id}_{count}.jpg")
                cv2.imwrite(rostro_path, rostro)
                count += 1
                cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

            cv2.imshow("Captura de Rostros", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

    def entrenar_modelo(self):
        """Entrena el modelo con las imágenes capturadas."""
        caras = []
        etiquetas = []
        for filename in os.listdir(self.dataset_path):
            if filename.endswith(".jpg"):
                try:
                    user_id_str = filename.split("_")[1]  # Extraemos el ID de usuario
                    user_id = int(user_id_str)
                except (IndexError, ValueError):
                    print(f"Archivo con nombre incorrecto: {filename}. Ignorando este archivo.")
                    continue  # Salta al siguiente archivo

                img_path = os.path.join(self.dataset_path, filename)
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                caras.append(img)
                etiquetas.append(user_id)

        if len(caras) == 0:
            flash('No se encontraron imágenes válidas para entrenar el modelo. Asegúrate de capturar rostros primero.', 'danger')
            print("No se encontraron imágenes válidas para entrenar el modelo.")
            return

        self.model = cv2.face.LBPHFaceRecognizer_create()
        self.model.train(caras, np.array(etiquetas))
        self.model.save(self.model_path)
        flash('Modelo entrenado y guardado con éxito.', 'success')
        print("Modelo entrenado y guardado con éxito.")

    def autenticar_usuario(self, user_id):
        """Autentica al usuario con reconocimiento facial en tiempo real, con cuenta regresiva de 20 segundos."""
        cap = cv2.VideoCapture(0)
        start_time = time.time()  # Marca el tiempo de inicio
        timeout = 20  # Establece el tiempo máximo de autenticación en 20 segundos

        while True:
            ret, frame = cap.read()
            if not ret:
                flash('Error al capturar la imagen. Intenta nuevamente.', 'danger')
                break

            # Calcular el tiempo transcurrido
            elapsed_time = time.time() - start_time
            remaining_time = timeout - elapsed_time

            # Mostrar el contador de tiempo en la imagen
            cv2.putText(frame, f"Tiempo restante: {int(remaining_time)}s", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            if remaining_time <= 0:  # Si el tiempo se agota
                flash('Tiempo de autenticación agotado. La cámara se cerrará.', 'danger')
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

            for (x, y, w, h) in faces:
                rostro = gray[y:y + h, x:x + w]
                if self.model:
                    id_usuario, confianza = self.model.predict(rostro)
                    cv2.putText(frame, f"ID: {id_usuario} - Confianza: {confianza:.2f}", (x, y - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                    # Verifica si el ID del usuario coincide y si la confianza es mayor al 75%
                    if id_usuario == int(user_id) and confianza < 100:  # Verificar ID y si la confianza es alta
                        if confianza < 25:  # La confianza debe ser mayor a 75% (menor valor de confianza)
                            cap.release()
                            cv2.destroyAllWindows()
                            return True
                    else:
                        flash('El rostro no coincide con el ID de usuario o la confianza es baja. Intenta nuevamente.', 'danger')
                        cv2.putText(frame, "Rostro no coincide o confianza baja", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

                else:
                    cv2.putText(frame, "Modelo no entrenado", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

                cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

            cv2.imshow("Autenticación Facial", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()
        return False  # Si no se detecta una coincidencia o la confianza es baja o el tiempo se agota

face_recognizer = FaceRecognizer()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form['user_id']  # Obtener ID del formulario

        if not user_id:
            flash('Por favor ingresa un ID de usuario.', 'warning')
            return redirect(url_for('login'))

        try:
            # Captura y autentica al usuario con el reconocimiento facial
            if face_recognizer.autenticar_usuario(user_id):
                flash('Bienvenido al sistema', 'success')
                return redirect(url_for('home'))  # Redirigir a la página de inicio
            else:
                flash('Autenticación fallida. Intenta nuevamente.', 'danger')
                return redirect(url_for('login'))  # Volver al login

        except Exception as e:
            flash(f'Error durante la autenticación: {str(e)}', 'danger')
            return redirect(url_for('login'))  # Si ocurre un error, volver al login

    return render_template('login.html')  # Si el método no es POST, simplemente mostrar el login

@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        user_id = request.form['user_id']
        if user_id:
            try:
                # Registrar usuario (capturar rostros)
                face_recognizer.capturar_rostros(user_id)
                flash('Registro exitoso. Rostros capturados.', 'success')

                # Entrenar el modelo inmediatamente después de registrar
                face_recognizer.entrenar_modelo()
                flash('Modelo entrenado exitosamente.', 'success')

            except Exception as e:
                flash(f'Error al registrar al usuario o entrenar el modelo: {str(e)}', 'danger')

            return redirect(url_for('index'))  # Volver a la página principal

        flash('Por favor ingresa un ID de usuario.', 'warning')
        return redirect(url_for('index'))  # Volver a la página principal

    return render_template('registrar.html')

@app.route('/home')
def home():
    return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True)
