import time
import seedsbot.main as seedsbot

RETRY_INTERVAL = 5

if __name__ == "__main__":
    while True:
        try:
            seedsbot.run()
        except Exception as err:
            print(err)
            print("Retrying in", RETRY_INTERVAL)
            time.sleep(RETRY_INTERVAL)
