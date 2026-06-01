with open('boardroom.py', 'r') as f:
    content = f.read()

old = '''            prior_args = "\\n\\n".join([
                f"[{e['agent']}]: {e['argument']}"
                for e in debate_log
            ]) if debate_log else "You are the first to speak."'''

new = '''            prior_args = "\\n\\n".join([
                f"[{e['agent']}]: {e['argument'][:250]}"
                for e in debate_log[-2:]
            ]) if debate_log else "You are the first to speak."'''

if old in content:
    content = content.replace(old, new)
    with open('boardroom.py', 'w') as f:
        f.write(content)
    print("patched -- agents now see last 2 args, 250 chars each")
else:
    print("pattern not found -- paste boardroom.py and I'll fix manually")
