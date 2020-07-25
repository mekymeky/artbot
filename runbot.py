import time
import seedsbot.main as seedsbot
import flask
import threading
import os

RETRY_INTERVAL = 5
ENABLE_LIVECHECKER_ENV_VAR = "ENABLE_LIVECHECKER"

lc_env = os.getenv(ENABLE_LIVECHECKER_ENV_VAR)
ENABLE_LIVECHECKER = lc_env is not None and lc_env.lower() in ["1", "true", "yes"]
print("Live checker enabled:", ENABLE_LIVECHECKER)

flask_app = flask.Flask(__name__)

@flask_app.route('/')
def livecheck():
    return "Hi!"

def run_livechecker():
    flask_app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    
    if ENABLE_LIVECHECKER:
        lc_thread = threading.Thread(daemon=True, target=run_livechecker)
        lc_thread.start()
        
    while True:
        try:
            seedsbot.run()
        except Exception as err:
            print(err)
            print("Retrying in", RETRY_INTERVAL)
            time.sleep(RETRY_INTERVAL)
