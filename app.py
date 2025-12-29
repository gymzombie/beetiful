import os
from beetiful import app
from dotenv import load_dotenv

load_dotenv()

# Read port from environment variable, defaulting to 3000 if not set
port = int(os.getenv("FLASK_PORT", 3000))

app.run(debug=True, host="0.0.0.0", port=port)
