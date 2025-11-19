#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test pour obtenir un token OAuth2 Air France
et afficher la réponse.
"""

import base64
import json
import os
import ssl
import urllib.parse
import http.client

API_KEY = "7krxvvkty8jn3dcgzuar7wck"
API_SECRET = "MWNCqDZryu"

# === Construction de l'Authorization: Basic <base64(key:secret)> ===
pair = f"{API_KEY}:{API_SECRET}"
auth_header = base64.b64encode(pair.encode()).decode()

# === URL token AF ===
TOKEN_ENDPOINT = f"/opendata/cid/token?client_id={API_KEY}"

HOST = "api.airfranceklm.com"

headers = {
    "Authorization": f"Basic {auth_header}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

body = json.dumps({
    "grant_type": "client_credentials"
})

print("🔐 Obtention d’un token OAuth2...")
print(f"➡️ POST https://{HOST}{TOKEN_ENDPOINT}")

context = ssl._create_unverified_context()  # éviter erreur SSL Mac

conn = http.client.HTTPSConnection(HOST, context=context)
conn.request("POST", TOKEN_ENDPOINT, body=body, headers=headers)

res = conn.getresponse()
data = res.read().decode()

if res.status != 200:
    print(f"❌ Erreur token ({res.status}) : {data}")
    exit(1)

print("✅ Token reçu :")
print(json.dumps(json.loads(data), indent=2, ensure_ascii=False))