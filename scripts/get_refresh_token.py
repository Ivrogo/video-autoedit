"""Flujo OAuth de un solo uso: genera token.json y muestra los valores para GitHub Secrets.

Requisitos previos (una sola vez, ~10 min):
1. https://console.cloud.google.com -> crear proyecto (p. ej. "autoedit").
2. "APIs y servicios" -> "Biblioteca" -> habilitar "Google Drive API".
3. "APIs y servicios" -> "Pantalla de consentimiento OAuth" -> tipo Externo,
   añadir tu propio email como usuario de prueba.
4. "Credenciales" -> "Crear credenciales" -> "ID de cliente de OAuth" ->
   tipo "Aplicación de escritorio" -> descargar el JSON como credentials.json
   en la raíz de este proyecto.

Uso:  py -3.12 scripts/get_refresh_token.py
"""

import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive"]


def main() -> int:
    creds_file = Path("credentials.json")
    if not creds_file.exists():
        print("ERROR: falta credentials.json en la raíz del proyecto.")
        print("Sigue los pasos del docstring de este script para crearlo.")
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
    creds = flow.run_local_server(port=0)

    Path("token.json").write_text(creds.to_json(), encoding="utf-8")
    client_config = json.loads(creds_file.read_text(encoding="utf-8"))["installed"]

    print("\ntoken.json creado (para uso local).")
    print("\nGuarda estos tres valores como GitHub Secrets del repo:")
    print(f"  GDRIVE_CLIENT_ID     = {client_config['client_id']}")
    print(f"  GDRIVE_CLIENT_SECRET = {client_config['client_secret']}")
    print(f"  GDRIVE_REFRESH_TOKEN = {creds.refresh_token}")
    print("\nComando rápido (con gh):")
    print('  gh secret set GDRIVE_CLIENT_ID --body "<valor>"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
