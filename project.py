from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_
from flask_marshmallow import Marshmallow
from flask_bcrypt import Bcrypt
import uuid
import jwt
import datetime
from functools import wraps
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from slugify import slugify
import os, sys, shutil, json
import os.path
from flask_cors import CORS, cross_origin
import transcode
import subprocess
from flask_inputs import Inputs
import glob



# from flask_cors import CORS, cross_origin
# init app
app = Flask(__name__)
# CORS(app, support_credentials=True)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:mypass@localhost/sampledb'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '#th3coder$$'
app.config['PATH_NAME'] =  os.path.dirname(sys.argv[0])
app.config['VIDEOS_PATH_NAME'] =  "assets/media/videos"
app.config["ALLOWED_VIDEO_EXTENSIONS"] = ["MP4"]

# init db
db = SQLAlchemy(app)
# init Ma
ma = Marshmallow(app)
# init Bycrypt
bcrypt = Bcrypt(app)

def create_error_log(error):  # pass error as string
    try:
        f = open("error_log.log", "a+")
        f.write("Log: " + str(datetime.datetime.now())+ " " + str(error)  + " \r\n")
        f.close()
    except Exception as e:
        pass

def allowed_image(filename):
    # We only want files with a . in the filename
    if not "." in filename:
        return jsonify({'input_error': {'message': 'Upload correct images'}})

    # Split the extension from the filename
    ext = filename.rsplit(".", 1)[1]

    # Check if the extension is in ALLOWED_IMAGE_EXTENSIONS
    if not ext.upper() in app.config["ALLOWED_IMAGE_EXTENSIONS"]:
        return False
    else:
        return True

def allowed_video(filename):
    # We only want files with a . in the filename
    if not "." in filename:
        return jsonify({'input_error': {'message': 'Only mp4 videos are allowed'}})

    # Split the extension from the filename
    ext = filename.rsplit(".", 1)[1]
    # Check if the extension is in ALLOWED_IMAGE_EXTENSIONS
    if not ext.upper() in app.config["ALLOWED_VIDEO_EXTENSIONS"]:
        return False
    else:
        return True

def get_file_extension(filename):
    if not "." in filename:
        return jsonify({'input_error': {'message': 'Upload correct files'}})

    # Split the extension from the filename
    ext = filename.rsplit(".", 1)[1]
    return ext.upper()


def get_actual_filename(name):
    name = "%s[%s]" % (name[:-1], name[-1])
    return glob.glob(name)[0]

def getLength(input_video):
    result = subprocess.Popen('ffprobe -i input_video -show_entries format=duration -v quiet -of csv="p=0"', stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    output = result.communicate()
    return output[0]

def get_duration(file):
    duration = subprocess.check_output(['ffprobe', '-i', file, '-show_entries', 'format=duration', '-v', 'quiet', '-of', 'csv=%s' % ("p=0")])
    print(duration)

def delete_files(files_to_delete):
    try:
        for file_to_delete in files_to_delete:
            if os.path.isfile(file_to_delete):
                os.remove(file_to_delete)
            elif os.path.isdir(file_to_delete):
                shutil.rmtree(file_to_delete)
            else:
                create_error_log("Can't find the folder "+str(file_to_delete))
    except Exception as e:
        create_error_log(str(e))
        pass

def delete_objects(objects_to_delete):
    try:
        for object_to_delete in objects_to_delete:
            db.session.delete(object_to_delete)
    except Exception as e:
        create_error_log(str(e))
        pass

class Video(db.Model):
    __tablename__ = "videos"
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(100), unique=True, nullable=False)
    trailer_id = db.Column(db.Integer, db.ForeignKey('trailers.id'), nullable=True, default=None)
    video_file = db.Column(db.String(100), nullable=False)
    video_file_type = db.Column(db.String(7), nullable=False)

    def __init__(self, public_id, video_file, video_file_type):
        self.public_id = public_id
        self.video_file = video_file
        self.video_file_type = video_file_type
      
