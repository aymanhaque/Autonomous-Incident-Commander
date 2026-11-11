# -----------------------------------------
# LLM Configuration
# -----------------------------------------
import os

GEMINI_MODEL = os.getenv("AIC_GEMINI_MODEL", "gemini-2.5-flash")

LLM_TEMPERATURE = float(os.getenv("AIC_LLM_TEMPERATURE", "0.2"))
