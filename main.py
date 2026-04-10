from flask import Flask, render_template, redirect, url_for, request, send_file, make_response

from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import FileField, SelectField, BooleanField
from wtforms.validators import InputRequired, Optional

from flask_simple_captcha import CAPTCHA

import json
import io
import ffmpeg

import numpy as np
from scipy.io.wavfile import write

with open("credentials.json", "r") as f:
    credentials = json.load(f)

app = Flask(__name__)

app.config["SECRET_KEY"] = credentials["secretKey"] #flask-wtf
csrf = CSRFProtect(app)

CAPTCHA_CONFIG = {
    "CAPTCHA_LENGTH": 6,
    "CAPTCHA_DIGITS": True
}

SIMPLE_CAPTCHA = CAPTCHA(CAPTCHA_CONFIG)
app = SIMPLE_CAPTCHA.init_app(app)

class File_form(FlaskForm):
    transfer_type = SelectField("transfer type", choices=[("audio", "Audio"), ("video", "Video")])
    download = BooleanField("Direct Download")
    file = FileField("file", validators=[InputRequired()])

@app.route("/")
def index():
    file_form = File_form()
    captcha = SIMPLE_CAPTCHA.create()
    return render_template("index.html", captcha=captcha, file=file_form, error=request.args.get("error"))

@app.route("/download", methods=["post", "get"])
def download():
    if request.method == "GET":
        return redirect(url_for("index"))
    
    file_form = File_form()
    if not file_form.validate_on_submit():
        return redirect(url_for("index", error="invalid input"))
    
    c_hash = request.form.get("captcha-hash")
    c_text = request.form.get("captcha-text")
    if False: # not SIMPLE_CAPTCHA.verify(c_text, c_hash):
        return redirect(url_for("index", error="captcha failed!"))

    file = file_form.file.data

    if file_form.transfer_type.data == "audio":
        response = send_file(file_to_audio(file.read()), mimetype="audio/wav", as_attachment=file_form.download.data, download_name=f"{file.filename}.brain.wav")

    if file_form.transfer_type.data == "video":
        response = send_file(file_to_video(file.read()), mimetype="video/mp4", as_attachment=file_form.download.data, download_name=f"{file.filename}.brain.mp4")

    return response

def file_to_audio(data):
    padding = len(data) % 2
    if padding != 0:
        data += b"\x00"

    data = np.frombuffer(data, dtype=np.int16) #int32)
    audio = io.BytesIO()
    write(audio, 44100, data)

    return audio

def file_to_video(data):
    process = (
        ffmpeg
        .input("pipe:", format="rawvideo", pix_fmt="rgb8", s="64x64", r=60)
        .output("pipe:", pix_fmt="yuv420p", format="matroska", preset="ultrafast")
        .run_async(pipe_stdin=True, pipe_stdout=True)
    )

    padding = len(data) % 3072
    if padding != 0:
        data += b"\x00" * (3072 - padding)
    output_data, _ = process.communicate(input=data)
    
    return io.BytesIO(output_data)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")