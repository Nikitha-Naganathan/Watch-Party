from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_from_directory
)

from flask_socketio import (
    SocketIO,
    join_room,
    leave_room,
    emit
)

import sqlite3
import random
import string
import uuid
import os
import re


# =========================================================
# APP
# =========================================================

app = Flask(
    __name__,
    static_folder='Static',
    static_url_path='/Static'
)

app.config["SECRET_KEY"] = "watch-party-secret-key"

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    logger=True,
    engineio_logger=True
)


# =========================================================
# DATABASE
# =========================================================

DATABASE = "database/watchparty.db"


# =========================================================
# TEMPORARY VIDEO STORAGE
# =========================================================

UPLOAD_FOLDER = "temporary_videos"

ALLOWED_VIDEO_EXTENSIONS = {
    "mp4",
    "webm",
    "ogg",
    "mov",
    "m4v"
}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():

    connection = sqlite3.connect(
        DATABASE
    )

    connection.row_factory = sqlite3.Row

    return connection


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def initialize_database():

    os.makedirs(
        os.path.dirname(DATABASE),
        exist_ok=True
    )

    connection = get_db()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rooms (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            room_code TEXT UNIQUE NOT NULL,

            room_name TEXT NOT NULL,

            room_type TEXT NOT NULL,

            max_players INTEGER NOT NULL,

            theme TEXT NOT NULL,

            creator TEXT NOT NULL,

            active INTEGER DEFAULT 1

        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS participants (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            room_code TEXT NOT NULL,

            player_name TEXT NOT NULL

        )
        """
    )

    participant_columns = connection.execute(
        "PRAGMA table_info(participants)"
    ).fetchall()

    participant_column_names = [
        column["name"]
        for column in participant_columns
    ]

    if "player_id" not in participant_column_names:

        connection.execute(
            """
            ALTER TABLE participants
            ADD COLUMN player_id TEXT
            """
        )

    room_columns = connection.execute(
        "PRAGMA table_info(rooms)"
    ).fetchall()

    room_column_names = [
        column["name"]
        for column in room_columns
    ]

    if "creator_player_id" not in room_column_names:

        connection.execute(
            """
            ALTER TABLE rooms
            ADD COLUMN creator_player_id TEXT
            """
        )

    if "video_type" not in room_column_names:

        connection.execute(
            """
            ALTER TABLE rooms
            ADD COLUMN video_type TEXT
            """
        )

    if "video_source" not in room_column_names:

        connection.execute(
            """
            ALTER TABLE rooms
            ADD COLUMN video_source TEXT
            """
        )

    if "video_name" not in room_column_names:

        connection.execute(
            """
            ALTER TABLE rooms
            ADD COLUMN video_name TEXT
            """
        )

    connection.commit()

    connection.close()


# Initialize database
initialize_database()


# =========================================================
# ROOM CODE
# =========================================================

def generate_room_code():

    characters = (
        string.ascii_uppercase
        + string.digits
    )

    while True:

        code = "".join(
            random.choices(
                characters,
                k=6
            )
        )

        connection = get_db()

        existing_room = connection.execute(
            """
            SELECT id
            FROM rooms
            WHERE room_code = ?
            """,
            (code,)
        ).fetchone()

        connection.close()

        if existing_room is None:

            return code


# =========================================================
# PLAYER ID
# =========================================================

def generate_player_id():

    return str(
        uuid.uuid4()
    )


# =========================================================
# GET PARTICIPANTS
# =========================================================

def get_participants(room_code):

    connection = get_db()

    participants = connection.execute(
        """
        SELECT
            id,
            room_code,
            player_name,
            player_id

        FROM participants

        WHERE room_code = ?

        ORDER BY id ASC
        """,
        (room_code,)
    ).fetchall()

    connection.close()

    return participants


# =========================================================
# GET PLAYER COUNT
# =========================================================

def get_player_count(room_code):

    connection = get_db()

    count = connection.execute(
        """
        SELECT COUNT(*) AS total

        FROM participants

        WHERE room_code = ?
        """,
        (room_code,)
    ).fetchone()["total"]

    connection.close()

    return count


# =========================================================
# VIDEO HELPERS
# =========================================================

def allowed_video(filename):

    if not filename:

        return False

    if "." not in filename:

        return False

    extension = filename.rsplit(
        ".",
        1
    )[1].lower()

    return extension in ALLOWED_VIDEO_EXTENSIONS


# =========================================================
# DELETE UPLOADED VIDEO
# =========================================================

def delete_room_video(room):

    if room is None:
        return

    try:

        video_type = room["video_type"]

        video_source = room["video_source"]

    except (KeyError, IndexError):

        return

    if video_type != "upload":
        return

    if not video_source:
        return

    filename = os.path.basename(
        video_source
    )

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    try:

        if os.path.exists(filepath):

            os.remove(filepath)

    except OSError:

        pass


# =========================================================
# YOUTUBE ID EXTRACTION
# =========================================================

def get_youtube_id(url):

    if not url:
        return None

    url = url.strip()

    patterns = [

        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_-]{11})",

        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?[^#]*v=([A-Za-z0-9_-]{11})",

        r"(?:https?://)?(?:www\.)?youtu\.be/([A-Za-z0-9_-]{11})",

        r"(?:https?://)?(?:www\.)?youtube\.com/embed/([A-Za-z0-9_-]{11})",

        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]{11})",

        r"(?:https?://)?(?:www\.)?youtube-nocookie\.com/embed/([A-Za-z0-9_-]{11})"

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            url,
            re.IGNORECASE
        )

        if match:

            return match.group(1)

    return None


# =========================================================
# YOUTUBE URL VALIDATION
# =========================================================

def is_youtube_url(url):

    return get_youtube_id(url) is not None


# =========================================================
# ROOM STATE
# =========================================================

def get_room_state(room_code):

    connection = get_db()

    room = connection.execute(
        """
        SELECT *

        FROM rooms

        WHERE room_code = ?

        AND active = 1
        """,
        (room_code,)
    ).fetchone()

    if room is None:

        connection.close()

        return None

    participants = connection.execute(
        """
        SELECT
            player_name,
            player_id

        FROM participants

        WHERE room_code = ?

        ORDER BY id ASC
        """,
        (room_code,)
    ).fetchall()

    connection.close()

    return {

        "room_code":
            room["room_code"],

        "room_name":
            room["room_name"],

        "room_type":
            room["room_type"],

        "max_players":
            room["max_players"],

        "theme":
            room["theme"],

        "creator":
            room["creator"],

        "creator_player_id":
            room["creator_player_id"],

        "video_type":
            room["video_type"],

        "video_source":
            room["video_source"],

        "video_name":
            room["video_name"],

        "participants": [

            {
                "player_name":
                    participant["player_name"],

                "player_id":
                    participant["player_id"]

            }

            for participant in participants

        ]

    }


# =========================================================
# BROADCAST ROOM UPDATE
# =========================================================

def broadcast_room_update(room_code):

    state = get_room_state(
        room_code
    )

    if state is not None:

        socketio.emit(
            "room_updated",
            state,
            to=room_code
        )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# CREATE ROOM PAGE
# =========================================================

@app.route("/create-room")
def create_room_page():

    return render_template(
        "create_room.html"
    )


# =========================================================
# CREATE ROOM
# =========================================================

@app.route(
    "/create-room",
    methods=["POST"]
)
def create_room():

    room_name = request.form[
        "room_name"
    ].strip()

    room_type = request.form[
        "room_type"
    ]

    max_players = int(
        request.form[
            "max_players"
        ]
    )

    theme = request.form[
        "theme"
    ]

    creator = request.form[
        "creator"
    ].strip()

    video_type = request.form.get(
        "video_type"
    )

    room_code = generate_room_code()

    player_id = generate_player_id()

    video_source = None

    video_name = None

    if video_type == "upload":

        video_file = request.files.get(
            "video_file"
        )

        if (
            video_file is None
            or not video_file.filename
        ):

            return render_template(
                "create_room.html",
                error="Please select a video to upload."
            )

        if not allowed_video(
            video_file.filename
        ):

            return render_template(
                "create_room.html",
                error=(
                    "Unsupported video format. "
                    "Use MP4, WebM, OGG, MOV or M4V."
                )
            )

        original_filename = (
            video_file.filename
        )

        extension = (
            original_filename
            .rsplit(".", 1)[1]
            .lower()
        )

        temporary_filename = (
            room_code
            + "_"
            + str(uuid.uuid4())
            + "."
            + extension
        )

        video_source = os.path.join(
            app.config["UPLOAD_FOLDER"],
            temporary_filename
        )

        try:

            video_file.save(
                video_source
            )

        except Exception:

            return render_template(
                "create_room.html",
                error="Could not save the uploaded video."
            )

        video_name = original_filename

    elif video_type == "youtube":

        youtube_url = request.form.get(
            "youtube_url",
            ""
        ).strip()

        youtube_id = get_youtube_id(
            youtube_url
        )

        if not youtube_id:

            return render_template(
                "create_room.html",
                error="Please enter a valid YouTube URL."
            )

        video_source = youtube_id

        video_name = youtube_id

    else:

        return render_template(
            "create_room.html",
            error="Please choose a video source."
        )

    connection = get_db()

    try:

        connection.execute(
            """
            INSERT INTO rooms
            (
                room_code,
                room_name,
                room_type,
                max_players,
                theme,
                creator,
                creator_player_id,
                video_type,
                video_source,
                video_name
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                room_code,
                room_name,
                room_type,
                max_players,
                theme,
                creator,
                player_id,
                video_type,
                video_source,
                video_name
            )
        )

        connection.execute(
            """
            INSERT INTO participants
            (
                room_code,
                player_name,
                player_id
            )

            VALUES (?, ?, ?)
            """,
            (
                room_code,
                creator,
                player_id
            )
        )

        connection.commit()

    except Exception:

        connection.rollback()

        connection.close()

        if (
            video_type == "upload"
            and video_source
            and os.path.exists(video_source)
        ):

            try:
                os.remove(video_source)
            except OSError:
                pass

        return render_template(
            "create_room.html",
            error="Could not create the room."
        )

    connection.close()

    session["player_name"] = creator

    session["room_code"] = room_code

    session["player_id"] = player_id

    return redirect(
        url_for(
            "room_created",
            room_code=room_code,
            player_id=player_id
        )
    )


