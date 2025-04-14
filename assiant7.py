import redis
import subprocess
import re

# Connect to Redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Get session ID
session_id = input("Enter your session ID: ")

# Ask if user wants command extraction
extract_commands = input("Do you want to extract possible commands from responses? (y/n): ").strip().lower()
command_mode = extract_commands == 'y'

# Log file
log_file = f"session_{session_id}.log"

def log_entry(entry):
    """Logs conversation details."""
    with open(log_file, "a") as f:
        f.write(entry + "\n")

def clean_output(text):
    """Removes unnecessary characters from AI output."""
    text = re.sub(r'[`]', '', text)  # Remove backticks
    text = re.sub(r'\(.*?\)', '', text)  # Remove content inside parentheses
    text = re.sub(r'\[.*?\]', '', text)  # Remove content inside square brackets
    return text.strip()

def chat_with_ai(user_input, session_id):
    """Sends request to tgpt and processes AI output"""
    memory = r.get(f"conversation:{session_id}:history")
    
    # Append AI instruction if command mode is enabled
    additional_prompt = ""
    if command_mode:
        additional_prompt = "\n(At the end of your response, list all commands you explained in one line separated by '^'. If no command exists, return '0' and list all these commands in last line,don't tell anything after it and generate it each time please.)"

    prompt = f"You: {user_input}\nAI:{additional_prompt}"
    if memory:
        prompt = memory + "\n" + prompt

    process = subprocess.Popen(['tgpt', prompt], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if stderr:
        print(f"Error: {stderr.decode('utf-8')}")
        return None

    ai_reply = stdout.decode('utf-8').strip()
    cleaned_reply = clean_output(ai_reply)

    # Debugging AI response
    print(f"\nAI: {cleaned_reply}")

    # Update Redis conversation history
    new_memory = prompt + " " + cleaned_reply
    r.set(f"conversation:{session_id}:history", new_memory)

    return cleaned_reply

def extract_commands_from_response(ai_output):
    """Extracts commands from AI response (last line should contain commands separated by '^')."""
    lines = ai_output.strip().split("\n")
    
    # Find the last line containing a '^' (assumed to be the command list)
    for line in reversed(lines):
        if "^" in line:
            commands = line.strip().split("^")
            return [cmd.strip() for cmd in commands if cmd.strip() and cmd.strip() != "0"]

    return None

while True:
    user_input = input("\nYou: ")
    if user_input.lower() in ["exit", "quit"]:
        print("Goodbye!")
        break

    ai_output = chat_with_ai(user_input, session_id)
    if not ai_output:
        continue

    # Extract and display commands
    extracted_commands = extract_commands_from_response(ai_output)
    if command_mode and extracted_commands:
        print("\nPossible commands extracted:")
        for i, cmd in enumerate(extracted_commands, 1):
            print(f"[{i}] {cmd}")

        # Log extracted commands
        log_entry(f"Extracted Commands: {' ^ '.join(extracted_commands)}")

        # Let the user choose a command to execute
        choice = input("\nEnter the number of the command to execute (or press Enter to skip): ").strip()
        if choice.isdigit():
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(extracted_commands):
                selected_command = extracted_commands[choice_idx]
                print(f"\nExecuting: {selected_command}")
                log_entry(f"Selected Command: {selected_command}")

                # Execute the command
                cmd_process = subprocess.Popen(selected_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                cmd_stdout, cmd_stderr = cmd_process.communicate()

                if cmd_stderr:
                    print(f"Error: {cmd_stderr.decode('utf-8')}")
                    log_entry(f"Command Error: {cmd_stderr.decode('utf-8')}")
                else:
                    output = cmd_stdout.decode('utf-8')
                    print(f"\n{output}")
                    log_entry(f"Command Output: {output}")