# video routes begin here
@app.route('/video', methods=['POST'])
def add_video():
    try:
        uploaded_files = []
        created_objects = []
        video_file = request.files['video_file']
    
        # generate a unique id for the media
        public_id = str(uuid.uuid4())
        # upload video
        ext = get_file_extension(video_file.filename)
        video_file_name = "" + public_id + "." + ext
        video_file.save(os.path.join(app.config['VIDEOS_PATH_NAME'], video_file_name))
        video_file_type = ext
        # get media base name
        try:
            subprocess.run([app.config['PATH_NAME'] + "/transcode.py", app.config['VIDEOS_PATH_NAME'] + "/" + video_file_name])
            os.remove(app.config['VIDEOS_PATH_NAME'] + "/" + video_file_name)
            video_folder_name = os.path.splitext(app.config['VIDEOS_PATH_NAME']+"/"+video_file_name)[0]
                
            uploaded_files.append(video_folder_name)

        except Exception as e:
            create_error_log(str(e))
            for uploaded_file in uploaded_files:
                os.remove(uploaded_file)
            return jsonify({'db_error': {'message': 'Video Conversion error'}})
        # save the video details.
        try:
            new_video = Video(public_id, video_file_name, video_file_type)
            db.session.add(new_video)
            db.session.commit()
            created_objects.append(new_video)
        except Exception as e:
            create_error_log(str(e))
            delete_files(uploaded_files)
            delete_objects(created_objects)
            return jsonify({'db_error': {'message': 'There was an internal error'}})

        return jsonify({'response': {'message': 'Video created successfully'}})
    except Exception as e:
        create_error_log(str(e))
        delete_files(uploaded_files)
        delete_objects(created_objects)
        return jsonify({'db_error': {'message': 'There was an internal error'}})
# end create video

# start edit video
@app.route('/videos/<public_id>', methods=['PUT'])
def update_video(public_id):
    try:
        # check if this video exists
        video = Video.query.filter_by(public_id=public_id).first()
        if not video:
            return jsonify({'not_found': {'message': 'This video cannot be found'}})
        this_video = video_schema.dump(video)
       
        try:
            video_file = request.files['video_file']
            status = 'review'
        except KeyError as e:
            create_error_log(str(e))
            return jsonify({'input_error': {'message': 'Some required fields are not filled.'}})
        except Exception as e:
            create_error_log(str(e))
            return jsonify({'input_error': {'message': 'Some required fields are not filled.'}})

        # generate a unique id for the media
        duration = 7.00
        if video_file:
            if video_file.filename == "":
                return jsonify({'input_error': {'message': 'Video file is missing'}})
            if not allowed_video(video_file.filename):
                return jsonify({'input_error': {'message': 'Only mp4 videos are allowed.'}})
        # create videos folder
        try:
            if not os.path.exists(app.config['VIDEOS_PATH_NAME']):
                original_umask = os.umask(0o000)
                os.makedirs(app.config['VIDEOS_PATH_NAME'], 0o777)
        except FileExistsError as e:
            pass
        except Exception as e:
            create_error_log(str(e))
            return jsonify({'db_error': {'message': 'Folder creation error'}})
        finally:
            os.umask(0o000)
        
        # upload video
        if video_file:
            # remove older video
            if os.path.isdir(app.config['VIDEOS_PATH_NAME']+"/"+public_id):
                shutil.rmtree(app.config['VIDEOS_PATH_NAME']+"/"+public_id)
            ext = get_file_extension(video_file.filename)
            video_file_name = "" + public_id + "." + ext
            video_file_type = ext
            video_file.save(os.path.join(app.config['VIDEOS_PATH_NAME'], video_file_name))
            try:
                subprocess.run([app.config['PATH_NAME'] + "/transcode.py", app.config['VIDEOS_PATH_NAME']+"/"+video_file_name])
                os.remove(app.config['VIDEOS_PATH_NAME']+"/"+video_file_name)
                video.video_file = video_file_name
                video.video_file_type = video_file_type
            except Exception as e:
                create_error_log(str(e))
                if os.path.isfile(app.config['VIDEOS_PATH_NAME']+"/"+video_file_name):
                    os.remove(app.config['VIDEOS_PATH_NAME']+"/"+video_file_name)
                return jsonify({'db_error': {'message':'Video conversion error'}})
            return jsonify({'response': {'message': 'Video updated successfully'}})
    except Exception as e:
        print(e)
        create_error_log(str(e))
        return jsonify({'db_error': {'message': 'There was an internal error'}})
class VideoSchema(ma.Schema):
    class Meta:
        strict = True
        fields = ('id', 'public_id', 'video_file')

video_schema = VideoSchema()
videos_schema = VideoSchema(many=True)

# Run server
if __name__ == '__main__':
    app.run(debug=True)