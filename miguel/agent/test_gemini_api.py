import google.generativeai as genai
import os

# --- Gemini API Configuration ---
def configure_gemini_api():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        print("Please set the GEMINI_API_KEY environment variable before running.")
        exit(1)
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-pro')

# --- Test Gemini API Functionality ---
def test_gemini_api_response(prompt):
    model = configure_gemini_api()
    print(f"\nSending prompt to Gemini: '{prompt}'")
    try:
        response = model.generate_content(prompt)
        bot_response_text = ""
        for part in response.parts:
            if hasattr(part, 'text'):
                bot_response_text += part.text
        print("\nGemini's response:")
        print(bot_response_text)
        return bot_response_text
    except Exception as e:
        print(f"An error occurred while calling the Gemini API: {e}")
        return None

# --- Main Execution ---
if __name__ == "__main__":
    test_prompt = "What is the capital of France?"
    test_gemini_api_response(test_prompt)