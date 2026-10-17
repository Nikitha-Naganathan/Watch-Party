# 🎬 StreamMates

### Watch Together. Anywhere.

**StreamMates** is a real-time web-based watch party application that allows friends to watch videos together from different locations.

Users can create or join rooms, synchronize video playback, communicate through live chat, and enjoy a shared watching experience.

##  Live Demo

🔗 **[Open StreamMates](https://streammates.onrender.com/)**

##  Features

-  **Synchronized Watching**  
  Video playback is synchronized between users in the same room.

- **Create a Room**  
  Create a watch room and invite friends to join.

- **Join a Room**  
  Join an existing watch party using the room details.

-  **Live Chat**  
  Communicate with other participants in real time.

- **Custom Themes**  
  Switch between different visual themes.
  NOTE: Not yet applied. Only the buttons are there, but the theme is yet to be applied

- **Real-Time Communication**  
  Uses Socket.IO to communicate changes between connected users.

- **Database Support**  
  Uses SQLite for storing application and room-related data.

##Tech Stack

| Category | Technology |
|----------|------------|
| Frontend | HTML5, CSS3, JavaScript |
| Backend | Python, Flask |
| Real-Time Communication | Flask-SocketIO |
| Database | SQLite |
| Deployment | Render |

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
