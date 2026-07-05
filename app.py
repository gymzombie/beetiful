import os
from beetiful import app, env_flag
from dotenv import load_dotenv

load_dotenv()

# Read port from environment variable, defaulting to 3000 if not set
port = int(os.getenv("FLASK_PORT", 3000))

# Debug is OFF unless FLASK_DEBUG is explicitly enabled: the Werkzeug debugger
# exposes an interactive console (RCE) on any unhandled exception.
app.run(debug=env_flag("FLASK_DEBUG"), host="0.0.0.0", port=port)
