import requests, json, datetime, time, pyttsx3, re, httplib2, random, sys, time, os
from moviepy.editor import *
from apiclient.discovery import build
from apiclient.errors import HttpError
from apiclient.http import MediaFileUpload
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

#TODO list:
#   - Auto run

def SetUp():
    global headers
    print("\nAuthorising Reddit account...")

    with open("reddit_info.json", "r") as info:
        info = json.load(info)

    CLIENT_ID = info["API"]["CLIENT_ID"]
    SECRET_KEY = info["API"]["SECRET_KEY"]
    auth = requests.auth.HTTPBasicAuth(CLIENT_ID, SECRET_KEY)

    data = {
        "grant_type": "password",
        "username": info["login"]["username"],
        "password": info["login"]["password"]
    }

    headers = {"User-Agent": "MyAPI/0.0.1"}
    res = requests.post("https://www.reddit.com/api/v1/access_token",auth=auth, data=data, headers=headers)
    TOKEN = res.json()["access_token"]
    headers["Authorization"] = f"bearer {TOKEN}"

    SortingVideos()

def SortingVideos():
    print("Sorting new videos...")
    with open("Video_Files/video_data.json") as dataRaw:
        data = json.load(dataRaw)
    files = [f for f in os.listdir(data["videoDir"]) if os.path.isfile(os.path.join(data["videoDir"], f))]
    for file in files:
        fileDir = data["videoDir"] + file
        clip = VideoFileClip(fileDir)

        if (clip.duration >= 60): #Set clips 60sec+ to Usable folder
            fileDirGo = data["videoDir"] + "Usable/" + file

            with open("Video_Files/video_data.json", "r+") as video_data_raw:
                video_data = json.load(video_data_raw)
                item = '{' + \
                    f'"name" : "{file}",' + \
                    '"time_since_use" : 0 ' + \
                    '}'
                video_data["videos"].append(json.loads(item))
                video_data_raw.seek(0)
                json.dump(video_data, video_data_raw, indent = 4)

            if (clip.duration >= 120): #Warns if video could be split into 2
                print(f"====================\n\
                    Notification:\nVideo {file} is {clip.duration}s long, meaning it can make multiple clips, spit video into multiple 60s clips to use it all\
                    \n====================")
        else: #Set clips under 60sec to Delete folder
            fileDirGo = data["videoDir"] + "Delete/" + file
        clip.close()
        MoveVideo(fileDir, fileDirGo) #Actually move video

    GetSubreddit("AskReddit")

def MoveVideo(fileDir, fileDirGo):
    os.replace(fileDir, fileDirGo)
    print(f"    {fileDir} > {fileDirGo}")

def GetSubreddit(subredditName):
    print("Getting posts...")
    res = requests.get("https://oauth.reddit.com/r/"+subredditName+"/top", headers=headers)
    with open("Post_Data/posts_data.json", "w") as outFile:
       json.dump(res.json(), outFile, indent=6)
    GetPostInfo(res, 1) #Get posts from online
    #GetPostsFromJson() #WARNING THIS FEATURE MAY NOT WORK! Get local store of posts/comments, remove above to not update posts

def GetPostsFromJson():
    postsArray = [ [ 0 for i in range(35) ] for j in range(25) ]

    count = 0
    with open("Post_Data/posts_data.json") as posts_data_raw:
        posts_data = json.load(posts_data_raw)
        for post in posts_data["data"]["children"]:
            postsArray[count][0] = post["data"]["title"]
            with open(f"Post_Data/Comment_Data/{count}.json") as posts_data:
                comments = json.load(posts_data)
                for commentNum in range(0, len(postsArray[0]) - 1):
                    comment = comments["Data"][1]["data"]["children"][commentNum]["data"]["body"]
                    postsArray[count][commentNum + 1] = comment
            count += 1
            if (count > 0): #number of videos
                break

    VideoSetup(postsArray)

def GetPostInfo(res, numOfVideos):
    print("Sorting posts...")

    for x in range(numOfVideos): #repeat for num of posts
        postCount = 0
        with open("Finished_Videos/video_data.json", "r") as video_data_raw:
            video_data = json.load(video_data_raw)
            uploadDay = (video_data["videos"][len(video_data["videos"]) - 1]["uploadTime"])[8:10]
            if (datetime.datetime.now().strftime("%d") != uploadDay):
                with open("post_num.txt", "r") as postCountF:
                    postCount = int(postCountF.read())

        postsArray = [[0 for i in range(60)] for j in range(24)]
        post_data = res.json()
        post = post_data["data"]["children"][postCount]
        daysSincePost = datetime.datetime.fromtimestamp(time.time() - post["data"]["created"]).strftime('%d')
        while (post["data"]["whitelist_status"] == "promo_adult_nsfw" or daysSincePost != "01"):
            postCount += 1
            post = post_data["data"]["children"][postCount]
            daysSincePost = datetime.datetime.fromtimestamp(time.time() - post["data"]["created"]).strftime('%d')
        postsArray[postCount][0] = post["data"]["title"]
        postsArray[postCount] = GetComments(post, postsArray, postCount)

        with open("post_num.txt", "w") as postCountF:
            postCountF.write(str(postCount + 1))
        VideoSetup(postsArray[postCount])

