#!/bin/bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this command as root." >&2
    exit 1
fi

source /etc/websitepi-sec/redirect.env
host="${WEBSITEPI_HTTPS_HOST:-}"
case "$host" in
    ""|.*|*..*|*[!A-Za-z0-9.-]*)
        echo "Invalid HTTPS hostname." >&2
        exit 1
        ;;
esac
certificate="/etc/letsencrypt/live/$host/fullchain.pem"
private_key="/etc/letsencrypt/live/$host/privkey.pem"
directory="/etc/websitepi-sec/tls"
temporary=$(mktemp -d "$directory/.refresh-XXXXXXXX")
cleanup() {
    rm -f -- "$temporary/server.crt" "$temporary/server.key"
    rmdir -- "$temporary"
}
trap cleanup EXIT

openssl verify -purpose sslserver -verify_hostname "$host" \
    -CAfile /etc/ssl/certs/ca-certificates.crt -untrusted "$certificate" "$certificate" >/dev/null
cert_public=$(openssl x509 -in "$certificate" -pubkey -noout | openssl pkey -pubin -outform DER | sha256sum | cut -d' ' -f1)
key_public=$(openssl pkey -in "$private_key" -pubout -outform DER | sha256sum | cut -d' ' -f1)
if [ "$cert_public" != "$key_public" ]; then
    echo "The server certificate and private key do not match." >&2
    exit 1
fi

install -o root -g websitepi -m 640 "$certificate" "$temporary/server.crt"
install -o root -g websitepi -m 640 "$private_key" "$temporary/server.key"
mv -f -- "$temporary/server.crt" "$directory/server.crt"
mv -f -- "$temporary/server.key" "$directory/server.key"
if systemctl is-active --quiet security-https.service; then
    systemctl restart security-https.service
fi
echo "HTTPS certificate updated for $host."
