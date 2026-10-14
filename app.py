from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import random
import string

app = Flask(__name__)
app.config["SECRET_KEY"] = "watch-party-secret-key"

DATABASE = "database/watchparty.db"


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():

    connection = get_db()

    connection.execute("""
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
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT NOT NULL,
            player_name TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()


def generate_room_code():

    characters = string.ascii_uppercase + string.digits

    while True:

        code = ''.join(
            random.choices(characters, k=6)
        )

        connection = get_db()

        existing_room = connection.execute(
            "SELECT id FROM rooms WHERE room_code = ?",
            (code,)
        ).fetchone()

        connection.close()

        if existing_room is None:
            return code


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


@app.route("/")
def home():

    return render_template("index.html")


# -----------------------------
# CREATE ROOM
# -----------------------------

@app.route("/create-room")
def create_room_page():

    return render_template("create_room.html")


@app.route("/create-room", methods=["POST"])
def create_room():

    room_name = request.form["room_name"]
    room_type = request.form["room_type"]
    max_players = int(request.form["max_players"])
    theme = request.form["theme"]
    creator = request.form["creator"]

    room_code = generate_room_code()

    connection = get_db()

    connection.execute(
        """
        INSERT INTO rooms
        (room_code, room_name, room_type, max_players, theme, creator)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            room_code,
            room_name,
            room_type,
            max_players,
            theme,
            creator
        )
    )

    connection.execute(
        """
        INSERT INTO participants
        (room_code, player_name)
        VALUES (?, ?)
        """,
        (
            room_code,
            creator
        )
    )

    connection.commit()
    connection.close()

    session["player_name"] = creator
    session["room_code"] = room_code

    return redirect(
        url_for(
            "room_created",
            room_code=room_code
        )
    )

@app.route("/room-created/<room_code>")
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
        room=room
    )


# -----------------------------
# JOIN ROOM PAGE
# -----------------------------

@app.route("/join-room")
def join_room_page():

    return render_template("join_room.html")


# -----------------------------
# JOIN USING ROOM CODE
# -----------------------------

@app.route("/join-room", methods=["POST"])
def join_room():

    room_code = request.form["room_code"].strip().upper()
    player_name = request.form["player_name"].strip()

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
            error="Room not found. Check the code and try again."
        )

    player_count = get_player_count(room_code)

    if player_count >= room["max_players"]:

        return render_template(
            "join_room.html",
            error="This room is full."
        )

    connection = get_db()

    connection.execute(
        """
        INSERT INTO participants
        (room_code, player_name)
        VALUES (?, ?)
        """,
        (
            room_code,
            player_name
        )
    )

    connection.commit()
    connection.close()

    session["player_name"] = player_name
    session["room_code"] = room_code

    return redirect(
        url_for(
            "watch_room",
            room_code=room_code
        )
    )


# -----------------------------
# PUBLIC ROOMS
# -----------------------------

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


# -----------------------------
# JOIN PUBLIC ROOM
# -----------------------------

@app.route("/join-public/<room_code>", methods=["POST"])
def join_public(room_code):

    player_name = request.form["player_name"].strip()

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

    player_count = get_player_count(room_code)

    if player_count >= room["max_players"]:

        return redirect(
            url_for("public_rooms")
        )

    connection = get_db()

    connection.execute(
        """
        INSERT INTO participants
        (room_code, player_name)
        VALUES (?, ?)
        """,
        (
            room_code,
            player_name
        )
    )

    connection.commit()
    connection.close()

    session["player_name"] = player_name
    session["room_code"] = room_code

    return redirect(
        url_for(
            "watch_room",
            room_code=room_code
        )
    )


# -----------------------------
# WATCH ROOM
# -----------------------------

@app.route("/room/<room_code>")
def watch_room(room_code):

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

    participants = connection.execute(
        """
        SELECT player_name
        FROM participants
        WHERE room_code = ?
        """,
        (room_code,)
    ).fetchall()

    connection.close()

    if room is None:

        return "Room not found or party has ended.", 404

    return render_template(
        "room.html",
        room=room,
        participants=participants
    )

# -----------------------------
# QUIT ROOM
# -----------------------------

@app.route("/quit-room/<room_code>")
def quit_room(room_code):

    player_name = session.get("player_name")

    if not player_name:
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

    connection.close()

    if room is None:
        session.clear()
        return redirect(url_for("home"))

    # Check if the player is the host
    if player_name == room["creator"]:

        return render_template(
            "host_quit.html",
            room=room
        )

    # Normal player leaves immediately
    connection = get_db()

    connection.execute(
        """
        DELETE FROM participants
        WHERE room_code = ?
        AND player_name = ?
        """,
        (room_code, player_name)
    )

    connection.commit()
    connection.close()

    session.clear()

    return redirect(url_for("home"))


# -----------------------------
# HOST DELETES ROOM
# -----------------------------

@app.route("/delete-room/<room_code>", methods=["POST"])
def delete_room(room_code):

    player_name = session.get("player_name")

    if not player_name:
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

    # Only the host can delete the room
    if player_name != room["creator"]:

        connection.close()

        return "Only the room host can delete this room.", 403

    # Remove everyone from the room
    connection.execute(
        """
        DELETE FROM participants
        WHERE room_code = ?
        """,
        (room_code,)
    )

    # Deactivate the room
    connection.execute(
        """
        UPDATE rooms
        SET active = 0
        WHERE room_code = ?
        """,
        (room_code,)
    )

    connection.commit()
    connection.close()

    session.clear()

    return redirect(url_for("home"))


# -----------------------------
# HOST LEAVES WITHOUT DELETING
# -----------------------------

@app.route("/leave-room/<room_code>", methods=["POST"])
def leave_room(room_code):

    player_name = session.get("player_name")

    if not player_name:
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

    # Make sure only the host uses this route
    if player_name != room["creator"]:

        connection.close()

        return "Only the room host can use this option.", 403

    # Remove the current host
    connection.execute(
        """
        DELETE FROM participants
        WHERE room_code = ?
        AND player_name = ?
        """,
        (room_code, player_name)
    )

    # Find the next participant
    new_host = connection.execute(
        """
        SELECT player_name
        FROM participants
        WHERE room_code = ?
        ORDER BY id ASC
        LIMIT 1
        """,
        (room_code,)
    ).fetchone()

    if new_host:

        new_host_name = new_host["player_name"]

        # Transfer host ownership
        connection.execute(
            """
            UPDATE rooms
            SET creator = ?
            WHERE room_code = ?
            """,
            (
                new_host_name,
                room_code
            )
        )

    else:

        connection.execute(
            """
            UPDATE rooms
            SET active = 0
            WHERE room_code = ?
            """,
            (room_code,)
        )

    connection.commit()
    connection.close()

    session.clear()

    return redirect(url_for("home"))

if __name__ == "__main__":

    initialize_database()

    app.run(debug=True)