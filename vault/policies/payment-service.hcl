path "secret/data/services/payment-service/*" {
  capabilities = ["read"]
}

path "secret/data/stripe/*" {
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