# =========================================================
# ROOM CREATED
# =========================================================

@app.route(
    "/room-created/<room_code>"
)
def room_created(room_code):

    connection = get_db()

    room = connection.execute(
        """
        SELECT *

        FROM rooms

        WHERE room_code = ?
        """,
        (room_code,)
    ).fetchone()

    connection.close()

    if room is None:
        return "Room not found", 404

    return render_template(
        "room_created.html",
        room=room,
        player_id=request.args.get(
            "player_id"
        )
    )


# =========================================================
# JOIN ROOM PAGE
# =========================================================

@app.route("/join-room")
def join_room_page():

    return render_template(
        "join_room.html"
    )


# =========================================================
# JOIN USING ROOM CODE
# =========================================================

@app.route(
    "/join-room",
    methods=["POST"]
)
def join_room_route():

    room_code = request.form[
        "room_code"
    ].strip().upper()

    player_name = request.form[
        "player_name"
    ].strip()

    if not player_name:

        return render_template(
            "join_room.html",
            error="Please enter your name."
        )

    connection = get_db()

    room = connection.execute(
        """
        SELECT *

        FROM rooms

        WHERE room_code = ?

        AND active = 1
        """,
        (room_code,)
    ).fetchone()

    connection.close()

    if room is None:

        return render_template(
            "join_room.html",
            error=(
                "Room not found. "
                "Check the code and try again."
            )
        )

    player_count = get_player_count(
        room_code
    )

    if player_count >= room["max_players"]:

        return render_template(
            "join_room.html",
            error="This room is full."
        )

    player_id = generate_player_id()

    connection = get_db()

    connection.execute(
        """
        INSERT INTO participants
        (
            room_code,
            player_name,
            player_id
        )

        VALUES (?, ?, ?)
        """,
        (
            room_code,
            player_name,
            player_id
        )
    )

    connection.commit()

    connection.close()

    session["player_name"] = player_name

    session["room_code"] = room_code

    session["player_id"] = player_id

    return redirect(
        url_for(
            "watch_room",
            room_code=room_code,
            player_id=player_id
        )
    )


