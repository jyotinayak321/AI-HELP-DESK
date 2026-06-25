import json

realm = {
    "id": "ai-helpdesk",
    "realm": "ai-helpdesk",
    "enabled": True,
    "sslRequired": "external",
    "roles": {
        "realm": [
            {"name": "operator"},
            {"name": "admin"}
        ]
    },
    "clients": [
        {
            "clientId": "helpdesk-frontend",
            "enabled": True,
            "publicClient": True,
            "directAccessGrantsEnabled": True,
            "redirectUris": [
                "http://localhost:5173/*",
                "http://localhost:5174/*",
                "http://localhost:5175/*"
            ],
            "webOrigins": ["*"]
        }
    ],
    "users": []
}

operators = [
    {"user": "OP-10001", "pass": "pass_operator1"},
    {"user": "OP-10002", "pass": "pass_operator2"},
    {"user": "OP-10003", "pass": "pass_operator3"},
]

admins = [
    {"user": "ADM-20001", "pass": "pass_afnet"},
    {"user": "ADM-20002", "pass": "pass_hrms"},
    {"user": "ADM-20003", "pass": "pass_leave"},
    {"user": "ADM-20004", "pass": "pass_travel"},
    {"user": "ADM-20005", "pass": "pass_sso"},
    {"user": "ADM-20006", "pass": "pass_pay"},
    {"user": "ADM-20007", "pass": "pass_medical"},
]

for op in operators:
    realm["users"].append({
        "username": op["user"],
        "email": f"{op['user'].lower()}@afnet.local",
        "firstName": "Operator",
        "lastName": op["user"].split("-")[1],
        "enabled": True,
        "credentials": [{"type": "password", "value": op["pass"], "temporary": False}],
        "realmRoles": ["operator"]
    })

for ad in admins:
    realm["users"].append({
        "username": ad["user"],
        "email": f"{ad['user'].lower()}@afnet.local",
        "firstName": "Admin",
        "lastName": ad["user"].split("-")[1],
        "enabled": True,
        "credentials": [{"type": "password", "value": ad["pass"], "temporary": False}],
        "realmRoles": ["admin"]
    })

with open('keycloak-realm-export.json', 'w') as f:
    json.dump(realm, f, indent=4)

print("Created keycloak-realm-export.json")
