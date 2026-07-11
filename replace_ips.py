###### python replace_ips.py <PC_IP> 192.168.1.34


import os
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python replace_ips.py <NEW_IP> [OLD_IP]")
        print("Example: python replace_ips.py 10.0.0.5 192.168.1.34")
        sys.exit(1)

    new_ip = sys.argv[1]
    old_ip = sys.argv[2] if len(sys.argv) > 2 else "192.168.1.34"

    print(f"Replacing {old_ip} with {new_ip} across the project...\n")

    files_to_check = [
        "backend/test_ws_vad_real.py",
        "backend/test_ws_vad.py",
        "backend/test_mic_vad.py",
        "frontend/src/hooks/useVadStream.js",
        "frontend/src/components/voice/LiveKitAudioTransport.jsx",
        "frontend/src/api/voice.api.js",
        "frontend/src/components/voice/VoiceSessionPanel.jsx",
        "frontend/src/api/axios.js",
        "frontend/src/auth.config.js",
        "generate_keycloak_json.py",
        "keycloak-realm-export.json",
        "airgapped_setup_guide.md",
    ]

    # We do NOT include backend/config.py here because we reverted 
    # the internal database/Ollama routes back to localhost for stability.
    # However, if LIVEKIT_URL or KEYCLOAK_URL in config.py had the old IP, we should change it.
    files_to_check.append("backend/config.py")
    files_to_check.append("livekit-config.yaml")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    updated_count = 0

    for rel_path in files_to_check:
        filepath = os.path.join(base_dir, rel_path)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Simple string replacement
            new_content = content.replace(old_ip, new_ip)
                
            if new_content != content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"✅ Updated: {rel_path}")
                updated_count += 1
        else:
            print(f"⚠️ Not found: {rel_path}")

    print(f"\nDone! {updated_count} files modified.")
    print(f"Make sure to also update your .env files (frontend/.env and backend/.env) to use {new_ip}!")

if __name__ == "__main__":
    main()
