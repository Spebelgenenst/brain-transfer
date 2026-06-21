from flask import Flask, render_template, redirect, url_for, request, send_file, make_response, session

from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import FileField, SelectField, BooleanField, StringField
from wtforms.validators import InputRequired, Optional, ValidationError

from flask_simple_captcha import CAPTCHA

import json
import io
import ffmpeg
import os

import numpy as np
from scipy.io.wavfile import write

import psutil

from random import randint

from datetime import timedelta, datetime

from flask_apscheduler import APScheduler
import sys

sys.set_int_max_str_digits(1000000000)

with open("credentials.json", "r") as f:
    credentials = json.load(f)

app = Flask(__name__)

app.config["SECRET_KEY"] = credentials["secretKey"] #flask-wtf
csrf = CSRFProtect(app)

CAPTCHA_CONFIG = {
    "CAPTCHA_LENGTH": 6,
    "CAPTCHA_DIGITS": True,
    "BACKGROUND_COLOR": (255,255,255),
    "TEXT_COLOR": (0,0,255)
}

SIMPLE_CAPTCHA = CAPTCHA(CAPTCHA_CONFIG)
app = SIMPLE_CAPTCHA.init_app(app)

# initialize scheduler
scheduler = APScheduler()
# if you don't wanna use a config, you can set options here:
# scheduler.api_enabled = True
scheduler.init_app(app)
scheduler.start()


def FileSizeLimit():
    max_bytes = psutil.virtual_memory().available - 100*1024*1024
    def file_length_check(form, field):
        if len(field.data.read()) > max_bytes:
            raise ValidationError(f"File size must be less than {max_bytes/1024/1024}MB")
        field.data.seek(0)
    return file_length_check

class File_form(FlaskForm):
    transfer_type = SelectField("transfer type", choices=[("audio/wav", "Audio"), ("video/mp4", "Video"), ("words/txt", "Words"), ("number/txt", "Number")])
    download = BooleanField("Direct Download")
    file = FileField("file", [InputRequired(), FileSizeLimit()])

@app.route("/")
def index():
    file_form = File_form()
    captcha = SIMPLE_CAPTCHA.create()
    return render_template("index.html", captcha=captcha, file=file_form, error=request.args.get("error"))

@app.route("/process_file", methods=["post", "get"])
def process_file():
    if request.method == "GET":
        return redirect(url_for("index"))

    c_hash = request.form.get("captcha-hash")
    c_text = request.form.get("captcha-text")
    if False: # not (SIMPLE_CAPTCHA.verify(c_text, c_hash) or request.user_agent == "w3m"):
        return redirect(url_for("index", error="captcha failed!"))
    
    file_form = File_form()
    if not file_form.validate_on_submit():
        return redirect(url_for("index", error="invalid input"))

    file = file_form.file.data

    transfer_type = file_form.transfer_type.data

    file_name = str(datetime.now())
    session[transfer_type] = file_name

    if transfer_type == "audio/wav":
        file_to_audio(file.read(), file_name)

    if transfer_type == "video/mp4":
        file_to_video(file.read(), file_name)

    if transfer_type == "words/txt":
        file_to_words(file, file_name)

    if transfer_type == "number/txt":
        file_to_number(file, file_name)

    if file_form.download.data:
        return redirect(url_for("download", transfer_type=transfer_type))

    return redirect(url_for("media", transfer_type=transfer_type))

@app.route("/media", methods=["post", "get"])
def media():
    transfer_type = request.args.get("transfer_type")

    if transfer_type in ["words/txt", "number/txt"]:
        with open("media/" + session[transfer_type], "r") as f:
            text = f.read()
        return render_template("reader.html", text=text)
        
    return render_template("player.html", transfer_type=transfer_type)

@app.route("/get_file")
def get_file():
    transfer_type = request.args.get("transfer_type")
    file_path = "media/" + session[transfer_type]
    #if not os.path.exists(file_path):
    #    return redirect(url_for("index"))
    return send_file(file_path, as_attachment=False, mimetype=transfer_type)

@app.route("/download")
def download():
    transfer_type = request.args.get("transfer_type")
    file_path = "media/" + session[transfer_type]
    return send_file(file_path, download_name="brain_transfer_"+transfer_type.replace("/", "."), as_attachment=True)

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")
#@app.errorhandler(404)
#def error_404(e):
#    return "404"

def file_to_audio(data, file_name):
    padding = len(data) % 2
    if padding != 0:
        data += b"\x00"

    data = np.frombuffer(data, dtype=np.int16) #int32)
    write("media/" + file_name, 44100, data)

def file_to_video(data, file_name):
    process = (
        ffmpeg
        .input("pipe:", format="rawvideo", pix_fmt="rgb8", s="64x64", r=30)
        .output("media/" + file_name, pix_fmt="yuv420p", format="matroska", preset="ultrafast")
        .run_async(pipe_stdin=True)
    )

    padding = len(data) % 4096
    if padding != 0:
        data += b"\x00" * (4096 - padding)

    process.communicate(input=data)

def file_to_words(data, file_name):
    with open("media/" + file_name, "w") as file, open("words_alpha.txt", "r") as word_list:
        words = word_list.readlines()
        while True:
            byte_data = data.read(2)
            if not byte_data:
                break
            number = int.from_bytes(byte_data, byteorder='little')
            word = words[number*5].strip()
            file.write(str(word) + " ")

def file_to_number(data, file_name):
    with open("media/" + file_name, "w") as file:
        byte_data = data.read()
        number = int.from_bytes(byte_data, byteorder='little')
        file.write(str(number))

@scheduler.task("interval", hours=12)
def delete_files():
    cutoff_time = datetime.now() - timedelta(hours=12)
    files=os.listdir("media/")
    
    for file in files:
        if datetime.strptime(file, '%Y-%m-%d %H:%M:%S.%f') < cutoff_time:
            os.remove("media/"+file)
        

if __name__ == "__main__":
    delete_files()
    app.run(debug=True, host="0.0.0.0")