# =========================================================
# PUBLIC ROOMS
# =========================================================

@app.route("/public-rooms")
def public_rooms():

    connection = get_db()

    rooms = connection.execute(
        """
        SELECT *

        FROM rooms

        WHERE room_type = 'public'

        AND active = 1

        ORDER BY id DESC
        """
    ).fetchall()

    connection.close()

    room_data = []

    for room in rooms:

        count = get_player_count(
            room["room_code"]
        )

        room_data.append(
            {
                "room": room,
                "count": count
            }
        )

    return render_template(
        "public_rooms.html",
        rooms=room_data
    )


# =========================================================
# JOIN PUBLIC ROOM
# =========================================================

@app.route(
    "/join-public/<room_code>",
    methods=["POST"]
)
def join_public(room_code):

    player_name = request.form[
        "player_name"
    ].strip()

    if not player_name:

        return redirect(
            url_for("public_rooms")
        )

    connection = get_db()

    room = connection.execute(
        """
        SELECT *

        FROM rooms

        WHERE room_code = ?

        AND room_type = 'public'

        AND active = 1
        """,
        (room_code,)
    ).fetchone()

    connection.close()

    if room is None:
        return "Room not found.", 404

    player_count = get_player_count(
        room_code
    )

    if player_count >= room["max_players"]:

        return redirect(
            url_for("public_rooms")
        )

    player_id = generate_player_id()

    connection = get_db()

    connection.execute(
        """
        INSERT INTO participants
        (
            room_code,
            player_name,
            player_id
        )

        VALUES (?, ?, ?)
        """,
        (
            room_code,
            player_name,
            player_id
        )
    )

    connection.commit()

    connection.close()

    session["player_name"] = player_name

    session["room_code"] = room_code

    session["player_id"] = player_id

    return redirect(
        url_for(
            "watch_room",
            room_code=room_code,
            player_id=player_id
        )
    )


# =========================================================
# WATCH ROOM
# =========================================================

@app.route(
    "/room/<room_code>"
)
def watch_room(room_code):

    player_id = request.args.get(
        "player_id"
    )

    if not player_id:

        player_id = session.get(
            "player_id"
        )

    connection = get_db()

    room = connection.execute(
        """
        SELECT *

        FROM rooms

        WHERE room_code = ?

        AND active = 1
        """,
        (room_code,)
    ).fetchone()

    if room is None:

        connection.close()

        return (
            "Room not found or party has ended.",
            404
        )

    participants = connection.execute(
        """
        SELECT
            player_name,
            player_id

        FROM participants

        WHERE room_code = ?

        ORDER BY id ASC
        """,
        (room_code,)
    ).fetchall()

    current_player = None

    if player_id:

        current_player = connection.execute(
            """
            SELECT *

            FROM participants

            WHERE room_code = ?

            AND player_id = ?
            """,
            (
                room_code,
                player_id
            )
        ).fetchone()

    connection.close()

    if current_player is None:

        return (
            "You are not a participant in this room.",
            403
        )

    session["player_id"] = player_id

    session["room_code"] = room_code

    session["player_name"] = (
        current_player["player_name"]
    )

    return render_template(
        "room.html",
        room=room,
        participants=participants,
        player_id=player_id
    )


# =========================================================
# TEMPORARY UPLOADED VIDEO
# =========================================================

