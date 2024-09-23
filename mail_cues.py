import os

def read_mail_cues(file_path):
    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist. Creating a new file with default content.")
        default_content = """
# Mail Cues


## Calendar Events
_No calendar events yet._

## Order Updates
_No order updates yet._

## Newsletter Summaries
_No newsletter summaries yet._

## Follow Ups
_No follow ups yet._

"""
        with open(file_path, "w") as file:
            file.write(default_content)
        return default_content

    with open(file_path, "r") as file:
        return file.read()
    
def parse_mail_cues(markdown_content):
    calendar_events = []
    order_updates = []
    newsletter_summaries = []
    follow_ups = []
    
    current_section = None
    lines = markdown_content.split("\n")
    
    for line in lines:
        line = line.strip()  # Strip leading/trailing whitespace
        if line.startswith("## "):
            current_section = line[3:].strip()
        elif current_section == "Calendar Events":
            if "_No calendar events yet._" in line:
                calendar_events = []
            calendar_events.append(line)
        elif current_section == "Order Updates":
            if "_No order updates yet._" in line:
                order_updates = []
            order_updates.append(line)
        elif current_section == "Newsletter Summaries":
            if "_No newsletter summaries yet._" in line:
                newsletter_summaries = []
            newsletter_summaries.append(line)
        elif current_section == "Follow Ups":
            if "_No follow ups yet._" in line:
                follow_ups = []
            follow_ups.append(line)
    
    final_record = {
        "Calendar Events": calendar_events,
        "Order Updates": order_updates,
        "Newsletter Summaries": newsletter_summaries,
        "Follow Ups": follow_ups
    }
    print(f"Final parsed record: {final_record}")
    return final_record