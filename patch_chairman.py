with open('boardroom.py', 'r') as f:
    content = f.read()

old_chairman = '''chairman_prompt = f"""ORIGINAL INPUT:
{input_summary}

BOARDROOM DEBATE:
{full_debate}

You are the Chairman. The board has spoken. Now you decide.
Respond in strict JSON only:
{{"consensus":"","primary_risk":"","primary_opportunity":"","contested":"","verdict":"go | no-go | conditional","verdict_condition":""}}
Return ONLY the JSON. No preamble. No markdown."""'''

new_chairman = '''chairman_prompt = f"""You have just chaired a boardroom debate about the following:

{input_summary}

Here is what your board said:

{full_debate}

Now deliver your verdict as Chairman. You are not a committee.
You have heard the arguments. You have made a decision.

Speak plainly. No corporate language. No bullet points.
Write three short paragraphs:
1. What the room agreed on and what remained contested
2. The single biggest risk and the single biggest opportunity
3. Your verdict -- go, no-go, or conditional -- and exactly what condition must be met first

Then on a new line write only: VERDICT: go OR VERDICT: no-go OR VERDICT: conditional

Be direct. Be human. Sound like someone who has made hard calls before."""'''

if 'You are the Chairman' in content:
    content = content.replace(old_chairman, new_chairman)
    with open('boardroom.py', 'w') as f:
        f.write(content)
    print("chairman voice updated -- human, direct, no JSON soup")
else:
    print("chairman pattern not found")

# Fix the JSON parse -- chairman no longer returns JSON
old_parse = '''        clean = raw.strip().replace("```json","").replace("```","").strip()
        synthesis = json.loads(clean)'''

new_parse = '''        clean = raw.strip()
        # Extract verdict line
        verdict = "unknown"
        for line in clean.split("\\n"):
            if line.strip().startswith("VERDICT:"):
                verdict = line.replace("VERDICT:","").strip().lower()
                break
        synthesis = {
            "verdict": verdict,
            "chairman_statement": clean,
            "primary_risk": "",
            "primary_opportunity": "",
            "consensus": "",
            "contested": ""
        }'''

content = content.replace(old_parse, new_parse)

old_print = '''    print(f"\\n  VERDICT: {synthesis.get('verdict','unknown').upper()}")'''
new_print = '''    print(f"\\n{synthesis.get('chairman_statement','No statement')}")
    print(f"\\n  VERDICT: {synthesis.get('verdict','unknown').upper()}")'''

content = content.replace(old_print, new_print)
with open('boardroom.py', 'w') as f:
    f.write(content)
print("chairman JSON parse replaced with natural language parse")
