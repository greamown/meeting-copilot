#!/bin/sh
set -eu

service_uid="${SERVICE_UID:?SERVICE_UID is required}"
service_gid="${SERVICE_GID:?SERVICE_GID is required}"
service_home="${SERVICE_HOME:?SERVICE_HOME is required}"
service_user="${SERVICE_USER:?SERVICE_USER is required}"
secret_dir=/tmp/meeting-copilot-secrets
mkdir -p "$secret_dir"
chmod 0700 "$secret_dir"
chown "$service_uid:$service_gid" "$secret_dir"

copy_secret() {
    name="$1"
    if [ -f "/run/secrets/$name" ]; then
        cp "/run/secrets/$name" "$secret_dir/$name"
        chmod 0400 "$secret_dir/$name"
        chown "$service_uid:$service_gid" "$secret_dir/$name"
    fi
}

copy_secret worker_token
copy_secret postgres_password

if [ -f "$secret_dir/worker_token" ]; then
    export MC_WORKER_TOKEN_FILE="$secret_dir/worker_token"
fi
if [ -f "$secret_dir/postgres_password" ]; then
    export MC_POSTGRES_PASSWORD_FILE="$secret_dir/postgres_password"
fi

old_ifs="$IFS"
IFS=:
for path in ${SERVICE_WRITABLE_PATHS:-}; do
    if [ -d "$path" ]; then
        chown "$service_uid:$service_gid" "$path"
    fi
done
IFS="$old_ifs"

export HOME="$service_home"
export USER="$service_user"
export LOGNAME="$service_user"

exec setpriv --reuid "$service_uid" --regid "$service_gid" --clear-groups "$@"