def GetComments(post, postsArray, postNum):
    print(f"Getting comments to post {str(postNum)}: '{postsArray[postNum][0]}'...")

    urlEnding = post["data"]["permalink"]
    comments = requests.get("https://oauth.reddit.com" + urlEnding, headers=headers)

    outFile = open(f"Post_Data/Comment_Data/{postNum}.json", "w")
    outFile.write('{\n      "Data":\n')
    json.dump(comments.json(), outFile, indent=6)
    outFile.write('\n}')
    outFile.close()

    with open(f"Post_Data/Comment_Data/{postNum}.json") as comments_raw:
        comments = json.load(comments_raw)
        emptyComments = 0
        for commentNum in range(0, len(comments["Data"][1]["data"]["children"]) - 1):
            comment = comments["Data"][1]["data"]["children"][commentNum]["data"]["body"]
            comment = ReviewComment(comment, ["Edit:", "edit:", "Update:", "update"], emptyComments)
            if (comment == ""):
                emptyComments += 1
            else:
                postsArray[postNum][commentNum + 1 - emptyComments] = comment
            if (commentNum >= len(postsArray[0])):
                break

    return postsArray[postNum]

def ReviewComment(text, deleteAfterWord, numBlockedComments):
    text = text.replace('\n', ' ').replace('\r', '')
    
    for word in deleteAfterWord:
        text = text.split(word, 1)[0]

    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'www.\S+', '', text)
    
    with open("Post_Data/profanity_list.txt") as list:
        words = list.readlines()
        for word in words:
            if word.strip() in text.lower():
                print(f"        Comment Blocked '{word.strip()}'")
                text = ""

    return text


def VideoSetup(textArray):
    print("\nSetting Up Video:")

    videoDir = ""
    with open("Video_Files/video_data.json", "r+") as video_data_raw:
        video_data = json.load(video_data_raw)
        videoNum = 0
        for video in video_data["videos"]:
            if (video["time_since_use"] < time.time() - 475200):
                videoDir = video_data["videoDir"] + "Usable/" + video["name"]
                video["time_since_use"]

                video_data["videos"][videoNum]["time_since_use"] = time.time()
                video_data_raw.seek(0)
                json.dump(video_data, video_data_raw, indent=4)
                video_data_raw.truncate()
                break
            videoNum += 1

    MakeVideo(textArray, videoDir)

def MakeVideo(textArray, videoDir):
    print("    Using", videoDir)
    if(videoDir != ""):
        clip = VideoFileClip(videoDir)
        screensize = (608, 1080)
        textSize = (int(screensize[0] - screensize[0] / 20), int(screensize[1] - screensize[1] / 20))
        print("    Screen Size:", screensize, textSize)
        BGaudioFile = "Video_Files\Bet_On_It.mp3"
        BGaudio = AudioFileClip(BGaudioFile).volumex(0.3)

        startTime = 0
        txtList = []
        audioClips = []
        for row in range(0, len(textArray)):
            if (isinstance(textArray[row], str)):
                audioclip = AudioFileClip(TextToSpeach(str(textArray[row]), str(row))).volumex(1.3)
                duration = audioclip.duration - 0.4
                
                if (row == 0):
                    BGaudioStart = 0
                    if (duration < 15.6):
                        BGaudioStart = 15.6 - duration
                    BGaudio = BGaudio.subclip(BGaudioStart, 60 + BGaudioStart)
                    print(f"    Background audio: {BGaudioFile} | Starting: {BGaudioStart}")
                    print("    Making Comments:")

                if (startTime + duration < 58):
                    audioClips.append(audioclip.set_start(startTime))
                    print(f"      ({row}) [{round((duration + startTime), 2)}s]...")

                    color = "white"
                    if (row == 0):
                        color = "grey"
                    txtList.append(TextFormating(textArray[row], textSize, color, "black", startTime, duration))

                    startTime += duration
                else:
                    break
            else:
                break
        
        ExportVideo(clip, BGaudio, audioClips, txtList, screensize, startTime, textArray[0])
    else:
        print(f"====================\n\
Notification:\nNo background videos to use, please add new ones, or rest the Video_Files/video_data.json[videos][time_since_use] to 0 file to reuse them\
\n====================")
        exit()

