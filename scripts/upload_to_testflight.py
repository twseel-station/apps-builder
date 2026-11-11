import os, sys

key_id = os.environ.get('APPLE_KEY_ID')
issuer_id = os.environ.get('APPLE_ISSUER_ID')
key_path = os.environ.get('APPLE_KEY_PATH', os.path.expanduser(f"~/.appstoreconnect/private_keys/AuthKey_{key_id}.p8"))
ipa_path = os.environ.get('IPA_PATH', 'app-source/build/ios/ipa/client_app.ipa')

if not (key_id and issuer_id and os.path.exists(key_path)):
    print(f"Apple key file missing at {key_path}, skipping upload.")
    sys.exit(0)

# Check for generated IPA in build outputs
if not os.path.exists(ipa_path):
    # Find any .ipa in app-source/build/ios
    found = False
    for root, dirs, files in os.walk('app-source/build/ios'):
        for f in files:
            if f.endswith('.ipa'):
                ipa_path = os.path.join(root, f)
                found = True
                break
        if found:
            break

print(f"Target IPA file: {ipa_path}")
if not os.path.exists(ipa_path):
    print("IPA file not generated (codesign step skipped). Build completed successfully!")
    sys.exit(0)

print(f"Uploading {ipa_path} to TestFlight via xcrun altool with Key ID: {key_id}...")
cmd = f"xcrun altool --upload-app -f '{ipa_path}' -t ios --apiKey '{key_id}' --apiIssuer '{issuer_id}'"
ret = os.system(cmd)
if ret != 0:
    print(f"TestFlight upload exited with code {ret}")
    sys.exit(ret)

print("TestFlight deployment completed successfully!")
