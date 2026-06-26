"""
generate_char_clips.py
----------------------
Generates is_that_correct.wav and individual character WAV clips
(digits 0-9, letters A-Z, dash) using the same Zira voice settings
as the other static prompts, ensuring a consistent voice throughout.
"""
import pyttsx3, shutil, tempfile, os, string

engine = pyttsx3.init('sapi5')
engine.setProperty('rate', 170)  # Crisp pace for character-by-character read-back
engine.setProperty('volume', 1.0)
voices = engine.getProperty('voices')
zira = next((v for v in voices if 'zira' in v.name.lower()), voices[0])
engine.setProperty('voice', zira.id)
print(f'Voice: {zira.name}\n')

STATIC = os.path.join(os.path.dirname(__file__), 'voice', 'static_prompts')
CHARS_DIR = os.path.join(STATIC, 'chars')
os.makedirs(CHARS_DIR, exist_ok=True)

def synth(text, path):
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        tmp_path = tmp.name
    engine.save_to_file(text, tmp_path)
    engine.runAndWait()
    shutil.move(tmp_path, path)
    kb = os.path.getsize(path) / 1024
    print(f'  [OK] {os.path.basename(path):20s}  {kb:6.1f} KB   "{text}"')

# Phrase file
print("Phrase clips:")
synth('Is that correct?', os.path.join(STATIC, 'is_that_correct.wav'))

# Digit clips 0-9
print("\nDigit clips:")
DIGIT_WORDS = {
    '0':'zero','1':'one','2':'two','3':'three','4':'four',
    '5':'five','6':'six','7':'seven','8':'eight','9':'nine'
}
for ch, word in DIGIT_WORDS.items():
    synth(word, os.path.join(CHARS_DIR, f'{ch}.wav'))

# Letter clips A-Z
print("\nLetter clips:")
for letter in string.ascii_uppercase:
    synth(letter, os.path.join(CHARS_DIR, f'{letter}.wav'))

# Dash
print("\nPunctuation:")
synth('dash', os.path.join(CHARS_DIR, 'dash.wav'))

print('\nAll done.')
