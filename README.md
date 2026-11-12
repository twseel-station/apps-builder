# apps-builder

Every mobile pipeline of Tawseel Station lives here. The private app repos carry no workflows.

| workflow                                                     | what it does                                                                                                                                                              |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `client-app.yml` / `restaurant-app.yml` / `delivery-app.yml` | one per app: maps that app's variables to secrets, builds the APK, publishes it as a release in the private app repo, and pushes to the stores the app already lives on   |
| `_mobile-release.yml`                                        | the shared engine (android, ios, one merged telegram message)                                                                                                             |
| `watch-apps.yml`                                             | every 10 minutes: a commit on `develop` (test) or `main` (production) containing `[android]`, `[play]`, `[apk]`, `[ios]`, `[testflight]` or `[both]` starts a build, once |

Backend keeps its own workflow in its repo and only deploys when the commit message contains `[deploy]`.

## secrets naming

`<APP>_<VARIABLE>_<TEST|PROD>` where APP is `CLIENT_APP`, `RESTAURANT_APP` or `DELIVERY_APP`.
The variable list of each app is written in its workflow (`defines:`); a missing secret fails the build and names it.

Account-level secrets are shared: `GH_PAT`, `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEY_PROPERTIES`,
`GOOGLE_PLAY_SERVICE_ACCOUNT_JSON`, `APPLE_APP_STORE_KEY_P8`, `APPLE_KEY_ID`, `APPLE_ISSUER_ID`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

## environments

- `test`: develop servers, Google Play internal track
- `production`: live servers, Google Play production track as a **draft** (press start rollout in Play Console)