@app.route(
    "/temporary-video/<room_code>"
)
def temporary_video(room_code):

    connection = get_db()

    room = connection.execute(
        """
        SELECT *

        FROM rooms

        WHERE room_code = ?

        AND active = 1
        """,
        (room_code,)
    ).fetchone()

    connection.close()

    if room is None:
        return "Room not found.", 404

    if room["video_type"] != "upload":
        return "This room is not using an uploaded video.", 400

    if not room["video_source"]:
        return "Video not found.", 404

    filename = os.path.basename(
        room["video_source"]
    )

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    if not os.path.isfile(filepath):
        return "Video file not found.", 404

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# =========================================================
# CHANGE VIDEO
# =========================================================

@app.route(
    "/change-video/<room_code>",
    methods=["POST"]
)
def change_video(room_code):

    player_id = (
        request.form.get("player_id")
        or session.get("player_id")
    )

    if not player_id:
        return "Player identity missing.", 400

    connection = get_db()

    room = connection.execute(
        """
        SELECT *

        FROM rooms

        WHERE room_code = ?

        AND active = 1
        """,
        (room_code,)
    ).fetchone()

    if room is None:

        connection.close()

        return "Room not found.", 404

    if player_id != room["creator_player_id"]:

        connection.close()

        return (
            "Only the room host can change the video.",
            403
        )

    video_type = request.form.get(
        "video_type"
    )

    new_video_source = None

    new_video_name = None

    if video_type == "upload":

        video_file = request.files.get(
            "video_file"
        )

        if (
            video_file is None
            or not video_file.filename
        ):

            connection.close()

            return "Please select a video.", 400

        if not allowed_video(
            video_file.filename
        ):

            connection.close()

            return "Unsupported video format.", 400

        original_filename = (
            video_file.filename
        )

        extension = (
            original_filename
            .rsplit(".", 1)[1]
            .lower()
        )

        temporary_filename = (
            room_code
            + "_"
            + str(uuid.uuid4())
            + "."
            + extension
        )

        new_video_source = os.path.join(
            app.config["UPLOAD_FOLDER"],
            temporary_filename
        )

        try:

            video_file.save(
                new_video_source
            )

        except Exception:

            connection.close()

            return (
                "Could not save the new video.",
                500
            )

        new_video_name = original_filename

    elif video_type == "youtube":

        youtube_url = request.form.get(
            "youtube_url",
            ""
        ).strip()

        youtube_id = get_youtube_id(
            youtube_url
        )

        if not youtube_id:

            connection.close()

            return "Invalid YouTube URL.", 400

        new_video_source = youtube_id

        new_video_name = youtube_id

    else:

        connection.close()

        return "Invalid video type.", 400

    old_video_type = room["video_type"]

    old_video_source = room["video_source"]

    if (
        old_video_type == "upload"
        and old_video_source
    ):

        old_filename = os.path.basename(
            old_video_source
        )

        old_filepath = os.path.join(
            app.config["UPLOAD_FOLDER"],
            old_filename
        )

        try:

            if os.path.exists(old_filepath):
                os.remove(old_filepath)

        except OSError:
            pass

    connection.execute(
        """
        UPDATE rooms

        SET
            video_type = ?,
            video_source = ?,
            video_name = ?

        WHERE room_code = ?
        """,
        (
            video_type,
            new_video_source,
            new_video_name,
            room_code
        )
    )

    connection.commit()

    connection.close()

    state = get_room_state(
        room_code
    )

    socketio.emit(
        "video_changed",
        state,
        to=room_code
    )

    return redirect(
        url_for(
            "watch_room",
            room_code=room_code,
            player_id=player_id
        )
    )


# =========================================================
# QUIT ROOM
# =========================================================

@app.route(
    "/quit-room/<room_code>"
)
def quit_room(room_code):

    player_id = request.args.get(
        "player_id"
    )

    if not player_id:
        player_id = session.get(
            "player_id"
        )

    if not player_id:
        return redirect(
            url_for("home")
        )

    connection = get_db()

    room = connection.execute(
        """
        SELECT *

        FROM rooms

        WHERE room_code = ?

        AND active = 1
        """,
        (room_code,)
    ).fetchone()

    if room is None:

        connection.close()

        session.clear()

        return redirect(
            url_for("home")
        )

    participant = connection.execute(
        """
        SELECT *

        FROM participants

        WHERE room_code = ?

        AND player_id = ?
        """,
        (
            room_code,
            player_id
        )
    ).fetchone()

    connection.close()

    if participant is None:

        session.clear()

        return redirect(
            url_for("home")
        )

    # -----------------------------------------------------
    # HOST
    # -----------------------------------------------------

    if player_id == room["creator_player_id"]:

        return render_template(
            "host_quit.html",
            room=room,
            player_id=player_id
        )

    # -----------------------------------------------------
    # NORMAL MEMBER
    # -----------------------------------------------------

    player_name = participant["player_name"]

    connection = get_db()

    connection.execute(
        """
        DELETE FROM participants

        WHERE room_code = ?

        AND player_id = ?
        """,
        (
            room_code,
            player_id
        )
    )

    connection.commit()
    connection.close()

    socketio.emit(
        "member_left",
        {
            "player_id": player_id,
            "player_name": player_name,
            "message":
                player_name
                + " left the room."
        },
        to=room_code
    )

    broadcast_room_update(
        room_code
    )

    session.clear()

    return redirect(
        url_for("home")
    )


