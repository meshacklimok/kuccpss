#!/usr/bin/env bash
# Deploy on the DigitalOcean Droplet: pull, build (migrate, collectstatic, seeds), restart.
# Run from /srv/kuccpss as the deploy user:  ./deploy.sh
set -o errexit

cd "$(dirname "$0")"
git pull --ff-only
source venv/bin/activate
export GIT_COMMIT="$(git rev-parse HEAD)"
./build.sh
sudo systemctl restart kuccpss kuccpss-q
echo "Deployed ${GIT_COMMIT}"
