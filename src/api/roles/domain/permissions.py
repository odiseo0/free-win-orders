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

    CARDS_READ = "cards.read"
    CARDS_CREATE = "cards.create"
    CARDS_UPDATE = "cards.update"
    CARDS_DELETE = "cards.delete"
    CARD_LISTINGS_READ = "card_listings.read"

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


USER_PERMISSIONS = frozenset(
    {
        PermissionCode.USERS_READ_SELF,
        PermissionCode.USERS_UPDATE_SELF,
        PermissionCode.ADDRESSES_READ_SELF,
        PermissionCode.ADDRESSES_CREATE_SELF,
        PermissionCode.ADDRESSES_UPDATE_SELF,
        PermissionCode.ADDRESSES_DELETE_SELF,
        PermissionCode.CARDS_READ,
        PermissionCode.CARD_LISTINGS_READ,
        PermissionCode.ORDER_PERIODS_READ,
    }
)
