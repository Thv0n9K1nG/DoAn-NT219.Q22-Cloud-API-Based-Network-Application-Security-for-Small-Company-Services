path "secret/data/services/admin-service/*" {
  capabilities = ["read"]
}

path "secret/data/keycloak/*" {
  capabilities = ["read"]
}

path "secret/data/database/*" {
  capabilities = ["read"]
}

path "secret/data/pqc/*" {
  capabilities = ["read"]
}

path "transit/encrypt/tenant-*" {
  capabilities = ["update"]
}

path "transit/decrypt/tenant-*" {
  capabilities = ["update"]
}

path "pki/issue/internal-services" {
  capabilities = ["update"]
}
