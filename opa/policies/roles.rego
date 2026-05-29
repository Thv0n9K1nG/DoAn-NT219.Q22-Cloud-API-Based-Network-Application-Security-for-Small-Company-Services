package authz

import future.keywords.if
import future.keywords.in

# Role helpers keep RBAC data lookup separate from request-shape policy.
is_platform_admin if {
	"platform_admin" in object.get(input, "roles", [])
}

role_has_permission(permission) if {
	some role in object.get(input, "roles", [])
	permission in object.get(data.role_permissions, role, [])
}