# =========================================================
# DELETE ROOM
# =========================================================

@app.route(
    "/delete-room/<room_code>",
    methods=["POST"]
)
def delete_room(room_code):

    player_id = (
        request.form.get("player_id")
        or session.get("player_id")
    )

    if not player_id:
        return redirect(url_for("home"))

    connection = get_db()

    room = connection.execute(
        """
        SELECT *

        FROM rooms

        WHERE room_code = ?
        """,
        (room_code,)
    ).fetchone()

    if room is None:

        connection.close()

        session.clear()

        return redirect(url_for("home"))

    if player_id != room["creator_player_id"]:

        connection.close()

        return (
            "Only the room host can delete this room.",
            403
        )

    delete_room_video(room)

    socketio.emit(
        "room_deleted",
        {
            "message":
                "The host has ended this watch party."
        },
        to=room_code
    )

    connection.execute(
        """
        DELETE FROM participants

        WHERE room_code = ?
        """,
        (room_code,)
    )

    connection.execute(
        """
        UPDATE rooms

        SET
            active = 0,
            video_source = NULL,
            video_name = NULL

        WHERE room_code = ?
        """,
        (room_code,)
    )

    connection.commit()

    connection.close()

    session.clear()

    return redirect(
        url_for("home")
    )


# =========================================================
# HOST LEAVES WITHOUT DELETING
# =========================================================

@app.route(
    "/leave-room/<room_code>",
    methods=["POST"]
)
def leave_room_route(room_code):

    player_id = (
        request.form.get("player_id")
        or session.get("player_id")
    )

    if not player_id:

        return redirect(
            url_for("home")
        )

    connection = get_db()

    # -----------------------------------------------------
    # GET ACTIVE ROOM
    # -----------------------------------------------------

    room = connection.execute(
        """
        SELECT *

        FROM rooms

        WHERE room_code = ?

        AND active = 1
        """,
        (room_code,)
    ).fetchone()

    if room is None:

        connection.close()

        session.clear()

        return redirect(
            url_for("home")
        )

    # -----------------------------------------------------
    # VERIFY HOST
    # -----------------------------------------------------

    if player_id != room["creator_player_id"]:

        connection.close()

        return (
            "Only the room host can use this option.",
            403
        )

    # -----------------------------------------------------
    # GET OLD HOST NAME
    # -----------------------------------------------------

    old_host = connection.execute(
        """
        SELECT
            player_name,
            player_id

        FROM participants

        WHERE room_code = ?

        AND player_id = ?
        """,
        (
            room_code,
            player_id
        )
    ).fetchone()

    if old_host is None:

        connection.close()

        session.clear()

        return redirect(
            url_for("home")
        )

    old_host_name = old_host["player_name"]

    # -----------------------------------------------------
    # FIND NEXT HOST
    # -----------------------------------------------------

    new_host = connection.execute(
        """
        SELECT
            player_name,
            player_id

        FROM participants

        WHERE room_code = ?

        AND player_id != ?

        ORDER BY id ASC

        LIMIT 1
        """,
        (
            room_code,
            player_id
        )
    ).fetchone()

    # -----------------------------------------------------
    # CASE 1:
    # OTHER MEMBERS EXIST
    # -----------------------------------------------------

    if new_host is not None:

        connection.execute(
            """
            DELETE FROM participants

            WHERE room_code = ?

            AND player_id = ?
            """,
            (
                room_code,
                player_id
            )
        )

        connection.execute(
            """
            UPDATE rooms

            SET
                creator = ?,
                creator_player_id = ?

            WHERE room_code = ?
            """,
            (
                new_host["player_name"],
                new_host["player_id"],
                room_code
            )
        )

        connection.commit()

        connection.close()

        socketio.emit(
            "member_left",
            {
                "player_name": old_host_name,

                "message":
                    old_host_name
                    + " left the room."
            },
            to=room_code
        )

        socketio.emit(
            "host_changed",
            {
                "new_host_name":
                    new_host["player_name"],

                "new_host_id":
                    new_host["player_id"],

                "message":
                    new_host["player_name"]
                    + " is now the host."
            },
            to=room_code
        )

        broadcast_room_update(
            room_code
        )

    # -----------------------------------------------------
    # CASE 2:
    # HOST WAS THE ONLY PERSON
    # -----------------------------------------------------

    else:

        delete_room_video(
            room
        )

        connection.execute(
            """
            DELETE FROM participants

            WHERE room_code = ?
            """,
            (room_code,)
        )

        connection.execute(
            """
            UPDATE rooms

            SET
                active = 0,
                video_source = NULL,
                video_name = NULL

            WHERE room_code = ?
            """,
            (room_code,)
        )

        connection.commit()

        connection.close()

        socketio.emit(
            "room_deleted",
            {
                "message":
                    "The host left and the party has ended."
            },
            to=room_code
        )

    session.clear()

    return redirect(
        url_for("home")
    )


# =========================================================
# NORMAL MEMBER LEAVES
# =========================================================

