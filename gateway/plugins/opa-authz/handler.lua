local cjson = require "cjson.safe"
local http = require "resty.http"


local OpaAuthzHandler = {
  PRIORITY = 1005,
  VERSION = "0.1.0",
}


local function base64url_decode(value)
  local normalized = value:gsub("-", "+"):gsub("_", "/")
  local remainder = #normalized % 4
  if remainder > 0 then
    normalized = normalized .. string.rep("=", 4 - remainder)
  end
  return ngx.decode_base64(normalized)
end


local function extract_bearer_token()
  local authorization = kong.request.get_header("Authorization")
  if not authorization then
    return nil
  end

  local token = authorization:match("[Bb]earer%s+(.+)")
  return token
end


local function decode_jwt_payload(token)
  local payload_b64 = token and token:match("^[^.]+%.([^.]+)%.")
  if not payload_b64 then
    return nil, "Malformed bearer token"
  end

  local payload_json = base64url_decode(payload_b64)
  if not payload_json then
    return nil, "Unable to decode bearer token"
  end

  local payload, err = cjson.decode(payload_json)
  if not payload then
    return nil, "Unable to parse bearer token payload: " .. tostring(err)
  end

  return payload
end


local function contains(value, expected)
  if type(value) == "string" then
    return value == expected
  end

  if type(value) == "table" then
    for _, item in ipairs(value) do
      if item == expected then
        return true
      end
    end
  end

  return false
end


local function split_path(path)
  local segments = {}
  for segment in string.gmatch(path or "", "[^/]+") do
    table.insert(segments, segment)
  end
  return segments
end


local function roles_from_claims(claims)
  local realm_access = claims.realm_access or {}
  return realm_access.roles or claims.roles or {}
end


local function reject(status, code, message)
  return kong.response.exit(status, {
    error = {
      code = code,
      message = message,
    },
  })
end


function OpaAuthzHandler:access(conf)
  local method = kong.request.get_method()
  if conf.enforce_json_content_type and (method == "POST" or method == "PUT" or method == "PATCH") then
    local content_type = kong.request.get_header("Content-Type") or ""
    if not content_type:lower():find("application/json", 1, true) then
      return reject(415, "UNSUPPORTED_MEDIA_TYPE", "JSON content type is required")
    end
  end

  local token = extract_bearer_token()
  local claims, err = decode_jwt_payload(token)
  if not claims then
    return reject(401, "INVALID_TOKEN", err)
  end

  if conf.required_audience and conf.required_audience ~= "" and not contains(claims.aud, conf.required_audience) then
    return reject(401, "INVALID_TOKEN", "Invalid token audience")
  end

  local tenant_id = claims.tenant_id or ""
  local user_id = claims.sub or ""
  local roles = roles_from_claims(claims)

  -- Downstream services still verify JWTs; these headers are operational hints for logs and rate limits.
  if tenant_id ~= "" then
    kong.service.request.set_header("X-Tenant-ID", tenant_id)
  end
  if user_id ~= "" then
    kong.service.request.set_header("X-User-ID", user_id)
  end
  kong.service.request.set_header("X-Roles", table.concat(roles, ","))

  local opa_input = {
    input = {
      method = method,
      path = split_path(kong.request.get_path()),
      tenant_id = tenant_id,
      user_id = user_id,
      roles = roles,
      source_ip = kong.client.get_forwarded_ip(),
    },
  }

  local httpc = http.new()
  httpc:set_timeout(conf.opa_timeout)
  local response, request_err = httpc:request_uri(conf.opa_url, {
    method = "POST",
    body = cjson.encode(opa_input),
    headers = {
      ["Content-Type"] = "application/json",
      ["X-Request-ID"] = kong.request.get_header("X-Request-ID") or "",
    },
  })

  if not response then
    kong.log.err("OPA authorization request failed: ", request_err)
    return reject(503, "AUTHZ_UNAVAILABLE", "Authorization service is unavailable")
  end

  if response.status < 200 or response.status >= 300 then
    kong.log.err("OPA authorization returned HTTP ", response.status, ": ", response.body)
    return reject(503, "AUTHZ_UNAVAILABLE", "Authorization service returned an error")
  end

  local decision = cjson.decode(response.body)
  if not decision or decision.result ~= true then
    return reject(403, "ACCESS_DENIED", "Access denied by authorization policy")
  end
end


return OpaAuthzHandler
