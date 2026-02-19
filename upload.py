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