def TextFormating(string, size, color, outlinecolor, start, duration):
    fontSize = 50
    fontOutlineSize = 2
    if (len(string) > 350):
        fontPercent = (1 - ((len(string) - 350) / (950 - 350))) #(1 - ((characters - [min amont of characters]) / [max char amont] - [min char amont]))
        fontSize = int((50 - 34) * fontPercent + 34) #(([max font size] - [min font size]) * [num from above] + [min font size])
        fontOutlineSize = ((2 - 1) * fontPercent + 1) #(([max font outline size] - [min font outline size]) * [num from above] + [min font outline size])
    text = TextClip(string, size = size, method='caption', color = color, stroke_color=outlinecolor, stroke_width=fontOutlineSize, fontsize = fontSize, kerning=-3, interline=-5, font = "Consolas-bold").set_start(start).set_pos('center').set_duration(duration)
    return text
def TextToSpeach(text, name):
    engine = pyttsx3.init()
    fileName = "Video_Files/Voice_Clips/" + name + ".mp3"

    engine.save_to_file(text, fileName)
    engine.runAndWait()
    return fileName

def ExportVideo(video, BGaudio, audios, txts, screensize, videoDur, videoName):
    video = video.subclip(0, videoDur).crop(x1=(1920/2 - screensize[0]/2), y1=0, x2=(1920/2 + screensize[0]/2) ,y2=screensize[1])

    video = CompositeVideoClip([video, *txts])
    audio = CompositeAudioClip([BGaudio, *audios])
    video = video.set_audio(audio).set_duration(videoDur)

    fileName = str(datetime.datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')) + ".mp4"
    video.write_videofile("Finished_Videos/" +  fileName, threads = 6)
    video.close()
    VideoDataExported(fileName, videoName, str(datetime.date.today() + datetime.timedelta(1)), 
    ["01:00:00","06:00:00","13:00:00","14:00:00","15:00:00","16:00:00"])

def VideoDataExported(fileName, videoName, uploadDate, uploadTimes):
    print("\nSaving video data...")

    with open("Finished_Videos/video_data.json", "r+") as video_data_raw:
        video_data = json.load(video_data_raw)

        uploadTimeNum = 0
        if (len(video_data["videos"]) > 0):
            for time in uploadTimes:
                uploadTimeNum += 1
                if (time == str(video_data["videos"][len(video_data["videos"]) - 1]["uploadTime"])[11:19]):
                    break
            if (uploadTimeNum >= len(uploadTimes)):
                uploadTimeNum = 0

        if (len(videoName) > 100):
            videoName = videoName[0:96] + "..."
        
        videoName = videoName.replace('"','\\"')
        item = '{' + \
            f'"fileName" : "{fileName}",' + \
            f'"videoName" : "{videoName}",' + \
            f'"uploadTime" : "{uploadDate}T14:00:00+00:00"' + \
        '}'
        #f'"uploadTime" : "{uploadDate}T{uploadTimes[uploadTimeNum]}+00:00"' + \ (for different upload times)
        video_data["videos"].append(json.loads(item))
        video_data_raw.seek(0)
        json.dump(video_data, video_data_raw, indent = 4, ensure_ascii=False)

    YouTubeUploadSetup(json.loads(item))

def YouTubeUploadSetup(videoMetadata):
    print("\n\nAuthorising YouTube account...")
    httplib2.RETRIES = 1

    MAX_RETRIES = 10
    RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError)
    RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
    CLIENT_SECRETS_FILE = "youtube_info.json"
    YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
    YOUTUBE_API_SERVICE_NAME = "youtube"
    YOUTUBE_API_VERSION = "v3"
    MISSING_CLIENT_SECRETS_MESSAGE = """
    WARNING: Please configure OAuth 2.0

    To make this sample run you will need to populate the youtube_info.json file
    found at:

    %s

    with information from the API Console
    https://console.cloud.google.com/

    For more information about the youtube_info.json file format, please visit:
    https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
    """ % os.path.abspath(os.path.join(os.path.dirname(__file__),
                                    CLIENT_SECRETS_FILE))

    uploadData = {
        "MAX_RETRIES":                   MAX_RETRIES, 
        "RETRIABLE_EXCEPTIONS":          RETRIABLE_EXCEPTIONS, 
        "RETRIABLE_STATUS_CODES":        RETRIABLE_STATUS_CODES, 
        "CLIENT_SECRETS_FILE":           CLIENT_SECRETS_FILE, 
        "YOUTUBE_UPLOAD_SCOPE":          YOUTUBE_UPLOAD_SCOPE, 
        "YOUTUBE_API_SERVICE_NAME":      YOUTUBE_API_SERVICE_NAME, 
        "YOUTUBE_API_VERSION":           YOUTUBE_API_VERSION, 
        "MISSING_CLIENT_SECRETS_MESSAGE":MISSING_CLIENT_SECRETS_MESSAGE}

    UploadVideo(videoMetadata, uploadData)

