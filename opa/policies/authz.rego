package authz

import future.keywords.if

default allow := false
default deny_bola := false

allow if {
	is_platform_admin
}

allow if {
	not is_platform_admin
	tenant_context_present
	not admin_path
	permission := permission_for_request
	role_has_permission(permission)
}

deny_bola if {
	tenant_id := object.get(input, "tenant_id", "")
	resource_tenant_id := object.get(input, "resource_tenant_id", "")
	tenant_id != ""
	resource_tenant_id != ""
	tenant_id != resource_tenant_id
}

tenant_context_present if {
	tenant_id := object.get(input, "tenant_id", "")
	tenant_id != ""
	tenant_id != null
}

admin_path if {
	resource_kind == "admin"
}

permission_for_request := permission if {
	method_permissions := method_to_permission[upper(object.get(input, "method", ""))]
	permission := method_permissions[resource_kind]
}

resource_kind := segment if {
	count(normalized_path) > 2
	segment := normalized_path[2]
}

resource_kind := segment if {
	count(normalized_path) == 1
	segment := normalized_path[0]
}

normalized_path := segments if {
	# Kong plugins should send split paths without empty segments; this guard keeps policy stable if they do not.
	segments := [segment | segment := object.get(input, "path", [])[_]; segment != ""]
}

method_to_permission := {
	"GET": {
		"users": "read:users",
		"resources": "read:resources",
		"payments": "read:billing",
		"admin": "read:admin"
	},
	"POST": {
		"users": "write:users",
		"resources": "write:resources",
		"payments": "write:billing",
		"admin": "write:admin"
	},
	"PUT": {
		"users": "write:users",
		"resources": "write:resources"
	},
	"PATCH": {
		"users": "write:users",
		"resources": "write:resources"
	},
	"DELETE": {
		"users": "delete:users",
		"resources": "delete:resources"
	}
}
