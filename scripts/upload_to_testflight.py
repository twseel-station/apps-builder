import os, sys, time, jwt, urllib.request, json

key_id = os.environ.get('APPLE_KEY_ID')
issuer_id = os.environ.get('APPLE_ISSUER_ID')
key_path = os.environ.get('APPLE_KEY_PATH')
ipa_path = os.environ.get('IPA_PATH', 'build/ios/ipa/client_app.ipa')

if not (key_id and issuer_id and key_path and os.path.exists(key_path)):
    print("Apple credentials not provided or missing. Skipping TestFlight upload.")
    sys.exit(0)

print(f"Uploading {ipa_path} to TestFlight with Key ID: {key_id}")
# Uses xcrun altool or xcrun notarytool/altool on macOS runner
cmd = f"xcrun altool --upload-app -f '{ipa_path}' -t ios --apiKey '{key_id}' --apiIssuer '{issuer_id}'"
ret = os.system(cmd)
if ret != 0:
    print(f"Upload command exited with code {ret}")
    sys.exit(ret)
print("Successfully uploaded to TestFlight!")
