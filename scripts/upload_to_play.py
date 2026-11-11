import os, sys, json
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

play_json_path = os.environ.get('PLAY_JSON_PATH', '/tmp/play-service-account.json')
package_name = os.environ.get('PACKAGE_NAME', 'com.mada.twseel_station_client')
app_bundle_path = os.environ.get('BUNDLE_PATH', 'build/app/outputs/bundle/release/app-release.aab')
track_name = os.environ.get('TRACK_NAME', 'internal')

if not os.path.exists(play_json_path):
    print("Service account json not found, skipping Google Play upload.")
    sys.exit(0)

if not os.path.exists(app_bundle_path):
    print(f"Error: Bundle not found at {app_bundle_path}")
    sys.exit(1)

scope = ['https://www.googleapis.com/auth/androidpublisher']
credentials = ServiceAccountCredentials.from_json_keyfile_name(play_json_path, scope)
service = build('androidpublisher', 'v3', credentials=credentials)

edit = service.edits().insert(packageName=package_name, body={}).execute()
edit_id = edit['id']
print(f"Play Edit created: {edit_id}")

bundle_response = service.edits().bundles().upload(
    packageName=package_name,
    editId=edit_id,
    media_body=MediaFileUpload(app_bundle_path, mimetype='application/octet-stream')
).execute()

version_code = bundle_response['versionCode']
print(f"Uploaded bundle with version code: {version_code}")

track_response = service.edits().tracks().update(
    packageName=package_name,
    editId=edit_id,
    track=track_name,
    body={
        'releases': [{
            'versionCodes': [str(version_code)],
            'status': 'completed',
            'name': f'1.0.15 ({version_code}) Automated Internal Testing'
        }]
    }
).execute()

commit = service.edits().commit(packageName=package_name, editId=edit_id).execute()
print(f"Committed edit {edit_id} successfully: {commit}")