def UploadVideo(videoMetadata, uploadData):
    print("Making video metadata...\n\n")

    # argparser.add_argument("--file", help="Video file to upload", default=f"Finished_Videos/{videoMetadata['fileName']}")
    # argparser.add_argument("--publishedAt", help="Video upload time", default=videoMetadata["uploadTime"])
    # argparser.add_argument("--title", help="Video title", default=videoMetadata["videoName"])
    # argparser.add_argument("--selfDeclaredMadeForKids", default=False, help="Is video made for kids")
    # argparser.add_argument("--category", default="20", help="Numeric video category.")
    # argparser.add_argument("--privacyStatus", default="private", help="Video privacy status.")
    args = argparser.parse_args()
    args.file = f"Finished_Videos/{videoMetadata['fileName']}"
    args.publishedAt = videoMetadata["uploadTime"]
    args.title = videoMetadata["videoName"]
    args.selfDeclaredMadeForKids = False
    args.category = 19
    args.privacyStatus = "private"

    if not os.path.exists(args.file):
        exit("Please specify a valid file using the --file= parameter.")

    youtube = get_authenticated_service(args, uploadData)
    try:
        initialize_upload(youtube, args, uploadData, videoMetadata['fileName'])
    except HttpError as e:
        print("An HTTP error %d occurred:\n%s" % (e.resp.status, e.content))

def get_authenticated_service(args, uploadData):
  flow = flow_from_clientsecrets(uploadData["CLIENT_SECRETS_FILE"],
    scope=uploadData["YOUTUBE_UPLOAD_SCOPE"],
    message=uploadData["MISSING_CLIENT_SECRETS_MESSAGE"])

  storage = Storage("%s-oauth2.json" % sys.argv[0])
  credentials = storage.get()

  if credentials is None or credentials.invalid:
    credentials = run_flow(flow, storage, args)

  return build(uploadData["YOUTUBE_API_SERVICE_NAME"], uploadData["YOUTUBE_API_VERSION"],
    http=credentials.authorize(httplib2.Http()))
def initialize_upload(youtube, options, uploadData, fileName):
    tags = None

    body=dict(
    snippet=dict(
        title=options.title,
        description="",
        categoryId=options.category
    ),
    status=dict(
        privacyStatus="private",
        publishAt=options.publishedAt,
        selfDeclaredMadeForKids=False
    )
    )

    insert_request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,

        media_body=MediaFileUpload(options.file, chunksize=-1, resumable=True)
    )
    resumable_upload(insert_request, uploadData, fileName)
def resumable_upload(insert_request, uploadData, fileName):
    response = None
    error = None
    retry = 0
    while response is None:
        try:
            print("Uploading file...")
            status, response = insert_request.next_chunk()
            if response is not None:
                if 'id' in response:
                    print("   Video id '%s' was successfully uploaded." % response['id'])
                else:
                    exit("    The upload failed with an unexpected response: %s" % response)
        except HttpError as e:
            if e.resp.status in uploadData["RETRIABLE_STATUS_CODES"]:
                error = "A retriable HTTP error %d occurred:\n%s" % (e.resp.status,
                                                                    e.content)
            else:
                raise
        except uploadData["RETRIABLE_EXCEPTIONS"] as e:
            error = "A retriable error occurred: %s" % e

        if error is not None:
            print(    error)
            retry += 1
            if retry > uploadData["MAX_RETRIES"]:
                exit("No longer attempting to retry.")

            max_sleep = 2 ** retry
            sleep_seconds = random.random() * max_sleep
            print("   Sleeping %f seconds and then retrying..." % sleep_seconds)
            time.sleep(sleep_seconds)
    print("\n\n")


startOfScript = time.time()
SetUp()
print(f"\nFinished Script: {time.time() - startOfScript}s\n\n")

nextScript = "moveFinishedVideos.pyw"
print(f"Now running: {nextScript}")
os.system(nextScript)