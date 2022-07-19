"""
slackless.py: This script creates a CSV and PDF file of a given channel's message history.
Those files can be posted to the channel if specified in command line arguments.
"""

import sys
import os
import json
from dotenv import dotenv_values
from slack_sdk import WebClient
from virtual_courier import VirtualCourierArchive


if __name__ == "__main__":
    current_dir = os.getcwd()
    project_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    if len(sys.argv) < 2 or '-help' in sys.argv or '-h' in sys.argv:
        usage = """
        Usage: python3 path/to/slackless.py <channel_name> [-output] [-post] [-keep]
            <channel_name>: the name of a Slack channel that @Virtual Courier Archive has been invited to
            [-output]: the directory where the output folder should be saved
            [-json]: save a json file of the raw channel history in the output folder
            [-post]: send CSV and PDF to the channel
            [-keep]: save images downloaded from the Slack channel in the output folder
            """
        raise RuntimeError(usage)

    channel_name = sys.argv[1]
    token = dotenv_values(os.path.join(project_dir, ".env"))["VC_BOT_TOKEN"]
    client = WebClient(token=token, timeout=180)
    if '-output' in sys.argv:
        output_dir_ind = sys.argv.index('-output') + 1
        output_dir_rel = sys.argv[output_dir_ind]
        output_dir_abs = os.path.abspath(output_dir_rel)
    else:
        output_dir_abs = current_dir

    os.chdir(project_dir)
    arch = VirtualCourierArchive(client, output_dir_abs, channel_name=channel_name)
    arch.download_files()
    arch.make_csv()
    arch.make_pdf()
    if '-post' in sys.argv:
        arch.post("csv")
        arch.post("pdf")
    if '-keep' not in sys.argv:
        arch.cleanup()
    if '-json' in sys.argv:
        with open(os.path.join(arch.output_dir, f"{arch.channel_name}.json"), 'w') as f:
            json.dump(arch._raw_history.data, f)
