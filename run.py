"""
run.py: When this file is running, the Virtual Courier Archive Slack application
will listen for mentions in a Slack channel. Once mentioned, a CSV and PDF of the
channel history will be sent to the channel.
"""

import sys
import os
from dotenv import dotenv_values
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from virtual_courier import VirtualCourierArchive


project_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
connect_token = dotenv_values(os.path.join(project_dir, ".env"))["VC_CONNECT_TOKEN"]
app = App(token=connect_token)


@app.event("app_mention")
def handle_app_mention_events(body):
    print("Mentioned!")
    bot_token = dotenv_values(os.path.join(project_dir, ".env"))["VC_BOT_TOKEN"]
    client = WebClient(token=bot_token, timeout=180)
    msg_txt = "Working on it! I'll send a CSV and PDF in a few minutes."
    client.chat_postMessage(channel=body["event"]["channel"], text=msg_txt)
    arch = VirtualCourierArchive(client, output_dir=os.getcwd(), event=body["event"])
    arch.download_files()
    arch.make_csv()
    arch.make_pdf()
    arch.post("csv")
    arch.post("pdf")
    arch.cleanup()


if __name__ == "__main__":
    handler = SocketModeHandler(app, connect_token)
    handler.start()
