# Youtube Video Uploader Android Termux
A python script that uses YouTube Data API to upload videos automatically on YouTube from Android Mobile using Termux


# 1️⃣ Setup Environment 
```sh
termux-setup-storage #Run it and Make sure termux has Storage Permission
cd ~/.termux/tasker/YoutubeUpload #It should Be (~/.termux) then you can setup the folder structure of your choice
pkg install rust clang make pkg-config openssl libffi
python -m venv env
source env/bin/activate
pip install --upgrade pip
pip install google-api-python-client google-auth-oauthlib
deactivate
```

# 2️⃣ Create A Json File Named `uploadconfig.json` In termux accessible folder. 
```json
{
  "video_path": "/storage/emulated/0/Termux/Accessible/Path/videoFile.mp4",
  "thumbnail_path": "/storage/emulated/0/Termux/Accessible/Path/thumbnail.jpg",
  "title": "My Test Video",
  "description": "Uploaded from Termux",
  "tags": "termux,upload",
  "category_id": "22",
  "privacy": "private",
  "playlist_name": "TERMUX UPLOAD PLAYLIST"
}
```

## Mandatory Fields in `uploadconfig.json`
- Mandatory Fields             : `video_path` & `title` (YOU CANNOT LEAVE THESE EMPTY)
- Optional Can Be Skipped      : `thumbnail_path`, `description`, `tags` & `playlist_name` (These two will not processed at all if Skipped. If Playlist filled doesn't exists it will be created.
- Mandatory and Can Be Skipped : `category_id` & `privacy` (These Will set default to 22 & private by default if Skipped)
- And You should Place this `uploadconfig.json` file in a path where termux can easily access to and You have to mention it's path in the `upload.py` code


# 3️⃣ Required setup in Google Cloud Console

Create a Project in [Google API](https://console.cloud.google.com)

Open → APIs & Services → Enable API Services

Search `Youtube Data API V3` and Enable It

Credentials → Create Credential → OAuth 2.0 Client 

Click `Configure Concent Screen` → Get Started → Give it a Name like "Youtube Upload" Place Email Next → External Audience → Place your Email → Agree → Finish → Create.

Client → Create Client → Desktop app → Name It Anything Like "Youtube Upload" → Create → Download JSON and Rename the file to `client.json`

In Audience (Left Panel) Add Test User your email.

Place the Downloaded `client.json` file in the same folder where you have the Environment  setup. In this case it's `~/.termux/tasker/YoutubeUpload/client.json`

## `client.json` Should Look similar to this
```json
{
    "installed": {
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "client_id": "YOUR CLIENT ID.apps.googleusercontent.com",
        "client_secret": "YOUR CLIENT SECRET CODE",
        "project_id": "gen-lang-client-PROJECT ID",
        "redirect_uris": [
            "http://localhost"
        ],
        "token_uri": "https://oauth2.googleapis.com/token"
    }
}
```

# 4️⃣ Place the `upload.py`script in the Environment Folder in this case `~/.termux/tasker/YoutubeUpload/upload.py`

```py
import os
import json
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ===== CONFIG =====
CONFIG_PATH = "/storage/emulated/0/+TaskerData/YoutubeUpload/uploadconfig.json"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube"
]

# Load JSON config from Tasker
if not os.path.exists(CONFIG_PATH):
    print(f"Config file not found: {CONFIG_PATH}")
    exit(1)

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

# ----- Required -----
VIDEO_PATH = config.get("video_path")
TITLE = config.get("title")
if not VIDEO_PATH or not TITLE:
    print("VIDEO_PATH and TITLE are required.")
    exit(1)

# ----- Optional -----
DESCRIPTION = config.get("description", "")
TAGS = config.get("tags", "")
TAGS = [tag.strip() for tag in TAGS.split(",")] if TAGS else None

CATEGORY_ID = config.get("category_id")
PRIVACY = config.get("privacy")
if CATEGORY_ID not in [str(i) for i in range(1, 32)]:
    CATEGORY_ID = "22"
if PRIVACY not in ["private", "unlisted", "public"]:
    PRIVACY = "private"

PLAYLIST_NAME = config.get("playlist_name")
THUMBNAIL_PATH = config.get("thumbnail_path")
if THUMBNAIL_PATH and not os.path.exists(THUMBNAIL_PATH):
    print(f"Thumbnail path invalid, skipping thumbnail: {THUMBNAIL_PATH}")
    THUMBNAIL_PATH = None

# ===== Authentication =====
creds = None
if os.path.exists("token.pickle"):
    with open("token.pickle", "rb") as token:
        creds = pickle.load(token)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            "client.json",
            SCOPES,
            redirect_uri="urn:ietf:wg:oauth:2.0:oob"
        )
        auth_url, _ = flow.authorization_url(prompt="consent")
        print("\nOpen this URL in your browser:\n")
        print(auth_url)
        code = input("\nPaste the authorization code here: ").strip()
        flow.fetch_token(code=code)
        creds = flow.credentials

    with open("token.pickle", "wb") as token:
        pickle.dump(creds, token)

# ===== Build YouTube service =====
youtube = build("youtube", "v3", credentials=creds)

# ===== Upload Video =====
media = MediaFileUpload(VIDEO_PATH, resumable=True)
request = youtube.videos().insert(
    part="snippet,status",
    body={
        "snippet": {
            "title": TITLE,
            "description": DESCRIPTION,
            "tags": TAGS,
            "categoryId": CATEGORY_ID
        },
        "status": {"privacyStatus": PRIVACY}
    },
    media_body=media
)

print("Uploading video...")
response = None
while response is None:
    status, response = request.next_chunk()
    if status:
        print(f"Upload progress: {int(status.progress() * 100)}%")

video_id = response["id"]
print("\nUpload complete.")
print("Video ID:", video_id)

# ===== Upload Thumbnail =====
if THUMBNAIL_PATH:
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(THUMBNAIL_PATH)
        ).execute()
        print(f"Thumbnail uploaded: {THUMBNAIL_PATH}")
    except Exception as e:
        print(f"Failed to upload thumbnail, skipping. Error: {e}")

# ===== Playlist Handling =====
def get_or_create_playlist(youtube, name):
    playlists_request = youtube.playlists().list(
        part="snippet",
        mine=True,
        maxResults=50
    )
    while playlists_request:
        playlists_response = playlists_request.execute()
        for item in playlists_response.get("items", []):
            if item["snippet"]["title"] == name:
                return item["id"]
        playlists_request = youtube.playlists().list_next(playlists_request, playlists_response)

    create_request = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {"title": name, "description": "Playlist created via Termux script"},
            "status": {"privacyStatus": "private"}
        }
    )
    playlist_response = create_request.execute()
    return playlist_response["id"]

# Add video to playlist if provided
if PLAYLIST_NAME:
    playlist_id = get_or_create_playlist(youtube, PLAYLIST_NAME)
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        }
    ).execute()
    print(f"Video added to playlist '{PLAYLIST_NAME}'.")
```

## So the current Structure Look Like this
```tree
~/.termux/tasker/YoutubeUpload/
 ├── env/
 ├── upload.py
 ├── client.json
```

# 5️⃣ If You want to manually trigger the upload 
# ⚠❗(You should Do this for first Time Before Trying it in Tasker.)❗⚠
```sh
cd ~/.termux/tasker/YoutubeUpload #It should Be (~/.termux) then you can setup the folder structure of your choice
python -m venv env
source env/bin/activate
python upload.py #It will have (env) At Beginning. For the First Time You need to Autherize it with your Google Account. (Read Below) Once Upload Finished Deactivate the Virtual Environment
deactivate
```

By Doing this it will ask you to goto a link for Authentication code. Copy the link from termux and Paste it in your browser login to your google account And Allow the Permissions. Copy the Autherization Code and Paste it in Termux And Press Enter..

After Succefull Entry of Autherization Code your file structure will have new File Like this.
```
~/.termux/tasker/YoutubeUpload/
 ├── env/
 ├── upload.py
 ├── token.pickle
 ├── client.json
```

You need to delete this  `token.pickle` first if you ever want to use different account


# 6️⃣ Trigger upload From Tasker - Place the `upload.sh`script in the Environment Folder in this case `~/.termux/tasker/YoutubeUpload/upload.sh`

## `upload.sh`
```sh
cd /data/data/com.termux/files/home/.termux/tasker/YoutubeUpload && env/bin/python upload.py
```

Once You place this file the stucture look similar to 
```
~/.termux/tasker/YoutubeUpload/
 ├── env/
 ├── upload.py
 ├── upload.sh
 ├── token.pickle
 ├── client.json
```


And Make `upload.sh` executable by running this command in termux manually once.
```sh
cd ~/.termux/tasker/YoutubeUpload/
chmod +x upload.sh
```

And In Tasker Termux Action In executable Place `YoutubeUpload/upload.sh`

That's it. Now It will upload the File which is mentioned int the `uploadconfig.json` just modify the contents in it to make different Uploads.
