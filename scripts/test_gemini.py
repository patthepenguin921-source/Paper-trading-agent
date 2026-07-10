"""
One-off connectivity test for the Gemini integration — NOT part of the
trading pipeline. Calls the raw Gemini backend function with a trivial
prompt so we can verify auth + key failover work without waiting for
market hours or building a full decision context. Writes the result to
last_gemini_test.json so it can be read back via the GitHub Contents API.

Previously called a non-existent ai_agent._call_gemini(fake_context) —
always failed with AttributeError, so this workflow never actually tested
anything. Fixed to call the real function (backends._gemini_generate, via
ai_agent's re-export) with the shape it actually expects.
"""
import json

import ai_agent

try:
    result = ai_agent._gemini_generate(
        "You are a connectivity test.", "Reply with exactly one word: OK",
        json_mode=False, max_output_tokens=10,
    )
    output = {"success": True, "result": result}
except Exception as e:
    output = {"success": False, "error": str(e)}

with open("last_gemini_test.json", "w") as f:
    json.dump(output, f, indent=2)

print(json.dumps(output, indent=2))
