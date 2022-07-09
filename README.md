# slack-archive (aka virtual-courier)
This project supports a Slack application used by the Collections & Loans department of an art museum. When the application is added to a private channel, it generates a CSV and PDF of the channel history and sends the files to the channel. 
# Setup
- Install the virtual-courier package.
- Install dependencies shown in requirements.txt.
- Ensure that the __Virtual Courier Archive__ application has been installed in the Slack workspace.
- In the virtual-courier folder, create a file called .env to hold the tokens used to connect to Slack. You can use .env.example as a guide.
  ```
  VC_CONNECT_TOKEN="xapp-XXXXXXX"
  VC_BOT_TOKEN="xoxb-XXXXXXX"
  ```
# Usage
## Option 1
Trigger CSV and PDF creation via Slack.
### Step 1
- Run run.py from Command Prompt or Terminal: `python3 path/to/run.py`
- You should see this response: ⚡️ Bolt app is running!
### Step 2
- Mention __@Virtual Courier Archive__ in a Slack channel.
- If __@Virtual Courier Archive__ is not already a member of the channel, follow prompts to add it.
- Within a few minutes, __@Virtual Courier Archive__ will respond with a CSV, then a PDF.
- If you see an error in the Command Prompt or Terminal, press Ctrl + C to quit, then retry Steps 2 and 3.
### Step 3
- In Slack, hover over the files that __@Virtual Courier Archive__ sent.
- In the hover menu that appears, click the cloud icon with a down arrow in it.
- Follow prompts to download the CSV and/or PDF.
## Option 2
Trigger CSV and PDF creation from Command Prompt or Terminal.
### Step 1
- Invite __@Virtual Courier Archive__ to a Slack channel.
### Step 2
- Run slackless.py from Command Prompt or Terminal.
  ```
  Usage: python3 path/to/slackless.py <channel_name> [-output] [-post] [-keep]
     <channel_name>: the name of a Slack channel that @Virtual Courier Archive has been invited to
     [-output]: the location where the output folder should be created
     [-post]: send CSV and PDF to the Slack channel
     [-keep]: save images downloaded from the Slack channel in the output folder
  ```
- The Channel_Name Archive output folder will be created. This folder contains the CSV and PDF.
