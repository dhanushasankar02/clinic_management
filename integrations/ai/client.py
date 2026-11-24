import os
import logging

logger = logging.getLogger(__name__)

class AIClient:
    """Wrapper for Generative AI (Gemini / OpenAI) for smart medical triage & queries."""

    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY') or os.environ.get('OPENAI_API_KEY')

    def generate_reply(self, prompt, context=None):
        """Generates AI response or graceful fallback."""
        if not self.api_key:
            return None

        context_str = context if isinstance(context, str) else str(context or '')
        try:
            # 1. Try google.generativeai if available
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                system_instruction = (
                    "You are the official WhatsApp assistant for a healthcare clinic.\n"
                    "Instructions:\n"
                    "- Answer ONLY what the patient is asking directly and concisely.\n"
                    "- Do NOT output generic options menus or unrelated bullet points.\n"
                    "- Be polite, professional, and helpful.\n"
                    "- Keep answers brief (2-4 sentences max).\n\n"
                    f"Clinic Context:\n{context_str}\n\n"
                    f"Patient Query: {prompt}"
                )
                response = model.generate_content(system_instruction)
                if response and hasattr(response, 'text') and response.text:
                    return response.text.strip()
            except ImportError:
                pass

            # 2. Try OpenAI if OpenAI key or package is present
            try:
                import openai
                client = openai.OpenAI(api_key=self.api_key)
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are the official WhatsApp assistant for a healthcare clinic. "
                                "Answer ONLY what the patient is asking directly and concisely. "
                                "Do NOT dump menus or unrelated bullet points. Keep response under 3 sentences. "
                                f"Clinic Context: {context_str}"
                            )
                        },
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=200,
                    temperature=0.3
                )
                return completion.choices[0].message.content.strip()
            except ImportError:
                pass

        except Exception as e:
            logger.warning(f"AI generation failed: {e}")

        return None