@app.route(
    "/leave-member/<room_code>",
    methods=["POST"]
)
def leave_member(room_code):

    player_id = (
        request.form.get("player_id")
        or session.get("player_id")
    )

    if not player_id:
        return redirect(url_for("home"))

    connection = get_db()

    room = connection.execute(
        """
        SELECT *

        FROM rooms

        WHERE room_code = ?

        AND active = 1
        """,
        (room_code,)
    ).fetchone()

    if room is None:

        connection.close()

        session.clear()

        return redirect(url_for("home"))

    participant = connection.execute(
        """
        SELECT player_name

        FROM participants

        WHERE room_code = ?

        AND player_id = ?
        """,
        (
            room_code,
            player_id
        )
    ).fetchone()

    if participant is None:

        connection.close()

        session.clear()

        return redirect(url_for("home"))

    if player_id == room["creator_player_id"]:

        connection.close()

        return (
            "The host must use the host leave option.",
            403
        )

    player_name = participant["player_name"]

    connection.execute(
        """
        DELETE FROM participants

        WHERE room_code = ?

        AND player_id = ?
        """,
        (
            room_code,
            player_id
        )
    )

    connection.commit()

    connection.close()

    socketio.emit(
        "member_left",
        {
            "player_name":
                player_name,

            "message":
                player_name
                + " left the room."
        },
        to=room_code
    )

    broadcast_room_update(
        room_code
    )

    session.clear()

    return redirect(
        url_for("home")
    )


# =========================================================
# SOCKET.IO - JOIN WATCH ROOM
# =========================================================

@socketio.on(
    "join_watch_room"
)
def handle_join_watch_room(data):

    room_code = data.get(
        "room_code"
    )

    player_id = data.get(
        "player_id"
    )

    if not room_code or not player_id:
        return

    connection = get_db()

    participant = connection.execute(
        """
        SELECT *

        FROM participants

        WHERE room_code = ?

        AND player_id = ?
        """,
        (
            room_code,
            player_id
        )
    ).fetchone()

    room = connection.execute(
        """
        SELECT *

        FROM rooms

        WHERE room_code = ?

        AND active = 1
        """,
        (room_code,)
    ).fetchone()

    connection.close()

    if participant is None or room is None:
        return

    join_room(
        room_code
    )

    state = get_room_state(
        room_code
    )

    emit(
        "room_state",
        state
    )

    broadcast_room_update(
        room_code
    )


# =========================================================
# LEAVE SOCKET ROOM
# =========================================================

@socketio.on(
    "leave_watch_room"
)
def handle_leave_watch_room(data):

    room_code = data.get(
        "room_code"
    )

    if room_code:

        leave_room(
            room_code
        )


# =========================================================
# VIDEO PLAY
# =========================================================

@socketio.on(
    "video_play"
)
def handle_video_play(data):

    room_code = data.get(
        "room_code"
    )

    player_id = (
        data.get("player_id")
        or session.get("player_id")
    )

    current_time = float(
        data.get(
            "current_time",
            0
        )
    )

    if not room_code or not player_id:
        return

    connection = get_db()

    room = connection.execute(
        """
        SELECT creator_player_id

        FROM rooms

        WHERE room_code = ?

        AND active = 1
        """,
        (room_code,)
    ).fetchone()

    connection.close()

    if room is None:
        return

    if player_id != room[
        "creator_player_id"
    ]:
        return

    socketio.emit(
        "video_play",
        {
            "current_time":
                current_time
        },
        to=room_code,
        include_self=False
    )


# =========================================================
# VIDEO PAUSE
# =========================================================

@socketio.on(
    "video_pause"
)
def handle_video_pause(data):

    room_code = data.get(
        "room_code"
    )

    player_id = (
        data.get("player_id")
        or session.get("player_id")
    )

    current_time = float(
        data.get(
            "current_time",
            0
        )
    )

    if not room_code or not player_id:
        return

    connection = get_db()

    room = connection.execute(
        """
        SELECT creator_player_id

        FROM rooms

        WHERE room_code = ?

        AND active = 1
        """,
        (room_code,)
    ).fetchone()

    connection.close()

    if room is None:
        return

    if player_id != room[
        "creator_player_id"
    ]:
        return

    socketio.emit(
        "video_pause",
        {
            "current_time":
                current_time
        },
        to=room_code,
        include_self=False
    )


# =========================================================
# VIDEO SEEK
# =========================================================

@socketio.on(
    "video_seek"
)
def handle_video_seek(data):

    room_code = data.get(
        "room_code"
    )

    player_id = (
        data.get("player_id")
        or session.get("player_id")
    )

    current_time = float(
        data.get(
            "current_time",
            0
        )
    )

    if not room_code or not player_id:
        return

    connection = get_db()

    room = connection.execute(
        """
        SELECT creator_player_id

        FROM rooms

        WHERE room_code = ?

        AND active = 1
        """,
        (room_code,)
    ).fetchone()

    connection.close()

    if room is None:
        return

    if player_id != room[
        "creator_player_id"
    ]:
        return

    socketio.emit(
        "video_seek",
        {
            "current_time":
                current_time
        },
        to=room_code,
        include_self=False
    )


# =========================================================
# CHAT MESSAGE
# =========================================================

