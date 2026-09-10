from enum import StrEnum


class PermissionCode(StrEnum):
    USERS_READ_ANY = "users.read.any"
    USERS_READ_SELF = "users.read.self"
    USERS_UPDATE_ANY = "users.update.any"
    USERS_UPDATE_SELF = "users.update.self"
    USERS_DELETE_ANY = "users.delete.any"
    USERS_ASSIGN_ROLE = "users.assign_role"

    ADDRESSES_READ_ANY = "addresses.read.any"
    ADDRESSES_READ_SELF = "addresses.read.self"
    ADDRESSES_CREATE_ANY = "addresses.create.any"
    ADDRESSES_CREATE_SELF = "addresses.create.self"
    ADDRESSES_UPDATE_ANY = "addresses.update.any"
    ADDRESSES_UPDATE_SELF = "addresses.update.self"
    ADDRESSES_DELETE_ANY = "addresses.delete.any"
    ADDRESSES_DELETE_SELF = "addresses.delete.self"

    ROLES_READ = "roles.read"
    ROLES_CREATE = "roles.create"
    ROLES_UPDATE = "roles.update"
    ROLES_DELETE = "roles.delete"
    ROLES_ASSIGN_PERMISSIONS = "roles.assign_permissions"
    PERMISSIONS_READ = "permissions.read"

    ORDER_PERIODS_READ = "order_periods.read"
    ORDER_PERIODS_READ_DRAFTS = "order_periods.read_drafts"
    ORDER_PERIODS_CREATE = "order_periods.create"
    ORDER_PERIODS_UPDATE = "order_periods.update"
    ORDER_PERIODS_CLOSE = "order_periods.close"

    ORDER_REQUESTS_READ_SELF = "order_requests.read.self"
    ORDER_REQUESTS_READ_ANY = "order_requests.read.any"
    ORDER_REQUESTS_CREATE_SELF = "order_requests.create.self"
    ORDER_REQUESTS_UPDATE_SELF = "order_requests.update.self"
    ORDER_REQUESTS_UPDATE_ANY = "order_requests.update.any"
    ORDER_REQUESTS_REVIEW = "order_requests.review"

    DELIVERIES_READ_SELF = "deliveries.read.self"
    DELIVERIES_READ_ANY = "deliveries.read.any"
    DELIVERIES_SELECT_SELF = "deliveries.select.self"
    DELIVERIES_MANAGE_PAYMENTS = "deliveries.manage_payments"
    DELIVERIES_MANAGE = "deliveries.manage"
    DELIVERIES_REFRESH_SELF = "deliveries.refresh.self"
    DELIVERIES_REFRESH_ANY = "deliveries.refresh.any"
    DELIVERY_STAGES_MANAGE = "delivery_stages.manage"


USER_PERMISSIONS = frozenset(
    {
        PermissionCode.USERS_READ_SELF,
        PermissionCode.USERS_UPDATE_SELF,
        PermissionCode.ADDRESSES_READ_SELF,
        PermissionCode.ADDRESSES_CREATE_SELF,
        PermissionCode.ADDRESSES_UPDATE_SELF,
        PermissionCode.ADDRESSES_DELETE_SELF,
        PermissionCode.ORDER_PERIODS_READ,
        PermissionCode.ORDER_REQUESTS_READ_SELF,
        PermissionCode.ORDER_REQUESTS_CREATE_SELF,
        PermissionCode.ORDER_REQUESTS_UPDATE_SELF,
        PermissionCode.DELIVERIES_READ_SELF,
        PermissionCode.DELIVERIES_SELECT_SELF,
        PermissionCode.DELIVERIES_REFRESH_SELF,
    }
)
