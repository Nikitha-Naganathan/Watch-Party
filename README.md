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
```
## Run Locally
1. Clone the repository
git clone https://github.com/Nikitha-Naganathan/Watch-Party.git

2. Open the project folder
cd Watch-Party

3. Create a virtual environment
Windows:
python -m venv venv
venv\Scripts\activate

4. Install dependencies
pip install -r requirements.txt

5. Run the application
python app.py

## Deployment
StreamMates is deployed using Render.
The application runs using Gunicorn and Flask-SocketIO.

## Project Objective
StreamMates aims to make online movie and video watching more social by allowing friends to watch content together in a synchronized environment, communicate through live chat, and enjoy a shared virtual viewing experience.

## Future Scope
- User authentication and profiles
- Persistent chat history
- More customization options
- Improved scalability for larger watch parties
- Reactions during streaming of videos
- Integration of using various websites and not only youtube
