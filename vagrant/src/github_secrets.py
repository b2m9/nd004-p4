"""Fill in Github's client secrets for application testing.

- Go to https://github.com/settings/developers
- Register a new app
- Set homepage URL to address of Vagrant machine
- Set callback URL to address of Vagrant machine plus "/github-callback"
- Click "Register Application"
- Copy client id to `GITHUB_CLIENT_ID`
- Copy client secret to `GITHUB_CLIENT_SECRET`

"""
GITHUB_CLIENT_ID = None
GITHUB_CLIENT_SECRET = None
