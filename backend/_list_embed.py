import os
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
for m in genai.list_models():
    if "embedContent" in m.supported_generation_methods:
        print(m.name, "-- input:", m.input_token_limit, "-- methods:", m.supported_generation_methods)