@socketio.on(
    "send_chat_message"
)
def handle_chat_message(data):

    room_code = data.get(
        "room_code"
    )

    player_id = (
        data.get("player_id")
        or session.get("player_id")
    )

    message = data.get(
        "message",
        ""
    ).strip()

    if not room_code or not player_id or not message:
        return

    if len(message) > 500:
        message = message[:500]

    connection = get_db()

    participant = connection.execute(
        """
        SELECT player_name

        FROM participants

        WHERE room_code = ?

        AND player_id = ?
        """,
        (
            room_code,
            player_id
        )
    ).fetchone()

    room = connection.execute(
        """
        SELECT room_code

        FROM rooms

        WHERE room_code = ?

        AND active = 1
        """,
        (room_code,)
    ).fetchone()

    connection.close()

    if participant is None or room is None:
        return

    socketio.emit(
        "chat_message",
        {
            "player_name":
                participant["player_name"],

            "player_id":
                player_id,

            "message":
                message
        },
        to=room_code
    )


# =========================================================
# CHAT REACTIONS
# =========================================================

ALLOWED_REACTIONS = {
    "❤️",
    "😂",
    "😮",
    "😢",
    "👍",
    "👏",
    "🔥",
    "😍",
    "😡",
    "🎉"
}


@socketio.on(
    "send_reaction"
)
def handle_send_reaction(data):

    room_code = data.get(
        "room_code"
    )

    player_id = (
        data.get("player_id")
        or session.get("player_id")
    )

    reaction = data.get(
        "reaction",
        ""
    ).strip()

    # -----------------------------------------------------
    # VALIDATE
    # -----------------------------------------------------

    if (
        not room_code
        or not player_id
        or not reaction
    ):
        return

    if reaction not in ALLOWED_REACTIONS:
        return

    # -----------------------------------------------------
    # VERIFY PARTICIPANT
    # -----------------------------------------------------

    connection = get_db()

    participant = connection.execute(
        """
        SELECT
            player_name,
            player_id

        FROM participants

        WHERE room_code = ?

        AND player_id = ?
        """,
        (
            room_code,
            player_id
        )
    ).fetchone()

    room = connection.execute(
        """
        SELECT
            room_code

        FROM rooms

        WHERE room_code = ?

        AND active = 1
        """,
        (room_code,)
    ).fetchone()

    connection.close()

    if participant is None or room is None:
        return

    # -----------------------------------------------------
    # BROADCAST REACTION
    # -----------------------------------------------------

    socketio.emit(
        "reaction_received",
        {
            "reaction":
                reaction,

            "player_name":
                participant["player_name"],

            "player_id":
                player_id
        },
        to=room_code
    )


# =========================================================
# WEBRTC CALL HELPERS
# =========================================================

def get_call_room(room_code):

    return "call_" + room_code


def is_valid_call_participant(
    room_code,
    player_id
):

    if not room_code or not player_id:
        return False

    connection = get_db()

    participant = connection.execute(
        """
        SELECT player_id

        FROM participants

        WHERE room_code = ?

        AND player_id = ?
        """,
        (
            room_code,
            player_id
        )
    ).fetchone()

    room = connection.execute(
        """
        SELECT room_code

        FROM rooms

        WHERE room_code = ?

        AND active = 1
        """,
        (room_code,)
    ).fetchone()

    connection.close()

    return (
        participant is not None
        and room is not None
    )


def get_call_members(room_code):

    call_room = get_call_room(
        room_code
    )

    try:

        members = socketio.server.manager.get_participants(
            "/",
            call_room
        )

        return list(members)

    except Exception:

        return []


def get_call_socket_ids(
    room_code,
    exclude_socket_id=None
):

    socket_ids = []

    for sid, _ in get_call_members(
        room_code
    ):

        if sid == exclude_socket_id:
            continue

        socket_ids.append(sid)

    return socket_ids


# =========================================================
# WEBRTC CALL SIGNALING - JOIN
# =========================================================

@socketio.on(
    "call_join"
)
def handle_call_join(data):

    room_code = data.get(
        "room_code"
    )

    player_id = (
        data.get("player_id")
        or session.get("player_id")
    )

    if not room_code or not player_id:
        return

    connection = get_db()

    participant = connection.execute(
        """
        SELECT
            player_name,
            player_id

        FROM participants

        WHERE room_code = ?

        AND player_id = ?
        """,
        (
            room_code,
            player_id
        )
    ).fetchone()

    room = connection.execute(
        """
        SELECT room_code

        FROM rooms

        WHERE room_code = ?

        AND active = 1
        """,
        (room_code,)
    ).fetchone()

    connection.close()

    if participant is None or room is None:
        return

    call_room = get_call_room(
        room_code
    )

    # -----------------------------------------------------
    # GET EXISTING CALL PARTICIPANTS
    # -----------------------------------------------------

    existing_call_participants = []

    for sid, _ in get_call_members(
        room_code
    ):

        if sid == request.sid:
            continue

        existing_call_participants.append(
            {
                "socket_id":
                    sid
            }
        )

    # -----------------------------------------------------
    # JOIN CALL ROOM
    # -----------------------------------------------------

    join_room(
        call_room
    )

    # -----------------------------------------------------
    # SEND EXISTING USERS TO NEW PARTICIPANT
    # -----------------------------------------------------

    emit(
        "call_existing_users",
        {
            "participants":
                existing_call_participants
        }
    )

    # -----------------------------------------------------
    # NOTIFY EXISTING PARTICIPANTS
    # -----------------------------------------------------

    socketio.emit(
        "call_user_joined",
        {
            "socket_id":
                request.sid,

            "player_id":
                participant["player_id"],

            "player_name":
                participant["player_name"]
        },
        to=call_room,
        include_self=False
    )

    # -----------------------------------------------------
    # UPDATE CALL COUNT
    # -----------------------------------------------------

    socketio.emit(
        "call_participant_count",
        {
            "count":
                len(
                    get_call_members(
                        room_code
                    )
                )
        },
        to=call_room
    )


