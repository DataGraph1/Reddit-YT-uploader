import os, json

with open("Video_Files/video_data.json") as dataRaw:
    data = json.load(dataRaw)
videoDir = data["videoDir"]

for file in os.listdir("Finished_Videos/"):
    if (os.path.splitext(file)[-1] == ".mp4"):
        fileDir = "Finished_Videos/" + file
        fileDirGo = videoDir + "Delete/" + file
        os.replace(fileDir, fileDirGo)