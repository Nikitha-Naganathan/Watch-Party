#  StreamMates

### Watch Together. Anywhere.

StreamMates is a web-based watch party application that allows friends to watch videos together in real time, communicate through live chat, and enjoy a shared streaming experience from different locations.

##  Features

-  **Synchronized Watching** – Keep video playback synchronized for everyone in a room.
-  **Live Chat** – Communicate with other participants in real time.
-  **Create Rooms** – Create a private watch room and invite friends.
-  **Join Rooms** – Join an existing room using its room details.
-  **Custom Themes** – Switch between different visual themes.
-  **Real-Time Interaction** – Changes made by one participant can be reflected across the room.
-  **Database Support** – Store room and application data using SQLite.

##  Technologies Used

### Frontend
- HTML5
- CSS3
- JavaScript

### Backend
- Python
- Flask
- Flask-SocketIO

### Database
- SQLite

### Real-Time Communication
- WebSockets
- Socket.IO

## 📁 Project Structure

```text
Watch-Party/
│
├── database/
│   └── watchparty.db
│
├── Modules/
│
├── Static/
│   ├── Audio/
│   ├── CSS/
│   │   ├── dark.css
│   │   ├── light.css
│   │   └── style.css
│   ├── Fonts/
│   ├── Images/
│   ├── JS/
│   └── videos/
│
├── templates/
│   ├── create_room.html
│   ├── host_quit.html
│   ├── index.html
│   ├── join_room.html
│   ├── public_rooms.html
│   ├── room_created.html
│   └── room.html
│
├── app.py
├── requirements.txt
└── README.md
