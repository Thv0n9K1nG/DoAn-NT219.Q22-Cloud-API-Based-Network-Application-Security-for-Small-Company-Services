package authz

import future.keywords.if

test_default_deny_unknown_route if {
	not allow with input as {
		"method": "GET",
		"path": ["api", "v1", "unknown"],
		"tenant_id": "11111111-1111-1111-1111-111111111111",
		"user_id": "u1",
		"roles": ["tenant_user"]
	}
}

test_tenant_user_get_resources_allowed if {
	allow with input as {
		"method": "GET",
		"path": ["api", "v1", "resources"],
		"tenant_id": "11111111-1111-1111-1111-111111111111",
		"user_id": "u1",
		"roles": ["tenant_user"]
	}
}

test_tenant_user_post_resources_allowed if {
	allow with input as {
		"method": "POST",
		"path": ["api", "v1", "resources"],
		"tenant_id": "11111111-1111-1111-1111-111111111111",
		"user_id": "u1",
		"roles": ["tenant_user"]
	}
}

test_tenant_user_delete_resources_denied if {
	not allow with input as {
		"method": "DELETE",
		"path": ["api", "v1", "resources", "res-123"],
		"tenant_id": "11111111-1111-1111-1111-111111111111",
		"user_id": "u1",
		"roles": ["tenant_user"]
	}
}

test_tenant_user_get_admin_denied if {
	not allow with input as {
		"method": "GET",
		"path": ["api", "v1", "admin"],
		"tenant_id": "11111111-1111-1111-1111-111111111111",
		"user_id": "u1",
		"roles": ["tenant_user"]
	}
}

test_tenant_admin_delete_resources_allowed if {
	allow with input as {
		"method": "DELETE",
		"path": ["api", "v1", "resources", "res-123"],
		"tenant_id": "11111111-1111-1111-1111-111111111111",
		"user_id": "admin-1",
		"roles": ["tenant_admin"]
	}
}

test_tenant_admin_get_admin_denied if {
	not allow with input as {
		"method": "GET",
		"path": ["api", "v1", "admin"],
		"tenant_id": "11111111-1111-1111-1111-111111111111",
		"user_id": "admin-1",
		"roles": ["tenant_admin"]
	}
}

test_platform_admin_get_admin_allowed_without_tenant if {
	allow with input as {
		"method": "GET",
		"path": ["api", "v1", "admin"],
		"tenant_id": "",
		"user_id": "platform-1",
		"roles": ["platform_admin"]
	}
}

test_missing_tenant_id_tenant_user_denied if {
	not allow with input as {
		"method": "GET",
		"path": ["api", "v1", "resources"],
		"tenant_id": "",
		"user_id": "u1",
		"roles": ["tenant_user"]
	}
}

test_path_with_leading_empty_segment_is_normalized if {
	allow with input as {
		"method": "GET",
		"path": ["", "api", "v1", "resources"],
		"tenant_id": "11111111-1111-1111-1111-111111111111",
		"user_id": "u1",
		"roles": ["tenant_user"]
	}
}

test_bola_cross_tenant_denied if {
	deny_bola with input as {
		"tenant_id": "11111111-1111-1111-1111-111111111111",
		"resource_tenant_id": "22222222-2222-2222-2222-222222222222",
		"resource_id": "res-123",
		"user_id": "u1"
	}
}

test_bola_same_tenant_not_denied if {
	not deny_bola with input as {
		"tenant_id": "11111111-1111-1111-1111-111111111111",
		"resource_tenant_id": "11111111-1111-1111-1111-111111111111",
		"resource_id": "res-123",
		"user_id": "u1"
	}
}
