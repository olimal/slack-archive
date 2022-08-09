"""
virtual_courier.py: This file defines the VirtualCouerierArchive class, whose purpose
is to parse and store the message history of a Slack channel. It also contains helper methods.
"""

import json
import re
import requests
import os
from datetime import (datetime, timedelta)
from csv import DictWriter
from shutil import rmtree
from fpdf import FPDF
from slack_sdk.errors import SlackApiError
from urllib.error import URLError


def epoch_to_datetime(ts):
    """Given a timestamp in epoch format, returns a datetime"""
    epoch = datetime(1970, 1, 1)
    timestamp = epoch + timedelta(seconds=float(ts))
    return timestamp


def get_timestamp(ts):
    """Given a timestamp in epoch format, returns a string in mm/dd/yy at
    hh-mm am/pm format."""
    dt = epoch_to_datetime(ts)
    timestamp = dt.strftime("%m/%d/%Y at %I:%M %p")
    return str(timestamp)


def unique_filename(orig_filename, file_list):
    filename, ext = os.path.splitext(orig_filename)
    split_filename = filename
    if ext is None:
        ext = ''
    counter = 1
    while filename + ext in file_list:
        filename = split_filename + " (" + str(counter) + ")"
        counter += 1
    return filename + ext


class VirtualCourierArchive:
    """
    The VirtualCourierArchive class parses information about a Slack channel.
    client: a WebClient object from the slack_bolt package.
    channel_name: use this parameter if not running with an event listener.
    event: body["event"], where body is the response from an event listener.

    If channel_name is not None, then event should be None.
    If event is not None, then channel_name should be None.
    """

    def __init__(self, client, output_dir, channel_name=None, event=None):
        if channel_name is None and event is None:
            err_msg = "Either channel_name or event must not be None"
            raise RuntimeError(err_msg)
        self.client = client
        self._set_channel_id(channel_name, event)
        self._set_channel_name(channel_name, event)
        self._set_output_dir(output_dir)
        # Get the channel history
        self._raw_history = self._get_channel_history(self.channel_id)
        # Set member names for each user that sent a message to the channel
        self._set_members()
        # Set the name of the user who is performing this export
        self._set_user(event)
        self._set_timestamp(event)
        self._set_messages()

    def _set_channel_id(self, channel_name, event):
        if event is not None:
            channel_id = event["channel"]
        else:
            try:
                response_public = self.client.conversations_list(types="public_channel", exclude_archived=False).data
                response_private = self.client.conversations_list(types="private_channel", exclude_archived=False).data
                channels = response_public["channels"] + response_private["channels"]
                channel = list(filter(lambda c: c["name"].lower() == channel_name.lower(), channels))[0]
                channel_id = channel["id"]
            except (IndexError, SlackApiError):
                err_msg = f"Channel id not found for {channel_name}"
                raise RuntimeError(err_msg)
        self.channel_id = channel_id

    def _set_channel_name(self, channel_name, event):
        if event is not None:
            try:
                response = self.client.conversations_info(channel=event["channel"])
                channel_name = response.data["channel"]["name"]
            except SlackApiError:
                err_msg = "Error while fetching the channel information"
                raise RuntimeError(err_msg)
        self.channel_name = channel_name

    def _set_output_dir(self, output_dir):
        if output_dir is None:
            output_dir = os.path.join(os.getcwd(), f"{self.channel_name.title()} Archive")
        else:
            output_dir = os.path.join(output_dir, f"{self.channel_name.title()} Archive")
        self.output_dir = output_dir

    def _get_channel_history(self, channel_id):
        """Returns json of channel history."""
        client = self.client
        try:
            response_parent = client.conversations_history(channel=channel_id)
            response = response_parent
            while response.data["has_more"]:
                next = response.data["response_metadata"]["next_cursor"]
                response = client.conversations_history(channel=channel_id, cursor=next)
                response_parent.data["messages"] += response.data["messages"]
            if "response_metadata" in response_parent.data.keys():
                response_parent.data.pop("response_metadata")
                response_parent.data["has_more"] = False
            return response_parent
        except SlackApiError as e:
            print("Error while fetching the conversation history")
            raise e

    def _set_members(self):
        """Given the conversation history of a channel, returns a dictionary of user_id : user_name."""
        messages = self._raw_history["messages"]
        users = []
        for message in messages:
            user = message.get("user")
            if user is not None and user not in users:
                users.append(user)
        user_dict = {}
        for user in users:
            try:
                user_response = self.client.users_info(user=user)
                user_data = user_response.data["user"]
                try:
                    user_name = user_data["profile"]["real_name"]
                    if user_name == "Deactivated User":
                        user_name = user_data["name"]
                except KeyError:
                    with open("user_log.json", "a") as f:
                        json.dump(user_response.data, f)
                    user_name = user_data["name"]
                user_dict[user] = user_name
            except SlackApiError:
                with open("user_log.txt", "a") as f:
                    f.write(f"error: {user}")
                user_dict[user] = user
        self.members = user_dict

    def _set_user(self, event):
        # If event is not None, get the name of the user who triggered the event and the time it was triggered.
        if event is not None:
            user = self.members[event["user"]]
        else:
            user = os.getlogin()
        self.user = user

    def _set_timestamp(self, event):
        if event is not None:
            timestamp = epoch_to_datetime(event["ts"]).strftime("%m/%d/%Y at %I:%M %p")
        else:
            timestamp = datetime.now().strftime("%m/%d/%Y at %I:%M %p")
        self.timestamp = timestamp

    def _set_messages(self):
        """Returns parsed messages that were sent in the channel."""
        messages_raw = self._raw_history["messages"]
        messages_list = []
        for ind, message in enumerate(reversed(messages_raw)):
            message_dict = self._parse_message(message, ind + 1)
            messages_list.append(message_dict)
        self.messages = messages_list

    def _parse_message(self, message, message_id):
        """Returns pertinent information about a message."""
        files = []
        if "files" in message.keys():
            for file in message["files"]:
                filename_original = file.get("name")
                filename_modified = filename_original if filename_original is not None else "Unknown"
                filename = unique_filename(filename_modified, [f["filename"] for f in files])
                url_download = file.get("url_private_download")
                url = file.get("url_private")
                files.append({
                    "filename": filename,
                    "url_download": url_download,
                    "url": url
                    })
        subtype = message.get("subtype")
        raw_user = message.get("user")
        if subtype == 'channel_join':
            user = 'Slackbot'
        elif raw_user is None and subtype == 'bot_message':
            user = message["username"]
        elif raw_user is None:
            raise RuntimeError(f"No user for this message:\n{json.loads(message)}")
        else:
            user = self.members.get(raw_user)
            if user is None:
                user = raw_user
        timestamp = epoch_to_datetime(message["ts"])
        text = self._normalize_text(message.get("text"), possible_user_id=True)
        file_dir = os.path.join(self.output_dir, f"message_{message_id}")
        message_dict = {
            "message_id": message_id,
            "type": message.get("type"),
            "subtype": subtype,
            "text": text,
            "user": user,
            "files": files,
            "file_dir": file_dir,
            "timestamp_display": timestamp.strftime("%m/%d/%Y at %I:%M %p"),
            "timestamp": timestamp.strftime("%Y-%m-%d %I:%M%p")
            }
        return message_dict

    def _normalize_text(self, text, possible_user_id = True):
        """When user name is known, inserts user name in place of user id in message text.
        Decodes unicode characters that aren't recognized in latin-1.
        If possible_user_id is set, look for user IDs and replace with user name if found."""
        # Decode unicode character that isn't recognized in latin-1 encoding
        text = text.replace("\u2019", "'")
        text = text.replace("\u2026", "...")
        # Replace instances of user ID with user name.
        if possible_user_id:
            pattern = r"<@[a-zA-Z0-9]*>"
            result = re.search(pattern, text)
            if result is not None:
                result_text = result.group(0)
                user_id = result_text[2:-1]
                try:
                    user_name = self.members[user_id]
                except KeyError:
                    user_name = user_id
                replace_with = "@" + user_name
                new_text = text.replace(result_text, replace_with)
                return new_text
            else:
                return text

    def download_files(self):
        """Downloads the image files mentioned in the channel history."""
        supported_filetypes = tuple(['jpg', 'jpeg', 'png', 'gif'])
        for message in self.messages:
            files = message["files"]
            if len(files) > 0:
                files_to_download = list(filter(lambda f: f["filename"].lower().endswith(supported_filetypes), files))
                if len(files_to_download) > 0:
                    file_dir = message["file_dir"]
                    if not os.path.exists(file_dir):
                        os.makedirs(file_dir)
                    for file in files_to_download:
                        filepath = f"{file_dir}/{file['filename']}"
                        url = file["url_download"]
                        if url is not None:
                            response = requests.get(url, headers={'Authorization': f'Bearer {self.client.token}'})
                            if response is not None:
                                with open(filepath, "wb") as f:
                                    f.write(response.content)

    def make_csv(self):
        """Create CSV of channel history."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        filepath_abs = os.path.join(self.output_dir, f"{self.channel_name}.csv")
        csv_list = []
        for message in self.messages:
            columns = ["sender", "timestamp", "text", "file"]
            user = message["user"]
            ts = message["timestamp"]
            text = message["text"] if message["text"] is not None else ''
            files = message["files"]
            if len(files) > 0:
                for file in files:
                    url = file["url"]
                    csv_list.append({"sender": user, "timestamp": ts, "text": text, "file": url})
            else:
                csv_list.append({"sender": user, "timestamp": ts, "text": text, "file": ''})
        with open(filepath_abs, 'w', encoding='utf-8-sig', newline='') as csvfile:
            writer = DictWriter(csvfile, fieldnames=columns)
            writer.writeheader()
            writer.writerows(csv_list)
            self.csv_filepath = filepath_abs

    def make_pdf(self):
        """Generates a PDF based on the channel history."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        filepath_abs = os.path.join(self.output_dir, f"{self.channel_name}.pdf")
        pdf = FPDF("P", "in", "letter")
        supported_filetypes = tuple(['jpg', 'jpeg', 'png', 'gif'])
        pdf.add_page()
        pdf.set_margins(1, 1, 1)
        pdf.set_font('Arial', '', 12)
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.01)
        col_width = pdf.w - 2 * pdf.l_margin
        col_height = pdf.font_size
        line_break = pdf.font_size
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(col_width, col_height, f"{self.channel_name} Channel Archive".encode('latin-1','strict').decode('latin-1','strict'), ln=line_break)
        pdf.set_font('Arial', '', 12)
        pdf.cell(col_width, col_height, f"Exported on {self.timestamp}", ln=line_break)
        pdf.ln(line_break)
        for message in self.messages:
            user = message["user"]
            ts = message["timestamp_display"]
            file_dir = message["file_dir"]
            if message["subtype"] == 'channel_join':
                message_header = ts
            else:
                message_header = f"{user} on {ts}"
            pdf.cell(col_width, col_height, message_header, ln=line_break)
            if len(message["text"]) > 0:
                message_text = message["text"].encode('latin-1', 'backslashreplace').decode('latin-1')
                pdf.multi_cell(col_width, col_height, message_text)
            if len(message["files"]) > 0:
                for file in message["files"]:
                    filename = self._normalize_text(file["filename"], possible_user_id=False)
                    filepath = f"{file_dir}/{filename}"
                    url = file["url"]
                    if filepath.lower().endswith(supported_filetypes):
                        try:
                            pdf.image(filepath, w=col_width / 2.5)
                            pdf.ln(line_break)
                        except RuntimeError:
                            self._put_link(pdf, col_width, col_height, f"File: {filename}", line_break, url)
                    else:
                        self._put_link(pdf, col_width, col_height, f"File: {filename}", line_break, url)
            pdf.ln(line_break / 2)
            y = pdf.get_y()
            pdf.line(pdf.l_margin / 2, y, 8.5 - pdf.r_margin / 2, y)
            pdf.ln(line_break / 2)
        pdf.output(filepath_abs)
        self.pdf_filepath = filepath_abs

    def _put_link(self, pdf, col_width, col_height, text, ln, url):
        pdf.set_text_color(6, 69, 173)  # hyperlink blue
        pdf.cell(col_width, col_height, text, ln=ln, link=url)
        pdf.set_text_color(0, 0, 0)  # reset to black

    def post(self, format="csv"):
        """Posts a file to the channel. format can be "csv" or "pdf". """
        if format.lower() == "csv":
            fp = self.csv_filepath
        elif format.lower() == "pdf":
            fp = self.pdf_filepath
        else:
            err_msg = "format parameter must be 'csv' or 'pdf'."
            raise RuntimeError(err_msg)
        try:
            self.client.files_upload(channels=self.channel_id, file=fp, title=f"{self.channel_name} {format}")
        except URLError as e:
            err_msg = "An error occurred while uploading the file to this channel. Contact <@U03F805UUDC> for support."
            self.client.chat_postMessage(channel=self.channel_id, text=err_msg)
            raise e

    def cleanup(self):
        """Delete all files that were downloaded."""
        target_dir = self.output_dir
        tree = list(filter(lambda item: item[0] != target_dir, os.walk(target_dir)))
        dirs_to_remove = [d[0] for d in tree]
        for d in dirs_to_remove:
            rmtree(d)
