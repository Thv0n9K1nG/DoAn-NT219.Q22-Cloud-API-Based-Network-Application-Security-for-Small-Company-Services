path "secret/data/services/user-service/*" {
  capabilities = ["read"]
}

path "secret/data/keycloak/*" {
  capabilities = ["read"]
}

path "secret/data/pqc/*" {
  capabilities = ["read"]
}

path "pki/issue/internal-services" {
  capabilities = ["update"]
}
