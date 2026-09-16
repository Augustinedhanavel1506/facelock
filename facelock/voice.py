import threading


def speak(text: str):
    """Fire-and-forget TTS on a throwaway thread -- SAPI/COM engines aren't
    safe to share across threads, so each call gets its own engine instance
    instead of reusing one globally."""

    def _run():
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