# =========================================================
# WEBRTC OFFER
# =========================================================

@socketio.on(
    "webrtc_offer"
)
def handle_webrtc_offer(data):

    target_socket_id = data.get(
        "target_socket_id"
    )

    offer = data.get(
        "offer"
    )

    room_code = data.get(
        "room_code"
    )

    player_id = (
        data.get("player_id")
        or session.get("player_id")
    )

    if (
        not target_socket_id
        or not offer
        or not room_code
        or not player_id
    ):
        return

    if not is_valid_call_participant(
        room_code,
        player_id
    ):
        return

    if target_socket_id not in get_call_socket_ids(
        room_code
    ):
        return

    emit(
        "webrtc_offer",
        {
            "offer":
                offer,

            "sender_socket_id":
                request.sid
        },
        to=target_socket_id
    )


# =========================================================
# WEBRTC ANSWER
# =========================================================

@socketio.on(
    "webrtc_answer"
)
def handle_webrtc_answer(data):

    target_socket_id = data.get(
        "target_socket_id"
    )

    answer = data.get(
        "answer"
    )

    room_code = data.get(
        "room_code"
    )

    player_id = (
        data.get("player_id")
        or session.get("player_id")
    )

    if (
        not target_socket_id
        or not answer
        or not room_code
        or not player_id
    ):
        return

    if not is_valid_call_participant(
        room_code,
        player_id
    ):
        return

    if target_socket_id not in get_call_socket_ids(
        room_code
    ):
        return

    emit(
        "webrtc_answer",
        {
            "answer":
                answer,

            "sender_socket_id":
                request.sid
        },
        to=target_socket_id
    )


# =========================================================
# WEBRTC ICE CANDIDATE
# =========================================================

@socketio.on(
    "webrtc_ice_candidate"
)
def handle_webrtc_ice_candidate(data):

    target_socket_id = data.get(
        "target_socket_id"
    )

    candidate = data.get(
        "candidate"
    )

    room_code = data.get(
        "room_code"
    )

    player_id = (
        data.get("player_id")
        or session.get("player_id")
    )

    if (
        not target_socket_id
        or not candidate
        or not room_code
        or not player_id
    ):
        return

    if not is_valid_call_participant(
        room_code,
        player_id
    ):
        return

    if target_socket_id not in get_call_socket_ids(
        room_code
    ):
        return

    emit(
        "webrtc_ice_candidate",
        {
            "candidate":
                candidate,

            "sender_socket_id":
                request.sid
        },
        to=target_socket_id
    )


# =========================================================
# CALL LEAVE
# =========================================================

@socketio.on(
    "call_leave"
)
def handle_call_leave(data):

    room_code = data.get(
        "room_code"
    )

    player_id = (
        data.get("player_id")
        or session.get("player_id")
    )

    if not room_code or not player_id:
        return

    if not is_valid_call_participant(
        room_code,
        player_id
    ):
        return

    call_room = get_call_room(
        room_code
    )

    # -----------------------------------------------------
    # NOTIFY OTHER PARTICIPANTS
    # -----------------------------------------------------

    emit(
        "call_user_left",
        {
            "socket_id":
                request.sid,

            "player_id":
                player_id
        },
        to=call_room,
        include_self=False
    )

    # -----------------------------------------------------
    # LEAVE CALL ROOM
    # -----------------------------------------------------

    leave_room(
        call_room
    )

    remaining_count = len(
        get_call_members(
            room_code
        )
    )

    socketio.emit(
        "call_participant_count",
        {
            "count":
                remaining_count
        },
        to=call_room
    )


# =========================================================
# SOCKET DISCONNECT
# =========================================================

@socketio.on(
    "disconnect"
)
def handle_disconnect():

    # -----------------------------------------------------
    # REMOVE USER FROM CALL PEERS
    # -----------------------------------------------------

    try:

        joined_rooms = list(
            socketio.server.manager.get_rooms(
                "/",
                request.sid
            )
        )

    except Exception:

        joined_rooms = []

    for room_name in joined_rooms:

        if not room_name.startswith(
            "call_"
        ):
            continue

        # Notify other call participants
        socketio.emit(
            "call_user_left",
            {
                "socket_id":
                    request.sid
            },
            to=room_name,
            include_self=False
        )

        # Calculate remaining users
        try:

            remaining_members = (
                socketio.server.manager.get_participants(
                    "/",
                    room_name
                )
            )

            remaining_count = len(
                list(remaining_members)
            )

        except Exception:

            remaining_count = 0

        # Update call count
        socketio.emit(
            "call_participant_count",
            {
                "count":
                    remaining_count
            },
            to=room_name
        )


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    socketio.run(
        app,
        debug=True
    )