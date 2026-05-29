local typedefs = require "kong.db.schema.typedefs"


return {
  name = "opa-authz",
  fields = {
    { consumer = typedefs.no_consumer },
    { protocols = typedefs.protocols_http },
    {
      config = {
        type = "record",
        fields = {
          { opa_url = typedefs.url({ required = true, default = "http://opa:8181/v1/data/authz/allow" }) },
          { opa_timeout = { type = "integer", default = 1000, between = { 100, 10000 } } },
          { required_audience = { type = "string", default = "saas-api" } },
          { enforce_json_content_type = { type = "boolean", default = true } },
        },
      },
    },
  },
}
